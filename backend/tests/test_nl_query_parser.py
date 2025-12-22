"""Tests for NL Query Parser service."""

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.nl_query import DateRange, NLQueryParseResponse, ParsedQueryIntent


class TestTimeExpressionParsing:
    """Tests for temporal expression parsing."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.services.nl_query_parser import NLQueryParser

        # Create parser with mock db
        self.mock_db = AsyncMock()
        self.parser = NLQueryParser(self.mock_db)

    def test_parse_last_n_years(self):
        """Should parse 'last N years' expressions."""
        result = self.parser._parse_time_expression("last 2 years")

        assert result is not None
        assert result.start_date is not None
        assert result.end_date == date.today()
        assert result.start_date.year == date.today().year - 2
        assert result.original_expression == "last 2 years"

    def test_parse_last_n_years_singular(self):
        """Should parse 'last 1 year' expression."""
        result = self.parser._parse_time_expression("last 1 year")

        assert result is not None
        assert result.start_date is not None
        assert result.end_date == date.today()
        assert result.start_date.year == date.today().year - 1

    def test_parse_last_n_months(self):
        """Should parse 'last N months' expressions."""
        result = self.parser._parse_time_expression("last 6 months")

        assert result is not None
        assert result.start_date is not None
        assert result.end_date == date.today()
        # Approximately 6 months ago
        expected_start = date.today() - timedelta(days=180)
        assert abs((result.start_date - expected_start).days) <= 5

    def test_parse_last_n_months_singular(self):
        """Should parse 'last 1 month' expression."""
        result = self.parser._parse_time_expression("last 1 month")

        assert result is not None
        assert result.start_date is not None
        # Approximately 1 month ago
        expected_start = date.today() - timedelta(days=30)
        assert abs((result.start_date - expected_start).days) <= 5

    def test_parse_since_year(self):
        """Should parse 'since YYYY' expressions."""
        result = self.parser._parse_time_expression("since 2023")

        assert result is not None
        assert result.start_date == date(2023, 1, 1)
        assert result.end_date == date.today()

    def test_parse_quarter_q1(self):
        """Should parse 'Q1 YYYY' expression."""
        result = self.parser._parse_time_expression("Q1 2024")

        assert result is not None
        assert result.start_date == date(2024, 1, 1)
        assert result.end_date == date(2024, 3, 31)

    def test_parse_quarter_q2(self):
        """Should parse 'Q2 YYYY' expression."""
        result = self.parser._parse_time_expression("Q2 2024")

        assert result is not None
        assert result.start_date == date(2024, 4, 1)
        assert result.end_date == date(2024, 6, 30)

    def test_parse_quarter_q3(self):
        """Should parse 'Q3 YYYY' expression."""
        result = self.parser._parse_time_expression("Q3 2024")

        assert result is not None
        assert result.start_date == date(2024, 7, 1)
        assert result.end_date == date(2024, 9, 30)

    def test_parse_quarter_q4(self):
        """Should parse 'Q4 YYYY' expression."""
        result = self.parser._parse_time_expression("Q4 2024")

        assert result is not None
        assert result.start_date == date(2024, 10, 1)
        assert result.end_date == date(2024, 12, 31)

    def test_parse_this_year(self):
        """Should parse 'this year' expression."""
        result = self.parser._parse_time_expression("this year")

        assert result is not None
        assert result.start_date == date(date.today().year, 1, 1)
        assert result.end_date == date.today()

    def test_parse_single_year(self):
        """Should parse standalone year '2024'."""
        result = self.parser._parse_time_expression("2024")

        assert result is not None
        assert result.start_date == date(2024, 1, 1)
        assert result.end_date == date(2024, 12, 31)

    def test_parse_invalid_expression_returns_none(self):
        """Should return None for unrecognized expressions."""
        result = self.parser._parse_time_expression("some random text")
        assert result is None

    def test_parse_empty_expression_returns_none(self):
        """Should return None for empty expressions."""
        assert self.parser._parse_time_expression("") is None
        assert self.parser._parse_time_expression(None) is None

    def test_parse_case_insensitive(self):
        """Should parse expressions case-insensitively."""
        result1 = self.parser._parse_time_expression("Last 2 Years")
        result2 = self.parser._parse_time_expression("LAST 2 YEARS")
        result3 = self.parser._parse_time_expression("last 2 years")

        assert result1 is not None
        assert result2 is not None
        assert result3 is not None
        assert result1.start_date == result2.start_date == result3.start_date


class TestStatusParsing:
    """Tests for status filter parsing."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.services.nl_query_parser import NLQueryParser

        self.mock_db = AsyncMock()
        self.parser = NLQueryParser(self.mock_db)

    def test_parse_single_status(self):
        """Should parse single status value."""
        from app.models.project import ProjectStatus

        result = self.parser._parse_status_list(["active"])

        assert len(result) == 1
        assert ProjectStatus.ACTIVE in result

    def test_parse_multiple_statuses(self):
        """Should parse multiple status values."""
        from app.models.project import ProjectStatus

        result = self.parser._parse_status_list(["active", "completed"])

        assert len(result) == 2
        assert ProjectStatus.ACTIVE in result
        assert ProjectStatus.COMPLETED in result

    def test_parse_on_hold_variations(self):
        """Should handle 'on_hold' and 'on hold' variations."""
        from app.models.project import ProjectStatus

        result1 = self.parser._parse_status_list(["on_hold"])
        result2 = self.parser._parse_status_list(["on hold"])

        assert result1 == result2
        assert ProjectStatus.ON_HOLD in result1

    def test_parse_cancelled_variations(self):
        """Should handle 'cancelled' and 'canceled' variations."""
        from app.models.project import ProjectStatus

        result1 = self.parser._parse_status_list(["cancelled"])
        result2 = self.parser._parse_status_list(["canceled"])

        assert result1 == result2
        assert ProjectStatus.CANCELLED in result1

    def test_parse_invalid_status_ignored(self):
        """Should ignore invalid status values."""
        result = self.parser._parse_status_list(
            ["active", "invalid_status", "completed"]
        )

        assert len(result) == 2

    def test_parse_empty_list(self):
        """Should return empty list for empty input."""
        result = self.parser._parse_status_list([])
        assert result == []

    def test_parse_all_statuses(self):
        """Should parse all valid status values."""
        from app.models.project import ProjectStatus

        result = self.parser._parse_status_list(
            ["active", "completed", "on_hold", "approved", "cancelled"]
        )

        assert len(result) == 5
        assert ProjectStatus.ACTIVE in result
        assert ProjectStatus.COMPLETED in result
        assert ProjectStatus.ON_HOLD in result
        assert ProjectStatus.APPROVED in result
        assert ProjectStatus.CANCELLED in result

    def test_parse_deduplicates_statuses(self):
        """Should not return duplicate status values."""
        result = self.parser._parse_status_list(["active", "active", "Active"])

        assert len(result) == 1


