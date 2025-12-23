"""Tests for Monday.com admin API endpoints."""


class TestMondayEndpointsConfiguration:
    """Tests for Monday config endpoint."""

    def test_get_monday_config_configured(self):
        """Test MondayConfigResponse when configured."""
        from app.schemas.monday import MondayConfigResponse

        response = MondayConfigResponse(
            is_configured=True,
            organizations_board_id="123456",
            contacts_board_id="789012",
        )

        assert response.is_configured is True
        assert response.organizations_board_id == "123456"
        assert response.contacts_board_id == "789012"

    def test_get_monday_config_not_configured(self):
        """Test MondayConfigResponse when not configured."""
        from app.schemas.monday import MondayConfigResponse

        response = MondayConfigResponse(
            is_configured=False,
            organizations_board_id=None,
            contacts_board_id=None,
        )

        assert response.is_configured is False
        assert response.organizations_board_id is None
        assert response.contacts_board_id is None


class TestMondaySyncSchemas:
    """Tests for Monday sync Pydantic schemas."""

    def test_sync_trigger_request_with_board_id(self):
        """Test MondaySyncTriggerRequest with board_id override."""
        from app.models.monday_sync import MondaySyncType
        from app.schemas.monday import MondaySyncTriggerRequest

        request = MondaySyncTriggerRequest(
            sync_type=MondaySyncType.ORGANIZATIONS, board_id="custom_board_123"
        )

        assert request.sync_type == MondaySyncType.ORGANIZATIONS
        assert request.board_id == "custom_board_123"

    def test_sync_trigger_request_without_board_id(self):
        """Test MondaySyncTriggerRequest without board_id (uses default)."""
        from app.models.monday_sync import MondaySyncType
        from app.schemas.monday import MondaySyncTriggerRequest

        request = MondaySyncTriggerRequest(sync_type=MondaySyncType.CONTACTS)

        assert request.sync_type == MondaySyncType.CONTACTS
        assert request.board_id is None

    def test_sync_log_response_serialization(self):
        """Test MondaySyncLogResponse serializes from model correctly."""
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.models.monday_sync import (
            MondaySyncLog,
            MondaySyncStatus,
            MondaySyncType,
        )
        from app.schemas.monday import MondaySyncLogResponse

        sync_log = MondaySyncLog(
            id=uuid4(),
            sync_type=MondaySyncType.ORGANIZATIONS,
            status=MondaySyncStatus.COMPLETED,
            board_id="123456",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            items_processed=100,
            items_created=50,
            items_updated=30,
            items_skipped=20,
            error_message=None,
        )

        response = MondaySyncLogResponse.model_validate(sync_log)

        assert response.sync_type == MondaySyncType.ORGANIZATIONS
        assert response.status == MondaySyncStatus.COMPLETED
        assert response.items_processed == 100
        assert response.items_created == 50
        assert response.items_updated == 30
        assert response.items_skipped == 20

    def test_sync_status_response(self):
        """Test MondaySyncStatusResponse structure."""
        from app.schemas.monday import MondaySyncStatusResponse

        response = MondaySyncStatusResponse(
            is_configured=True,
            last_org_sync=None,
            last_contact_sync=None,
            recent_logs=[],
        )

        assert response.is_configured is True
        assert response.last_org_sync is None
        assert response.last_contact_sync is None
        assert response.recent_logs == []

    def test_board_info_response(self):
        """Test MondayBoardInfo and MondayBoardsResponse."""
        from app.schemas.monday import (
            MondayBoardColumn,
            MondayBoardInfo,
            MondayBoardsResponse,
        )

        column = MondayBoardColumn(id="col1", title="Email", type="email")
        board = MondayBoardInfo(id="123", name="Test Board", columns=[column])
        response = MondayBoardsResponse(boards=[board])

        assert len(response.boards) == 1
        assert response.boards[0].id == "123"
        assert response.boards[0].name == "Test Board"
        assert len(response.boards[0].columns) == 1
        assert response.boards[0].columns[0].id == "col1"


class TestMondayContactSearchSchemas:
    """Tests for Monday contact search schemas."""

    def test_monday_contact_match_schema(self):
        """Test MondayContactMatch schema structure."""
        from app.schemas.monday import MondayContactMatch

        match = MondayContactMatch(
            monday_id="12345",
            name="John Doe",
            email="john@example.com",
            phone="555-1234",
            role_title="Manager",
            organization="Acme Corp",
            board_id="board123",
        )

        assert match.monday_id == "12345"
        assert match.name == "John Doe"
        assert match.email == "john@example.com"
        assert match.phone == "555-1234"
        assert match.role_title == "Manager"
        assert match.organization == "Acme Corp"
        assert match.board_id == "board123"

    def test_monday_contact_match_optional_fields(self):
        """Test MondayContactMatch with only required fields."""
        from app.schemas.monday import MondayContactMatch

        match = MondayContactMatch(
            monday_id="12345",
            name="John Doe",
            board_id="board123",
        )

        assert match.monday_id == "12345"
        assert match.name == "John Doe"
        assert match.email is None
        assert match.phone is None
        assert match.role_title is None
        assert match.organization is None

    def test_monday_contact_search_response(self):
        """Test MondayContactSearchResponse schema."""
        from app.schemas.monday import MondayContactMatch, MondayContactSearchResponse

        match = MondayContactMatch(
            monday_id="12345",
            name="John Doe",
            board_id="board123",
        )

        response = MondayContactSearchResponse(
            matches=[match],
            total_matches=1,
            query="John",
            board_id="board123",
            has_more=False,
            cursor=None,
        )

        assert len(response.matches) == 1
        assert response.total_matches == 1
        assert response.query == "John"
        assert response.board_id == "board123"
        assert response.has_more is False
        assert response.cursor is None

    def test_monday_contact_search_response_with_pagination(self):
        """Test MondayContactSearchResponse with pagination."""
        from app.schemas.monday import MondayContactSearchResponse

        response = MondayContactSearchResponse(
            matches=[],
            total_matches=0,
            query="test",
            board_id="board123",
            has_more=True,
            cursor="next_page_cursor",
        )

        assert response.has_more is True
        assert response.cursor == "next_page_cursor"


class TestMondaySyncModels:
    """Tests for Monday sync database models."""

    def test_sync_type_enum_values(self):
        """Test MondaySyncType enum has correct values."""
        from app.models.monday_sync import MondaySyncType

        assert MondaySyncType.ORGANIZATIONS.value == "organizations"
        assert MondaySyncType.CONTACTS.value == "contacts"

    def test_sync_status_enum_values(self):
        """Test MondaySyncStatus enum has correct values."""
        from app.models.monday_sync import MondaySyncStatus

        assert MondaySyncStatus.PENDING.value == "pending"
        assert MondaySyncStatus.IN_PROGRESS.value == "in_progress"
        assert MondaySyncStatus.COMPLETED.value == "completed"
        assert MondaySyncStatus.FAILED.value == "failed"

    def test_sync_log_repr(self):
        """Test MondaySyncLog string representation."""
        from app.models.monday_sync import (
            MondaySyncLog,
            MondaySyncStatus,
            MondaySyncType,
        )

        log = MondaySyncLog(
            sync_type=MondaySyncType.ORGANIZATIONS,
            status=MondaySyncStatus.COMPLETED,
            board_id="123",
        )

        assert "organizations" in repr(log)
        assert "completed" in repr(log)
