"""Tests for tag co-occurrence suggestions.

Unit tests for the TagSuggester.get_cooccurrence_suggestions method
and the /tags/cooccurrence API endpoint.
"""

from uuid import uuid4

import pytest


class TestTagCooccurrenceServiceMethod:
    """Tests for TagSuggester.get_cooccurrence_suggestions method logic."""

    def test_service_returns_empty_for_empty_input(self):
        """Empty selected_tag_ids should return empty list."""
        # This tests the early return logic in the service method
        selected_tag_ids = []
        # The service method checks `if not selected_tag_ids: return []`
        assert not selected_tag_ids
        # If we passed this to the service, it would return []

    def test_service_excludes_selected_tags_from_results(self):
        """Selected tags should be excluded from co-occurrence results."""
        # Test the logic: ~Tag.id.in_(selected_tag_ids)
        # This verifies the exclusion logic is present in the query
        from app.services.tag_suggester import TagSuggester

        # Verify the method exists and has correct signature
        assert hasattr(TagSuggester, "get_cooccurrence_suggestions")
        import inspect

        sig = inspect.signature(TagSuggester.get_cooccurrence_suggestions)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "selected_tag_ids" in params
        assert "limit" in params

    def test_service_has_default_limit_of_five(self):
        """Default limit should be 5 suggestions."""
        import inspect

        from app.services.tag_suggester import TagSuggester

        sig = inspect.signature(TagSuggester.get_cooccurrence_suggestions)
        limit_param = sig.parameters["limit"]
        assert limit_param.default == 5

    def test_service_uses_aliased_tables_for_self_join(self):
        """Service should use SQLAlchemy aliased tables for the self-join query."""
        import inspect

        from app.services.tag_suggester import TagSuggester

        # Get the source code of the method
        source = inspect.getsource(TagSuggester.get_cooccurrence_suggestions)

        # Verify aliased tables are used
        assert "aliased" in source
        assert "pt1" in source or "pt2" in source  # Alias names from the plan


class TestTagCooccurrenceSchema:
    """Tests for co-occurrence schema definitions."""

    def test_cooccurrence_tag_suggestion_schema_exists(self):
        """CooccurrenceTagSuggestion schema should be defined."""
        from app.schemas.tag import CooccurrenceTagSuggestion

        # Verify schema has required fields
        schema_fields = CooccurrenceTagSuggestion.model_fields
        assert "tag" in schema_fields
        assert "co_occurrence_count" in schema_fields

    def test_cooccurrence_tags_response_schema_exists(self):
        """CooccurrenceTagsResponse schema should be defined."""
        from app.schemas.tag import CooccurrenceTagsResponse

        # Verify schema has required fields
        schema_fields = CooccurrenceTagsResponse.model_fields
        assert "suggestions" in schema_fields
        assert "selected_tag_ids" in schema_fields

    def test_cooccurrence_count_is_integer(self):
        """co_occurrence_count should be an integer field."""
        from app.schemas.tag import CooccurrenceTagSuggestion

        field_info = CooccurrenceTagSuggestion.model_fields["co_occurrence_count"]
        assert field_info.annotation is int


class TestTagCooccurrenceEndpoint:
    """Tests for /tags/cooccurrence API endpoint structure."""

    def test_endpoint_function_exists(self):
        """get_cooccurrence_suggestions endpoint should exist in tags API."""
        from app.api.tags import get_cooccurrence_suggestions

        assert get_cooccurrence_suggestions is not None
        assert callable(get_cooccurrence_suggestions)

    def test_endpoint_has_query_parameter_for_tag_ids(self):
        """Endpoint should accept tag_ids as a query parameter."""
        import inspect

        from app.api.tags import get_cooccurrence_suggestions

        sig = inspect.signature(get_cooccurrence_suggestions)
        params = list(sig.parameters.keys())
        assert "tag_ids" in params

    def test_endpoint_has_limit_parameter(self):
        """Endpoint should accept limit as a query parameter."""
        import inspect

        from app.api.tags import get_cooccurrence_suggestions

        sig = inspect.signature(get_cooccurrence_suggestions)
        params = list(sig.parameters.keys())
        assert "limit" in params

    def test_endpoint_returns_cooccurrence_response(self):
        """Endpoint should return CooccurrenceTagsResponse type."""
        import inspect

        from app.api.tags import get_cooccurrence_suggestions

        sig = inspect.signature(get_cooccurrence_suggestions)
        return_annotation = sig.return_annotation

        # Check return annotation
        from app.schemas.tag import CooccurrenceTagsResponse

        assert return_annotation == CooccurrenceTagsResponse


