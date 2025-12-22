"""LLM-powered summarization service for search results."""

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.services.search_service import SearchService

logger = get_logger(__name__)


@dataclass
class SummarizationContext:
    """Context assembled for LLM summarization."""

    query: str
    projects: list[dict]  # Project summaries
    document_chunks: list[dict]  # Relevant document excerpts
    total_tokens_estimate: int


@dataclass
class SummarizationResult:
    """Result of summarization."""

    summary: str
    context_used: int  # Number of chunks/projects used
    truncated: bool  # Whether context was truncated due to token limits
    error: str | None = None


class SummarizationService:
    """Service for generating LLM-powered summaries over search results."""

    # Token limits
    MAX_CONTEXT_TOKENS = 6000  # Leave room for prompt and response
    MAX_RESPONSE_TOKENS = 1000
    CHARS_PER_TOKEN = 4  # Approximation

    SYSTEM_PROMPT = """You are a helpful assistant summarizing search results from a project management database.

Given the user's query and relevant project/document information, provide a concise, informative summary that directly answers their question.

Guidelines:
- Be factual and cite specific projects/dates when relevant
- If the search results don't fully answer the query, acknowledge this
- Keep summaries focused and actionable
- Use bullet points for multiple items when appropriate"""

    def __init__(self, db: AsyncSession):
        """Initialize the summarization service."""
        self.db = db
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url
        self.model = self.settings.ollama_chat_model
        self.search_service = SearchService(db)

    async def summarize(
        self,
        query: str,
        projects: list,
        max_chunks: int = 10,
    ) -> SummarizationResult:
        """Generate a summary for search results."""
        # Edge case: No results
        if not projects:
            return SummarizationResult(
                summary="No matching projects found for your query. Try broadening your search terms.",
                context_used=0,
                truncated=False,
            )

        # Edge case: Too many results (summarize first N)
        original_count = len(projects)
        if len(projects) > 20:
            projects = projects[:20]
            logger.info(
                "summarization_projects_truncated",
                original_count=original_count,
                used_count=20,
            )

        try:
            # Assemble context
            context = await self._assemble_context(query, projects, max_chunks)
            context_text, truncated = self._truncate_context(context)

            # Call LLM
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": self.SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": f"Query: {query}\n\nRelevant Information:\n{context_text}",
                            },
                        ],
                        "stream": False,
                        "options": {
                            "num_predict": self.MAX_RESPONSE_TOKENS,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()

            summary = data.get("message", {}).get("content", "")

            if not summary:
                return self._create_fallback_result(projects, "Empty LLM response")

            return SummarizationResult(
                summary=summary,
                context_used=len(context.projects) + len(context.document_chunks),
                truncated=truncated,
            )

        except httpx.HTTPError as e:
            logger.warning("summarization_llm_error", error=str(e))
            return self._create_fallback_result(projects, f"LLM unavailable: {e}")
        except Exception as e:
            logger.error(
                "summarization_error", error=str(e), error_type=type(e).__name__
            )
            return self._create_fallback_result(projects, str(e))

    async def summarize_stream(
        self,
        query: str,
        projects: list,
        max_chunks: int = 10,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming summary for search results."""
        if not projects:
            yield "data: No matching projects found for your query.\n\n"
            return

        try:
            context = await self._assemble_context(query, projects, max_chunks)
            context_text, _ = self._truncate_context(context)

            client = httpx.AsyncClient(timeout=120.0)
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": self.SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": f"Query: {query}\n\nRelevant Information:\n{context_text}",
                            },
                        ],
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                content = data.get("message", {}).get("content", "")
                                if content:
                                    yield f"data: {content}\n\n"
                            except json.JSONDecodeError:
                                continue
            finally:
                await client.aclose()

        except Exception as e:
            logger.error("summarization_stream_error", error=str(e))
            yield f"data: [Error generating summary: {e}]\n\n"

        yield "data: [DONE]\n\n"

    async def _assemble_context(
        self,
        query: str,
        projects: list,
        max_chunks: int,
    ) -> SummarizationContext:
        """Assemble context from projects and document chunks."""
        # Extract project summaries
        project_summaries: list[dict] = []
        for project in projects:
            project_data = {
                "name": project.name,
                "description": project.description or "",
            }
            # Add organization if available
            if hasattr(project, "organization") and project.organization:
                project_data["organization"] = project.organization.name
            # Add status if available
            if hasattr(project, "status") and project.status:
                project_data["status"] = project.status.value
            # Add dates if available
            if hasattr(project, "start_date") and project.start_date:
                project_data["start_date"] = str(project.start_date)
            if hasattr(project, "end_date") and project.end_date:
                project_data["end_date"] = str(project.end_date)

            project_summaries.append(project_data)

        # Get relevant document chunks using vector search
        document_chunks = await self.search_service.search_documents(
            query, limit=max_chunks
        )

        # Calculate token estimate
        context_str = str(project_summaries) + str(document_chunks)
        total_tokens = self._estimate_tokens(context_str)

        return SummarizationContext(
            query=query,
            projects=project_summaries,
            document_chunks=document_chunks,
            total_tokens_estimate=total_tokens,
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(text) // self.CHARS_PER_TOKEN

    def _truncate_context(
        self,
        context: SummarizationContext,
    ) -> tuple[str, bool]:
        """Truncate context to fit within token budget."""
        # Build formatted context string
        parts: list[str] = []

        # Add projects section
        if context.projects:
            parts.append("## Projects")
            for proj in context.projects:
                proj_lines = [f"- **{proj.get('name', 'Unknown')}**"]
                if proj.get("organization"):
                    proj_lines.append(f"  - Organization: {proj['organization']}")
                if proj.get("description"):
                    # Truncate long descriptions
                    desc = proj["description"]
                    if len(desc) > 200:
                        desc = desc[:200] + "..."
                    proj_lines.append(f"  - Description: {desc}")
                if proj.get("status"):
                    proj_lines.append(f"  - Status: {proj['status']}")
                if proj.get("start_date"):
                    proj_lines.append(f"  - Start Date: {proj['start_date']}")
                if proj.get("end_date"):
                    proj_lines.append(f"  - End Date: {proj['end_date']}")
                parts.append("\n".join(proj_lines))

        # Add document chunks section
        if context.document_chunks:
            parts.append("\n## Relevant Document Excerpts")
            for chunk in context.document_chunks:
                chunk_content = chunk.get("content", "")
                doc_name = chunk.get("document_name", "Unknown document")
                if chunk_content:
                    # Truncate long chunks
                    if len(chunk_content) > 500:
                        chunk_content = chunk_content[:500] + "..."
                    parts.append(f"- From **{doc_name}**:\n  {chunk_content}")

        context_text = "\n\n".join(parts)

        # Check if truncation needed
        current_tokens = self._estimate_tokens(context_text)
        truncated = False

        if current_tokens > self.MAX_CONTEXT_TOKENS:
            truncated = True
            # Truncate by reducing chunks first, then projects
            max_chars = self.MAX_CONTEXT_TOKENS * self.CHARS_PER_TOKEN
            if len(context_text) > max_chars:
                context_text = (
                    context_text[:max_chars] + "\n\n[Context truncated due to length]"
                )

        return context_text, truncated

    def _create_fallback_result(
        self, projects: list, reason: str
    ) -> SummarizationResult:
        """Create fallback result when LLM is unavailable."""
        # Generate basic summary from project names
        project_names = [p.name for p in projects[:5]]
        fallback_summary = (
            f"Found {len(projects)} matching project(s): {', '.join(project_names)}"
        )
        if len(projects) > 5:
            fallback_summary += f" and {len(projects) - 5} more."

        return SummarizationResult(
            summary=fallback_summary,
            context_used=len(projects),
            truncated=False,
            error=reason,
        )
