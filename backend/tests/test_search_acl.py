"""Tests for search endpoint ACL enforcement."""

import inspect


class TestSearchExportACL:
    """Tests for search CSV export ACL."""

    def test_generate_search_csv_rows_accepts_user_param(self):
        """CSV row generator should accept user parameter for ACL filtering."""
        from app.api.search import _generate_search_csv_rows

        sig = inspect.signature(_generate_search_csv_rows)
        params = sig.parameters

        assert "user" in params, "Missing 'user' parameter for ACL filtering"

    def test_export_csv_passes_user_to_generator(self):
        """Export endpoint should pass current_user to the generator."""
        from app.api.search import export_search_results_csv

        source = inspect.getsource(export_search_results_csv)

        # Verify that user=current_user is passed to the generator
        assert (
            "user=current_user" in source
        ), "export_search_results_csv must pass user=current_user to _generate_search_csv_rows"


class TestSummarizationACL:
    """Tests for summarization endpoint ACL."""

    def test_fetch_projects_by_ids_accepts_user_param(self):
        """Project fetch helper should accept user for ACL filtering."""
        from app.api.search import _fetch_projects_by_ids

        sig = inspect.signature(_fetch_projects_by_ids)
        params = sig.parameters

        assert "user" in params, "Missing 'user' parameter for ACL filtering"

    def test_summarize_passes_user_to_fetch_projects(self):
        """Summarize endpoint should pass current_user to _fetch_projects_by_ids."""
        from app.api.search import summarize_search_results

        source = inspect.getsource(summarize_search_results)

        # Verify that current_user is passed to the helper
        assert (
            "_fetch_projects_by_ids(db, body.project_ids, current_user)" in source
        ), "summarize_search_results must pass current_user to _fetch_projects_by_ids"

    def test_summarize_passes_user_to_search(self):
        """Summarize endpoint should pass current_user to search_projects."""
        from app.api.search import summarize_search_results

        source = inspect.getsource(summarize_search_results)

        # Verify that user=current_user is passed to search_projects
        assert (
            "user=current_user" in source
        ), "summarize_search_results must pass user=current_user to search_projects"


class TestPermissionServiceIntegration:
    """Tests for PermissionService usage in _fetch_projects_by_ids."""

    def test_fetch_projects_uses_permission_service(self):
        """_fetch_projects_by_ids should use PermissionService for ACL filtering."""
        from app.api.search import _fetch_projects_by_ids

        source = inspect.getsource(_fetch_projects_by_ids)

        # Verify PermissionService is imported and used
        assert (
            "PermissionService" in source
        ), "_fetch_projects_by_ids must use PermissionService"
        assert (
            "get_accessible_project_ids" in source
        ), "_fetch_projects_by_ids must call get_accessible_project_ids"
