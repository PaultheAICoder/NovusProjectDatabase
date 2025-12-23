"""Tests for Monday.com service."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.monday_service import MondayService


class TestMondayServiceConfiguration:
    """Tests for MondayService configuration."""

    @patch("app.services.monday_service.settings")
    def test_is_configured_true(self, mock_settings):
        """Test is_configured returns True when API key is set."""
        mock_settings.monday_api_key = "test-api-key"
        mock_db = AsyncMock()
        service = MondayService(mock_db)
        assert service.is_configured is True

    @patch("app.services.monday_service.settings")
    def test_is_configured_false(self, mock_settings):
        """Test is_configured returns False when API key is empty."""
        mock_settings.monday_api_key = ""
        mock_db = AsyncMock()
        service = MondayService(mock_db)
        assert service.is_configured is False

    @patch("app.services.monday_service.settings")
    def test_is_configured_false_when_none(self, mock_settings):
        """Test is_configured returns False when API key is None."""
        mock_settings.monday_api_key = None
        mock_db = AsyncMock()
        service = MondayService(mock_db)
        assert service.is_configured is False


class TestMondayServiceGraphQL:
    """Tests for MondayService GraphQL operations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def monday_service(self, mock_db):
        """Create MondayService instance."""
        return MondayService(mock_db)

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_get_boards(self, mock_settings, monday_service):
        """Test fetching boards from Monday API."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        # Mock the HTTP client response
        with patch.object(monday_service, "_execute_query") as mock_query:
            mock_query.return_value = {
                "boards": [{"id": "123", "name": "Test Board", "columns": []}]
            }

            boards = await monday_service.get_boards()
            assert len(boards) == 1
            assert boards[0]["id"] == "123"
            assert boards[0]["name"] == "Test Board"

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_get_board_items_first_page(self, mock_settings, monday_service):
        """Test fetching first page of board items."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_query") as mock_query:
            mock_query.return_value = {
                "boards": [
                    {
                        "items_page": {
                            "cursor": "next_cursor_value",
                            "items": [
                                {"id": "item1", "name": "Item 1", "column_values": []}
                            ],
                        }
                    }
                ]
            }

            items, cursor = await monday_service.get_board_items("123")
            assert len(items) == 1
            assert items[0]["id"] == "item1"
            assert cursor == "next_cursor_value"

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_get_board_items_with_cursor(self, mock_settings, monday_service):
        """Test fetching subsequent pages with cursor."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_query") as mock_query:
            mock_query.return_value = {
                "next_items_page": {
                    "cursor": None,  # Last page
                    "items": [{"id": "item2", "name": "Item 2", "column_values": []}],
                }
            }

            items, cursor = await monday_service.get_board_items(
                "123", cursor="prev_cursor"
            )
            assert len(items) == 1
            assert items[0]["id"] == "item2"
            assert cursor is None


class TestMondayServiceColumnExtraction:
    """Tests for column value extraction."""

    @pytest.fixture
    def monday_service(self):
        """Create MondayService instance."""
        return MondayService(AsyncMock())

    def test_get_column_value(self, monday_service):
        """Test extracting column value from item."""
        item = {
            "column_values": [
                {"id": "email", "text": "test@example.com"},
                {"id": "phone", "text": "123-456-7890"},
            ]
        }

        assert monday_service._get_column_value(item, "email") == "test@example.com"
        assert monday_service._get_column_value(item, "phone") == "123-456-7890"
        assert monday_service._get_column_value(item, "missing") == ""

    def test_get_column_value_empty_column_id(self, monday_service):
        """Test _get_column_value returns empty string for empty column_id."""
        item = {"column_values": [{"id": "test", "text": "value"}]}

        assert monday_service._get_column_value(item, "") == ""

    def test_get_column_value_null_text(self, monday_service):
        """Test _get_column_value handles null text values."""
        item = {
            "column_values": [
                {"id": "nullable", "text": None},
            ]
        }

        assert monday_service._get_column_value(item, "nullable") == ""


class TestMondayServiceOrganizationSync:
    """Tests for organization sync operations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def monday_service(self, mock_db):
        """Create MondayService instance."""
        return MondayService(mock_db)

    @pytest.mark.asyncio
    async def test_find_organization_by_monday_id(self, monday_service, mock_db):
        """Test finding organization by Monday ID."""
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.name = "Test Org"
        mock_org.monday_id = "12345"

        # Setup mock query result - make scalar_one_or_none return the org directly
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await monday_service._find_organization("12345", "Test Org")
        assert result == mock_org

    @pytest.mark.asyncio
    async def test_find_organization_by_name_fallback(self, monday_service, mock_db):
        """Test finding organization by name when monday_id not found."""
        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.name = "Test Org"
        mock_org.monday_id = None

        # First query (by monday_id) returns None, second (by name) returns org
        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None

        mock_result_org = MagicMock()
        mock_result_org.scalar_one_or_none.return_value = mock_org

        mock_db.execute = AsyncMock(side_effect=[mock_result_none, mock_result_org])

        result = await monday_service._find_organization("99999", "Test Org")
        assert result == mock_org


