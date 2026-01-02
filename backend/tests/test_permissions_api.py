"""Tests for project permission API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.project_permission import PermissionLevel, ProjectVisibility
from app.models.user import UserRole


class TestListPermissionsEndpoint:
    """Tests for GET /api/v1/projects/{id}/permissions."""

    def test_list_permissions_returns_all(self):
        """List returns all permissions for a project."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        # Mock project
        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.visibility = ProjectVisibility.RESTRICTED

        # Mock permissions
        mock_perm1 = MagicMock()
        mock_perm1.id = uuid4()
        mock_perm1.project_id = project_id
        mock_perm1.user_id = uuid4()
        mock_perm1.team_id = None
        mock_perm1.permission_level = PermissionLevel.EDITOR
        mock_perm1.granted_by = owner_user.id
        mock_perm1.granted_at = datetime.now(UTC)

        mock_perm2 = MagicMock()
        mock_perm2.id = uuid4()
        mock_perm2.project_id = project_id
        mock_perm2.user_id = None
        mock_perm2.team_id = uuid4()
        mock_perm2.permission_level = PermissionLevel.VIEWER
        mock_perm2.granted_by = owner_user.id
        mock_perm2.granted_at = datetime.now(UTC)

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            # Mock database
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_perm1, mock_perm2]
            mock_db.execute.return_value = mock_result

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.get(f"/api/v1/projects/{project_id}/permissions")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2

    def test_list_permissions_empty_project(self):
        """List returns empty for project with no permissions."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute.return_value = mock_result

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.get(f"/api/v1/projects/{project_id}/permissions")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["items"] == []


class TestCreatePermissionEndpoint:
    """Tests for POST /api/v1/projects/{id}/permissions."""

    def test_create_user_permission_success(self):
        """Owner can grant user permission."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        target_user_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        mock_target_user = MagicMock()
        mock_target_user.id = target_user_id

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()

            # Mock user lookup - returns user
            async def scalar_side_effect(query):
                query_str = str(query)
                if "users" in query_str:
                    return mock_target_user
                return None

            mock_db.scalar = AsyncMock(side_effect=scalar_side_effect)
            mock_db.add = MagicMock()
            mock_db.flush = AsyncMock()
            mock_db.refresh = AsyncMock()

            def add_side_effect(perm):
                perm.id = uuid4()
                perm.granted_at = datetime.now(UTC)

            mock_db.add.side_effect = add_side_effect

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.post(
                f"/api/v1/projects/{project_id}/permissions",
                json={
                    "user_id": str(target_user_id),
                    "permission_level": "editor",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["user_id"] == str(target_user_id)
            assert data["permission_level"] == "editor"

    def test_create_team_permission_success(self):
        """Owner can grant team permission."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        team_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        mock_team = MagicMock()
        mock_team.id = team_id

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()

            async def scalar_side_effect(query):
                query_str = str(query)
                if "teams" in query_str:
                    return mock_team
                return None

            mock_db.scalar = AsyncMock(side_effect=scalar_side_effect)
            mock_db.add = MagicMock()
            mock_db.flush = AsyncMock()
            mock_db.refresh = AsyncMock()

            def add_side_effect(perm):
                perm.id = uuid4()
                perm.granted_at = datetime.now(UTC)

            mock_db.add.side_effect = add_side_effect

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.post(
                f"/api/v1/projects/{project_id}/permissions",
                json={
                    "team_id": str(team_id),
                    "permission_level": "viewer",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["team_id"] == str(team_id)
            assert data["permission_level"] == "viewer"

    def test_create_duplicate_user_permission_fails(self):
        """Cannot grant duplicate user permission (409)."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        target_user_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        mock_target_user = MagicMock()
        mock_target_user.id = target_user_id

        existing_perm = MagicMock()
        existing_perm.id = uuid4()

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            call_count = 0

            async def scalar_side_effect(query):  # noqa: ARG001
                nonlocal call_count
                call_count += 1
                # First call: user lookup
                if call_count == 1:
                    return mock_target_user
                # Second call: existing permission check
                if call_count == 2:
                    return existing_perm
                return None

            mock_db.scalar = AsyncMock(side_effect=scalar_side_effect)

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.post(
                f"/api/v1/projects/{project_id}/permissions",
                json={
                    "user_id": str(target_user_id),
                    "permission_level": "editor",
                },
            )

            assert response.status_code == 409
            assert "already has permission" in response.json()["detail"]

    def test_create_permission_invalid_user(self):
        """Cannot grant to non-existent user (400)."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            mock_db.scalar = AsyncMock(return_value=None)  # User not found

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.post(
                f"/api/v1/projects/{project_id}/permissions",
                json={
                    "user_id": str(uuid4()),
                    "permission_level": "editor",
                },
            )

            assert response.status_code == 400
            assert "User not found" in response.json()["detail"]

    def test_create_permission_invalid_team(self):
        """Cannot grant to non-existent team (400)."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            mock_db.scalar = AsyncMock(return_value=None)  # Team not found

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.post(
                f"/api/v1/projects/{project_id}/permissions",
                json={
                    "team_id": str(uuid4()),
                    "permission_level": "viewer",
                },
            )

            assert response.status_code == 400
            assert "Team not found" in response.json()["detail"]


class TestUpdatePermissionEndpoint:
    """Tests for PUT /api/v1/projects/{id}/permissions/{perm_id}."""

    def test_update_permission_level(self):
        """Owner can update permission level."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        permission_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        mock_permission = MagicMock()
        mock_permission.id = permission_id
        mock_permission.project_id = project_id
        mock_permission.user_id = uuid4()
        mock_permission.team_id = None
        mock_permission.permission_level = PermissionLevel.VIEWER
        mock_permission.granted_by = owner_user.id
        mock_permission.granted_at = datetime.now(UTC)

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            mock_db.scalar = AsyncMock(return_value=mock_permission)
            mock_db.flush = AsyncMock()
            mock_db.refresh = AsyncMock()

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.put(
                f"/api/v1/projects/{project_id}/permissions/{permission_id}",
                json={"permission_level": "editor"},
            )

            assert response.status_code == 200

    def test_update_not_found(self):
        """Returns 404 for non-existent permission."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        permission_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            mock_db.scalar = AsyncMock(return_value=None)

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.put(
                f"/api/v1/projects/{project_id}/permissions/{permission_id}",
                json={"permission_level": "editor"},
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Permission not found"

    def test_update_prevents_last_owner_demotion(self):
        """Cannot demote last owner (400)."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        permission_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        mock_permission = MagicMock()
        mock_permission.id = permission_id
        mock_permission.project_id = project_id
        mock_permission.user_id = uuid4()
        mock_permission.team_id = None
        mock_permission.permission_level = PermissionLevel.OWNER  # Current is OWNER
        mock_permission.granted_by = owner_user.id
        mock_permission.granted_at = datetime.now(UTC)

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            call_count = 0

            async def scalar_side_effect(query):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return mock_permission  # Permission lookup
                return 1  # Owner count

            mock_db.scalar = AsyncMock(side_effect=scalar_side_effect)

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.put(
                f"/api/v1/projects/{project_id}/permissions/{permission_id}",
                json={"permission_level": "editor"},  # Demoting from OWNER
            )

            assert response.status_code == 400
            assert "Cannot demote the last owner" in response.json()["detail"]


class TestDeletePermissionEndpoint:
    """Tests for DELETE /api/v1/projects/{id}/permissions/{perm_id}."""

    def test_delete_permission_success(self):
        """Owner can revoke permission."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        permission_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        mock_permission = MagicMock()
        mock_permission.id = permission_id
        mock_permission.project_id = project_id
        mock_permission.user_id = uuid4()
        mock_permission.team_id = None
        mock_permission.permission_level = PermissionLevel.EDITOR  # Not owner
        mock_permission.granted_by = owner_user.id

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            mock_db.scalar = AsyncMock(return_value=mock_permission)
            mock_db.delete = AsyncMock()
            mock_db.flush = AsyncMock()
            mock_db.refresh = AsyncMock()

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.delete(
                f"/api/v1/projects/{project_id}/permissions/{permission_id}"
            )

            assert response.status_code == 204
            mock_db.delete.assert_called_once_with(mock_permission)

    def test_delete_not_found(self):
        """Returns 404 for non-existent permission."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            mock_db.scalar = AsyncMock(return_value=None)

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.delete(
                f"/api/v1/projects/{project_id}/permissions/{uuid4()}"
            )

            assert response.status_code == 404

    def test_delete_prevents_last_owner_removal(self):
        """Cannot remove last owner (400)."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        permission_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id

        mock_permission = MagicMock()
        mock_permission.id = permission_id
        mock_permission.project_id = project_id
        mock_permission.user_id = uuid4()
        mock_permission.team_id = None
        mock_permission.permission_level = PermissionLevel.OWNER

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            call_count = 0

            async def scalar_side_effect(query):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return mock_permission
                return 1  # Only one owner

            mock_db.scalar = AsyncMock(side_effect=scalar_side_effect)

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.delete(
                f"/api/v1/projects/{project_id}/permissions/{permission_id}"
            )

            assert response.status_code == 400
            assert "Cannot remove the last owner" in response.json()["detail"]


class TestVisibilityEndpoint:
    """Tests for PUT /api/v1/projects/{id}/visibility."""

    def test_change_to_restricted(self):
        """Owner can change visibility to restricted."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.visibility = ProjectVisibility.PUBLIC

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            mock_db.flush = AsyncMock()
            mock_db.refresh = AsyncMock()

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.put(
                f"/api/v1/projects/{project_id}/visibility",
                json={"visibility": "restricted"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["visibility"] == "restricted"
            assert "Visibility changed" in data["message"]

    def test_change_to_public(self):
        """Owner can change visibility to public."""
        from app.api.project_permissions import router
        from app.core.permissions import require_project_owner
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        project_id = uuid4()
        owner_user = MagicMock()
        owner_user.id = uuid4()
        owner_user.is_active = True
        owner_user.role = UserRole.ADMIN

        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.visibility = ProjectVisibility.RESTRICTED

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = owner_user
            app.dependency_overrides[require_project_owner] = lambda: mock_project

            mock_db = AsyncMock()
            mock_db.flush = AsyncMock()
            mock_db.refresh = AsyncMock()

            from app.core.auth import get_current_active_user

            app.dependency_overrides[get_db] = lambda: mock_db
            app.dependency_overrides[get_current_active_user] = lambda: owner_user

            client = TestClient(app)
            response = client.put(
                f"/api/v1/projects/{project_id}/visibility",
                json={"visibility": "public"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["visibility"] == "public"


class TestSchemaValidation:
    """Tests for permission Pydantic schemas."""

    def test_create_requires_user_or_team(self):
        """ProjectPermissionCreate requires user_id or team_id."""
        from pydantic import ValidationError

        from app.schemas.project_permission import ProjectPermissionCreate

        with pytest.raises(ValidationError) as exc_info:
            ProjectPermissionCreate(permission_level=PermissionLevel.EDITOR)

        assert "Either user_id or team_id must be provided" in str(exc_info.value)

    def test_create_rejects_both_user_and_team(self):
        """ProjectPermissionCreate rejects both user_id and team_id."""
        from pydantic import ValidationError

        from app.schemas.project_permission import ProjectPermissionCreate

        with pytest.raises(ValidationError) as exc_info:
            ProjectPermissionCreate(
                user_id=uuid4(),
                team_id=uuid4(),
                permission_level=PermissionLevel.EDITOR,
            )

        assert "Only one of user_id or team_id can be provided" in str(exc_info.value)

    def test_create_valid_user_permission(self):
        """ProjectPermissionCreate accepts valid user permission."""
        from app.schemas.project_permission import ProjectPermissionCreate

        perm = ProjectPermissionCreate(
            user_id=uuid4(),
            permission_level=PermissionLevel.EDITOR,
        )
        assert perm.user_id is not None
        assert perm.team_id is None

    def test_create_valid_team_permission(self):
        """ProjectPermissionCreate accepts valid team permission."""
        from app.schemas.project_permission import ProjectPermissionCreate

        perm = ProjectPermissionCreate(
            team_id=uuid4(),
            permission_level=PermissionLevel.VIEWER,
        )
        assert perm.team_id is not None
        assert perm.user_id is None

    def test_update_requires_permission_level(self):
        """ProjectPermissionUpdate requires permission_level."""
        from pydantic import ValidationError

        from app.schemas.project_permission import ProjectPermissionUpdate

        with pytest.raises(ValidationError):
            ProjectPermissionUpdate()  # type: ignore[call-arg]

    def test_update_valid(self):
        """ProjectPermissionUpdate accepts valid data."""
        from app.schemas.project_permission import ProjectPermissionUpdate

        update = ProjectPermissionUpdate(permission_level=PermissionLevel.OWNER)
        assert update.permission_level == PermissionLevel.OWNER

    def test_visibility_update_valid(self):
        """ProjectVisibilityUpdate accepts valid visibility."""
        from app.schemas.project_permission import ProjectVisibilityUpdate

        update = ProjectVisibilityUpdate(visibility=ProjectVisibility.RESTRICTED)
        assert update.visibility == ProjectVisibility.RESTRICTED

    def test_permission_response(self):
        """ProjectPermissionResponse includes all fields."""
        from app.schemas.project_permission import ProjectPermissionResponse

        perm_id = uuid4()
        project_id = uuid4()
        user_id = uuid4()
        granted_by = uuid4()
        now = datetime.now(UTC)

        response = ProjectPermissionResponse(
            id=perm_id,
            project_id=project_id,
            user_id=user_id,
            team_id=None,
            permission_level=PermissionLevel.EDITOR,
            granted_by=granted_by,
            granted_at=now,
        )

        assert response.id == perm_id
        assert response.project_id == project_id
        assert response.user_id == user_id
        assert response.team_id is None
        assert response.permission_level == PermissionLevel.EDITOR

    def test_permission_list_response(self):
        """ProjectPermissionListResponse structure is correct."""
        from app.schemas.project_permission import (
            ProjectPermissionListResponse,
            ProjectPermissionResponse,
        )

        perm_id = uuid4()
        project_id = uuid4()
        now = datetime.now(UTC)

        item = ProjectPermissionResponse(
            id=perm_id,
            project_id=project_id,
            user_id=uuid4(),
            team_id=None,
            permission_level=PermissionLevel.VIEWER,
            granted_by=uuid4(),
            granted_at=now,
        )

        response = ProjectPermissionListResponse(
            items=[item],
            total=1,
        )

        assert len(response.items) == 1
        assert response.total == 1
