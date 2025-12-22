"""Tests for semantic search API endpoint."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.project import ProjectStatus
from app.schemas.nl_query import DateRange, NLQueryParseResponse, ParsedQueryIntent
from app.schemas.search import (
    ParsedQueryMetadata,
    SemanticSearchFilters,
    SemanticSearchRequest,
    SemanticSearchResponse,
)


class TestSemanticSearchEndpoint:
    """Tests for POST /api/v1/search/semantic endpoint."""

    @pytest.fixture
    def mock_parse_response(self):
        """Create a mock NL query parse response."""
        return NLQueryParseResponse(
            original_query="show me IoT projects from last 2 years",
            parsed_intent=ParsedQueryIntent(
                search_text="projects",
                date_range=DateRange(
                    start_date=date.today() - timedelta(days=730),
                    end_date=date.today(),
                    original_expression="last 2 years",
                ),
                technology_keywords=["IoT"],
                tag_ids=[],
                status=[],
                confidence=0.85,
            ),
            fallback_used=False,
            parse_explanation="Searching for: 'projects' | Time filter: last 2 years | Technologies: IoT (0/1 matched to tags)",
        )

    @pytest.mark.asyncio
    async def test_semantic_search_parses_query_and_searches(self, mock_parse_response):
        """Should parse query using NLQueryParser and search with SearchService."""
        from fastapi import Request

        from app.api.search import semantic_search

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = uuid4()

        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        body = SemanticSearchRequest(query="show me IoT projects from last 2 years")

        with (
            patch("app.api.search.NLQueryParser") as MockParser,
            patch("app.api.search.SearchService") as MockSearchService,
        ):
            # Mock NL parser
            parser_instance = MagicMock()
            parser_instance.parse_query = AsyncMock(return_value=mock_parse_response)
            MockParser.return_value = parser_instance

            # Mock search service to return empty results
            search_instance = MagicMock()
            search_instance.search_projects = AsyncMock(return_value=([], 0))
            MockSearchService.return_value = search_instance

            response = await semantic_search(
                request=mock_request,
                body=body,
                db=mock_db,
                current_user=mock_user,
            )

            # Verify parser was called with the query
            parser_instance.parse_query.assert_called_once_with(body.query)

            # Verify search service was called with parsed results
            search_instance.search_projects.assert_called_once()
            call_kwargs = search_instance.search_projects.call_args.kwargs
            assert call_kwargs["query"] == "projects"  # From parsed_intent.search_text
            assert call_kwargs["page"] == 1
            assert call_kwargs["page_size"] == 20

            # Verify response structure
            assert isinstance(response, SemanticSearchResponse)
            assert response.query == body.query
            assert response.parsed_query.fallback_used is False
            assert response.total == 0

    @pytest.mark.asyncio
    async def test_semantic_search_applies_filter_overrides(self, mock_parse_response):
        """Should apply filter overrides over parsed filters."""
        from fastapi import Request

        from app.api.search import semantic_search

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        org_id = uuid4()
        body = SemanticSearchRequest(
            query="test query",
            filters=SemanticSearchFilters(
                status=[ProjectStatus.ACTIVE, ProjectStatus.COMPLETED],
                organization_id=org_id,
            ),
        )

        with (
            patch("app.api.search.NLQueryParser") as MockParser,
            patch("app.api.search.SearchService") as MockSearchService,
        ):
            parser_instance = MagicMock()
            parser_instance.parse_query = AsyncMock(return_value=mock_parse_response)
            MockParser.return_value = parser_instance

            search_instance = MagicMock()
            search_instance.search_projects = AsyncMock(return_value=([], 0))
            MockSearchService.return_value = search_instance

            await semantic_search(
                request=mock_request,
                body=body,
                db=mock_db,
                current_user=mock_user,
            )

            # Verify filter overrides were applied
            call_kwargs = search_instance.search_projects.call_args.kwargs
            assert call_kwargs["status"] == [
                ProjectStatus.ACTIVE,
                ProjectStatus.COMPLETED,
            ]
            assert call_kwargs["organization_id"] == org_id

    @pytest.mark.asyncio
    async def test_semantic_search_pagination(self, mock_parse_response):
        """Should support pagination parameters."""
        from fastapi import Request

        from app.api.search import semantic_search

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        body = SemanticSearchRequest(query="test", page=3, page_size=10)

        with (
            patch("app.api.search.NLQueryParser") as MockParser,
            patch("app.api.search.SearchService") as MockSearchService,
        ):
            parser_instance = MagicMock()
            parser_instance.parse_query = AsyncMock(return_value=mock_parse_response)
            MockParser.return_value = parser_instance

            search_instance = MagicMock()
            search_instance.search_projects = AsyncMock(return_value=([], 50))
            MockSearchService.return_value = search_instance

            response = await semantic_search(
                request=mock_request,
                body=body,
                db=mock_db,
                current_user=mock_user,
            )

            # Verify pagination in response
            assert response.page == 3
            assert response.page_size == 10
            assert response.total == 50

            # Verify pagination passed to search service
            call_kwargs = search_instance.search_projects.call_args.kwargs
            assert call_kwargs["page"] == 3
            assert call_kwargs["page_size"] == 10

    @pytest.mark.asyncio
    async def test_semantic_search_fallback_mode(self):
        """Should handle LLM failure with fallback."""
        from fastapi import Request

        from app.api.search import semantic_search

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        fallback_response = NLQueryParseResponse(
            original_query="test query",
            parsed_intent=ParsedQueryIntent(
                search_text="test query",
                confidence=0.0,
            ),
            fallback_used=True,
            parse_explanation="Fallback to keyword search: LLM unavailable",
        )

        body = SemanticSearchRequest(query="test query")

        with (
            patch("app.api.search.NLQueryParser") as MockParser,
            patch("app.api.search.SearchService") as MockSearchService,
        ):
            parser_instance = MagicMock()
            parser_instance.parse_query = AsyncMock(return_value=fallback_response)
            MockParser.return_value = parser_instance

            search_instance = MagicMock()
            search_instance.search_projects = AsyncMock(return_value=([], 0))
            MockSearchService.return_value = search_instance

            response = await semantic_search(
                request=mock_request,
                body=body,
                db=mock_db,
                current_user=mock_user,
            )

            assert response.parsed_query.fallback_used is True
            assert "Fallback" in response.parsed_query.parse_explanation

    @pytest.mark.asyncio
    async def test_semantic_search_with_date_range(self):
        """Should apply date range from parsed query."""
        from fastapi import Request

        from app.api.search import semantic_search

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        start_date = date.today() - timedelta(days=730)
        end_date = date.today()

        parse_response = NLQueryParseResponse(
            original_query="projects from last 2 years",
            parsed_intent=ParsedQueryIntent(
                search_text="projects",
                date_range=DateRange(
                    start_date=start_date,
                    end_date=end_date,
                    original_expression="last 2 years",
                ),
                confidence=0.9,
            ),
            fallback_used=False,
            parse_explanation="Time filter: last 2 years",
        )

        body = SemanticSearchRequest(query="projects from last 2 years")

        with (
            patch("app.api.search.NLQueryParser") as MockParser,
            patch("app.api.search.SearchService") as MockSearchService,
        ):
            parser_instance = MagicMock()
            parser_instance.parse_query = AsyncMock(return_value=parse_response)
            MockParser.return_value = parser_instance

            search_instance = MagicMock()
            search_instance.search_projects = AsyncMock(return_value=([], 0))
            MockSearchService.return_value = search_instance

            await semantic_search(
                request=mock_request,
                body=body,
                db=mock_db,
                current_user=mock_user,
            )

            # Verify date range was passed to search service
            call_kwargs = search_instance.search_projects.call_args.kwargs
            assert call_kwargs["start_date_from"] == start_date
            assert call_kwargs["start_date_to"] == end_date


class TestSearchServiceDateFiltering:
    """Tests for date range filtering in search service."""

    @pytest.mark.asyncio
    async def test_filter_by_start_date_from(self):
        """Should filter projects with start_date >= from date."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()
        service = SearchService(mock_db)

        start_date = date(2024, 1, 1)

        conditions = service._build_filter_conditions(
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            start_date_from=start_date,
            start_date_to=None,
        )

        # Should have one condition for start_date_from
        assert len(conditions) == 1
        # Verify it's a date comparison (checking structure)
        condition_str = str(conditions[0])
        assert "start_date" in condition_str
        assert ">=" in condition_str

    @pytest.mark.asyncio
    async def test_filter_by_start_date_to(self):
        """Should filter projects with start_date <= to date."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()
        service = SearchService(mock_db)

        end_date = date(2024, 12, 31)

        conditions = service._build_filter_conditions(
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            start_date_from=None,
            start_date_to=end_date,
        )

        # Should have one condition for start_date_to
        assert len(conditions) == 1
        condition_str = str(conditions[0])
        assert "start_date" in condition_str
        assert "<=" in condition_str

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self):
        """Should filter projects within date range."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()
        service = SearchService(mock_db)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)

        conditions = service._build_filter_conditions(
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            start_date_from=start_date,
            start_date_to=end_date,
        )

        # Should have two conditions: start_date >= from AND start_date <= to
        assert len(conditions) == 2

    @pytest.mark.asyncio
    async def test_date_filter_combined_with_other_filters(self):
        """Should combine date filters with other filters correctly."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()
        service = SearchService(mock_db)

        org_id = uuid4()
        start_date = date(2024, 1, 1)

        conditions = service._build_filter_conditions(
            status=[ProjectStatus.ACTIVE],
            organization_id=org_id,
            tag_ids=None,
            owner_id=None,
            start_date_from=start_date,
            start_date_to=None,
        )

        # Should have 3 conditions: status, organization_id, and start_date_from
        assert len(conditions) == 3

    @pytest.mark.asyncio
    async def test_date_filter_defaults_dont_affect_existing_calls(self):
        """Ensure date filter defaults maintain backward compatibility."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()
        service = SearchService(mock_db)

        # Existing call pattern without date parameters
        conditions = service._build_filter_conditions(
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
        )

        # Should return empty list (no conditions)
        assert len(conditions) == 0