class TestMondayServiceContactSync:
    """Tests for contact sync operations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def monday_service(self, mock_db):
        """Create MondayService instance."""
        return MondayService(mock_db)

    @pytest.mark.asyncio
    async def test_find_contact_by_monday_id(self, monday_service, mock_db):
        """Test finding contact by Monday ID."""
        mock_contact = MagicMock()
        mock_contact.id = uuid4()
        mock_contact.name = "John Doe"
        mock_contact.monday_id = "12345"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await monday_service._find_contact(
            "12345", "john@example.com", uuid4()
        )
        assert result == mock_contact

    @pytest.mark.asyncio
    async def test_find_or_create_organization_creates_new(
        self, monday_service, mock_db
    ):
        """Test _find_or_create_organization creates new org if not found."""
        # First query returns None (org not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        await monday_service._find_or_create_organization("New Org")

        # Should have added a new organization
        assert mock_db.add.called
        assert mock_db.flush.called

    @pytest.mark.asyncio
    async def test_find_or_create_organization_returns_none_for_empty_name(
        self, monday_service
    ):
        """Test _find_or_create_organization returns None for empty name."""
        result = await monday_service._find_or_create_organization("")
        assert result is None


class TestMondayServiceFieldMapping:
    """Tests for field mapping application."""

    @pytest.fixture
    def monday_service(self):
        """Create MondayService instance."""
        return MondayService(AsyncMock())

    def test_apply_field_mapping_notes(self, monday_service):
        """Test applying notes field mapping to organization."""
        from app.models.organization import Organization

        org = Organization(name="Test Org")
        item = {
            "column_values": [
                {"id": "notes_col", "text": "Test notes content"},
            ]
        }
        mapping = {"notes": "notes_col"}

        monday_service._apply_field_mapping(org, item, mapping)
        assert org.notes == "Test notes content"

    def test_apply_contact_field_mapping(self, monday_service):
        """Test applying field mapping to contact."""
        from app.models.contact import Contact

        contact = Contact(
            name="John Doe",
            email="john@example.com",
            organization_id=uuid4(),
        )
        item = {
            "column_values": [
                {"id": "role_col", "text": "Manager"},
                {"id": "phone_col", "text": "555-1234"},
                {"id": "notes_col", "text": "Contact notes"},
            ]
        }
        mapping = {
            "role_title": "role_col",
            "phone": "phone_col",
            "notes": "notes_col",
        }

        monday_service._apply_contact_field_mapping(contact, item, mapping)
        assert contact.role_title == "Manager"
        assert contact.phone == "555-1234"
        assert contact.notes == "Contact notes"


class TestMondayServiceSyncStatus:
    """Tests for sync status operations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def monday_service(self, mock_db):
        """Create MondayService instance."""
        return MondayService(mock_db)

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_get_sync_status(self, mock_settings, monday_service, mock_db):
        """Test getting sync status."""
        mock_settings.monday_api_key = "test-key"

        # Mock the scalar calls to return None (no logs yet)
        mock_db.scalar = AsyncMock(return_value=None)

        # Mock the scalars call for recent logs
        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = []
        mock_db.scalars = AsyncMock(return_value=mock_scalars_result)

        status = await monday_service.get_sync_status()

        assert status["is_configured"] is True
        assert status["last_org_sync"] is None
        assert status["last_contact_sync"] is None
        assert status["recent_logs"] == []


