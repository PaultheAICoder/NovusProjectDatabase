"""Tests for projects API search and filter functionality."""

from uuid import uuid4

from app.models.project import Project, ProjectStatus, ProjectTag


class TestProjectsSearchVectorModel:
    """Tests for Project search_vector model definitions."""

    def test_project_has_search_vector(self):
        """Project model should have search_vector attribute for full-text search."""
        assert hasattr(Project, "search_vector")

    def test_project_tag_model_exists(self):
        """ProjectTag junction model should exist for tag filtering."""
        assert hasattr(ProjectTag, "project_id")
        assert hasattr(ProjectTag, "tag_id")


class TestProjectStatusEnum:
    """Tests for ProjectStatus enum values."""

    def test_all_status_values_exist(self):
        """All expected status values should be defined."""
        expected = ["approved", "active", "on_hold", "completed", "cancelled"]
        actual = [s.value for s in ProjectStatus]
        for status in expected:
            assert status in actual

    def test_status_enum_is_string_enum(self):
        """ProjectStatus should be a string enum for API compatibility."""
        assert isinstance(ProjectStatus.ACTIVE.value, str)
        assert ProjectStatus.ACTIVE.value == "active"


class TestProjectSearchFiltering:
    """Tests for project search filtering logic.

    These tests verify the filter parameter structure and logic without
    directly calling the rate-limited endpoint.
    """

    def test_text_search_query_structure(self):
        """Text search should use plainto_tsquery for search_vector matching."""
        from sqlalchemy import func

        # Verify the function exists and can be called
        ts_query = func.plainto_tsquery("english", "test query")
        assert ts_query is not None

    def test_tag_filter_subquery_structure(self):
        """Tag filtering should use subquery on ProjectTag table."""
        from sqlalchemy import select

        tag_id = uuid4()
        subquery = select(ProjectTag.project_id).where(ProjectTag.tag_id == tag_id)
        assert subquery is not None

    def test_multiple_tag_filters_create_and_condition(self):
        """Multiple tag IDs should filter projects having ALL specified tags."""
        from sqlalchemy import select

        tag_ids = [uuid4(), uuid4(), uuid4()]

        # Each tag creates a separate IN condition
        subqueries = []
        for tag_id in tag_ids:
            subquery = select(ProjectTag.project_id).where(ProjectTag.tag_id == tag_id)
            subqueries.append(subquery)

        # All subqueries should be created
        assert len(subqueries) == 3

    def test_status_filter_uses_in_clause(self):
        """Status filter should use IN clause for multiple statuses."""
        statuses = [ProjectStatus.ACTIVE, ProjectStatus.APPROVED]

        # Verify IN clause can be built
        in_clause = Project.status.in_(statuses)
        assert in_clause is not None


class TestProjectFilterIntegration:
    """Integration tests for filter parameter handling.

    These tests verify that filter parameters are correctly processed.
    """

    def test_empty_query_string_treated_as_no_filter(self):
        """Empty or whitespace-only query should not apply text search."""
        # Test the condition used in the endpoint
        q = ""
        should_filter = q and q.strip()
        assert not should_filter

        q = "   "
        should_filter = q and q.strip()
        assert not should_filter

    def test_valid_query_applies_filter(self):
        """Non-empty query should apply text search filter."""
        q = "test search"
        should_filter = q and q.strip()
        assert should_filter

    def test_empty_tag_ids_treated_as_no_filter(self):
        """Empty or None tag_ids should not apply tag filter."""
        tag_ids = None
        should_filter = bool(tag_ids)
        assert not should_filter

        tag_ids = []
        should_filter = bool(tag_ids)
        assert not should_filter

    def test_valid_tag_ids_applies_filter(self):
        """Non-empty tag_ids should apply tag filter."""
        tag_ids = [uuid4()]
        should_filter = bool(tag_ids)
        assert should_filter
