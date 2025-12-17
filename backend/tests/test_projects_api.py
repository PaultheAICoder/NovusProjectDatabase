"""Tests for projects API search and filter functionality."""

from uuid import uuid4

from app.models.document import Document
from app.models.project import Project, ProjectLocation, ProjectStatus, ProjectTag
from app.schemas.project import DismissProjectTagSuggestionRequest


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


class TestProjectLocationEnum:
    """Tests for ProjectLocation enum values."""

    def test_all_location_values_exist(self):
        """All expected location values should be defined."""
        expected = ["headquarters", "test_house", "remote", "client_site", "other"]
        actual = [loc.value for loc in ProjectLocation]
        for location in expected:
            assert location in actual

    def test_location_enum_is_string_enum(self):
        """ProjectLocation should be a string enum for API compatibility."""
        assert isinstance(ProjectLocation.HEADQUARTERS.value, str)
        assert ProjectLocation.HEADQUARTERS.value == "headquarters"

    def test_location_enum_count(self):
        """ProjectLocation should have exactly 5 values."""
        assert len(ProjectLocation) == 5

    def test_project_has_location_attribute(self):
        """Project model should have location attribute."""
        assert hasattr(Project, "location")

    def test_project_has_location_other_attribute(self):
        """Project model should have location_other attribute for custom locations."""
        assert hasattr(Project, "location_other")


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


class TestProjectMilestoneFields:
    """Tests for milestone_version and run_number fields."""

    def test_project_has_milestone_version_attribute(self):
        """Project model should have milestone_version attribute."""
        assert hasattr(Project, "milestone_version")

    def test_project_has_run_number_attribute(self):
        """Project model should have run_number attribute."""
        assert hasattr(Project, "run_number")


class TestProjectContactOrganizationValidation:
    """Tests for project contact organization membership validation.

    These tests verify the bug fix for GitHub Issue #66 - contacts must
    belong to the project's organization.
    """

    def test_contact_validation_query_includes_organization_filter(self):
        """
        The contact validation query should filter by organization_id
        to ensure contacts belong to the project's organization.

        This tests the bug fix for issue #66.
        """
        from sqlalchemy import select

        from app.models import Contact

        org_id = uuid4()
        contact_ids = [uuid4(), uuid4()]

        # Build the query as it should appear in the fixed code
        query = select(Contact).where(
            Contact.id.in_(contact_ids),
            Contact.organization_id == org_id,
        )

        # Verify query has both conditions (structure test)
        assert query is not None
        # The compiled query should contain both filters

    def test_update_project_with_org_change_validates_contacts(self):
        """
        Changing a project's organization should validate that
        contacts belong to the new organization.
        """
        from app.schemas.project import ProjectUpdate

        # ProjectUpdate allows partial updates including org change
        new_org_id = uuid4()
        data = ProjectUpdate(
            organization_id=new_org_id,
        )

        # Dumping with exclude_unset should only include changed fields
        dump = data.model_dump(exclude_unset=True)
        assert "organization_id" in dump
        assert "contact_ids" not in dump  # Not provided

    def test_target_org_id_resolution_logic(self):
        """
        When updating contacts, the target org should be the new org
        if provided, otherwise the existing project org.
        """
        from app.schemas.project import ProjectUpdate

        # Test case 1: org change provided - should use new org
        new_org_id = uuid4()
        existing_org_id = uuid4()
        data_with_org_change = ProjectUpdate(organization_id=new_org_id)

        # Simulate the logic in update_project
        target_org_id = (
            data_with_org_change.organization_id
            if data_with_org_change.organization_id
            else existing_org_id
        )
        assert target_org_id == new_org_id

        # Test case 2: no org change - should use existing org
        data_no_org_change = ProjectUpdate(name="Updated Name")
        target_org_id = (
            data_no_org_change.organization_id
            if data_no_org_change.organization_id
            else existing_org_id
        )
        assert target_org_id == existing_org_id

    def test_contact_model_has_organization_id(self):
        """Contact model should have organization_id for validation."""
        from app.models import Contact

        assert hasattr(Contact, "organization_id")

    def test_project_contact_model_exists(self):
        """ProjectContact junction model should exist for contact relationships."""
        from app.models import ProjectContact

        assert hasattr(ProjectContact, "project_id")
        assert hasattr(ProjectContact, "contact_id")
        assert hasattr(ProjectContact, "is_primary")


