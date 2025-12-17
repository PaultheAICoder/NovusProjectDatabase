"""Tests for sync_service background sync functions."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.monday_sync import RecordSyncStatus, SyncDirection


class TestSyncContactToMonday:
    """Tests for sync_contact_to_monday function."""

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_creates_new_monday_item_when_no_monday_id(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that contact without monday_id creates new Monday item."""
        # Setup settings
        mock_settings.is_monday_configured = True
        mock_settings.monday_contacts_board_id = "board123"

        contact_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.monday_id = None
        mock_contact.sync_enabled = True
        mock_contact.sync_direction = SyncDirection.BIDIRECTIONAL
        mock_contact.name = "Test Contact"
        mock_contact.email = "test@example.com"
        mock_contact.phone = "555-1234"
        mock_contact.role_title = "Manager"
        mock_contact.notes = None

        # Mock db session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        # Create context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        # Mock MondayService
        mock_service = AsyncMock()
        mock_service.create_item.return_value = {
            "id": "monday123",
            "name": "Test Contact",
        }
        mock_service.close = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        # Execute
        from app.services.sync_service import sync_contact_to_monday

        await sync_contact_to_monday(contact_id)

        # Verify
        mock_service.create_item.assert_called_once()
        assert mock_contact.monday_id == "monday123"
        assert mock_contact.sync_status == RecordSyncStatus.SYNCED
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_updates_existing_monday_item_when_has_monday_id(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that contact with monday_id updates existing Monday item."""
        # Setup settings
        mock_settings.is_monday_configured = True
        mock_settings.monday_contacts_board_id = "board123"

        contact_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.monday_id = "monday456"
        mock_contact.sync_enabled = True
        mock_contact.sync_direction = SyncDirection.NPD_TO_MONDAY
        mock_contact.name = "Test Contact"
        mock_contact.email = "test@example.com"
        mock_contact.phone = None
        mock_contact.role_title = None
        mock_contact.notes = None

        # Mock db session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        # Mock MondayService
        mock_service = AsyncMock()
        mock_service.update_item.return_value = {
            "id": "monday456",
            "name": "Test Contact",
        }
        mock_service.close = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        # Execute
        from app.services.sync_service import sync_contact_to_monday

        await sync_contact_to_monday(contact_id)

        # Verify update was called, not create
        mock_service.update_item.assert_called_once()
        mock_service.create_item.assert_not_called()
        assert mock_contact.sync_status == RecordSyncStatus.SYNCED

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_skips_when_sync_enabled_is_false(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that contact with sync_enabled=False is skipped."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_contacts_board_id = "board123"

        contact_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.sync_enabled = False  # Sync disabled
        mock_contact.sync_direction = SyncDirection.BIDIRECTIONAL

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        mock_service = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        from app.services.sync_service import sync_contact_to_monday

        await sync_contact_to_monday(contact_id)

        # Verify MondayService methods were never called
        mock_service.create_item.assert_not_called()
        mock_service.update_item.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_skips_when_sync_direction_is_monday_to_npd(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that contact with sync_direction=MONDAY_TO_NPD is skipped."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_contacts_board_id = "board123"

        contact_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.sync_enabled = True
        mock_contact.sync_direction = SyncDirection.MONDAY_TO_NPD  # Wrong direction

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        mock_service = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        from app.services.sync_service import sync_contact_to_monday

        await sync_contact_to_monday(contact_id)

        mock_service.create_item.assert_not_called()
        mock_service.update_item.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_skips_when_sync_direction_is_none(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that contact with sync_direction=NONE is skipped."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_contacts_board_id = "board123"

        contact_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.sync_enabled = True
        mock_contact.sync_direction = SyncDirection.NONE

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        mock_service = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        from app.services.sync_service import sync_contact_to_monday

        await sync_contact_to_monday(contact_id)

        mock_service.create_item.assert_not_called()
        mock_service.update_item.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.sync_service.settings")
    async def test_skips_when_monday_not_configured(self, mock_settings):
        """Test that sync is skipped when Monday.com is not configured."""
        mock_settings.is_monday_configured = False

        from app.services.sync_service import sync_contact_to_monday

        # Should not raise an exception
        await sync_contact_to_monday(uuid4())

    @pytest.mark.asyncio
    @patch("app.services.sync_service.settings")
    async def test_skips_when_board_id_not_configured(self, mock_settings):
        """Test that sync is skipped when board ID is not configured."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_contacts_board_id = ""

        from app.services.sync_service import sync_contact_to_monday

        await sync_contact_to_monday(uuid4())

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.settings")
    async def test_handles_contact_not_found(self, mock_settings, mock_session_maker):
        """Test that missing contact is handled gracefully."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_contacts_board_id = "board123"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Contact not found
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        from app.services.sync_service import sync_contact_to_monday

        # Should not raise an exception
        await sync_contact_to_monday(uuid4())

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_handles_api_failure_gracefully(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that API failures are handled gracefully without raising."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_contacts_board_id = "board123"

        contact_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.monday_id = None
        mock_contact.sync_enabled = True
        mock_contact.sync_direction = SyncDirection.BIDIRECTIONAL
        mock_contact.name = "Test Contact"
        mock_contact.email = "test@example.com"
        mock_contact.phone = None
        mock_contact.role_title = None
        mock_contact.notes = None

        # First session - fetch contact
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.rollback = AsyncMock()

        # Second session - enqueue for retry (no existing queue item)
        mock_db2 = AsyncMock()
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None  # No existing queue item
        mock_db2.execute = AsyncMock(return_value=mock_result2)
        mock_db2.add = MagicMock()
        mock_db2.flush = AsyncMock()
        mock_db2.commit = AsyncMock()

        # Third session - update sync status to pending
        mock_db3 = AsyncMock()
        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = mock_contact
        mock_db3.execute = AsyncMock(return_value=mock_result3)
        mock_db3.commit = AsyncMock()

        # Setup context managers
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None

        mock_context2 = AsyncMock()
        mock_context2.__aenter__.return_value = mock_db2
        mock_context2.__aexit__.return_value = None

        mock_context3 = AsyncMock()
        mock_context3.__aenter__.return_value = mock_db3
        mock_context3.__aexit__.return_value = None

        mock_session_maker.side_effect = [mock_context, mock_context2, mock_context3]

        # Mock MondayService to raise an exception
        mock_service = AsyncMock()
        mock_service.create_item.side_effect = Exception("API Error")
        mock_service.close = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        from app.services.sync_service import sync_contact_to_monday

        # Should not raise an exception
        await sync_contact_to_monday(contact_id)

        # Verify status was updated to PENDING after failure
        assert mock_contact.sync_status == RecordSyncStatus.PENDING


class TestSyncOrganizationToMonday:
    """Tests for sync_organization_to_monday function."""

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_creates_new_monday_item_when_no_monday_id(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that organization without monday_id creates new Monday item."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_organizations_board_id = "board456"

        org_id = uuid4()
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.monday_id = None
        mock_org.sync_enabled = True
        mock_org.sync_direction = SyncDirection.BIDIRECTIONAL
        mock_org.name = "Test Organization"
        mock_org.notes = "Some notes"
        mock_org.address_street = None
        mock_org.address_city = None
        mock_org.address_state = None
        mock_org.address_zip = None
        mock_org.address_country = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        mock_service = AsyncMock()
        mock_service.create_item.return_value = {
            "id": "monday789",
            "name": "Test Organization",
        }
        mock_service.close = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        from app.services.sync_service import sync_organization_to_monday

        await sync_organization_to_monday(org_id)

        mock_service.create_item.assert_called_once()
        assert mock_org.monday_id == "monday789"
        assert mock_org.sync_status == RecordSyncStatus.SYNCED

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_updates_existing_monday_item_when_has_monday_id(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that organization with monday_id updates existing Monday item."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_organizations_board_id = "board456"

        org_id = uuid4()
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.monday_id = "monday999"
        mock_org.sync_enabled = True
        mock_org.sync_direction = SyncDirection.NPD_TO_MONDAY
        mock_org.name = "Test Organization"
        mock_org.notes = None
        mock_org.address_street = "123 Main St"
        mock_org.address_city = "Anytown"
        mock_org.address_state = "CA"
        mock_org.address_zip = "12345"
        mock_org.address_country = "USA"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        mock_service = AsyncMock()
        mock_service.update_item.return_value = {
            "id": "monday999",
            "name": "Test Organization",
        }
        mock_service.close = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        from app.services.sync_service import sync_organization_to_monday

        await sync_organization_to_monday(org_id)

        mock_service.update_item.assert_called_once()
        mock_service.create_item.assert_not_called()
        assert mock_org.sync_status == RecordSyncStatus.SYNCED

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_skips_when_sync_enabled_is_false(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that organization with sync_enabled=False is skipped."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_organizations_board_id = "board456"

        org_id = uuid4()
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.sync_enabled = False
        mock_org.sync_direction = SyncDirection.BIDIRECTIONAL

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        mock_service = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        from app.services.sync_service import sync_organization_to_monday

        await sync_organization_to_monday(org_id)

        mock_service.create_item.assert_not_called()
        mock_service.update_item.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_skips_when_sync_direction_is_monday_to_npd(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that organization with sync_direction=MONDAY_TO_NPD is skipped."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_organizations_board_id = "board456"

        org_id = uuid4()
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.sync_enabled = True
        mock_org.sync_direction = SyncDirection.MONDAY_TO_NPD

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        mock_service = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        from app.services.sync_service import sync_organization_to_monday

        await sync_organization_to_monday(org_id)

        mock_service.create_item.assert_not_called()
        mock_service.update_item.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.sync_service.settings")
    async def test_skips_when_monday_not_configured(self, mock_settings):
        """Test that sync is skipped when Monday.com is not configured."""
        mock_settings.is_monday_configured = False

        from app.services.sync_service import sync_organization_to_monday

        await sync_organization_to_monday(uuid4())

    @pytest.mark.asyncio
    @patch("app.services.sync_service.settings")
    async def test_skips_when_board_id_not_configured(self, mock_settings):
        """Test that sync is skipped when board ID is not configured."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_organizations_board_id = ""

        from app.services.sync_service import sync_organization_to_monday

        await sync_organization_to_monday(uuid4())

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.settings")
    async def test_handles_organization_not_found(
        self, mock_settings, mock_session_maker
    ):
        """Test that missing organization is handled gracefully."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_organizations_board_id = "board456"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        from app.services.sync_service import sync_organization_to_monday

        await sync_organization_to_monday(uuid4())

    @pytest.mark.asyncio
    @patch("app.services.sync_service.async_session_maker")
    @patch("app.services.sync_service.MondayService")
    @patch("app.services.sync_service.settings")
    async def test_handles_api_failure_gracefully(
        self, mock_settings, mock_monday_service_class, mock_session_maker
    ):
        """Test that API failures are handled gracefully without raising."""
        mock_settings.is_monday_configured = True
        mock_settings.monday_organizations_board_id = "board456"

        org_id = uuid4()
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.monday_id = None
        mock_org.sync_enabled = True
        mock_org.sync_direction = SyncDirection.BIDIRECTIONAL
        mock_org.name = "Test Organization"
        mock_org.notes = None
        mock_org.address_street = None
        mock_org.address_city = None
        mock_org.address_state = None
        mock_org.address_zip = None
        mock_org.address_country = None

        # First session - fetch org
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.rollback = AsyncMock()

        # Second session - enqueue for retry (no existing queue item)
        mock_db2 = AsyncMock()
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None  # No existing queue item
        mock_db2.execute = AsyncMock(return_value=mock_result2)
        mock_db2.add = MagicMock()
        mock_db2.flush = AsyncMock()
        mock_db2.commit = AsyncMock()

        # Third session - update sync status to pending
        mock_db3 = AsyncMock()
        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = mock_org
        mock_db3.execute = AsyncMock(return_value=mock_result3)
        mock_db3.commit = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None

        mock_context2 = AsyncMock()
        mock_context2.__aenter__.return_value = mock_db2
        mock_context2.__aexit__.return_value = None

        mock_context3 = AsyncMock()
        mock_context3.__aenter__.return_value = mock_db3
        mock_context3.__aexit__.return_value = None

        mock_session_maker.side_effect = [mock_context, mock_context2, mock_context3]

        mock_service = AsyncMock()
        mock_service.create_item.side_effect = Exception("API Error")
        mock_service.close = AsyncMock()
        mock_monday_service_class.return_value = mock_service

        from app.services.sync_service import sync_organization_to_monday

        await sync_organization_to_monday(org_id)

        assert mock_org.sync_status == RecordSyncStatus.PENDING


class TestBuildColumnValues:
    """Tests for column value building helper functions."""

    def test_build_contact_column_values_full(self):
        """Test building column values for contact with all fields."""
        from app.services.sync_service import _build_contact_column_values

        mock_contact = MagicMock()
        mock_contact.email = "test@example.com"
        mock_contact.phone = "555-1234"
        mock_contact.role_title = "Manager"
        mock_contact.notes = "Some notes"

        result = _build_contact_column_values(mock_contact)

        assert "email" in result
        assert result["email"]["email"] == "test@example.com"
        assert "phone" in result
        assert result["phone"]["phone"] == "555-1234"
        assert "role_title" in result
        assert result["role_title"] == "Manager"
        assert "notes" in result
        assert result["notes"] == "Some notes"

    def test_build_contact_column_values_minimal(self):
        """Test building column values for contact with minimal fields."""
        from app.services.sync_service import _build_contact_column_values

        mock_contact = MagicMock()
        mock_contact.email = "test@example.com"
        mock_contact.phone = None
        mock_contact.role_title = None
        mock_contact.notes = None

        result = _build_contact_column_values(mock_contact)

        assert "email" in result
        assert "phone" not in result
        assert "role_title" not in result
        assert "notes" not in result

    def test_build_organization_column_values_full(self):
        """Test building column values for organization with all fields."""
        from app.services.sync_service import _build_organization_column_values

        mock_org = MagicMock()
        mock_org.notes = "Organization notes"
        mock_org.address_street = "123 Main St"
        mock_org.address_city = "Anytown"
        mock_org.address_state = "CA"
        mock_org.address_zip = "12345"
        mock_org.address_country = "USA"

        result = _build_organization_column_values(mock_org)

        assert "notes" in result
        assert result["notes"] == "Organization notes"
        assert "address" in result
        assert "123 Main St" in result["address"]
        assert "Anytown" in result["address"]

    def test_build_organization_column_values_minimal(self):
        """Test building column values for organization with minimal fields."""
        from app.services.sync_service import _build_organization_column_values

        mock_org = MagicMock()
        mock_org.notes = None
        mock_org.address_street = None
        mock_org.address_city = None
        mock_org.address_state = None
        mock_org.address_zip = None
        mock_org.address_country = None

        result = _build_organization_column_values(mock_org)

        assert "notes" not in result
        assert "address" not in result
