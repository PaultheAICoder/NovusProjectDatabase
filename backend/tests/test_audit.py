"""Tests for audit log model and schemas."""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.audit import AuditAction, AuditLog
from app.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditLogSummary,
    FieldChange,
)


class TestAuditAction:
    """Tests for AuditAction enum."""

    def test_action_values(self):
        """All expected action values exist."""
        assert AuditAction.CREATE.value == "create"
        assert AuditAction.UPDATE.value == "update"
        assert AuditAction.DELETE.value == "delete"
        assert AuditAction.ARCHIVE.value == "archive"

    def test_action_is_string_enum(self):
        """AuditAction is a string enum."""
        assert isinstance(AuditAction.CREATE, str)
        assert AuditAction.CREATE == "create"


class TestAuditLogModel:
    """Tests for AuditLog SQLAlchemy model."""

    def test_model_repr(self):
        """Model has useful repr."""
        log = AuditLog(
            entity_type="project",
            entity_id=uuid4(),
            action=AuditAction.CREATE,
        )
        repr_str = repr(log)
        assert "AuditLog" in repr_str
        assert "project" in repr_str
        assert "create" in repr_str

    def test_model_tablename(self):
        """Model has correct table name."""
        assert AuditLog.__tablename__ == "audit_logs"


class TestAuditLogResponse:
    """Tests for AuditLogResponse schema."""

    def test_valid_response(self):
        """Valid response schema accepts all fields."""
        response = AuditLogResponse(
            id=uuid4(),
            entity_type="project",
            entity_id=uuid4(),
            action=AuditAction.UPDATE,
            user_id=uuid4(),
            changed_fields={"name": {"old": "Old Name", "new": "New Name"}},
            metadata={"ip": "192.168.1.1"},
            created_at=datetime.now(UTC),
        )
        assert response.entity_type == "project"
        assert response.action == AuditAction.UPDATE

    def test_nullable_fields(self):
        """Optional fields can be None."""
        response = AuditLogResponse(
            id=uuid4(),
            entity_type="contact",
            entity_id=uuid4(),
            action=AuditAction.DELETE,
            user_id=None,
            changed_fields=None,
            metadata=None,
            created_at=datetime.now(UTC),
        )
        assert response.user_id is None
        assert response.changed_fields is None

    def test_metadata_alias(self):
        """metadata alias maps correctly."""
        data = {
            "id": uuid4(),
            "entity_type": "project",
            "entity_id": uuid4(),
            "action": "create",
            "metadata": {"source": "api"},
            "created_at": datetime.now(UTC),
        }
        response = AuditLogResponse(**data)
        assert response.metadata_ == {"source": "api"}


class TestAuditLogListResponse:
    """Tests for paginated list response."""

    def test_list_response(self):
        """List response includes pagination info."""
        response = AuditLogListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
        )
        assert response.total == 0
        assert response.page == 1


class TestFieldChange:
    """Tests for FieldChange schema."""

    def test_field_change_with_values(self):
        """FieldChange accepts old and new values."""
        change = FieldChange(old="old_value", new="new_value")
        assert change.old == "old_value"
        assert change.new == "new_value"

    def test_field_change_with_none(self):
        """FieldChange accepts None for create/delete."""
        change = FieldChange(old=None, new="new_value")
        assert change.old is None


class TestAuditLogSummary:
    """Tests for AuditLogSummary schema."""

    def test_summary_fields(self):
        """Summary contains minimal fields."""
        summary = AuditLogSummary(
            id=uuid4(),
            action=AuditAction.CREATE,
            user_id=uuid4(),
            created_at=datetime.now(UTC),
        )
        assert summary.action == AuditAction.CREATE