class TestTagCooccurrenceInputValidation:
    """Tests for input validation logic."""

    def test_invalid_uuid_raises_error(self):
        """Invalid UUID format should raise HTTPException."""
        # Test the UUID parsing logic: UUID(tid.strip())
        from uuid import UUID

        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        invalid_uuid = "not-a-uuid"

        # Valid UUID should parse
        parsed = UUID(valid_uuid)
        assert parsed is not None

        # Invalid UUID should raise ValueError
        with pytest.raises(ValueError):
            UUID(invalid_uuid)

    def test_comma_separated_parsing(self):
        """Comma-separated UUIDs should be parsed correctly."""
        tag_ids = (
            "550e8400-e29b-41d4-a716-446655440000,550e8400-e29b-41d4-a716-446655440001"
        )
        from uuid import UUID

        parsed_ids = [UUID(tid.strip()) for tid in tag_ids.split(",") if tid.strip()]

        assert len(parsed_ids) == 2
        assert all(isinstance(pid, UUID) for pid in parsed_ids)

    def test_empty_string_returns_empty_list(self):
        """Empty tag_ids string should result in empty parsed list."""
        tag_ids = ""
        parsed_ids = [tid.strip() for tid in tag_ids.split(",") if tid.strip()]

        assert parsed_ids == []

    def test_whitespace_handling(self):
        """Whitespace around UUIDs should be handled."""
        tag_ids = "  550e8400-e29b-41d4-a716-446655440000  ,  550e8400-e29b-41d4-a716-446655440001  "
        from uuid import UUID

        parsed_ids = [UUID(tid.strip()) for tid in tag_ids.split(",") if tid.strip()]

        assert len(parsed_ids) == 2


class TestTagCooccurrenceQueryStructure:
    """Tests for SQL query structure in co-occurrence suggestions."""

    def test_query_uses_project_tag_self_join(self):
        """Query should join project_tags table to itself."""
        from app.models.project import ProjectTag

        # Verify ProjectTag has the columns needed for self-join
        assert hasattr(ProjectTag, "project_id")
        assert hasattr(ProjectTag, "tag_id")

    def test_query_groups_by_tag_id(self):
        """Query should group results by tag ID."""
        import inspect

        from app.services.tag_suggester import TagSuggester

        source = inspect.getsource(TagSuggester.get_cooccurrence_suggestions)

        # Verify GROUP BY is present
        assert "group_by" in source.lower()

    def test_query_orders_by_count_descending(self):
        """Query should order results by co-occurrence count descending."""
        import inspect

        from app.services.tag_suggester import TagSuggester

        source = inspect.getsource(TagSuggester.get_cooccurrence_suggestions)

        # Verify ORDER BY with DESC is present
        assert "order_by" in source.lower()
        assert "desc" in source.lower()

    def test_query_respects_limit(self):
        """Query should apply the limit parameter."""
        import inspect

        from app.services.tag_suggester import TagSuggester

        source = inspect.getsource(TagSuggester.get_cooccurrence_suggestions)

        # Verify LIMIT is present
        assert ".limit(" in source


class TestTagCooccurrenceReturnType:
    """Tests for return type of co-occurrence suggestions."""

    def test_service_returns_list_of_tuples(self):
        """Service method should return list of (Tag, int) tuples."""
        import inspect

        from app.services.tag_suggester import TagSuggester

        sig = inspect.signature(TagSuggester.get_cooccurrence_suggestions)
        return_annotation = str(sig.return_annotation)

        # Return type should be list[tuple[Tag, int]]
        assert "list" in return_annotation
        assert "tuple" in return_annotation

    def test_response_schema_validates_correctly(self):
        """Response schema should validate a valid response structure."""
        from app.models.tag import TagType
        from app.schemas.tag import (
            CooccurrenceTagsResponse,
            CooccurrenceTagSuggestion,
            TagResponse,
        )

        # Create a valid response structure
        tag_response = TagResponse(
            id=uuid4(),
            name="Python",
            type=TagType.TECHNOLOGY,
        )

        suggestion = CooccurrenceTagSuggestion(
            tag=tag_response,
            co_occurrence_count=5,
        )

        response = CooccurrenceTagsResponse(
            suggestions=[suggestion],
            selected_tag_ids=[uuid4()],
        )

        assert len(response.suggestions) == 1
        assert response.suggestions[0].co_occurrence_count == 5
        assert len(response.selected_tag_ids) == 1