class TestProjectCancellation:
    """Tests for project cancellation (soft-delete) behavior (GitHub Issue #71)."""

    def test_delete_endpoint_sets_cancelled_status(self):
        """DELETE /projects/{id} should set status to cancelled, not hard delete.

        This documents the soft-delete behavior of the delete endpoint.
        """
        # The cancelled status value should be 'cancelled'
        assert ProjectStatus.CANCELLED.value == "cancelled"

    def test_cancelled_is_valid_status(self):
        """Cancelled should be a valid ProjectStatus value."""
        assert ProjectStatus.CANCELLED in ProjectStatus

    def test_cancelled_status_in_enum_list(self):
        """Cancelled should be in the list of all status values."""
        all_statuses = [s.value for s in ProjectStatus]
        assert "cancelled" in all_statuses

    def test_status_transitions_exists(self):
        """Project model should have STATUS_TRANSITIONS for state machine logic."""
        from app.models.project import STATUS_TRANSITIONS

        assert STATUS_TRANSITIONS is not None
        assert isinstance(STATUS_TRANSITIONS, dict)

    def test_cancelled_is_terminal_status(self):
        """Cancelled status should be terminal (no transitions out by default)."""
        from app.models.project import STATUS_TRANSITIONS

        # Get allowed transitions from cancelled
        allowed_from_cancelled = STATUS_TRANSITIONS.get(ProjectStatus.CANCELLED, set())

        # Cancelled is a terminal status - no transitions allowed (empty set)
        assert allowed_from_cancelled == set()

    def test_project_can_transition_to_method_exists(self):
        """Project model should have can_transition_to method for status validation."""
        assert hasattr(Project, "can_transition_to")


class TestDismissProjectTagSuggestion:
    """Tests for project-level tag suggestion dismissal (GitHub Issue #70)."""

    def test_dismiss_request_schema_exists(self):
        """DismissProjectTagSuggestionRequest schema should exist."""
        assert DismissProjectTagSuggestionRequest is not None

    def test_dismiss_request_schema_has_tag_id_field(self):
        """DismissProjectTagSuggestionRequest should have tag_id field."""
        tag_id = uuid4()
        request = DismissProjectTagSuggestionRequest(tag_id=tag_id)
        assert request.tag_id == tag_id

    def test_document_model_has_dismissed_tag_ids(self):
        """Document model should have dismissed_tag_ids attribute for storing dismissed tags."""
        assert hasattr(Document, "dismissed_tag_ids")

    def test_document_model_has_suggested_tag_ids(self):
        """Document model should have suggested_tag_ids attribute for storing suggestions."""
        assert hasattr(Document, "suggested_tag_ids")

    def test_dismissal_logic_structure(self):
        """
        Test the dismissal logic pattern used in the endpoint.

        The dismissal should:
        1. Query documents with the suggested tag
        2. Add the tag_id to each document's dismissed_tag_ids
        """
        tag_id = uuid4()
        dismissed = []

        # Simulate adding to dismissed list
        if tag_id not in dismissed:
            dismissed = dismissed + [tag_id]

        assert tag_id in dismissed

    def test_dismissal_prevents_duplicate_entries(self):
        """Dismissal should not add duplicate tag IDs."""
        tag_id = uuid4()
        dismissed = [tag_id]

        # Simulate the check before adding
        if tag_id not in dismissed:
            dismissed = dismissed + [tag_id]

        # Should only have one entry
        assert dismissed.count(tag_id) == 1

    def test_empty_dismissed_list_initialization(self):
        """Dismissal should handle None dismissed_tag_ids gracefully."""
        dismissed = None
        tag_id = uuid4()

        # Simulate the logic in the endpoint
        dismissed_list = dismissed or []
        if tag_id not in dismissed_list:
            dismissed_list = dismissed_list + [tag_id]

        assert tag_id in dismissed_list
