"""Tests for AuditService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.audit import AuditAction
from app.services.audit_service import AuditService


class TestComputeDiff:
    """Tests for compute_diff static method."""

    def test_compute_diff_no_changes(self):
        """No changes returns empty dict."""
        old = {"name": "Test", "value": 123}
        new = {"name": "Test", "value": 123}
        result = AuditService.compute_diff(old, new)
        assert result == {}

    def test_compute_diff_single_change(self):
        """Single field change is captured."""
        old = {"name": "Old Name", "value": 123}
        new = {"name": "New Name", "value": 123}
        result = AuditService.compute_diff(old, new)
        assert result == {"name": {"old": "Old Name", "new": "New Name"}}

    def test_compute_diff_multiple_changes(self):
        """Multiple field changes are captured."""
        old = {"name": "Old", "status": "active"}
        new = {"name": "New", "status": "completed"}
        result = AuditService.compute_diff(old, new)
        assert "name" in result
        assert "status" in result

    def test_compute_diff_added_field(self):
        """New field is captured as change from None."""
        old = {"name": "Test"}
        new = {"name": "Test", "description": "Added"}
        result = AuditService.compute_diff(old, new)
        assert result == {"description": {"old": None, "new": "Added"}}

    def test_compute_diff_removed_field(self):
        """Removed field is captured as change to None."""
        old = {"name": "Test", "description": "Removed"}
        new = {"name": "Test"}
        result = AuditService.compute_diff(old, new)
        assert result == {"description": {"old": "Removed", "new": None}}

    def test_compute_diff_handles_none_values(self):
        """None values are handled correctly."""
        old = {"name": None}
        new = {"name": "Value"}
        result = AuditService.compute_diff(old, new)
        assert result == {"name": {"old": None, "new": "Value"}}

    def test_compute_diff_nested_dict_change(self):
        """Nested dict changes are captured."""
        old = {"meta": {"key": "old"}}
        new = {"meta": {"key": "new"}}
        result = AuditService.compute_diff(old, new)
        assert "meta" in result


class TestLogCreate:
    """Tests for log_create method."""

    @pytest.mark.asyncio
    async def test_log_create_creates_audit_record(self):
        """log_create creates AuditLog with action=CREATE."""
        entity_id = uuid4()
        user_id = uuid4()

        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = AuditService(mock_db)
        await service.log_create(
            entity_type="project",
            entity_id=entity_id,
            entity_data={"name": "Test Project", "status": "active"},
            user_id=user_id,
        )

        assert mock_db.add.called
        add_call = mock_db.add.call_args
        audit_log = add_call[0][0]

        assert audit_log.entity_type == "project"
        assert audit_log.entity_id == entity_id
        assert audit_log.action == AuditAction.CREATE
        assert audit_log.user_id == user_id
        assert "name" in audit_log.changed_fields
        assert audit_log.changed_fields["name"]["old"] is None
        assert audit_log.changed_fields["name"]["new"] == "Test Project"

    @pytest.mark.asyncio
    async def test_log_create_with_metadata(self):
        """log_create stores metadata."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = AuditService(mock_db)
        metadata = {"ip": "192.168.1.1", "user_agent": "TestClient"}

        await service.log_create(
            entity_type="project",
            entity_id=uuid4(),
            entity_data={"name": "Test"},
            metadata=metadata,
        )

        add_call = mock_db.add.call_args
        audit_log = add_call[0][0]
        assert audit_log.metadata_ == metadata

    @pytest.mark.asyncio
    async def test_log_create_without_user_id(self):
        """log_create works for system-triggered actions."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = AuditService(mock_db)
        await service.log_create(
            entity_type="project",
            entity_id=uuid4(),
            entity_data={"name": "Test"},
            user_id=None,
        )

        add_call = mock_db.add.call_args
        audit_log = add_call[0][0]
        assert audit_log.user_id is None


class TestLogUpdate:
    """Tests for log_update method."""

    @pytest.mark.asyncio
    async def test_log_update_creates_audit_record(self):
        """log_update creates AuditLog with computed diff."""
        entity_id = uuid4()
        user_id = uuid4()

        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = AuditService(mock_db)
        await service.log_update(
            entity_type="project",
            entity_id=entity_id,
            old_data={"name": "Old Name", "status": "active"},
            new_data={"name": "New Name", "status": "active"},
            user_id=user_id,
        )

        assert mock_db.add.called
        add_call = mock_db.add.call_args
        audit_log = add_call[0][0]

        assert audit_log.entity_type == "project"
        assert audit_log.action == AuditAction.UPDATE
        assert "name" in audit_log.changed_fields
        assert "status" not in audit_log.changed_fields  # No change

    @pytest.mark.asyncio
    async def test_log_update_returns_none_when_no_changes(self):
        """log_update returns None if no fields changed."""
        mock_db = AsyncMock()

        service = AuditService(mock_db)
        result = await service.log_update(
            entity_type="project",
            entity_id=uuid4(),
            old_data={"name": "Same", "value": 123},
            new_data={"name": "Same", "value": 123},
            user_id=uuid4(),
        )

        assert result is None
        assert not mock_db.add.called

    @pytest.mark.asyncio
    async def test_log_update_captures_multiple_changes(self):
        """log_update captures all changed fields."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = AuditService(mock_db)
        await service.log_update(
            entity_type="project",
            entity_id=uuid4(),
            old_data={"name": "Old", "status": "active", "description": "Old desc"},
            new_data={"name": "New", "status": "completed", "description": "Old desc"},
            user_id=uuid4(),
        )

        add_call = mock_db.add.call_args
        audit_log = add_call[0][0]

        assert len(audit_log.changed_fields) == 2
        assert "name" in audit_log.changed_fields
        assert "status" in audit_log.changed_fields
        assert "description" not in audit_log.changed_fields


