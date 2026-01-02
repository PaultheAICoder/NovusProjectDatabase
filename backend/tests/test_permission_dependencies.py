"""Tests for permission-based route protection dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.permissions import (
    get_project_with_permission,
    require_project_editor,
    require_project_owner,
    require_project_viewer,
)
from app.models.project import Project
from app.models.project_permission import (
    PermissionLevel,
    ProjectVisibility,
)
from app.models.user import User, UserRole


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


class TestGetProjectWithPermission:
    """Tests for get_project_with_permission factory."""

    @pytest.mark.asyncio
    async def test_returns_project_when_access_granted(
        self, mock_db, regular_user, public_project
    ):
        """Dependency returns project when user has sufficient access."""
        # Mock project lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = public_project
        mock_db.execute.return_value = mock_result

        # Create dependency with VIEWER level
        dependency = get_project_with_permission(PermissionLevel.VIEWER)

        with patch("app.core.permissions.PermissionService") as mock_perm_service_class:
            mock_perm_service = MagicMock()
            mock_perm_service.check_project_access = AsyncMock(return_value=True)
            mock_perm_service_class.return_value = mock_perm_service

            result = await dependency(
                project_id=public_project.id,
                db=mock_db,
                current_user=regular_user,
            )

            assert result == public_project
            mock_perm_service.check_project_access.assert_awaited_once_with(
                regular_user, public_project, PermissionLevel.VIEWER
            )

    @pytest.mark.asyncio
    async def test_raises_404_when_project_not_found(self, mock_db, regular_user):
        """Dependency raises 404 when project does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        dependency = get_project_with_permission(PermissionLevel.VIEWER)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(
                project_id=uuid4(),
                db=mock_db,
                current_user=regular_user,
            )

        assert exc_info.value.status_code == 404
        assert "Project not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_403_when_access_denied(
        self, mock_db, regular_user, restricted_project
    ):
        """Dependency raises 403 when user lacks required permission."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = restricted_project
        mock_db.execute.return_value = mock_result

        dependency = get_project_with_permission(PermissionLevel.EDITOR)

        with patch("app.core.permissions.PermissionService") as mock_perm_service_class:
            mock_perm_service = MagicMock()
            mock_perm_service.check_project_access = AsyncMock(return_value=False)
            mock_perm_service_class.return_value = mock_perm_service

            with pytest.raises(HTTPException) as exc_info:
                await dependency(
                    project_id=restricted_project.id,
                    db=mock_db,
                    current_user=regular_user,
                )

            assert exc_info.value.status_code == 403
            assert "Insufficient permissions" in exc_info.value.detail
            assert "editor" in exc_info.value.detail.lower()


class TestPreBuiltDependencies:
    """Tests for pre-built convenience dependencies."""

    def test_require_project_viewer_exists(self):
        """require_project_viewer is a callable dependency."""
        assert callable(require_project_viewer)

    def test_require_project_editor_exists(self):
        """require_project_editor is a callable dependency."""
        assert callable(require_project_editor)

    def test_require_project_owner_exists(self):
        """require_project_owner is a callable dependency."""
        assert callable(require_project_owner)


class TestPermissionLevelIntegration:
    """Tests for permission level hierarchy."""

    @pytest.mark.asyncio
    async def test_viewer_level_grants_viewer_access(
        self, mock_db, regular_user, public_project
    ):
        """User with VIEWER level can access VIEWER-protected routes."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = public_project
        mock_db.execute.return_value = mock_result

        with patch("app.core.permissions.PermissionService") as mock_perm_service_class:
            mock_perm_service = MagicMock()
            mock_perm_service.check_project_access = AsyncMock(return_value=True)
            mock_perm_service_class.return_value = mock_perm_service

            result = await require_project_viewer(
                project_id=public_project.id,
                db=mock_db,
                current_user=regular_user,
            )

            assert result == public_project

    @pytest.mark.asyncio
    async def test_admin_always_has_access(
        self, mock_db, admin_user, restricted_project
    ):
        """Admin users always get access regardless of explicit permissions."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = restricted_project
        mock_db.execute.return_value = mock_result

        with patch("app.core.permissions.PermissionService") as mock_perm_service_class:
            mock_perm_service = MagicMock()
            # PermissionService.check_project_access returns True for admins
            mock_perm_service.check_project_access = AsyncMock(return_value=True)
            mock_perm_service_class.return_value = mock_perm_service

            result = await require_project_owner(
                project_id=restricted_project.id,
                db=mock_db,
                current_user=admin_user,
            )

            assert result == restricted_project


class TestErrorMessages:
    """Tests for clear error messages."""

    @pytest.mark.asyncio
    async def test_403_includes_required_level_viewer(
        self, mock_db, regular_user, restricted_project
    ):
        """403 error message includes 'viewer' for viewer requirement."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = restricted_project
        mock_db.execute.return_value = mock_result

        with patch("app.core.permissions.PermissionService") as mock_perm_service_class:
            mock_perm_service = MagicMock()
            mock_perm_service.check_project_access = AsyncMock(return_value=False)
            mock_perm_service_class.return_value = mock_perm_service

            with pytest.raises(HTTPException) as exc_info:
                await require_project_viewer(
                    project_id=restricted_project.id,
                    db=mock_db,
                    current_user=regular_user,
                )

            assert "viewer" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_403_includes_required_level_editor(
        self, mock_db, regular_user, restricted_project
    ):
        """403 error message includes 'editor' for editor requirement."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = restricted_project
        mock_db.execute.return_value = mock_result

        with patch("app.core.permissions.PermissionService") as mock_perm_service_class:
            mock_perm_service = MagicMock()
            mock_perm_service.check_project_access = AsyncMock(return_value=False)
            mock_perm_service_class.return_value = mock_perm_service

            with pytest.raises(HTTPException) as exc_info:
                await require_project_editor(
                    project_id=restricted_project.id,
                    db=mock_db,
                    current_user=regular_user,
                )

            assert "editor" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_403_includes_required_level_owner(
        self, mock_db, regular_user, restricted_project
    ):
        """403 error message includes 'owner' for owner requirement."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = restricted_project
        mock_db.execute.return_value = mock_result

        with patch("app.core.permissions.PermissionService") as mock_perm_service_class:
            mock_perm_service = MagicMock()
            mock_perm_service.check_project_access = AsyncMock(return_value=False)
            mock_perm_service_class.return_value = mock_perm_service

            with pytest.raises(HTTPException) as exc_info:
                await require_project_owner(
                    project_id=restricted_project.id,
                    db=mock_db,
                    current_user=regular_user,
                )

            assert "owner" in exc_info.value.detail.lower()
