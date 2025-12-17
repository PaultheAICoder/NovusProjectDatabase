"""Tests for inbound Monday.com sync functions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.monday_sync import RecordSyncStatus, SyncDirection


class TestProcessMondayCreate:
    """Tests for process_monday_create function."""

    @pytest.mark.asyncio
    async def test_creates_organization_from_monday(self):
        """Test that create event creates new organization."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        # No existing org
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = MondayService(mock_db)

        result = await service.process_monday_create(
            board_id="board123",
            monday_item_id="item456",
            item_name="Acme Corp",
            board_type="organizations",
        )

        assert result["action"] == "created"
        assert result["entity_type"] == "organization"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_duplicate_organization(self):
        """Test that duplicate create event is skipped."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = MondayService(mock_db)

        result = await service.process_monday_create(
            board_id="board123",
            monday_item_id="item456",
            item_name="Acme Corp",
            board_type="organizations",
        )

        assert result["action"] == "skipped"
        assert result["reason"] == "already_exists"

    @pytest.mark.asyncio
    async def test_contact_create_skipped_needs_data(self):
        """Test that contact create is skipped (needs email/org)."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = MondayService(mock_db)

        result = await service.process_monday_create(
            board_id="board123",
            monday_item_id="item456",
            item_name="John Doe",
            board_type="contacts",
        )

        assert result["action"] == "skipped"
        assert "requires_email" in result["reason"]

    @pytest.mark.asyncio
    async def test_unknown_board_type_skipped(self):
        """Test that unknown board type is skipped."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        service = MondayService(mock_db)

        result = await service.process_monday_create(
            board_id="board123",
            monday_item_id="item456",
            item_name="Test Item",
            board_type="unknown",
        )

        assert result["action"] == "skipped"
        assert "unknown_board_type" in result["reason"]


class TestProcessMondayUpdate:
    """Tests for process_monday_update function."""

    @pytest.mark.asyncio
    async def test_updates_organization_field(self):
        """Test that update event updates organization field."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.sync_enabled = True
        mock_org.sync_direction = SyncDirection.BIDIRECTIONAL
        mock_org.monday_last_synced = datetime.now(UTC) - timedelta(hours=1)
        mock_org.updated_at = datetime.now(UTC) - timedelta(hours=2)
        mock_org.notes = "Old notes"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = MondayService(mock_db)

        result = await service.process_monday_update(
            board_id="board123",
            monday_item_id="item456",
            column_id="notes",
            new_value={"text": "New notes"},
            previous_value={"text": "Old notes"},
            board_type="organizations",
        )

        assert result["action"] == "updated"
        assert result["entity_type"] == "organization"

    @pytest.mark.asyncio
    async def test_updates_contact_email_field(self):
        """Test that update event updates contact email field."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_contact = MagicMock()
        mock_contact.id = uuid4()
        mock_contact.sync_enabled = True
        mock_contact.sync_direction = SyncDirection.MONDAY_TO_NPD
        mock_contact.monday_last_synced = datetime.now(UTC) - timedelta(hours=1)
        mock_contact.updated_at = datetime.now(UTC) - timedelta(hours=2)
        mock_contact.email = "old@example.com"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = MondayService(mock_db)

        result = await service.process_monday_update(
            board_id="board123",
            monday_item_id="item456",
            column_id="email",
            new_value={"email": "new@example.com", "text": "new@example.com"},
            previous_value={"email": "old@example.com", "text": "old@example.com"},
            board_type="contacts",
        )

        assert result["action"] == "updated"
        assert result["entity_type"] == "contact"

    @pytest.mark.asyncio
    async def test_detects_conflict(self):
        """Test that conflict is detected when NPD was modified after last sync."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.sync_enabled = True
        mock_org.sync_direction = SyncDirection.BIDIRECTIONAL
        # Modified AFTER last sync - should trigger conflict
        mock_org.monday_last_synced = datetime.now(UTC) - timedelta(hours=2)
        mock_org.updated_at = datetime.now(UTC) - timedelta(hours=1)
        mock_org.notes = "NPD modified notes"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = MondayService(mock_db)

        result = await service.process_monday_update(
            board_id="board123",
            monday_item_id="item456",
            column_id="notes",
            new_value={"text": "Monday notes"},
            previous_value={"text": "Old notes"},
            board_type="organizations",
        )

        assert result["action"] == "conflict"
        assert mock_org.sync_status == RecordSyncStatus.CONFLICT
        mock_db.add.assert_called_once()  # SyncConflict record added

    @pytest.mark.asyncio
    async def test_skips_when_sync_disabled(self):
        """Test that update is skipped when sync_enabled=False."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.sync_enabled = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = MondayService(mock_db)

        result = await service.process_monday_update(
            board_id="board123",
            monday_item_id="item456",
            column_id="notes",
            new_value={"text": "New notes"},
            previous_value=None,
            board_type="organizations",
        )

        assert result["action"] == "skipped"
        assert result["reason"] == "sync_disabled"

    @pytest.mark.asyncio
    async def test_skips_when_sync_direction_npd_to_monday(self):
        """Test that update is skipped when sync_direction is NPD_TO_MONDAY."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.sync_enabled = True
        mock_org.sync_direction = SyncDirection.NPD_TO_MONDAY

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = MondayService(mock_db)

        result = await service.process_monday_update(
            board_id="board123",
            monday_item_id="item456",
            column_id="notes",
            new_value={"text": "New notes"},
            previous_value=None,
            board_type="organizations",
        )

        assert result["action"] == "skipped"
        assert "sync_direction" in result["reason"]

    @pytest.mark.asyncio
    async def test_skips_when_sync_direction_none(self):
        """Test that update is skipped when sync_direction is NONE."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.sync_enabled = True
        mock_org.sync_direction = SyncDirection.NONE

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = MondayService(mock_db)

        result = await service.process_monday_update(
            board_id="board123",
            monday_item_id="item456",
            column_id="notes",
            new_value={"text": "New notes"},
            previous_value=None,
            board_type="organizations",
        )

        assert result["action"] == "skipped"
        assert "sync_direction:none" in result["reason"]

    @pytest.mark.asyncio
    async def test_skips_when_record_not_found(self):
        """Test that update is skipped when record not found."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = MondayService(mock_db)

        result = await service.process_monday_update(
            board_id="board123",
            monday_item_id="item456",
            column_id="notes",
            new_value={"text": "New notes"},
            previous_value=None,
            board_type="organizations",
        )

        assert result["action"] == "skipped"
        assert result["reason"] == "record_not_found"

    @pytest.mark.asyncio
    async def test_skips_unmapped_column(self):
        """Test that update is skipped for unmapped columns."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.sync_enabled = True
        mock_org.sync_direction = SyncDirection.BIDIRECTIONAL
        mock_org.monday_last_synced = datetime.now(UTC) - timedelta(hours=1)
        mock_org.updated_at = datetime.now(UTC) - timedelta(hours=2)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = MondayService(mock_db)

        result = await service.process_monday_update(
            board_id="board123",
            monday_item_id="item456",
            column_id="unknown_column_id",
            new_value={"text": "Value"},
            previous_value=None,
            board_type="organizations",
        )

        assert result["action"] == "skipped"
        assert "unmapped_column" in result["reason"]


class TestProcessMondayDelete:
    """Tests for process_monday_delete function."""

    @pytest.mark.asyncio
    async def test_unlinks_organization(self):
        """Test that delete event unlinks but preserves organization."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.monday_id = "item456"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = MondayService(mock_db)

        result = await service.process_monday_delete(
            board_id="board123",
            monday_item_id="item456",
            board_type="organizations",
        )

        assert result["action"] == "unlinked"
        assert mock_org.monday_id is None
        assert mock_org.sync_status == RecordSyncStatus.DISABLED
        assert mock_org.sync_enabled is False

    @pytest.mark.asyncio
    async def test_unlinks_contact(self):
        """Test that delete event unlinks but preserves contact."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_contact = MagicMock()
        mock_contact.id = uuid4()
        mock_contact.monday_id = "item456"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = MondayService(mock_db)

        result = await service.process_monday_delete(
            board_id="board123",
            monday_item_id="item456",
            board_type="contacts",
        )

        assert result["action"] == "unlinked"
        assert mock_contact.monday_id is None
        assert mock_contact.sync_status == RecordSyncStatus.DISABLED
        assert mock_contact.sync_enabled is False

    @pytest.mark.asyncio
    async def test_skips_when_record_not_found(self):
        """Test that delete is skipped when record not found."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = MondayService(mock_db)

        result = await service.process_monday_delete(
            board_id="board123",
            monday_item_id="item456",
            board_type="organizations",
        )

        assert result["action"] == "skipped"
        assert result["reason"] == "record_not_found"

    @pytest.mark.asyncio
    async def test_unknown_board_type_skipped(self):
        """Test that unknown board type is skipped."""
        from app.services.monday_service import MondayService

        mock_db = AsyncMock()
        service = MondayService(mock_db)

        result = await service.process_monday_delete(
            board_id="board123",
            monday_item_id="item456",
            board_type="unknown",
        )

        assert result["action"] == "skipped"
        assert "unknown_board_type" in result["reason"]


