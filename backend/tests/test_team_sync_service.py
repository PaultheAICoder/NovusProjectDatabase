"""Tests for TeamSyncService with mocked Azure AD Graph API."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.user import UserRole


class TestTeamSyncServiceConfiguration:
    """Tests for TeamSyncService configuration checks."""

    def test_is_configured_returns_true_when_all_set(self):
        """is_configured returns True when Azure AD credentials are set."""
        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = "secret"

            from app.services.team_sync_service import TeamSyncService

            service = TeamSyncService()
            assert service.is_configured() is True

    def test_is_configured_returns_false_when_tenant_missing(self):
        """is_configured returns False when tenant ID is missing."""
        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = ""
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = "secret"

            from app.services.team_sync_service import TeamSyncService

            service = TeamSyncService()
            assert service.is_configured() is False

    def test_is_configured_returns_false_when_client_id_missing(self):
        """is_configured returns False when client ID is missing."""
        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = ""
            mock_settings.return_value.azure_ad_client_secret = "secret"

            from app.services.team_sync_service import TeamSyncService

            service = TeamSyncService()
            assert service.is_configured() is False

    def test_is_configured_returns_false_when_client_secret_missing(self):
        """is_configured returns False when client secret is missing."""
        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = ""

            from app.services.team_sync_service import TeamSyncService

            service = TeamSyncService()
            assert service.is_configured() is False

    def test_is_configured_returns_false_when_all_missing(self):
        """is_configured returns False when all credentials are missing."""
        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = ""
            mock_settings.return_value.azure_ad_client_id = ""
            mock_settings.return_value.azure_ad_client_secret = ""

            from app.services.team_sync_service import TeamSyncService

            service = TeamSyncService()
            assert service.is_configured() is False

    def test_get_status_shows_configuration_status(self):
        """get_status returns configuration status."""
        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = "secret"

            from app.services.team_sync_service import TeamSyncService

            service = TeamSyncService()
            status = service.get_status()

            assert status["configured"] is True
            assert status["tenant_id"] is True
            assert status["client_id"] is True
            assert status["client_secret"] is True


class TestTeamSyncServiceGetClient:
    """Tests for _get_client method."""

    def test_get_client_returns_none_when_not_configured(self):
        """_get_client returns None when not configured."""
        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = ""
            mock_settings.return_value.azure_ad_client_id = ""
            mock_settings.return_value.azure_ad_client_secret = ""

            from app.services.team_sync_service import TeamSyncService

            service = TeamSyncService()
            client = service._get_client()
            assert client is None

    def test_get_client_creates_client_when_configured(self):
        """_get_client creates GraphServiceClient when configured."""
        with (
            patch("app.services.team_sync_service.get_settings") as mock_settings,
            patch(
                "app.services.team_sync_service.ClientSecretCredential"
            ) as mock_credential,
            patch(
                "app.services.team_sync_service.GraphServiceClient"
            ) as mock_graph_client,
        ):
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = "secret"

            from app.services.team_sync_service import TeamSyncService

            service = TeamSyncService()
            client = service._get_client()

            mock_credential.assert_called_once_with(
                tenant_id="tenant-id",
                client_id="client-id",
                client_secret="secret",
            )
            mock_graph_client.assert_called_once()
            assert client is not None


class TestTeamSyncServiceSyncTeam:
    """Tests for sync_team method."""

    @pytest.mark.asyncio
    async def test_sync_team_adds_new_members(self):
        """sync_team adds new members from AD group."""
        from app.services.team_sync_service import TeamSyncService

        # Create mock team
        team_id = uuid4()
        mock_team = MagicMock()
        mock_team.id = team_id
        mock_team.name = "Engineering"
        mock_team.azure_ad_group_id = "ad-group-123"

        # Create mock users
        user1_id = uuid4()
        user2_id = uuid4()

        mock_user1 = MagicMock()
        mock_user1.id = user1_id
        mock_user1.azure_id = "ad-user-1"

        mock_user2 = MagicMock()
        mock_user2.id = user2_id
        mock_user2.azure_id = "ad-user-2"

        # Mock db session
        mock_db = AsyncMock()

        # First execute returns empty existing members
        mock_existing_result = MagicMock()
        mock_existing_result.scalars.return_value.all.return_value = []

        # Second execute returns users matching AD OIDs
        mock_users_result = MagicMock()
        mock_users_result.scalars.return_value.all.return_value = [
            mock_user1,
            mock_user2,
        ]

        mock_db.execute.side_effect = [mock_existing_result, mock_users_result]
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        with (
            patch("app.services.team_sync_service.get_settings") as mock_settings,
            patch.object(TeamSyncService, "_get_client") as mock_get_client,
            patch.object(
                TeamSyncService, "_fetch_group_members_with_retry"
            ) as mock_fetch,
        ):
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = "secret"

            mock_get_client.return_value = MagicMock()
            mock_fetch.return_value = ["ad-user-1", "ad-user-2"]

            service = TeamSyncService()
            result = await service.sync_team(mock_db, mock_team)

            assert result.members_added == 2
            assert result.members_removed == 0
            assert result.members_unchanged == 0
            assert len(result.errors) == 0
            assert mock_db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_team_removes_departed_members(self):
        """sync_team removes members no longer in AD group."""
        from app.services.team_sync_service import TeamSyncService

        # Create mock team
        team_id = uuid4()
        mock_team = MagicMock()
        mock_team.id = team_id
        mock_team.name = "Engineering"
        mock_team.azure_ad_group_id = "ad-group-123"

        # Create mock existing member (to be removed)
        user1_id = uuid4()
        mock_existing_member = MagicMock()
        mock_existing_member.team_id = team_id
        mock_existing_member.user_id = user1_id

        # Mock db session
        mock_db = AsyncMock()

        # First execute returns existing member
        mock_existing_result = MagicMock()
        mock_existing_result.scalars.return_value.all.return_value = [
            mock_existing_member
        ]

        # Second execute returns no users (AD group is now empty)
        mock_users_result = MagicMock()
        mock_users_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_existing_result, mock_users_result]
        mock_db.flush = AsyncMock()

        with (
            patch("app.services.team_sync_service.get_settings") as mock_settings,
            patch.object(TeamSyncService, "_get_client") as mock_get_client,
            patch.object(
                TeamSyncService, "_fetch_group_members_with_retry"
            ) as mock_fetch,
        ):
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = "secret"

            mock_get_client.return_value = MagicMock()
            mock_fetch.return_value = []  # AD group has no members

            service = TeamSyncService()
            result = await service.sync_team(mock_db, mock_team)

            assert result.members_removed == 1
            assert result.members_added == 0
            assert result.members_unchanged == 0
            assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_sync_team_handles_missing_azure_ad_group_id(self):
        """sync_team handles team without Azure AD group ID."""
        from app.services.team_sync_service import TeamSyncService

        mock_team = MagicMock()
        mock_team.id = uuid4()
        mock_team.name = "Test Team"
        mock_team.azure_ad_group_id = None

        mock_db = AsyncMock()

        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = "secret"

            service = TeamSyncService()
            result = await service.sync_team(mock_db, mock_team)

            assert "Team has no Azure AD group ID configured" in result.errors

    @pytest.mark.asyncio
    async def test_sync_team_handles_not_configured(self):
        """sync_team handles Azure AD not configured."""
        from app.services.team_sync_service import TeamSyncService

        mock_team = MagicMock()
        mock_team.id = uuid4()
        mock_team.name = "Test Team"
        mock_team.azure_ad_group_id = "ad-group-123"

        mock_db = AsyncMock()

        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = ""
            mock_settings.return_value.azure_ad_client_id = ""
            mock_settings.return_value.azure_ad_client_secret = ""

            service = TeamSyncService()
            result = await service.sync_team(mock_db, mock_team)

            assert "Azure AD not configured" in result.errors


class TestTeamSyncServiceSyncAllTeams:
    """Tests for sync_all_teams method."""

    @pytest.mark.asyncio
    async def test_sync_all_teams_processes_all(self):
        """sync_all_teams processes all teams."""
        from app.services.team_sync_service import TeamSyncResult, TeamSyncService

        mock_team1 = MagicMock()
        mock_team1.id = uuid4()
        mock_team1.name = "Team 1"

        mock_team2 = MagicMock()
        mock_team2.id = uuid4()
        mock_team2.name = "Team 2"

        with (
            patch("app.services.team_sync_service.get_settings") as mock_settings,
            patch(
                "app.services.team_sync_service.async_session_maker"
            ) as mock_session_maker,
            patch.object(TeamSyncService, "sync_team") as mock_sync_team,
        ):
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = "secret"

            # Mock async context manager for session
            mock_session = AsyncMock()
            mock_teams_result = MagicMock()
            mock_teams_result.scalars.return_value.all.return_value = [
                mock_team1,
                mock_team2,
            ]
            mock_session.execute.return_value = mock_teams_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            mock_session_maker.return_value = mock_session

            # Mock sync_team to return successful results
            mock_sync_team.side_effect = [
                TeamSyncResult(
                    team_id=mock_team1.id,
                    team_name="Team 1",
                    members_added=2,
                    members_removed=0,
                    members_unchanged=3,
                ),
                TeamSyncResult(
                    team_id=mock_team2.id,
                    team_name="Team 2",
                    members_added=1,
                    members_removed=1,
                    members_unchanged=2,
                ),
            ]

            service = TeamSyncService()
            result = await service.sync_all_teams()

            assert result["status"] == "success"
            assert result["teams_processed"] == 2
            assert result["teams_succeeded"] == 2
            assert result["teams_failed"] == 0
            assert result["total_members_added"] == 3
            assert result["total_members_removed"] == 1

    @pytest.mark.asyncio
    async def test_sync_all_teams_isolates_errors(self):
        """sync_all_teams continues when one team fails."""
        from app.services.team_sync_service import TeamSyncResult, TeamSyncService

        mock_team1 = MagicMock()
        mock_team1.id = uuid4()
        mock_team1.name = "Team 1"

        mock_team2 = MagicMock()
        mock_team2.id = uuid4()
        mock_team2.name = "Team 2"

        with (
            patch("app.services.team_sync_service.get_settings") as mock_settings,
            patch(
                "app.services.team_sync_service.async_session_maker"
            ) as mock_session_maker,
            patch.object(TeamSyncService, "sync_team") as mock_sync_team,
        ):
            mock_settings.return_value.azure_ad_tenant_id = "tenant-id"
            mock_settings.return_value.azure_ad_client_id = "client-id"
            mock_settings.return_value.azure_ad_client_secret = "secret"

            mock_session = AsyncMock()
            mock_teams_result = MagicMock()
            mock_teams_result.scalars.return_value.all.return_value = [
                mock_team1,
                mock_team2,
            ]
            mock_session.execute.return_value = mock_teams_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            mock_session_maker.return_value = mock_session

            # First team fails, second succeeds
            mock_sync_team.side_effect = [
                TeamSyncResult(
                    team_id=mock_team1.id,
                    team_name="Team 1",
                    errors=["Graph API error"],
                ),
                TeamSyncResult(
                    team_id=mock_team2.id,
                    team_name="Team 2",
                    members_added=1,
                ),
            ]

            service = TeamSyncService()
            result = await service.sync_all_teams()

            assert result["status"] == "partial"
            assert result["teams_processed"] == 2
            assert result["teams_succeeded"] == 1
            assert result["teams_failed"] == 1
            assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_sync_all_teams_returns_skipped_when_not_configured(self):
        """sync_all_teams returns skipped status when not configured."""
        from app.services.team_sync_service import TeamSyncService

        with patch("app.services.team_sync_service.get_settings") as mock_settings:
            mock_settings.return_value.azure_ad_tenant_id = ""
            mock_settings.return_value.azure_ad_client_id = ""
            mock_settings.return_value.azure_ad_client_secret = ""

            service = TeamSyncService()
            result = await service.sync_all_teams()

            assert result["status"] == "skipped"
            assert result["reason"] == "Azure AD not configured"
            assert result["teams_processed"] == 0


class TestTeamSyncEndpoint:
    """Tests for POST /teams/{id}/sync endpoint."""

    def test_sync_team_endpoint_success(self):
        """Manual sync endpoint works for admin."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.teams import router
        from app.core.auth import get_current_admin_user
        from app.database import get_db
        from app.services.team_sync_service import TeamSyncResult

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
        mock_team.azure_ad_group_id = "ad-group-123"

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.api.teams.TeamSyncService") as mock_service_class,
        ):
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_team
            mock_db.execute.return_value = mock_result
            mock_db.commit = AsyncMock()

            app.dependency_overrides[get_db] = lambda: mock_db

            mock_service = MagicMock()
            mock_service.is_configured.return_value = True
            mock_service.sync_team = AsyncMock(
                return_value=TeamSyncResult(
                    team_id=team_id,
                    team_name="Engineering",
                    members_added=2,
                    members_removed=0,
                    members_unchanged=3,
                )
            )
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.post(f"/api/v1/teams/{team_id}/sync")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["members_added"] == 2
            assert data["members_removed"] == 0
            assert data["members_unchanged"] == 3

    def test_sync_team_endpoint_not_found(self):
        """Sync returns 404 for non-existent team."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

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
            response = client.post(f"/api/v1/teams/{uuid4()}/sync")

            assert response.status_code == 404
            assert response.json()["detail"] == "Team not found"

    def test_sync_team_endpoint_returns_503_when_not_configured(self):
        """Returns 503 when Azure AD not configured."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

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
        mock_team.azure_ad_group_id = "ad-group-123"

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.api.teams.TeamSyncService") as mock_service_class,
        ):
            mock_session.return_value = admin_user
            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_team
            mock_db.execute.return_value = mock_result

            app.dependency_overrides[get_db] = lambda: mock_db

            mock_service = MagicMock()
            mock_service.is_configured.return_value = False
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.post(f"/api/v1/teams/{team_id}/sync")

            assert response.status_code == 503
            assert "Azure AD not configured" in response.json()["detail"]


