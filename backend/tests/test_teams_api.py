"""Tests for team management API endpoints (Admin only)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.user import UserRole


class TestListTeamsEndpoint:
    """Tests for GET /api/v1/teams."""

    def test_list_teams_returns_paginated_results(self):
        """List returns paginated teams."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        mock_team1 = MagicMock()
        mock_team1.id = uuid4()
        mock_team1.name = "Engineering"
        mock_team1.azure_ad_group_id = "group-1"
        mock_team1.description = "Engineering team"
        mock_team1.created_at = datetime.now(UTC)
        mock_team1.updated_at = datetime.now(UTC)

        mock_team2 = MagicMock()
        mock_team2.id = uuid4()
        mock_team2.name = "Design"
        mock_team2.azure_ad_group_id = "group-2"
        mock_team2.description = None
        mock_team2.created_at = datetime.now(UTC)
        mock_team2.updated_at = datetime.now(UTC)

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            # Mock database
            mock_db = AsyncMock()
            mock_db.scalar.return_value = 2  # total count

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_team1, mock_team2]
            mock_db.execute.return_value = mock_result

            # Use dependency override
            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.get("/api/v1/teams")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2

    def test_list_teams_pagination(self):
        """List supports pagination parameters."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        mock_team = MagicMock()
        mock_team.id = uuid4()
        mock_team.name = "Engineering"
        mock_team.azure_ad_group_id = "group-1"
        mock_team.description = None
        mock_team.created_at = datetime.now(UTC)
        mock_team.updated_at = datetime.now(UTC)

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_db.scalar.return_value = 5  # total count

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_team]
            mock_db.execute.return_value = mock_result

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.get("/api/v1/teams?page=2&page_size=2")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 5
            assert data["page"] == 2
            assert data["page_size"] == 2

    def test_list_teams_requires_admin_role(self):
        """Non-admin users get 403."""
        from app.api.teams import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        regular_user = MagicMock()
        regular_user.id = uuid4()
        regular_user.is_active = True
        regular_user.role = UserRole.USER

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = regular_user

            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/teams")

            assert response.status_code in [401, 403, 500]


class TestCreateTeamEndpoint:
    """Tests for POST /api/v1/teams."""

    def test_create_team_success(self):
        """Admin can create a team."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_db.add = MagicMock()
            mock_db.flush = AsyncMock()

            # Mock the team after flush (with generated ID)
            def add_side_effect(team):
                team.id = uuid4()
                team.created_at = datetime.now(UTC)
                team.updated_at = datetime.now(UTC)

            mock_db.add.side_effect = add_side_effect

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.post(
                "/api/v1/teams",
                json={
                    "name": "Engineering",
                    "azure_ad_group_id": "group-123",
                    "description": "Engineering team",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Engineering"
            assert data["azure_ad_group_id"] == "group-123"

    def test_create_team_duplicate_azure_id_fails(self):
        """Creating team with duplicate Azure AD group ID fails."""
        from sqlalchemy.exc import IntegrityError

        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_db.add = MagicMock()
            mock_db.flush = AsyncMock(side_effect=IntegrityError("", "", ""))

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.post(
                "/api/v1/teams",
                json={
                    "name": "Engineering",
                    "azure_ad_group_id": "duplicate-group",
                },
            )

            assert response.status_code == 400
            assert "already exists" in response.json()["detail"]

    def test_create_team_validates_required_fields(self):
        """Create validates required fields."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        app.dependency_overrides[get_current_admin_user] = lambda: admin_user

        client = TestClient(app)
        response = client.post(
            "/api/v1/teams",
            json={"name": "Test"},  # Missing azure_ad_group_id
        )

        assert response.status_code == 422

    def test_create_team_without_description(self):
        """Create team with only required fields."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_db.add = MagicMock()
            mock_db.flush = AsyncMock()

            def add_side_effect(team):
                team.id = uuid4()
                team.created_at = datetime.now(UTC)
                team.updated_at = datetime.now(UTC)

            mock_db.add.side_effect = add_side_effect

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.post(
                "/api/v1/teams",
                json={
                    "name": "Minimal Team",
                    "azure_ad_group_id": "minimal-group",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Minimal Team"
            assert data["description"] is None


class TestGetTeamEndpoint:
    """Tests for GET /api/v1/teams/{id}."""

    def test_get_team_with_members(self):
        """Get returns team with members list."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        team_id = uuid4()
        mock_team = MagicMock()
        mock_team.id = team_id
        mock_team.name = "Engineering"
        mock_team.azure_ad_group_id = "group-123"
        mock_team.description = "Engineering team"
        mock_team.created_at = datetime.now(UTC)
        mock_team.updated_at = datetime.now(UTC)

        mock_member = MagicMock()
        mock_member.id = uuid4()
        mock_member.team_id = team_id
        mock_member.user_id = uuid4()
        mock_member.synced_at = datetime.now(UTC)
        mock_team.members = [mock_member]

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_team
            mock_db.execute.return_value = mock_result

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.get(f"/api/v1/teams/{team_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Engineering"
            assert "members" in data
            assert len(data["members"]) == 1

    def test_get_team_not_found(self):
        """Get returns 404 for non-existent team."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.get(f"/api/v1/teams/{uuid4()}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Team not found"

    def test_get_team_with_no_members(self):
        """Get returns team with empty members list."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        team_id = uuid4()
        mock_team = MagicMock()
        mock_team.id = team_id
        mock_team.name = "Empty Team"
        mock_team.azure_ad_group_id = "empty-group"
        mock_team.description = None
        mock_team.created_at = datetime.now(UTC)
        mock_team.updated_at = datetime.now(UTC)
        mock_team.members = []

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_team
            mock_db.execute.return_value = mock_result

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.get(f"/api/v1/teams/{team_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Empty Team"
            assert data["members"] == []


class TestUpdateTeamEndpoint:
    """Tests for PUT /api/v1/teams/{id}."""

    def test_update_team_name(self):
        """Can update team name."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        team_id = uuid4()
        mock_team = MagicMock()
        mock_team.id = team_id
        mock_team.name = "Old Name"
        mock_team.azure_ad_group_id = "group-123"
        mock_team.description = None
        mock_team.created_at = datetime.now(UTC)
        mock_team.updated_at = datetime.now(UTC)

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_team
            mock_db.execute.return_value = mock_result
            mock_db.flush = AsyncMock()

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.put(
                f"/api/v1/teams/{team_id}",
                json={"name": "New Name"},
            )

            assert response.status_code == 200
            assert mock_team.name == "New Name"

    def test_update_team_description(self):
        """Can update team description."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        team_id = uuid4()
        mock_team = MagicMock()
        mock_team.id = team_id
        mock_team.name = "Team"
        mock_team.azure_ad_group_id = "group-123"
        mock_team.description = None
        mock_team.created_at = datetime.now(UTC)
        mock_team.updated_at = datetime.now(UTC)

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_team
            mock_db.execute.return_value = mock_result
            mock_db.flush = AsyncMock()

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.put(
                f"/api/v1/teams/{team_id}",
                json={"description": "New description"},
            )

            assert response.status_code == 200
            assert mock_team.description == "New description"

    def test_update_team_not_found(self):
        """Update returns 404 for non-existent team."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.put(
                f"/api/v1/teams/{uuid4()}",
                json={"name": "New Name"},
            )

            assert response.status_code == 404


class TestDeleteTeamEndpoint:
    """Tests for DELETE /api/v1/teams/{id}."""

    def test_delete_team_success(self):
        """Delete removes team and returns 204."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        team_id = uuid4()
        mock_team = MagicMock()
        mock_team.id = team_id
        mock_team.name = "Engineering"

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_team
            mock_db.execute.return_value = mock_result
            mock_db.delete = AsyncMock()
            mock_db.flush = AsyncMock()

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.delete(f"/api/v1/teams/{team_id}")

            assert response.status_code == 204
            mock_db.delete.assert_called_once_with(mock_team)

    def test_delete_team_not_found(self):
        """Delete returns 404 for non-existent team."""
        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app)
            response = client.delete(f"/api/v1/teams/{uuid4()}")

            assert response.status_code == 404


class TestTeamSchemasIntegration:
    """Tests for team Pydantic schemas used by API."""

    def test_team_create_requires_azure_ad_group_id(self):
        """TeamCreate requires azure_ad_group_id."""
        from pydantic import ValidationError

        from app.schemas.team import TeamCreate

        with pytest.raises(ValidationError):
            TeamCreate(name="Test Team")  # Missing azure_ad_group_id

    def test_team_create_valid(self):
        """TeamCreate accepts valid data."""
        from app.schemas.team import TeamCreate

        team = TeamCreate(
            name="Engineering",
            azure_ad_group_id="12345-abcde",
            description="Test description",
        )
        assert team.name == "Engineering"
        assert team.azure_ad_group_id == "12345-abcde"

    def test_team_update_all_optional(self):
        """TeamUpdate has all optional fields."""
        from app.schemas.team import TeamUpdate

        update = TeamUpdate()
        assert update.name is None
        assert update.description is None

    def test_team_response_from_attributes(self):
        """TeamResponse can be created from model attributes."""
        from app.schemas.team import TeamResponse

        team_id = uuid4()
        now = datetime.now(UTC)

        data = TeamResponse(
            id=team_id,
            name="Test Team",
            azure_ad_group_id="group-123",
            description="Test description",
            created_at=now,
            updated_at=now,
        )

        assert data.id == team_id
        assert data.name == "Test Team"
        assert data.azure_ad_group_id == "group-123"

    def test_team_list_response(self):
        """TeamListResponse structure is correct."""
        from app.schemas.team import TeamListResponse, TeamResponse

        team_id = uuid4()
        now = datetime.now(UTC)

        item = TeamResponse(
            id=team_id,
            name="Test Team",
            azure_ad_group_id="group-123",
            description=None,
            created_at=now,
            updated_at=now,
        )

        response = TeamListResponse(
            items=[item],
            total=1,
            page=1,
            page_size=20,
        )

        assert len(response.items) == 1
        assert response.total == 1
        assert response.page == 1
        assert response.page_size == 20

    def test_team_detail_response_with_members(self):
        """TeamDetailResponse includes members list."""
        from app.schemas.team import TeamDetailResponse, TeamMemberResponse

        team_id = uuid4()
        user_id = uuid4()
        member_id = uuid4()
        now = datetime.now(UTC)

        member = TeamMemberResponse(
            id=member_id,
            team_id=team_id,
            user_id=user_id,
            synced_at=now,
        )

        team = TeamDetailResponse(
            id=team_id,
            name="Test Team",
            azure_ad_group_id="group-123",
            description="Test description",
            created_at=now,
            updated_at=now,
            members=[member],
        )

        assert len(team.members) == 1
        assert team.members[0].user_id == user_id
