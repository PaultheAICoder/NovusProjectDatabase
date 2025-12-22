"""Tests for summarization API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.search import SummarizationRequest, SummarizationResponse
from app.services.summarization_service import SummarizationResult


class TestSummarizeEndpoint:
    """Tests for POST /api/v1/search/summarize endpoint."""

    @pytest.mark.asyncio
    async def test_summarize_non_streaming(self):
        """Should return JSON response for non-streaming request."""
        from fastapi import Request

        from app.api.search import summarize_search_results

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        body = SummarizationRequest(query="IoT projects", stream=False)

        mock_result = SummarizationResult(
            summary="Found 2 IoT projects.",
            context_used=5,
            truncated=False,
        )

        with (
            patch("app.api.search.NLQueryParser") as MockParser,
            patch("app.api.search.SearchService") as MockSearchService,
            patch("app.api.search.SummarizationService") as MockSummarizationService,
        ):
            parser_instance = MagicMock()
            parser_instance.parse_query = AsyncMock(
                return_value=MagicMock(
                    parsed_intent=MagicMock(search_text="IoT projects")
                )
            )
            MockParser.return_value = parser_instance

            search_instance = MagicMock()
            search_instance.search_projects = AsyncMock(return_value=([], 0))
            MockSearchService.return_value = search_instance

            summarization_instance = MagicMock()
            summarization_instance.summarize = AsyncMock(return_value=mock_result)
            MockSummarizationService.return_value = summarization_instance

            response = await summarize_search_results(
                request=mock_request,
                body=body,
                db=mock_db,
                current_user=mock_user,
            )

            assert isinstance(response, SummarizationResponse)
            assert response.summary == "Found 2 IoT projects."
            assert response.context_used == 5
            assert response.truncated is False

    @pytest.mark.asyncio
    async def test_summarize_with_project_ids(self):
        """Should summarize specific projects when IDs provided."""
        from fastapi import Request

        from app.api.search import summarize_search_results

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        project_id = uuid4()
        body = SummarizationRequest(
            query="summarize this project",
            project_ids=[project_id],
            stream=False,
        )

        mock_result = SummarizationResult(
            summary="Project summary here.",
            context_used=3,
            truncated=False,
        )

        with (
            patch("app.api.search._fetch_projects_by_ids") as mock_fetch,
            patch("app.api.search.SummarizationService") as MockSummarizationService,
        ):
            mock_project = MagicMock()
            mock_project.name = "Test Project"
            mock_fetch.return_value = [mock_project]

            summarization_instance = MagicMock()
            summarization_instance.summarize = AsyncMock(return_value=mock_result)
            MockSummarizationService.return_value = summarization_instance

            response = await summarize_search_results(
                request=mock_request,
                body=body,
                db=mock_db,
                current_user=mock_user,
            )

            mock_fetch.assert_called_once()
            assert response.summary == "Project summary here."

    @pytest.mark.asyncio
    async def test_summarize_streaming_returns_streaming_response(self):
        """Should return StreamingResponse for streaming request."""
        from fastapi import Request
        from fastapi.responses import StreamingResponse

        from app.api.search import summarize_search_results

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        body = SummarizationRequest(query="IoT projects", stream=True)

        async def mock_stream():
            yield "data: Test\n\n"
            yield "data: [DONE]\n\n"

        with (
            patch("app.api.search.NLQueryParser") as MockParser,
            patch("app.api.search.SearchService") as MockSearchService,
            patch("app.api.search.SummarizationService") as MockSummarizationService,
        ):
            parser_instance = MagicMock()
            parser_instance.parse_query = AsyncMock(
                return_value=MagicMock(
                    parsed_intent=MagicMock(search_text="IoT projects")
                )
            )
            MockParser.return_value = parser_instance

            search_instance = MagicMock()
            search_instance.search_projects = AsyncMock(return_value=([], 0))
            MockSearchService.return_value = search_instance

            summarization_instance = MagicMock()
            summarization_instance.summarize_stream = MagicMock(
                return_value=mock_stream()
            )
            MockSummarizationService.return_value = summarization_instance

            response = await summarize_search_results(
                request=mock_request,
                body=body,
                db=mock_db,
                current_user=mock_user,
            )

            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_summarize_uses_search_when_no_project_ids(self):
        """Should use search service when no project IDs provided."""
        from fastapi import Request

        from app.api.search import summarize_search_results

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        body = SummarizationRequest(query="IoT projects", stream=False)

        mock_result = SummarizationResult(
            summary="Found projects.",
            context_used=2,
            truncated=False,
        )

        mock_project = MagicMock()
        mock_project.name = "Found Project"

        with (
            patch("app.api.search.NLQueryParser") as MockParser,
            patch("app.api.search.SearchService") as MockSearchService,
            patch("app.api.search.SummarizationService") as MockSummarizationService,
        ):
            parser_instance = MagicMock()
            parser_instance.parse_query = AsyncMock(
                return_value=MagicMock(
                    parsed_intent=MagicMock(search_text="IoT projects")
                )
            )
            MockParser.return_value = parser_instance

            search_instance = MagicMock()
            search_instance.search_projects = AsyncMock(
                return_value=([mock_project], 1)
            )
            MockSearchService.return_value = search_instance

            summarization_instance = MagicMock()
            summarization_instance.summarize = AsyncMock(return_value=mock_result)
            MockSummarizationService.return_value = summarization_instance

            response = await summarize_search_results(
                request=mock_request,
                body=body,
                db=mock_db,
                current_user=mock_user,
            )

            # Parser and search should have been called
            parser_instance.parse_query.assert_called_once_with("IoT projects")
            search_instance.search_projects.assert_called_once()

            assert response.query == "IoT projects"


class TestFetchProjectsByIds:
    """Tests for _fetch_projects_by_ids helper."""

    @pytest.mark.asyncio
    async def test_fetch_projects_returns_list(self):
        """Should return list of projects."""
        from app.api.search import _fetch_projects_by_ids

        mock_db = AsyncMock()
        project_id = uuid4()

        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.name = "Test Project"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_project]
        mock_db.execute.return_value = mock_result

        result = await _fetch_projects_by_ids(mock_db, [project_id])

        assert len(result) == 1
        assert result[0].name == "Test Project"

    @pytest.mark.asyncio
    async def test_fetch_projects_empty_ids(self):
        """Should return empty list for empty IDs."""
        from app.api.search import _fetch_projects_by_ids

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await _fetch_projects_by_ids(mock_db, [])

        assert len(result) == 0


class TestSummarizationSchemas:
    """Tests for summarization Pydantic schemas."""

    def test_summarization_request_requires_query(self):
        """Should require non-empty query field."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SummarizationRequest(query="")

        # Should accept valid query
        req = SummarizationRequest(query="test query")
        assert req.query == "test query"

    def test_summarization_request_defaults(self):
        """Should have correct default values."""
        req = SummarizationRequest(query="test")

        assert req.project_ids is None
        assert req.max_chunks == 10
        assert req.stream is False

    def test_summarization_request_max_chunks_constraints(self):
        """Should enforce max_chunks constraints."""
        from pydantic import ValidationError

        # max_chunks must be >= 1
        with pytest.raises(ValidationError):
            SummarizationRequest(query="test", max_chunks=0)

        # max_chunks must be <= 50
        with pytest.raises(ValidationError):
            SummarizationRequest(query="test", max_chunks=51)

        # Valid values should work
        req = SummarizationRequest(query="test", max_chunks=25)
        assert req.max_chunks == 25

    def test_summarization_request_with_project_ids(self):
        """Should accept project IDs."""
        project_id = uuid4()
        req = SummarizationRequest(
            query="summarize",
            project_ids=[project_id],
        )

        assert req.project_ids == [project_id]

    def test_summarization_response_structure(self):
        """Should have correct response structure."""
        response = SummarizationResponse(
            summary="Test summary",
            query="test query",
            context_used=5,
            truncated=False,
        )

        assert response.summary == "Test summary"
        assert response.query == "test query"
        assert response.context_used == 5
        assert response.truncated is False