class TestLogDelete:
    """Tests for log_delete method."""

    @pytest.mark.asyncio
    async def test_log_delete_creates_audit_record(self):
        """log_delete creates AuditLog with action=DELETE."""
        entity_id = uuid4()
        user_id = uuid4()

        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = AuditService(mock_db)
        await service.log_delete(
            entity_type="project",
            entity_id=entity_id,
            entity_data={"name": "Deleted Project", "status": "active"},
            user_id=user_id,
        )

        assert mock_db.add.called
        add_call = mock_db.add.call_args
        audit_log = add_call[0][0]

        assert audit_log.entity_type == "project"
        assert audit_log.entity_id == entity_id
        assert audit_log.action == AuditAction.DELETE
        assert "name" in audit_log.changed_fields
        assert audit_log.changed_fields["name"]["old"] == "Deleted Project"
        assert audit_log.changed_fields["name"]["new"] is None

    @pytest.mark.asyncio
    async def test_log_delete_preserves_all_entity_data(self):
        """log_delete preserves all non-null fields as old values."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = AuditService(mock_db)
        entity_data = {
            "name": "Test",
            "status": "active",
            "description": "Desc",
            "empty_field": None,  # Should be excluded
        }

        await service.log_delete(
            entity_type="project",
            entity_id=uuid4(),
            entity_data=entity_data,
            user_id=uuid4(),
        )

        add_call = mock_db.add.call_args
        audit_log = add_call[0][0]

        assert len(audit_log.changed_fields) == 3  # Excludes None value
        assert "empty_field" not in audit_log.changed_fields


class TestSerializeEntity:
    """Tests for serialize_entity static method."""

    def test_serialize_entity_basic_fields(self):
        """serialize_entity extracts basic field types."""
        mock_entity = MagicMock()
        mock_entity.name = "Test"
        mock_entity.count = 42
        mock_entity.active = True
        mock_entity._sa_instance_state = "private"

        result = AuditService.serialize_entity(mock_entity)

        assert result["name"] == "Test"
        assert result["count"] == 42
        assert result["active"] is True
        assert "_sa_instance_state" not in result

    def test_serialize_entity_uuid_conversion(self):
        """serialize_entity converts UUIDs to strings."""
        test_uuid = uuid4()
        mock_entity = MagicMock()
        mock_entity.id = test_uuid
        mock_entity._sa_instance_state = "private"

        result = AuditService.serialize_entity(mock_entity)

        assert result["id"] == str(test_uuid)

    def test_serialize_entity_datetime_conversion(self):
        """serialize_entity converts datetime to ISO format."""
        test_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        mock_entity = MagicMock()
        mock_entity.created_at = test_dt
        mock_entity._sa_instance_state = "private"

        result = AuditService.serialize_entity(mock_entity)

        assert result["created_at"] == test_dt.isoformat()

    def test_serialize_entity_enum_conversion(self):
        """serialize_entity converts enums to their value."""
        mock_entity = MagicMock()
        mock_entity.status = AuditAction.CREATE
        mock_entity._sa_instance_state = "private"

        result = AuditService.serialize_entity(mock_entity)

        assert result["status"] == "create"

    def test_serialize_entity_with_include_fields(self):
        """serialize_entity respects include_fields."""
        mock_entity = MagicMock()
        mock_entity.name = "Test"
        mock_entity.secret = "hidden"
        mock_entity._sa_instance_state = "private"

        result = AuditService.serialize_entity(
            mock_entity,
            include_fields=["name"],
        )

        assert "name" in result
        assert "secret" not in result

    def test_serialize_entity_with_exclude_fields(self):
        """serialize_entity respects exclude_fields."""
        mock_entity = MagicMock()
        mock_entity.name = "Test"
        mock_entity.secret = "hidden"
        mock_entity._sa_instance_state = "private"

        result = AuditService.serialize_entity(
            mock_entity,
            exclude_fields=["secret"],
        )

        assert "name" in result
        assert "secret" not in result
