"""Tests for contacts API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.monday_sync import RecordSyncStatus, SyncDirection
from app.schemas.contact import ContactSyncResponse


class TestContactSyncResponseSchema:
    """Tests for ContactSyncResponse schema."""

    def test_contact_sync_response_basic_fields(self):
        """ContactSyncResponse should have correct fields."""
        contact_id = uuid4()
        response = ContactSyncResponse(
            contact_id=contact_id,
            sync_triggered=True,
            message="Sync triggered",
            monday_id=None,
        )

        assert response.contact_id == contact_id
        assert response.sync_triggered is True
        assert response.message == "Sync triggered"
        assert response.monday_id is None

    def test_contact_sync_response_with_monday_id(self):
        """ContactSyncResponse should include monday_id if available."""
        contact_id = uuid4()
        response = ContactSyncResponse(
            contact_id=contact_id,
            sync_triggered=True,
            message="Sync triggered",
            monday_id="monday123",
        )

        assert response.monday_id == "monday123"


class TestSyncContactToMondayManualEndpoint:
    """Tests for POST /api/v1/contacts/{contact_id}/sync-to-monday."""

    def test_sync_contact_not_found(self):
        """Test 404 when contact doesn't exist."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.contacts import router
        from app.core.auth import get_current_active_user
        from app.database import get_db
        from app.models.user import UserRole

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        # Mock the db session to return None (contact not found)
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        fake_contact_id = uuid4()
        client = TestClient(app)
        response = client.post(f"/api/v1/contacts/{fake_contact_id}/sync-to-monday")

        assert response.status_code == 404
        assert response.json()["detail"] == "Contact not found"

    def test_sync_monday_not_configured(self):
        """Test 400 when Monday not configured."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.contacts import router
        from app.core.auth import get_current_active_user
        from app.database import get_db
        from app.models.user import UserRole

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        contact_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.monday_id = None
        mock_contact.sync_enabled = True

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.contacts.settings") as mock_settings:
            mock_settings.is_monday_configured = False
            mock_settings.monday_contacts_board_id = None

            client = TestClient(app)
            response = client.post(f"/api/v1/contacts/{contact_id}/sync-to-monday")

            assert response.status_code == 400
            assert "not configured" in response.json()["detail"]

    def test_sync_triggers_background_task(self):
        """Test that endpoint triggers background sync."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.contacts import router
        from app.core.auth import get_current_active_user
        from app.database import get_db
        from app.models.user import UserRole

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        contact_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.monday_id = "monday456"
        mock_contact.sync_enabled = True
        mock_contact.sync_status = RecordSyncStatus.SYNCED
        mock_contact.sync_direction = SyncDirection.BIDIRECTIONAL

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with (
            patch("app.api.contacts.settings") as mock_settings,
            patch("app.api.contacts.sync_contact_to_monday"),
        ):
            mock_settings.is_monday_configured = True
            mock_settings.monday_contacts_board_id = "board123"

            client = TestClient(app)
            response = client.post(f"/api/v1/contacts/{contact_id}/sync-to-monday")

            assert response.status_code == 200
            data = response.json()
            assert data["sync_triggered"] is True
            assert data["contact_id"] == str(contact_id)
            assert data["monday_id"] == "monday456"
            assert "triggered" in data["message"]

    def test_sync_response_includes_existing_monday_id(self):
        """Test that response includes existing monday_id."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.contacts import router
        from app.core.auth import get_current_active_user
        from app.database import get_db
        from app.models.user import UserRole

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        contact_id = uuid4()
        existing_monday_id = "monday_existing_789"
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.monday_id = existing_monday_id

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with (
            patch("app.api.contacts.settings") as mock_settings,
            patch("app.api.contacts.sync_contact_to_monday"),
        ):
            mock_settings.is_monday_configured = True
            mock_settings.monday_contacts_board_id = "board123"

            client = TestClient(app)
            response = client.post(f"/api/v1/contacts/{contact_id}/sync-to-monday")

            assert response.status_code == 200
            data = response.json()
            assert data["monday_id"] == existing_monday_id

    def test_sync_new_contact_without_monday_id(self):
        """Test sync for contact that has never been synced."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.contacts import router
        from app.core.auth import get_current_active_user
        from app.database import get_db
        from app.models.user import UserRole

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        contact_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.monday_id = None  # Never synced before

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with (
            patch("app.api.contacts.settings") as mock_settings,
            patch("app.api.contacts.sync_contact_to_monday"),
        ):
            mock_settings.is_monday_configured = True
            mock_settings.monday_contacts_board_id = "board123"

            client = TestClient(app)
            response = client.post(f"/api/v1/contacts/{contact_id}/sync-to-monday")

            assert response.status_code == 200
            data = response.json()
            assert data["sync_triggered"] is True
            assert data["monday_id"] is None  # Will be set after background task