class TestMondayColumnParser:
    """Tests for MondayColumnParser utility class."""

    def test_parse_email(self):
        """Test email column parsing."""
        from app.services.monday_service import MondayColumnParser

        result = MondayColumnParser.parse_email(
            {"email": "test@example.com", "text": "test@example.com"}
        )
        assert result == "test@example.com"

        result = MondayColumnParser.parse_email(None)
        assert result is None

    def test_parse_email_fallback_to_text(self):
        """Test email parsing falls back to text field."""
        from app.services.monday_service import MondayColumnParser

        result = MondayColumnParser.parse_email({"text": "test@example.com"})
        assert result == "test@example.com"

    def test_parse_phone(self):
        """Test phone column parsing."""
        from app.services.monday_service import MondayColumnParser

        result = MondayColumnParser.parse_phone(
            {"phone": "+12025550169", "countryShortName": "US"}
        )
        assert result == "+12025550169"

        result = MondayColumnParser.parse_phone(None)
        assert result is None

    def test_parse_text_from_dict(self):
        """Test text column parsing from dict."""
        from app.services.monday_service import MondayColumnParser

        result = MondayColumnParser.parse_text({"text": "Hello"})
        assert result == "Hello"

        result = MondayColumnParser.parse_text({"value": "World"})
        assert result == "World"

    def test_parse_text_direct_string(self):
        """Test text column parsing from direct string."""
        from app.services.monday_service import MondayColumnParser

        result = MondayColumnParser.parse_text("Direct string")
        assert result == "Direct string"

    def test_parse_text_none(self):
        """Test text column parsing with None."""
        from app.services.monday_service import MondayColumnParser

        result = MondayColumnParser.parse_text(None)
        assert result is None


