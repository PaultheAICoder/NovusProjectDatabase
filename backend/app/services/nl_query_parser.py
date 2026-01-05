"""Natural Language Query Parser service using Ollama LLM."""

import json
import re
from datetime import date, timedelta
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.models.organization import Organization
from app.models.project import ProjectStatus
from app.models.tag import Tag, TagType
from app.schemas.nl_query import (
    DateRange,
    NLQueryParseResponse,
    ParsedQueryIntent,
)

logger = get_logger(__name__)


class NLQueryParser:
    """Service for parsing natural language search queries using LLM."""

    # Prompt template for LLM
    SYSTEM_PROMPT = """You are a search query parser for a project management system.
Extract structured information from the user's search query.

The system has these filter types:
- Time ranges: "last N years/months", "since YYYY", "Q1-Q4 YYYY", "this year"
- Organizations/Clients: company names mentioned as clients
- Technologies: IoT, Bluetooth, WiFi, 5G, embedded, sensor, etc.
- Status: active, completed, on_hold, approved, cancelled

Return a JSON object with these fields:
{
  "search_text": "remaining keywords not captured by other fields",
  "time_expression": "exact temporal phrase from query or null",
  "organization_mention": "client/company name or null",
  "technologies": ["list", "of", "technology", "terms"],
  "status_filter": ["list of status values"] or [],
  "confidence": 0.0-1.0
}

Only extract what is explicitly mentioned. Do not infer."""

    def __init__(self, db: AsyncSession):
        """Initialize the NL Query Parser service.

        Args:
            db: Async database session for entity resolution
        """
        self.db = db
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url
        self.model = getattr(self.settings, "ollama_chat_model", "mistral")

    async def parse_query(self, query: str) -> NLQueryParseResponse:
        """
        Parse a natural language query into structured search parameters.

        Args:
            query: Natural language search query

        Returns:
            NLQueryParseResponse with parsed intent or fallback
        """
        if not query or not query.strip():
            return self._create_fallback_response(query, "Empty query")

        try:
            # Step 1: Call LLM for initial parsing
            llm_result = await self._call_llm(query)

            if llm_result is None:
                return self._create_fallback_response(query, "LLM parsing failed")

            # Step 2: Resolve entities to database IDs
            parsed_intent = await self._resolve_entities(llm_result)

            # Step 3: Build explanation
            explanation = self._build_explanation(llm_result, parsed_intent)

            return NLQueryParseResponse(
                original_query=query,
                parsed_intent=parsed_intent,
                fallback_used=False,
                parse_explanation=explanation,
            )

        except Exception as e:
            logger.warning(
                "nl_query_parse_error",
                query=query[:50],
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return self._create_fallback_response(query, str(e))

    async def _call_llm(self, query: str) -> dict | None:
        """Call Ollama LLM for query parsing."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": self.SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": f"Parse this search query: {query}",
                            },
                        ],
                        "stream": False,
                        "format": "json",  # Request JSON output
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Extract message content
                content = data.get("message", {}).get("content", "")
                if not content:
                    return None

                # Parse JSON from response
                return json.loads(content)

        except httpx.HTTPError as e:
            logger.warning("ollama_llm_error", error=str(e))
            return None
        except json.JSONDecodeError as e:
            logger.warning("llm_json_parse_error", error=str(e))
            return None

    async def _resolve_entities(self, llm_result: dict) -> ParsedQueryIntent:
        """Resolve organization names and technology keywords to database IDs."""
        intent = ParsedQueryIntent(
            search_text=llm_result.get("search_text", ""),
            confidence=llm_result.get("confidence", 0.5),
        )

        # Parse time expression
        time_expr = llm_result.get("time_expression")
        if time_expr:
            intent.date_range = self._parse_time_expression(time_expr)

        # Resolve organization
        org_mention = llm_result.get("organization_mention")
        if org_mention:
            intent.organization_name = org_mention
            org_id = await self._find_organization(org_mention)
            if org_id:
                intent.organization_id = org_id

        # Resolve technology keywords to tags
        technologies = llm_result.get("technologies", [])
        if technologies:
            intent.technology_keywords = technologies
            tag_ids = await self._find_technology_tags(technologies)
            intent.tag_ids = tag_ids

        # Parse status filters
        status_filter = llm_result.get("status_filter", [])
        intent.status = self._parse_status_list(status_filter)

        return intent

    def _parse_time_expression(self, expression: str) -> DateRange | None:
        """Parse temporal expressions into date ranges."""
        if not expression:
            return None

        expression_lower = expression.lower().strip()
        today = date.today()

        # Pattern: "last N years"
        match = re.search(r"last\s+(\d+)\s+years?", expression_lower)
        if match:
            years = int(match.group(1))
            start = today.replace(year=today.year - years)
            return DateRange(
                start_date=start, end_date=today, original_expression=expression
            )

        # Pattern: "last N months"
        match = re.search(r"last\s+(\d+)\s+months?", expression_lower)
        if match:
            months = int(match.group(1))
            # Approximate: 30 days per month
            start = today - timedelta(days=months * 30)
            return DateRange(
                start_date=start, end_date=today, original_expression=expression
            )

        # Pattern: "since YYYY"
        match = re.search(r"since\s+(\d{4})", expression_lower)
        if match:
            year = int(match.group(1))
            start = date(year, 1, 1)
            return DateRange(
                start_date=start, end_date=today, original_expression=expression
            )

        # Pattern: "Q1-Q4 YYYY" (quarters)
        match = re.search(r"q([1-4])\s+(\d{4})", expression_lower)
        if match:
            quarter = int(match.group(1))
            year = int(match.group(2))
            quarter_start_months = {1: 1, 2: 4, 3: 7, 4: 10}
            quarter_end_months = {1: 3, 2: 6, 3: 9, 4: 12}
            start = date(year, quarter_start_months[quarter], 1)
            # End of quarter
            end_month = quarter_end_months[quarter]
            if end_month == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, end_month + 1, 1) - timedelta(days=1)
            return DateRange(
                start_date=start, end_date=end, original_expression=expression
            )

        # Pattern: "this year"
        if "this year" in expression_lower:
            start = date(today.year, 1, 1)
            return DateRange(
                start_date=start, end_date=today, original_expression=expression
            )

        # Pattern: "YYYY" (just a year)
        match = re.search(r"^(\d{4})$", expression_lower.strip())
        if match:
            year = int(match.group(1))
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            return DateRange(
                start_date=start, end_date=end, original_expression=expression
            )

        return None

    async def _find_organization(self, name: str) -> UUID | None:
        """Find organization by name or alias (fuzzy match)."""
        name_lower = name.lower().strip()

        # Exact match on name (case-insensitive)
        stmt = select(Organization).where(func.lower(Organization.name) == name_lower)
        result = await self.db.execute(stmt)
        org = result.scalar_one_or_none()
        if org:
            return org.id

        # Check aliases
        stmt = select(Organization).where(Organization.aliases.isnot(None))
        result = await self.db.execute(stmt)
        all_orgs = result.scalars().all()

        for org in all_orgs:
            if org.aliases:
                for alias in org.aliases:
                    if alias.lower() == name_lower:
                        return org.id

        # Partial match on name (contains)
        stmt = select(Organization).where(
            func.lower(Organization.name).contains(name_lower)
        )
        result = await self.db.execute(stmt)
        org = result.scalar_one_or_none()
        if org:
            return org.id

        return None

    async def _find_technology_tags(self, keywords: list[str]) -> list[UUID]:
        """Find tags matching technology keywords."""
        tag_ids: list[UUID] = []

        for keyword in keywords:
            keyword_lower = keyword.lower().strip()

            # Look for TECHNOLOGY type tags first, then any tag
            stmt = (
                select(Tag)
                .where(func.lower(Tag.name).contains(keyword_lower))
                .order_by(
                    # Prefer TECHNOLOGY type
                    Tag.type != TagType.TECHNOLOGY,
                    Tag.name,
                )
                .limit(1)
            )

            result = await self.db.execute(stmt)
            tag = result.scalar_one_or_none()

            if tag and tag.id not in tag_ids:
                tag_ids.append(tag.id)

        return tag_ids

    def _parse_status_list(self, status_list: list[str]) -> list[ProjectStatus]:
        """Parse status strings to ProjectStatus enum values."""
        valid_statuses: list[ProjectStatus] = []
        status_map = {
            "active": ProjectStatus.ACTIVE,
            "completed": ProjectStatus.COMPLETED,
            "on_hold": ProjectStatus.ON_HOLD,
            "on hold": ProjectStatus.ON_HOLD,
            "approved": ProjectStatus.APPROVED,
            "cancelled": ProjectStatus.CANCELLED,
            "canceled": ProjectStatus.CANCELLED,
        }

        for s in status_list:
            status = status_map.get(s.lower().strip())
            if status and status not in valid_statuses:
                valid_statuses.append(status)

        return valid_statuses

    def _build_explanation(self, _llm_result: dict, intent: ParsedQueryIntent) -> str:
        """Build human-readable explanation of parsing."""
        parts: list[str] = []

        if intent.search_text:
            parts.append(f"Searching for: '{intent.search_text}'")

        if intent.date_range:
            parts.append(f"Time filter: {intent.date_range.original_expression}")

        if intent.organization_name:
            if intent.organization_id:
                parts.append(f"Client: {intent.organization_name} (found)")
            else:
                parts.append(
                    f"Client: {intent.organization_name} (not found in database)"
                )

        if intent.technology_keywords:
            matched = len(intent.tag_ids)
            total = len(intent.technology_keywords)
            parts.append(
                f"Technologies: {', '.join(intent.technology_keywords)} "
                f"({matched}/{total} matched to tags)"
            )

        if intent.status:
            parts.append(f"Status: {', '.join(s.value for s in intent.status)}")

        if not parts:
            return "Query used as keyword search"

        return " | ".join(parts)

    def _create_fallback_response(
        self, query: str, reason: str
    ) -> NLQueryParseResponse:
        """Create fallback response using query as-is."""
        logger.info(
            "nl_query_fallback",
            query=query[:50] if query else "",
            reason=reason,
        )
        return NLQueryParseResponse(
            original_query=query,
            parsed_intent=ParsedQueryIntent(
                search_text=query,
                confidence=0.0,
            ),
            fallback_used=True,
            parse_explanation=f"Fallback to keyword search: {reason}",
        )
