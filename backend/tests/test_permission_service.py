"""Tests for PermissionService - ACL permission checking logic."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.project import Project
from app.models.project_permission import (
    PermissionLevel,
    ProjectVisibility,
)
from app.models.user import User, UserRole
from app.services.permission_service import PermissionService


@pytest.fixture
def mock_db():
    """Create a mock AsyncSession."""
    return AsyncMock()


@pytest.fixture
def regular_user():
    """Create a regular (non-admin) user."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.role = UserRole.USER
    user.email = "user@example.com"
    return user


@pytest.fixture
def admin_user():
    """Create an admin user."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.role = UserRole.ADMIN
    user.email = "admin@example.com"
    return user


@pytest.fixture
def public_project():
    """Create a public project."""
    project = MagicMock(spec=Project)
    project.id = uuid4()
    project.visibility = ProjectVisibility.PUBLIC
    project.name = "Public Project"
    return project


@pytest.fixture
def restricted_project():
    """Create a restricted project."""
    project = MagicMock(spec=Project)
    project.id = uuid4()
    project.visibility = ProjectVisibility.RESTRICTED
    project.name = "Restricted Project"
    return project


class TestAdminOverride:
    """Tests for admin users always having full access."""

    @pytest.mark.asyncio
    async def test_admin_has_owner_access_on_public_project(
        self, mock_db, admin_user, public_project
    ):
        """Admin gets OWNER level on public projects."""
        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(admin_user, public_project)
        assert level == PermissionLevel.OWNER

    @pytest.mark.asyncio
    async def test_admin_has_owner_access_on_restricted_project(
        self, mock_db, admin_user, restricted_project
    ):
        """Admin gets OWNER level on restricted projects without explicit permission."""
        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(admin_user, restricted_project)
        assert level == PermissionLevel.OWNER

    @pytest.mark.asyncio
    async def test_admin_passes_all_access_checks(
        self, mock_db, admin_user, restricted_project
    ):
        """Admin passes check_project_access for all levels."""
        service = PermissionService(mock_db)

        for required_level in PermissionLevel:
            result = await service.check_project_access(
                admin_user, restricted_project, required_level
            )
            assert result is True, f"Admin should pass {required_level} check"

    def test_is_admin_returns_true_for_admin(self, mock_db, admin_user):
        """is_admin returns True for admin users."""
        service = PermissionService(mock_db)
        assert service.is_admin(admin_user) is True

    def test_is_admin_returns_false_for_regular_user(self, mock_db, regular_user):
        """is_admin returns False for regular users."""
        service = PermissionService(mock_db)
        assert service.is_admin(regular_user) is False


class TestPublicVisibility:
    """Tests for public project visibility granting viewer access."""

    @pytest.mark.asyncio
    async def test_regular_user_has_viewer_on_public_project(
        self, mock_db, regular_user, public_project
    ):
        """Regular user gets VIEWER level on public projects (no explicit permission)."""
        # Mock: no direct permission, no team permissions
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(regular_user, public_project)

        assert level == PermissionLevel.VIEWER

    @pytest.mark.asyncio
    async def test_regular_user_no_access_on_restricted_project(
        self, mock_db, regular_user, restricted_project
    ):
        """Regular user has no access to restricted project without permission."""
        # Mock: no direct permission, no team permissions
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(
            regular_user, restricted_project
        )

        assert level is None

    @pytest.mark.asyncio
    async def test_viewer_check_passes_on_public_project(
        self, mock_db, regular_user, public_project
    ):
        """check_project_access for VIEWER passes on public project."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        service = PermissionService(mock_db)
        result = await service.check_project_access(
            regular_user, public_project, PermissionLevel.VIEWER
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_editor_check_fails_on_public_project_without_permission(
        self, mock_db, regular_user, public_project
    ):
        """check_project_access for EDITOR fails on public project without explicit grant."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        service = PermissionService(mock_db)
        result = await service.check_project_access(
            regular_user, public_project, PermissionLevel.EDITOR
        )

        assert result is False


class TestDirectPermissions:
    """Tests for direct user permission resolution."""

    @pytest.mark.asyncio
    async def test_direct_editor_permission_is_used(
        self, mock_db, regular_user, restricted_project
    ):
        """User with direct EDITOR permission gets EDITOR level."""
        # Mock: direct EDITOR permission exists
        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = PermissionLevel.EDITOR

        mock_team = MagicMock()
        mock_team.fetchall.return_value = []  # No teams

        mock_db.execute.side_effect = [mock_direct, mock_team]

        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(
            regular_user, restricted_project
        )

        assert level == PermissionLevel.EDITOR

    @pytest.mark.asyncio
    async def test_direct_owner_permission_is_used(
        self, mock_db, regular_user, restricted_project
    ):
        """User with direct OWNER permission gets OWNER level."""
        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = PermissionLevel.OWNER

        mock_team = MagicMock()
        mock_team.fetchall.return_value = []

        mock_db.execute.side_effect = [mock_direct, mock_team]

        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(
            regular_user, restricted_project
        )

        assert level == PermissionLevel.OWNER

    @pytest.mark.asyncio
    async def test_direct_permission_overrides_public_visibility(
        self, mock_db, regular_user, public_project
    ):
        """Direct EDITOR permission is higher than public VIEWER."""
        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = PermissionLevel.EDITOR

        mock_team = MagicMock()
        mock_team.fetchall.return_value = []

        mock_db.execute.side_effect = [mock_direct, mock_team]

        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(regular_user, public_project)

        # Should get EDITOR (higher than VIEWER from public)
        assert level == PermissionLevel.EDITOR


class TestTeamPermissions:
    """Tests for team-based permission resolution."""

    @pytest.mark.asyncio
    async def test_team_permission_grants_access(
        self, mock_db, regular_user, restricted_project
    ):
        """User in team with permission gets access via team."""
        team_id = uuid4()

        # Mock: no direct permission
        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = None

        # Mock: user is in one team
        mock_team_membership = MagicMock()
        mock_team_membership.fetchall.return_value = [(team_id,)]

        # Mock: that team has VIEWER permission on project
        mock_team_perm = MagicMock()
        mock_team_perm.fetchall.return_value = [(PermissionLevel.VIEWER,)]

        mock_db.execute.side_effect = [
            mock_direct,
            mock_team_membership,
            mock_team_perm,
        ]

        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(
            regular_user, restricted_project
        )

        assert level == PermissionLevel.VIEWER

    @pytest.mark.asyncio
    async def test_highest_team_permission_wins(
        self, mock_db, regular_user, restricted_project
    ):
        """When user is in multiple teams, highest permission wins."""
        team_id_1 = uuid4()
        team_id_2 = uuid4()

        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = None

        mock_team_membership = MagicMock()
        mock_team_membership.fetchall.return_value = [(team_id_1,), (team_id_2,)]

        # Team 1 has VIEWER, Team 2 has EDITOR
        mock_team_perm = MagicMock()
        mock_team_perm.fetchall.return_value = [
            (PermissionLevel.VIEWER,),
            (PermissionLevel.EDITOR,),
        ]

        mock_db.execute.side_effect = [
            mock_direct,
            mock_team_membership,
            mock_team_perm,
        ]

        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(
            regular_user, restricted_project
        )

        assert level == PermissionLevel.EDITOR  # Higher of the two

    @pytest.mark.asyncio
    async def test_direct_permission_wins_over_team(
        self, mock_db, regular_user, restricted_project
    ):
        """Direct OWNER permission wins over team EDITOR."""
        team_id = uuid4()

        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = PermissionLevel.OWNER

        mock_team_membership = MagicMock()
        mock_team_membership.fetchall.return_value = [(team_id,)]

        mock_team_perm = MagicMock()
        mock_team_perm.fetchall.return_value = [(PermissionLevel.EDITOR,)]

        mock_db.execute.side_effect = [
            mock_direct,
            mock_team_membership,
            mock_team_perm,
        ]

        service = PermissionService(mock_db)
        level = await service.get_user_permission_level(
            regular_user, restricted_project
        )

        assert level == PermissionLevel.OWNER


class TestCheckProjectAccess:
    """Tests for check_project_access method."""

    @pytest.mark.asyncio
    async def test_viewer_can_view_but_not_edit(
        self, mock_db, regular_user, restricted_project
    ):
        """User with VIEWER can view but not edit."""
        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = PermissionLevel.VIEWER

        mock_team = MagicMock()
        mock_team.fetchall.return_value = []

        mock_db.execute.side_effect = [mock_direct, mock_team]

        service = PermissionService(mock_db)

        # VIEWER check passes
        mock_db.execute.side_effect = [mock_direct, mock_team]
        assert (
            await service.check_project_access(
                regular_user, restricted_project, PermissionLevel.VIEWER
            )
            is True
        )

        # EDITOR check fails
        mock_db.execute.side_effect = [mock_direct, mock_team]
        assert (
            await service.check_project_access(
                regular_user, restricted_project, PermissionLevel.EDITOR
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_editor_can_view_and_edit_but_not_own(
        self, mock_db, regular_user, restricted_project
    ):
        """User with EDITOR can view and edit but not manage permissions."""
        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = PermissionLevel.EDITOR

        mock_team = MagicMock()
        mock_team.fetchall.return_value = []

        service = PermissionService(mock_db)

        # Reset side_effect for each call
        for level, expected in [
            (PermissionLevel.VIEWER, True),
            (PermissionLevel.EDITOR, True),
            (PermissionLevel.OWNER, False),
        ]:
            mock_db.execute.side_effect = [mock_direct, mock_team]
            result = await service.check_project_access(
                regular_user, restricted_project, level
            )
            assert (
                result is expected
            ), f"EDITOR should {'pass' if expected else 'fail'} {level}"

    @pytest.mark.asyncio
    async def test_no_access_returns_false(
        self, mock_db, regular_user, restricted_project
    ):
        """User with no access fails all checks."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        service = PermissionService(mock_db)

        for level in PermissionLevel:
            result = await service.check_project_access(
                regular_user, restricted_project, level
            )
            assert result is False


class TestGetAccessibleProjectIds:
    """Tests for get_accessible_project_ids method."""

    @pytest.mark.asyncio
    async def test_admin_returns_empty_set(self, mock_db, admin_user):
        """Admin returns empty set (signal to skip filtering)."""
        service = PermissionService(mock_db)
        result = await service.get_accessible_project_ids(admin_user)
        assert result == set()

    @pytest.mark.asyncio
    async def test_includes_public_projects_for_viewer_level(
        self, mock_db, regular_user
    ):
        """Public projects are included when minimum level is VIEWER."""
        public_project_id = uuid4()

        # Mock: public projects query
        mock_public = MagicMock()
        mock_public.fetchall.return_value = [(public_project_id,)]

        # Mock: no direct permissions
        mock_direct = MagicMock()
        mock_direct.fetchall.return_value = []

        # Mock: no teams
        mock_teams = MagicMock()
        mock_teams.fetchall.return_value = []

        mock_db.execute.side_effect = [mock_public, mock_direct, mock_teams]

        service = PermissionService(mock_db)
        result = await service.get_accessible_project_ids(regular_user)

        assert public_project_id in result

    @pytest.mark.asyncio
    async def test_combines_direct_and_team_permissions(self, mock_db, regular_user):
        """Result includes projects from both direct and team permissions."""
        direct_project_id = uuid4()
        team_project_id = uuid4()
        team_id = uuid4()

        # Mock: direct EDITOR permission on one project
        mock_direct = MagicMock()
        mock_direct.fetchall.return_value = [(direct_project_id,)]

        # Mock: user in one team
        mock_teams = MagicMock()
        mock_teams.fetchall.return_value = [(team_id,)]

        # Mock: team has EDITOR permission on another project
        mock_team_perms = MagicMock()
        mock_team_perms.fetchall.return_value = [(team_project_id,)]

        mock_db.execute.side_effect = [mock_direct, mock_teams, mock_team_perms]

        service = PermissionService(mock_db)
        result = await service.get_accessible_project_ids(
            regular_user, minimum_level=PermissionLevel.EDITOR
        )

        assert direct_project_id in result
        assert team_project_id in result


class TestCanManagePermissions:
    """Tests for can_manage_permissions method."""

    @pytest.mark.asyncio
    async def test_owner_can_manage_permissions(
        self, mock_db, regular_user, restricted_project
    ):
        """User with OWNER permission can manage permissions."""
        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = PermissionLevel.OWNER

        mock_team = MagicMock()
        mock_team.fetchall.return_value = []

        mock_db.execute.side_effect = [mock_direct, mock_team]

        service = PermissionService(mock_db)
        result = await service.can_manage_permissions(regular_user, restricted_project)

        assert result is True

    @pytest.mark.asyncio
    async def test_editor_cannot_manage_permissions(
        self, mock_db, regular_user, restricted_project
    ):
        """User with EDITOR permission cannot manage permissions."""
        mock_direct = MagicMock()
        mock_direct.scalar_one_or_none.return_value = PermissionLevel.EDITOR

        mock_team = MagicMock()
        mock_team.fetchall.return_value = []

        mock_db.execute.side_effect = [mock_direct, mock_team]

        service = PermissionService(mock_db)
        result = await service.can_manage_permissions(regular_user, restricted_project)

        assert result is False

    @pytest.mark.asyncio
    async def test_admin_can_manage_permissions(
        self, mock_db, admin_user, restricted_project
    ):
        """Admin can manage permissions on any project."""
        service = PermissionService(mock_db)
        result = await service.can_manage_permissions(admin_user, restricted_project)

        assert result is True


class TestResolveTeamPermissions:
    """Tests for resolve_team_permissions public method."""

    @pytest.mark.asyncio
    async def test_resolve_team_permissions_with_user_objects(
        self, mock_db, regular_user, restricted_project
    ):
        """resolve_team_permissions public method works with User/Project objects."""
        team_id = uuid4()

        # Mock: user is in one team
        mock_team_membership = MagicMock()
        mock_team_membership.fetchall.return_value = [(team_id,)]

        # Mock: that team has EDITOR permission on project
        mock_team_perm = MagicMock()
        mock_team_perm.fetchall.return_value = [(PermissionLevel.EDITOR,)]

        mock_db.execute.side_effect = [mock_team_membership, mock_team_perm]

        service = PermissionService(mock_db)
        level = await service.resolve_team_permissions(regular_user, restricted_project)

        assert level == PermissionLevel.EDITOR

    @pytest.mark.asyncio
    async def test_resolve_team_permissions_no_teams(
        self, mock_db, regular_user, restricted_project
    ):
        """resolve_team_permissions returns None when user has no teams."""
        mock_team_membership = MagicMock()
        mock_team_membership.fetchall.return_value = []

        mock_db.execute.side_effect = [mock_team_membership]

        service = PermissionService(mock_db)
        level = await service.resolve_team_permissions(regular_user, restricted_project)

        assert level is None