class TestMondayColumnFormatter:
    """Tests for MondayColumnFormatter utility class."""

    def test_format_email(self):
        """Test email column formatting."""
        from app.services.monday_service import MondayColumnFormatter

        result = MondayColumnFormatter.format_email("test@example.com")
        assert result == {"email": "test@example.com", "text": "test@example.com"}

        result = MondayColumnFormatter.format_email("test@example.com", "Contact Email")
        assert result == {"email": "test@example.com", "text": "Contact Email"}

    def test_format_phone(self):
        """Test phone column formatting."""
        from app.services.monday_service import MondayColumnFormatter

        result = MondayColumnFormatter.format_phone("+12025550169")
        assert result == {"phone": "+12025550169", "countryShortName": "US"}

        result = MondayColumnFormatter.format_phone("+442071234567", "GB")
        assert result == {"phone": "+442071234567", "countryShortName": "GB"}

    def test_format_phone_lowercase_country_code(self):
        """Test phone column formatting normalizes country code to uppercase."""
        from app.services.monday_service import MondayColumnFormatter

        result = MondayColumnFormatter.format_phone("+12025550169", "us")
        assert result == {"phone": "+12025550169", "countryShortName": "US"}

    def test_format_text(self):
        """Test text column formatting."""
        from app.services.monday_service import MondayColumnFormatter

        result = MondayColumnFormatter.format_text("Hello World")
        assert result == "Hello World"

    def test_format_status(self):
        """Test status column formatting."""
        from app.services.monday_service import MondayColumnFormatter

        result = MondayColumnFormatter.format_status("Done")
        assert result == {"label": "Done"}

    def test_format_date_from_datetime(self):
        """Test date formatting from datetime object."""
        from datetime import datetime

        from app.services.monday_service import MondayColumnFormatter

        dt = datetime(2025, 12, 17, 10, 30, 0)
        result = MondayColumnFormatter.format_date(dt)
        assert result == "2025-12-17"

    def test_format_date_from_string(self):
        """Test date formatting passthrough for string."""
        from app.services.monday_service import MondayColumnFormatter

        result = MondayColumnFormatter.format_date("2025-12-17")
        assert result == "2025-12-17"