class TestSemanticSearchSchemas:
    """Tests for semantic search Pydantic schemas."""

    def test_semantic_search_request_requires_query(self):
        """Should require non-empty query field."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SemanticSearchRequest(query="")

        # Should accept valid query
        req = SemanticSearchRequest(query="test query")
        assert req.query == "test query"

    def test_semantic_search_request_defaults(self):
        """Should have correct default values."""
        req = SemanticSearchRequest(query="test")

        assert req.filters is None
        assert req.page == 1
        assert req.page_size == 20

    def test_semantic_search_request_pagination_constraints(self):
        """Should enforce pagination constraints."""
        from pydantic import ValidationError

        # Page must be >= 1
        with pytest.raises(ValidationError):
            SemanticSearchRequest(query="test", page=0)

        # Page size must be >= 1
        with pytest.raises(ValidationError):
            SemanticSearchRequest(query="test", page_size=0)

        # Page size must be <= 100
        with pytest.raises(ValidationError):
            SemanticSearchRequest(query="test", page_size=101)

    def test_semantic_search_filters_all_optional(self):
        """All filter fields should be optional."""
        filters = SemanticSearchFilters()

        assert filters.status is None
        assert filters.organization_id is None
        assert filters.tag_ids is None
        assert filters.owner_id is None

    def test_semantic_search_filters_with_values(self):
        """Should accept all filter values."""
        org_id = uuid4()
        tag_id = uuid4()
        owner_id = uuid4()

        filters = SemanticSearchFilters(
            status=[ProjectStatus.ACTIVE, ProjectStatus.COMPLETED],
            organization_id=org_id,
            tag_ids=[tag_id],
            owner_id=owner_id,
        )

        assert filters.status == [ProjectStatus.ACTIVE, ProjectStatus.COMPLETED]
        assert filters.organization_id == org_id
        assert filters.tag_ids == [tag_id]
        assert filters.owner_id == owner_id

    def test_parsed_query_metadata_structure(self):
        """ParsedQueryMetadata should have correct structure."""
        intent = ParsedQueryIntent(search_text="test", confidence=0.8)

        metadata = ParsedQueryMetadata(
            parsed_intent=intent,
            fallback_used=False,
            parse_explanation="Test explanation",
        )

        assert metadata.parsed_intent == intent
        assert metadata.fallback_used is False
        assert metadata.parse_explanation == "Test explanation"

    def test_semantic_search_response_structure(self):
        """SemanticSearchResponse should have correct structure."""
        intent = ParsedQueryIntent(search_text="test", confidence=0.8)
        metadata = ParsedQueryMetadata(
            parsed_intent=intent,
            fallback_used=False,
            parse_explanation="Test",
        )

        response = SemanticSearchResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            query="test query",
            parsed_query=metadata,
        )

        assert response.items == []
        assert response.total == 0
        assert response.page == 1
        assert response.page_size == 20
        assert response.query == "test query"
        assert response.parsed_query.fallback_used is False
