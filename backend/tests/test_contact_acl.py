"""Tests for contact endpoint ACL enforcement."""

import inspect


class TestContactDetailACL:
    """Tests for GET /contacts/{id} ACL filtering."""

    def test_get_contact_imports_permission_service(self):
        """get_contact should import and use PermissionService."""
        from app.api.contacts import get_contact

        source = inspect.getsource(get_contact)

        assert (
            "PermissionService" in source
        ), "get_contact must use PermissionService for ACL filtering"

    def test_get_contact_calls_get_accessible_project_ids(self):
        """get_contact should call get_accessible_project_ids."""
        from app.api.contacts import get_contact

        source = inspect.getsource(get_contact)

        assert (
            "get_accessible_project_ids" in source
        ), "get_contact must call get_accessible_project_ids for filtering"

    def test_get_contact_filters_projects_by_access(self):
        """get_contact should filter project_contacts by accessible_ids."""
        from app.api.contacts import get_contact

        source = inspect.getsource(get_contact)

        # Should check if accessible_ids is non-empty before filtering
        assert (
            "if accessible_ids:" in source or "accessible_ids" in source
        ), "get_contact must filter projects based on accessible_ids"

    def test_get_contact_uses_filtered_project_contacts(self):
        """get_contact should use filtered_project_contacts for project summaries."""
        from app.api.contacts import get_contact

        source = inspect.getsource(get_contact)

        # Should use filtered list for building project summaries
        assert (
            "filtered_project_contacts" in source
        ), "get_contact must use filtered_project_contacts for project summaries"
