"""Tests for SummarizationService."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.summarization_service import (
    SummarizationContext,
    SummarizationService,
)


class TestTokenEstimation:
    """Tests for token estimation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = AsyncMock()
        self.service = SummarizationService(self.mock_db)

    def test_estimate_tokens_short_text(self):
        """Should estimate tokens for short text."""
        # 16 chars / 4 = 4 tokens
        result = self.service._estimate_tokens("This is a test.")
        assert result == 3  # 15 chars / 4 = 3

    def test_estimate_tokens_empty_text(self):
        """Should return 0 for empty text."""
        result = self.service._estimate_tokens("")
        assert result == 0

    def test_estimate_tokens_longer_text(self):
        """Should estimate tokens for longer text."""
        # 100 chars / 4 = 25 tokens
        text = "a" * 100
        result = self.service._estimate_tokens(text)
        assert result == 25


class TestContextAssembly:
    """Tests for context assembly."""

    @pytest.mark.asyncio
    async def test_assemble_context_with_projects(self):
        """Should assemble context from projects."""
        mock_db = AsyncMock()
        service = SummarizationService(mock_db)

        # Mock search_documents to return empty
        with patch.object(
            service.search_service, "search_documents", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            mock_project = MagicMock()
            mock_project.id = uuid4()
            mock_project.name = "Test Project"
            mock_project.description = "A test project description"
            mock_project.organization = MagicMock()
            mock_project.organization.name = "Test Org"
            mock_project.status = MagicMock()
            mock_project.status.value = "active"
            mock_project.start_date = None
            mock_project.end_date = None

            context = await service._assemble_context(
                query="test query",
                projects=[mock_project],
                max_chunks=5,
            )

            assert len(context.projects) == 1
            assert context.projects[0]["name"] == "Test Project"
            assert context.projects[0]["organization"] == "Test Org"

    @pytest.mark.asyncio
    async def test_assemble_context_with_document_chunks(self):
        """Should include document chunks from search."""
        mock_db = AsyncMock()
        service = SummarizationService(mock_db)

        with patch.object(
            service.search_service, "search_documents", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [
                {
                    "chunk_id": str(uuid4()),
                    "content": "Document content here",
                    "document_name": "test.pdf",
                }
            ]

            mock_project = MagicMock()
            mock_project.name = "Test Project"
            mock_project.description = "Description"

            context = await service._assemble_context(
                query="test query",
                projects=[mock_project],
                max_chunks=5,
            )

            assert len(context.document_chunks) == 1
            assert context.document_chunks[0]["content"] == "Document content here"


class TestSummarization:
    """Tests for summarization."""

    @pytest.mark.asyncio
    async def test_summarize_no_results(self):
        """Should return appropriate message when no projects."""
        mock_db = AsyncMock()
        service = SummarizationService(mock_db)

        result = await service.summarize("test query", projects=[])

        assert "No matching projects" in result.summary
        assert result.context_used == 0
        assert result.truncated is False

    @pytest.mark.asyncio
    async def test_summarize_with_llm_success(self):
        """Should return LLM summary on success."""
        mock_db = AsyncMock()
        service = SummarizationService(mock_db)

        mock_project = MagicMock()
        mock_project.id = uuid4()
        mock_project.name = "IoT Project"
        mock_project.description = "Bluetooth IoT project"
        mock_project.organization = MagicMock()
        mock_project.organization.name = "Client A"
        mock_project.status = None
        mock_project.start_date = None
        mock_project.end_date = None

        llm_response = {
            "message": {
                "content": "Based on the search results, you worked on 1 IoT project for Client A."
            }
        }

        with patch.object(
            service.search_service, "search_documents", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

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

                result = await service.summarize(
                    "IoT projects for Client A", [mock_project]
                )

                assert "IoT project" in result.summary
                assert result.error is None

    @pytest.mark.asyncio
    async def test_summarize_llm_error_fallback(self):
        """Should return fallback on LLM error."""
        mock_db = AsyncMock()
        service = SummarizationService(mock_db)

        mock_project = MagicMock()
        mock_project.name = "Test Project"
        mock_project.description = "Description"

        with patch.object(
            service.search_service, "search_documents", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            with patch("httpx.AsyncClient") as MockClient:
                mock_context = AsyncMock()
                mock_context.__aenter__.return_value.post = AsyncMock(
                    side_effect=Exception("LLM unavailable")
                )
                mock_context.__aexit__.return_value = None
                MockClient.return_value = mock_context

                result = await service.summarize("test query", [mock_project])

                assert result.error is not None
                assert (
                    "Test Project" in result.summary
                )  # Fallback includes project name

    @pytest.mark.asyncio
    async def test_summarize_empty_llm_response_fallback(self):
        """Should return fallback on empty LLM response."""
        mock_db = AsyncMock()
        service = SummarizationService(mock_db)

        mock_project = MagicMock()
        mock_project.name = "Test Project"
        mock_project.description = "Description"

        with patch.object(
            service.search_service, "search_documents", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            with patch("httpx.AsyncClient") as MockClient:
                mock_context = AsyncMock()
                mock_http_response = MagicMock()
                mock_http_response.json.return_value = {"message": {"content": ""}}
                mock_http_response.raise_for_status = MagicMock()
                mock_context.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_http_response
                )
                mock_context.__aexit__.return_value = None
                MockClient.return_value = mock_context

                result = await service.summarize("test query", [mock_project])

                assert result.error is not None
                assert "Empty LLM response" in result.error

    @pytest.mark.asyncio
    async def test_summarize_truncates_many_projects(self):
        """Should truncate to 20 projects when more provided."""
        mock_db = AsyncMock()
        service = SummarizationService(mock_db)

        # Create 25 mock projects
        projects = []
        for i in range(25):
            mock_project = MagicMock()
            mock_project.name = f"Project {i}"
            mock_project.description = f"Description {i}"
            projects.append(mock_project)

        with patch.object(
            service.search_service, "search_documents", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            # LLM returns error so we get fallback with truncated projects
            with patch("httpx.AsyncClient") as MockClient:
                mock_context = AsyncMock()
                mock_context.__aenter__.return_value.post = AsyncMock(
                    side_effect=Exception("Test")
                )
                mock_context.__aexit__.return_value = None
                MockClient.return_value = mock_context

                result = await service.summarize("test query", projects)

                # Fallback should show 5 projects in message
                assert "Project 0" in result.summary
                # Context should be based on 20 projects (truncated from 25)
                assert result.context_used == 20


class TestContextTruncation:
    """Tests for context truncation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = AsyncMock()
        self.service = SummarizationService(self.mock_db)

    def test_truncate_context_under_limit(self):
        """Should not truncate if under limit."""
        context = SummarizationContext(
            query="test",
            projects=[{"name": "P1", "description": "Short"}],
            document_chunks=[],
            total_tokens_estimate=100,
        )

        result, truncated = self.service._truncate_context(context)

        assert truncated is False
        assert "P1" in result

    def test_truncate_context_over_limit(self):
        """Should truncate if over limit."""
        # Create context that exceeds token limit (6000 tokens * 4 chars = 24000 chars)
        # Need enough projects/chunks to generate 24000+ chars of formatted output
        # Each project generates ~300 chars with description truncated to 200
        # Need ~80+ projects to exceed limit, plus document chunks
        context = SummarizationContext(
            query="test",
            projects=[
                {"name": f"Project {i}" * 10, "description": "x" * 1000}
                for i in range(100)
            ],
            document_chunks=[
                {"content": "y" * 2000, "document_name": f"doc{j}.pdf"}
                for j in range(50)
            ],
            total_tokens_estimate=50000,
        )

        result, truncated = self.service._truncate_context(context)

        assert truncated is True
        # Result should be near the token limit (allow small buffer for truncation message)
        result_tokens = self.service._estimate_tokens(result)
        # Within 1% of limit is acceptable
        assert result_tokens <= self.service.MAX_CONTEXT_TOKENS * 1.01

    def test_truncate_context_includes_projects_section(self):
        """Should include projects section in formatted context."""
        context = SummarizationContext(
            query="test",
            projects=[
                {
                    "name": "Test Project",
                    "description": "A description",
                    "organization": "Test Org",
                    "status": "active",
                }
            ],
            document_chunks=[],
            total_tokens_estimate=100,
        )

        result, _ = self.service._truncate_context(context)

        assert "## Projects" in result
        assert "Test Project" in result
        assert "Test Org" in result
        assert "active" in result

    def test_truncate_context_includes_document_chunks(self):
        """Should include document chunks section in formatted context."""
        context = SummarizationContext(
            query="test",
            projects=[{"name": "P1"}],
            document_chunks=[
                {"content": "Document content here", "document_name": "test.pdf"}
            ],
            total_tokens_estimate=100,
        )

        result, _ = self.service._truncate_context(context)

        assert "## Relevant Document Excerpts" in result
        assert "Document content here" in result
        assert "test.pdf" in result

    def test_truncate_long_descriptions(self):
        """Should truncate long project descriptions."""
        long_description = "a" * 500  # Over 200 char limit
        context = SummarizationContext(
            query="test",
            projects=[{"name": "P1", "description": long_description}],
            document_chunks=[],
            total_tokens_estimate=100,
        )

        result, _ = self.service._truncate_context(context)

        # Description should be truncated with ellipsis
        assert "..." in result
        # Full description should not be present
        assert long_description not in result


class TestFallbackResult:
    """Tests for fallback result creation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = AsyncMock()
        self.service = SummarizationService(self.mock_db)

    def test_fallback_includes_project_names(self):
        """Should include project names in fallback summary."""
        projects = []
        for i in range(3):
            p = MagicMock()
            p.name = f"Project {i}"
            projects.append(p)

        result = self.service._create_fallback_result(projects, "Test error")

        assert "Project 0" in result.summary
        assert "Project 1" in result.summary
        assert "Project 2" in result.summary
        assert result.error == "Test error"

    def test_fallback_limits_to_five_projects(self):
        """Should only show first 5 project names in fallback."""
        projects = []
        for i in range(10):
            p = MagicMock()
            p.name = f"Project {i}"
            projects.append(p)

        result = self.service._create_fallback_result(projects, "Test error")

        assert "Project 4" in result.summary
        assert "Project 5" not in result.summary  # 6th project not shown
        assert "and 5 more" in result.summary
        assert result.context_used == 10

    def test_fallback_sets_truncated_false(self):
        """Should set truncated to False in fallback."""
        p = MagicMock()
        p.name = "Test"
        result = self.service._create_fallback_result([p], "Error")

        assert result.truncated is False


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_service_uses_configured_settings(self):
        """Should use settings from configuration."""
        mock_db = AsyncMock()
        service = SummarizationService(mock_db)

        # Should have settings from config
        assert service.base_url is not None
        assert service.model is not None
        assert isinstance(service.base_url, str)
        assert isinstance(service.model, str)

    def test_service_creates_search_service(self):
        """Should create a search service instance."""
        mock_db = AsyncMock()
        service = SummarizationService(mock_db)

        assert service.search_service is not None