class TestTeamSyncCronEndpoint:
    """Tests for GET /cron/team-sync endpoint."""

    def test_cron_team_sync_requires_auth(self):
        """Cron endpoint requires CRON_SECRET."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.cron import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        with patch("app.api.cron.settings") as mock_settings:
            mock_settings.cron_secret = "test-secret"

            client = TestClient(app)

            # No auth header
            response = client.get("/api/v1/cron/team-sync")
            assert response.status_code == 401

            # Wrong auth header
            response = client.get(
                "/api/v1/cron/team-sync",
                headers={"Authorization": "Bearer wrong-secret"},
            )
            assert response.status_code == 401

    def test_cron_team_sync_success(self):
        """Cron endpoint works with valid auth."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.cron import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        with (
            patch("app.api.cron.settings") as mock_settings,
            patch(
                "app.services.team_sync_service.TeamSyncService"
            ) as mock_service_class,
        ):
            mock_settings.cron_secret = "test-secret"

            mock_service = MagicMock()
            mock_service.is_configured.return_value = True
            mock_service.sync_all_teams = AsyncMock(
                return_value={
                    "status": "success",
                    "teams_processed": 2,
                    "teams_succeeded": 2,
                    "teams_failed": 0,
                    "total_members_added": 5,
                    "total_members_removed": 1,
                    "errors": [],
                }
            )
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.get(
                "/api/v1/cron/team-sync",
                headers={"Authorization": "Bearer test-secret"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["teams_processed"] == 2
            assert data["total_members_added"] == 5

    def test_cron_team_sync_skipped_when_not_configured(self):
        """Cron endpoint returns skipped when not configured."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.cron import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        with (
            patch("app.api.cron.settings") as mock_settings,
            patch(
                "app.services.team_sync_service.TeamSyncService"
            ) as mock_service_class,
        ):
            mock_settings.cron_secret = "test-secret"

            mock_service = MagicMock()
            mock_service.is_configured.return_value = False
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.get(
                "/api/v1/cron/team-sync",
                headers={"Authorization": "Bearer test-secret"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "skipped"
            assert "Azure AD not configured" in data["errors"][0]


class TestTeamSyncJobHandler:
    """Tests for handle_team_sync job handler."""

    @pytest.mark.asyncio
    async def test_handle_team_sync_success(self):
        """Job handler calls sync service."""
        from app.models.job import Job, JobStatus, JobType

        mock_job = MagicMock(spec=Job)
        mock_job.id = uuid4()
        mock_job.job_type = JobType.TEAM_SYNC
        mock_job.status = JobStatus.IN_PROGRESS

        mock_db = AsyncMock()

        with patch(
            "app.services.team_sync_service.TeamSyncService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.is_configured.return_value = True
            mock_service.sync_all_teams = AsyncMock(
                return_value={
                    "status": "success",
                    "teams_succeeded": 3,
                    "total_members_added": 10,
                    "total_members_removed": 2,
                }
            )
            mock_service_class.return_value = mock_service

            from app.services.job_handlers import handle_team_sync

            result = await handle_team_sync(mock_job, mock_db)

            assert result["status"] == "success"
            assert result["teams_succeeded"] == 3

    @pytest.mark.asyncio
    async def test_handle_team_sync_skipped_when_not_configured(self):
        """Job handler skips when not configured."""
        from app.models.job import Job, JobStatus, JobType

        mock_job = MagicMock(spec=Job)
        mock_job.id = uuid4()
        mock_job.job_type = JobType.TEAM_SYNC
        mock_job.status = JobStatus.IN_PROGRESS

        mock_db = AsyncMock()

        with patch(
            "app.services.team_sync_service.TeamSyncService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.is_configured.return_value = False
            mock_service_class.return_value = mock_service

            from app.services.job_handlers import handle_team_sync

            result = await handle_team_sync(mock_job, mock_db)

            assert result["status"] == "skipped"
            assert "Azure AD not configured" in result["reason"]
