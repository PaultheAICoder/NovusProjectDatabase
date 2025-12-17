"""Tests for Azure AD role mapping to internal UserRole."""

from unittest.mock import patch

from app.core.auth import _map_azure_roles_to_user_role
from app.models.user import UserRole


class TestMapAzureRolesToUserRole:
    """Tests for the _map_azure_roles_to_user_role helper function."""

    def test_returns_admin_when_admin_role_present(self):
        """Returns ADMIN when 'admin' role is in the list."""
        result = _map_azure_roles_to_user_role(["admin"])
        assert result == UserRole.ADMIN

    def test_returns_admin_case_insensitive(self):
        """Returns ADMIN regardless of case (Admin, ADMIN, etc.)."""
        assert _map_azure_roles_to_user_role(["Admin"]) == UserRole.ADMIN
        assert _map_azure_roles_to_user_role(["ADMIN"]) == UserRole.ADMIN
        assert _map_azure_roles_to_user_role(["aDmIn"]) == UserRole.ADMIN

    def test_returns_user_when_no_admin_role(self):
        """Returns USER when admin role is not present."""
        result = _map_azure_roles_to_user_role(["user", "reader"])
        assert result == UserRole.USER

    def test_returns_user_for_empty_roles(self):
        """Returns USER when roles list is empty."""
        result = _map_azure_roles_to_user_role([])
        assert result == UserRole.USER

    def test_returns_admin_when_admin_among_multiple_roles(self):
        """Returns ADMIN when admin is one of several roles."""
        result = _map_azure_roles_to_user_role(["user", "admin", "reader"])
        assert result == UserRole.ADMIN

    def test_uses_configured_admin_role_name(self):
        """Uses the configured azure_ad_admin_role setting."""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.azure_ad_admin_role = "Administrator"

            # Should match "Administrator" now, not "admin"
            result = _map_azure_roles_to_user_role(["Administrator"])
            assert result == UserRole.ADMIN

            # "admin" should no longer grant admin
            result = _map_azure_roles_to_user_role(["admin"])
            assert result == UserRole.USER

    def test_configured_role_is_case_insensitive(self):
        """Configured role name is also compared case-insensitively."""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.azure_ad_admin_role = "SuperAdmin"

            assert _map_azure_roles_to_user_role(["superadmin"]) == UserRole.ADMIN
            assert _map_azure_roles_to_user_role(["SUPERADMIN"]) == UserRole.ADMIN
            assert _map_azure_roles_to_user_role(["SuperAdmin"]) == UserRole.ADMIN

    def test_partial_match_does_not_grant_admin(self):
        """Partial matches like 'administrator' do not match 'admin'."""
        result = _map_azure_roles_to_user_role(["administrator"])
        assert result == UserRole.USER

        result = _map_azure_roles_to_user_role(["superadmin"])
        assert result == UserRole.USER