class TestMondayServiceMutations:
    """Tests for Monday.com mutation methods."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def monday_service(self, mock_db):
        """Create MondayService instance."""
        return MondayService(mock_db)

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_create_item_success(self, mock_settings, monday_service):
        """Test successful item creation."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_with_retry") as mock_execute:
            mock_execute.return_value = {
                "create_item": {"id": "12345", "name": "Test Item"}
            }

            result = await monday_service.create_item(
                board_id="board123",
                item_name="Test Item",
                column_values={
                    "email_col": {
                        "email": "test@example.com",
                        "text": "test@example.com",
                    }
                },
            )

            assert result["id"] == "12345"
            assert result["name"] == "Test Item"

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_create_item_without_column_values(
        self, mock_settings, monday_service
    ):
        """Test item creation without column values."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_with_retry") as mock_execute:
            mock_execute.return_value = {
                "create_item": {"id": "12345", "name": "Simple Item"}
            }

            result = await monday_service.create_item(
                board_id="board123",
                item_name="Simple Item",
            )

            assert result["id"] == "12345"
            assert result["name"] == "Simple Item"
            # Verify column_values was not included in variables
            call_args = mock_execute.call_args
            variables = (
                call_args[0][1] if call_args[0] else call_args[1].get("variables")
            )
            assert "column_values" not in variables

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_create_item_with_group_id(self, mock_settings, monday_service):
        """Test item creation with group ID."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_with_retry") as mock_execute:
            mock_execute.return_value = {
                "create_item": {"id": "12345", "name": "Grouped Item"}
            }

            result = await monday_service.create_item(
                board_id="board123",
                item_name="Grouped Item",
                group_id="group1",
            )

            assert result["id"] == "12345"
            # Verify group_id was included in variables
            call_args = mock_execute.call_args
            variables = (
                call_args[0][1] if call_args[0] else call_args[1].get("variables")
            )
            assert variables.get("group_id") == "group1"

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_update_item_success(self, mock_settings, monday_service):
        """Test successful item update."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_with_retry") as mock_execute:
            mock_execute.return_value = {
                "change_multiple_column_values": {"id": "12345", "name": "Updated Item"}
            }

            result = await monday_service.update_item(
                board_id="board123",
                item_id="12345",
                column_values={"text_col": "Updated value"},
            )

            assert result["id"] == "12345"
            assert result["name"] == "Updated Item"

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_delete_item_success(self, mock_settings, monday_service):
        """Test successful item deletion."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_with_retry") as mock_execute:
            mock_execute.return_value = {"delete_item": {"id": "12345"}}

            result = await monday_service.delete_item(item_id="12345")

            assert result["id"] == "12345"


class TestDefaultFieldMappings:
    """Tests for default field mapping functions."""

    def test_get_default_contact_field_mapping(self):
        """Test default contact field mapping contains required fields."""
        from app.services.monday_service import get_default_contact_field_mapping

        mapping = get_default_contact_field_mapping()

        # Should contain mappings for core contact fields
        assert "email" in mapping
        assert "phone" in mapping
        assert "role_title" in mapping
        assert "notes" in mapping
        assert "organization_name" in mapping

        # All values should be non-empty strings (column IDs)
        for value in mapping.values():
            assert isinstance(value, str)
            assert len(value) > 0

    def test_get_default_org_field_mapping(self):
        """Test default organization field mapping contains required fields."""
        from app.services.monday_service import get_default_org_field_mapping

        mapping = get_default_org_field_mapping()

        # Should contain mapping for notes field
        assert "notes" in mapping

        # All values should be non-empty strings
        for value in mapping.values():
            assert isinstance(value, str)
            assert len(value) > 0

    def test_default_contact_mapping_returns_new_dict(self):
        """Test that each call returns a new dict instance (not mutable shared state)."""
        from app.services.monday_service import get_default_contact_field_mapping

        mapping1 = get_default_contact_field_mapping()
        mapping2 = get_default_contact_field_mapping()

        # Should be equal but not the same object
        assert mapping1 == mapping2
        assert mapping1 is not mapping2

    def test_default_org_mapping_returns_new_dict(self):
        """Test that each call returns a new dict instance (not mutable shared state)."""
        from app.services.monday_service import get_default_org_field_mapping

        mapping1 = get_default_org_field_mapping()
        mapping2 = get_default_org_field_mapping()

        # Should be equal but not the same object
        assert mapping1 == mapping2
        assert mapping1 is not mapping2