class TestOrganizationLookup:
    """Tests for organization name resolution."""

    @pytest.mark.asyncio
    async def test_find_organization_exact_match(self):
        """Should find organization by exact name match."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        org_id = uuid4()

        # Mock exact match query
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute.return_value = mock_result

        parser = NLQueryParser(mock_db)
        result = await parser._find_organization("Acme Corp")

        assert result == org_id

    @pytest.mark.asyncio
    async def test_find_organization_not_found(self):
        """Should return None when organization not found."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()

        # Mock all queries returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        parser = NLQueryParser(mock_db)
        result = await parser._find_organization("Nonexistent Corp")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_organization_by_alias(self):
        """Should find organization by alias."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        org_id = uuid4()

        # First query returns None (no exact match)
        # Second query returns orgs with aliases
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.aliases = ["AC", "Acme", "AcmeCorp"]

        def execute_side_effect(stmt):
            mock_result = MagicMock()
            # Check if it's the alias query
            if hasattr(stmt, "_where_criteria") or "aliases" in str(stmt):
                # Return org with aliases on second call
                mock_result.scalar_one_or_none.return_value = None
                mock_result.scalars.return_value.all.return_value = [mock_org]
            else:
                mock_result.scalar_one_or_none.return_value = None
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        mock_db.execute.side_effect = execute_side_effect

        parser = NLQueryParser(mock_db)
        result = await parser._find_organization("Acme")

        assert result == org_id


class TestTagLookup:
    """Tests for technology keyword to tag resolution."""

    @pytest.mark.asyncio
    async def test_find_technology_tags(self):
        """Should find tags matching technology keywords."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        tag_id = uuid4()

        mock_tag = MagicMock()
        mock_tag.id = tag_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tag
        mock_db.execute.return_value = mock_result

        parser = NLQueryParser(mock_db)
        result = await parser._find_technology_tags(["IoT", "Bluetooth"])

        # Should have found tags (may dedupe to 1 if mock returns same)
        assert len(result) >= 1
        assert tag_id in result

    @pytest.mark.asyncio
    async def test_find_technology_tags_deduplicates(self):
        """Should not return duplicate tag IDs."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        tag_id = uuid4()

        # Same tag returned for multiple keywords
        mock_tag = MagicMock()
        mock_tag.id = tag_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tag
        mock_db.execute.return_value = mock_result

        parser = NLQueryParser(mock_db)
        result = await parser._find_technology_tags(["IoT", "Internet of Things"])

        # Should dedupe to single tag
        assert result.count(tag_id) == 1

    @pytest.mark.asyncio
    async def test_find_technology_tags_empty_keywords(self):
        """Should return empty list for empty keywords."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        parser = NLQueryParser(mock_db)
        result = await parser._find_technology_tags([])

        assert result == []

    @pytest.mark.asyncio
    async def test_find_technology_tags_no_matches(self):
        """Should return empty list when no tags match."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        parser = NLQueryParser(mock_db)
        result = await parser._find_technology_tags(["NonexistentTech"])

        assert result == []


class TestLLMIntegration:
    """Tests for LLM parsing integration."""

    @pytest.mark.asyncio
    async def test_parse_query_with_llm_success(self):
        """Should parse query successfully when LLM responds."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()

        # Mock DB to return no matches (simplifies test)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        parser = NLQueryParser(mock_db)

        # Mock LLM response
        llm_response = {
            "message": {
                "content": json.dumps(
                    {
                        "search_text": "projects",
                        "time_expression": "last 2 years",
                        "organization_mention": None,
                        "technologies": ["IoT", "Bluetooth"],
                        "status_filter": [],
                        "confidence": 0.85,
                    }
                )
            }
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_context = AsyncMock()
            mock_http_response = MagicMock()
            mock_http_response.json.return_value = llm_response
            mock_http_response.raise_for_status = MagicMock()
            mock_context.__aenter__.return_value.post = AsyncMock(
                return_value=mock_http_response
            )
            mock_context.__aexit__.return_value = None
            MockClient.return_value = mock_context

            result = await parser.parse_query(
                "show me IoT Bluetooth projects in the last 2 years"
            )

        assert isinstance(result, NLQueryParseResponse)
        assert result.fallback_used is False
        assert result.parsed_intent.date_range is not None
        assert "IoT" in result.parsed_intent.technology_keywords

    @pytest.mark.asyncio
    async def test_parse_query_fallback_on_llm_error(self):
        """Should fallback when LLM call fails."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        parser = NLQueryParser(mock_db)

        with patch("httpx.AsyncClient") as MockClient:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("LLM unavailable")
            )
            mock_context.__aexit__.return_value = None
            MockClient.return_value = mock_context

            result = await parser.parse_query("test query")

        assert result.fallback_used is True
        assert result.parsed_intent.search_text == "test query"
        assert result.parsed_intent.confidence == 0.0

    @pytest.mark.asyncio
    async def test_parse_empty_query(self):
        """Should handle empty query gracefully."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        parser = NLQueryParser(mock_db)

        result = await parser.parse_query("")

        assert result.fallback_used is True
        assert "Empty query" in result.parse_explanation

    @pytest.mark.asyncio
    async def test_parse_whitespace_only_query(self):
        """Should handle whitespace-only query gracefully."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        parser = NLQueryParser(mock_db)

        result = await parser.parse_query("   ")

        assert result.fallback_used is True
        assert "Empty query" in result.parse_explanation

    @pytest.mark.asyncio
    async def test_parse_query_llm_invalid_json(self):
        """Should fallback when LLM returns invalid JSON."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        parser = NLQueryParser(mock_db)

        # Mock LLM response with invalid JSON
        llm_response = {"message": {"content": "This is not valid JSON"}}

        with patch("httpx.AsyncClient") as MockClient:
            mock_context = AsyncMock()
            mock_http_response = MagicMock()
            mock_http_response.json.return_value = llm_response
            mock_http_response.raise_for_status = MagicMock()
            mock_context.__aenter__.return_value.post = AsyncMock(
                return_value=mock_http_response
            )
            mock_context.__aexit__.return_value = None
            MockClient.return_value = mock_context

            result = await parser.parse_query("test query")

        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_parse_query_llm_empty_response(self):
        """Should fallback when LLM returns empty content."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        parser = NLQueryParser(mock_db)

        # Mock LLM response with empty content
        llm_response = {"message": {"content": ""}}

        with patch("httpx.AsyncClient") as MockClient:
            mock_context = AsyncMock()
            mock_http_response = MagicMock()
            mock_http_response.json.return_value = llm_response
            mock_http_response.raise_for_status = MagicMock()
            mock_context.__aenter__.return_value.post = AsyncMock(
                return_value=mock_http_response
            )
            mock_context.__aexit__.return_value = None
            MockClient.return_value = mock_context

            result = await parser.parse_query("test query")

        assert result.fallback_used is True
        assert "LLM parsing failed" in result.parse_explanation


class TestExplanationBuilding:
    """Tests for parse explanation generation."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.services.nl_query_parser import NLQueryParser

        self.mock_db = AsyncMock()
        self.parser = NLQueryParser(self.mock_db)

    def test_explanation_with_all_fields(self):
        """Should build explanation with all parsed fields."""
        from app.models.project import ProjectStatus

        intent = ParsedQueryIntent(
            search_text="projects",
            date_range=DateRange(
                start_date=date(2023, 1, 1),
                end_date=date.today(),
                original_expression="last 2 years",
            ),
            organization_name="Acme",
            organization_id=uuid4(),
            technology_keywords=["IoT", "Bluetooth"],
            tag_ids=[uuid4()],
            status=[ProjectStatus.ACTIVE],
            confidence=0.9,
        )

        explanation = self.parser._build_explanation({}, intent)

        assert "projects" in explanation
        assert "last 2 years" in explanation
        assert "Acme" in explanation
        assert "IoT" in explanation
        assert "active" in explanation

    def test_explanation_with_unresolved_org(self):
        """Should indicate when organization not found in DB."""
        intent = ParsedQueryIntent(
            search_text="",
            organization_name="Unknown Corp",
            organization_id=None,
            confidence=0.5,
        )

        explanation = self.parser._build_explanation({}, intent)

        assert "Unknown Corp" in explanation
        assert "not found" in explanation

    def test_explanation_for_keyword_only(self):
        """Should indicate keyword search when no structured parsing."""
        intent = ParsedQueryIntent(
            search_text="",
            confidence=0.0,
        )

        explanation = self.parser._build_explanation({}, intent)

        assert "keyword search" in explanation.lower()

    def test_explanation_with_technologies_only(self):
        """Should build explanation with only technology keywords."""
        intent = ParsedQueryIntent(
            search_text="",
            technology_keywords=["IoT", "Bluetooth", "WiFi"],
            tag_ids=[uuid4(), uuid4()],
            confidence=0.8,
        )

        explanation = self.parser._build_explanation({}, intent)

        assert "IoT" in explanation
        assert "Bluetooth" in explanation
        assert "2/3" in explanation  # 2 matched out of 3

    def test_explanation_with_status_only(self):
        """Should build explanation with only status filter."""
        from app.models.project import ProjectStatus

        intent = ParsedQueryIntent(
            search_text="",
            status=[ProjectStatus.ACTIVE, ProjectStatus.COMPLETED],
            confidence=0.7,
        )

        explanation = self.parser._build_explanation({}, intent)

        assert "active" in explanation
        assert "completed" in explanation


class TestFallbackResponse:
    """Tests for fallback response creation."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.services.nl_query_parser import NLQueryParser

        self.mock_db = AsyncMock()
        self.parser = NLQueryParser(self.mock_db)

    def test_fallback_response_structure(self):
        """Should create properly structured fallback response."""
        result = self.parser._create_fallback_response("test query", "Test reason")

        assert result.original_query == "test query"
        assert result.parsed_intent.search_text == "test query"
        assert result.parsed_intent.confidence == 0.0
        assert result.fallback_used is True
        assert "Test reason" in result.parse_explanation

    def test_fallback_response_empty_query(self):
        """Should handle empty query in fallback."""
        result = self.parser._create_fallback_response("", "Empty query")

        assert result.original_query == ""
        assert result.parsed_intent.search_text == ""
        assert result.fallback_used is True


class TestParserInitialization:
    """Tests for parser initialization."""

    def test_parser_uses_default_model(self):
        """Should use default model when not configured."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        parser = NLQueryParser(mock_db)

        # Should have a model set
        assert parser.model is not None
        assert isinstance(parser.model, str)

    def test_parser_uses_configured_base_url(self):
        """Should use configured base URL."""
        from app.services.nl_query_parser import NLQueryParser

        mock_db = AsyncMock()
        parser = NLQueryParser(mock_db)

        # Should have base URL set from settings
        assert parser.base_url is not None
        assert isinstance(parser.base_url, str)