class TestParseWebhookColumnValue:
    """Tests for _parse_webhook_column_value helper method."""

    def test_parse_email_column(self):
        """Test parsing email column type."""
        from app.services.monday_service import MondayService

        mock_db = MagicMock()
        service = MondayService(mock_db)

        result = service._parse_webhook_column_value(
            "email", {"email": "test@example.com", "text": "test@example.com"}
        )
        assert result == "test@example.com"

    def test_parse_phone_column(self):
        """Test parsing phone column type."""
        from app.services.monday_service import MondayService

        mock_db = MagicMock()
        service = MondayService(mock_db)

        result = service._parse_webhook_column_value(
            "phone", {"phone": "+15551234567", "countryShortName": "US"}
        )
        assert result == "+15551234567"

    def test_parse_text_column(self):
        """Test parsing text column type."""
        from app.services.monday_service import MondayService

        mock_db = MagicMock()
        service = MondayService(mock_db)

        result = service._parse_webhook_column_value("notes", {"text": "Some notes"})
        assert result == "Some notes"

    def test_parse_none_value(self):
        """Test parsing None value returns None."""
        from app.services.monday_service import MondayService

        mock_db = MagicMock()
        service = MondayService(mock_db)

        result = service._parse_webhook_column_value("notes", None)
        assert result is None