class TestDefaultMappingsIntegration:
    """Integration tests for default field mappings with sync methods."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def monday_service(self, mock_db):
        """Create MondayService instance."""
        return MondayService(mock_db)

    def test_apply_contact_field_mapping_with_defaults(self, monday_service):
        """Test that _apply_contact_field_mapping works with default mapping structure."""
        from app.models.contact import Contact
        from app.services.monday_service import get_default_contact_field_mapping

        contact = Contact(
            name="John Doe",
            email="john@example.com",
            organization_id=uuid4(),
        )

        # Simulate item with Monday column values using default column IDs
        item = {
            "column_values": [
                {"id": "email", "text": "john@example.com"},
                {"id": "phone", "text": "555-1234"},
                {"id": "role_title", "text": "Manager"},
                {"id": "notes", "text": "Test notes"},
                {"id": "organization", "text": "Acme Corp"},
            ]
        }

        mapping = get_default_contact_field_mapping()
        monday_service._apply_contact_field_mapping(contact, item, mapping)

        # Verify fields were populated
        assert contact.role_title == "Manager"
        assert contact.phone == "555-1234"
        assert contact.notes == "Test notes"

    def test_apply_org_field_mapping_with_defaults(self, monday_service):
        """Test that _apply_field_mapping works with default org mapping structure."""
        from app.models.organization import Organization
        from app.services.monday_service import get_default_org_field_mapping

        org = Organization(name="Test Org")

        # Simulate item with Monday column values using default column IDs
        item = {
            "column_values": [
                {"id": "notes", "text": "Organization notes here"},
            ]
        }

        mapping = get_default_org_field_mapping()
        monday_service._apply_field_mapping(org, item, mapping)

        # Verify notes field was populated
        assert org.notes == "Organization notes here"


class TestMondayContactSearch:
    """Tests for Monday.com contact search functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def monday_service(self, mock_db):
        """Create MondayService instance."""
        return MondayService(mock_db)

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_search_monday_contacts_success(self, mock_settings, monday_service):
        """Test successful contact search."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_with_retry") as mock_execute:
            mock_execute.return_value = {
                "items_page_by_column_values": {
                    "cursor": None,
                    "items": [
                        {
                            "id": "12345",
                            "name": "John Doe",
                            "column_values": [
                                {"id": "email", "text": "john@example.com"},
                                {"id": "phone", "text": "555-1234"},
                            ],
                        }
                    ],
                }
            }

            result = await monday_service.search_monday_contacts(
                board_id="board123",
                query="John",
            )

            assert len(result["items"]) == 1
            assert result["items"][0]["id"] == "12345"
            assert result["items"][0]["name"] == "John Doe"
            assert result["cursor"] is None
            assert result["has_more"] is False

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_search_monday_contacts_with_pagination(
        self, mock_settings, monday_service
    ):
        """Test contact search with pagination cursor."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_with_retry") as mock_execute:
            mock_execute.return_value = {
                "items_page_by_column_values": {
                    "cursor": "next_page_cursor",
                    "items": [{"id": "1", "name": "Contact 1", "column_values": []}],
                }
            }

            result = await monday_service.search_monday_contacts(
                board_id="board123",
                query="test",
                limit=1,
            )

            assert result["cursor"] == "next_page_cursor"
            assert result["has_more"] is True

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_search_monday_contacts_custom_columns(
        self, mock_settings, monday_service
    ):
        """Test contact search with custom search columns."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_with_retry") as mock_execute:
            mock_execute.return_value = {
                "items_page_by_column_values": {
                    "cursor": None,
                    "items": [],
                }
            }

            await monday_service.search_monday_contacts(
                board_id="board123",
                query="test@example.com",
                search_columns=["email"],
            )

            # Verify the query was called with correct column config
            call_args = mock_execute.call_args
            variables = (
                call_args[0][1] if call_args[0] else call_args[1].get("variables")
            )
            assert len(variables["columns"]) == 1
            assert variables["columns"][0]["column_id"] == "email"

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_search_monday_contacts_limit_clamped(
        self, mock_settings, monday_service
    ):
        """Test that limit is clamped to valid range."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_with_retry") as mock_execute:
            mock_execute.return_value = {
                "items_page_by_column_values": {"cursor": None, "items": []}
            }

            # Test upper limit
            await monday_service.search_monday_contacts(
                board_id="board123",
                query="test",
                limit=100,  # Over max of 50
            )

            call_args = mock_execute.call_args
            variables = (
                call_args[0][1] if call_args[0] else call_args[1].get("variables")
            )
            assert variables["limit"] == 50  # Should be clamped

    def test_parse_contact_from_item(self, monday_service):
        """Test parsing Monday item into contact structure."""
        item = {
            "id": "12345",
            "name": "Jane Smith",
            "column_values": [
                {"id": "email", "text": "jane@example.com"},
                {"id": "phone", "text": "555-9999"},
                {"id": "role_title", "text": "Manager"},
                {"id": "organization", "text": "Acme Corp"},
            ],
        }

        contact = monday_service._parse_contact_from_item(item, "board123")

        assert contact["monday_id"] == "12345"
        assert contact["name"] == "Jane Smith"
        assert contact["email"] == "jane@example.com"
        assert contact["phone"] == "555-9999"
        assert contact["role_title"] == "Manager"
        assert contact["organization"] == "Acme Corp"
        assert contact["board_id"] == "board123"

    def test_parse_contact_from_item_missing_fields(self, monday_service):
        """Test parsing item with missing optional fields."""
        item = {
            "id": "12345",
            "name": "John Doe",
            "column_values": [],
        }

        contact = monday_service._parse_contact_from_item(item, "board123")

        assert contact["monday_id"] == "12345"
        assert contact["name"] == "John Doe"
        assert contact["email"] is None
        assert contact["phone"] is None
        assert contact["role_title"] is None
        assert contact["organization"] is None


