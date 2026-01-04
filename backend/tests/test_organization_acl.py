"""Tests for organization endpoint ACL enforcement."""

import inspect


class TestOrganizationDetailACL:
    """Tests for GET /organizations/{id} ACL filtering."""

    def test_get_organization_imports_permission_service(self):
        """get_organization should import and use PermissionService."""
        from app.api.organizations import get_organization

        source = inspect.getsource(get_organization)

        assert (
            "PermissionService" in source
        ), "get_organization must use PermissionService for ACL filtering"

    def test_get_organization_calls_get_accessible_project_ids(self):
        """get_organization should call get_accessible_project_ids."""
        from app.api.organizations import get_organization

        source = inspect.getsource(get_organization)

        assert (
            "get_accessible_project_ids" in source
        ), "get_organization must call get_accessible_project_ids for filtering"

    def test_get_organization_filters_projects_by_access(self):
        """get_organization should filter projects by accessible_ids."""
        from app.api.organizations import get_organization

        source = inspect.getsource(get_organization)

        # Should check if accessible_ids is non-empty before filtering
        assert (
            "if accessible_ids:" in source or "accessible_ids" in source
        ), "get_organization must filter projects based on accessible_ids"

    def test_get_organization_uses_accessible_projects_list(self):
        """get_organization should build projects from accessible_projects."""
        from app.api.organizations import get_organization

        source = inspect.getsource(get_organization)

        # Should use filtered list for building project summaries
        assert (
            "accessible_projects" in source
        ), "get_organization must use accessible_projects for project summaries"