class TestMondayServiceRetry:
    """Tests for retry logic with exponential backoff."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def monday_service(self, mock_db):
        """Create MondayService instance."""
        return MondayService(mock_db)

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_retry_on_rate_limit(self, mock_settings, monday_service):
        """Test that rate limit errors trigger retry."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_query") as mock_execute:
            # First call fails with rate limit, second succeeds
            mock_execute.side_effect = [
                ValueError("rate limit exceeded"),
                {"test": "data"},
            ]

            # Patch asyncio.sleep to avoid actual delays
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await monday_service._execute_with_retry("query")
                assert result == {"test": "data"}
                assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_retry_on_complexity_error(self, mock_settings, monday_service):
        """Test that complexity errors also trigger retry."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_query") as mock_execute:
            mock_execute.side_effect = [
                ValueError("Query complexity exceeded"),
                {"test": "data"},
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await monday_service._execute_with_retry("query")
                assert result == {"test": "data"}
                assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_max_retries_exceeded(self, mock_settings, monday_service):
        """Test that MondayRateLimitError raised after max retries."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        from app.services.monday_service import MondayRateLimitError

        with patch.object(monday_service, "_execute_query") as mock_execute:
            mock_execute.side_effect = ValueError("rate limit exceeded")

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(MondayRateLimitError):
                    await monday_service._execute_with_retry("query", max_retries=2)
                # Should have tried 3 times (initial + 2 retries)
                assert mock_execute.call_count == 3

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_non_rate_limit_error_not_retried(
        self, mock_settings, monday_service
    ):
        """Test that non-rate-limit errors are not retried."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        from app.services.monday_service import MondayAPIError

        with patch.object(monday_service, "_execute_query") as mock_execute:
            mock_execute.side_effect = ValueError("Invalid column ID")

            with pytest.raises(MondayAPIError):
                await monday_service._execute_with_retry("query")

            # Should only try once
            assert mock_execute.call_count == 1

    @pytest.mark.asyncio
    @patch("app.services.monday_service.settings")
    async def test_success_on_first_try(self, mock_settings, monday_service):
        """Test that successful first try doesn't retry."""
        mock_settings.monday_api_key = "test-key"
        mock_settings.monday_api_version = "2024-10"

        with patch.object(monday_service, "_execute_query") as mock_execute:
            mock_execute.return_value = {"test": "data"}

            result = await monday_service._execute_with_retry("query")
            assert result == {"test": "data"}
            assert mock_execute.call_count == 1
