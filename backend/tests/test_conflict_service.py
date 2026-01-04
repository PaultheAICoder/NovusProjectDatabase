"""Tests for ConflictService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.monday_sync import RecordSyncStatus, SyncConflict
from app.schemas.monday import ConflictResolutionType
from app.services.conflict_service import ConflictService


class TestListUnresolved:
    """Tests for list_unresolved method."""

    @pytest.mark.asyncio
    async def test_list_unresolved_returns_only_unresolved_conflicts(self):
        """Test that list_unresolved returns only conflicts without resolved_at."""
        conflict_id = uuid4()
        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.resolved_at = None
        mock_conflict.detected_at = datetime.now(UTC)

        mock_db = AsyncMock()
        # Mock count query
        mock_db.scalar.return_value = 1
        # Mock results query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_conflict]
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        conflicts, total = await service.list_unresolved()

        assert total == 1
        assert len(conflicts) == 1
        assert conflicts[0].id == conflict_id

    @pytest.mark.asyncio
    async def test_list_unresolved_filters_by_entity_type(self):
        """Test that entity_type filter is applied."""
        mock_db = AsyncMock()
        mock_db.scalar.return_value = 0
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        conflicts, total = await service.list_unresolved(entity_type="contact")

        assert total == 0
        assert len(conflicts) == 0
        # Verify execute was called (query was built)
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_list_unresolved_pagination_works(self):
        """Test pagination with page and page_size."""
        mock_conflict_1 = MagicMock(spec=SyncConflict)
        mock_conflict_1.id = uuid4()
        mock_conflict_1.resolved_at = None

        mock_db = AsyncMock()
        mock_db.scalar.return_value = 10  # Total 10 items
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_conflict_1]
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        conflicts, total = await service.list_unresolved(page=2, page_size=5)

        assert total == 10
        assert len(conflicts) == 1


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_conflict(self):
        """Test that get_by_id returns the conflict when found."""
        conflict_id = uuid4()
        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conflict
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        result = await service.get_by_id(conflict_id)

        assert result is not None
        assert result.id == conflict_id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_missing(self):
        """Test that get_by_id returns None when not found."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        result = await service.get_by_id(uuid4())

        assert result is None


class TestResolve:
    """Tests for resolve method."""

    @pytest.mark.asyncio
    @patch("app.services.sync_service.sync_contact_to_monday")
    async def test_resolve_keep_npd_triggers_sync_to_monday(
        self, mock_sync_contact_to_monday
    ):
        """Test that keep_npd resolution triggers sync to Monday."""
        conflict_id = uuid4()
        entity_id = uuid4()
        user_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.entity_type = "contact"
        mock_conflict.entity_id = entity_id
        mock_conflict.resolved_at = None
        mock_conflict.npd_data = {"name": "NPD Name"}
        mock_conflict.monday_data = {"name": "Monday Name"}
        mock_conflict.conflict_fields = ["name"]

        mock_contact = MagicMock()
        mock_contact.id = entity_id
        mock_contact.sync_status = RecordSyncStatus.CONFLICT

        mock_db = AsyncMock()
        # Mock get_by_id
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_conflict
        # Mock get_entity (contact)
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_contact

        mock_db.execute.side_effect = [mock_result1, mock_result2]
        mock_db.flush = AsyncMock()

        mock_sync_contact_to_monday.return_value = None

        service = ConflictService(mock_db)
        result = await service.resolve(
            conflict_id=conflict_id,
            resolution_type=ConflictResolutionType.KEEP_NPD,
            resolved_by_id=user_id,
        )

        assert result is not None
        mock_sync_contact_to_monday.assert_called_once_with(entity_id)
        assert mock_conflict.resolved_at is not None
        assert mock_conflict.resolution_type == "keep_npd"
        assert mock_conflict.resolved_by_id == user_id
        assert mock_contact.sync_status == RecordSyncStatus.SYNCED

    @pytest.mark.asyncio
    async def test_resolve_keep_monday_updates_npd_entity(self):
        """Test that keep_monday resolution updates NPD entity."""
        conflict_id = uuid4()
        entity_id = uuid4()
        user_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.entity_type = "contact"
        mock_conflict.entity_id = entity_id
        mock_conflict.resolved_at = None
        mock_conflict.npd_data = {"name": "NPD Name"}
        mock_conflict.monday_data = {"name": "Monday Name"}
        mock_conflict.conflict_fields = ["name"]

        mock_contact = MagicMock()
        mock_contact.id = entity_id
        mock_contact.name = "NPD Name"
        mock_contact.sync_status = RecordSyncStatus.CONFLICT

        mock_db = AsyncMock()
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_conflict
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_contact

        mock_db.execute.side_effect = [mock_result1, mock_result2]
        mock_db.flush = AsyncMock()

        service = ConflictService(mock_db)
        result = await service.resolve(
            conflict_id=conflict_id,
            resolution_type=ConflictResolutionType.KEEP_MONDAY,
            resolved_by_id=user_id,
        )

        assert result is not None
        assert mock_conflict.resolution_type == "keep_monday"
        # Verify entity was updated
        assert mock_contact.name == "Monday Name"
        assert mock_contact.sync_status == RecordSyncStatus.SYNCED

    @pytest.mark.asyncio
    @patch("app.services.sync_service.sync_contact_to_monday")
    async def test_resolve_merge_applies_field_selections(
        self, mock_sync_contact_to_monday
    ):
        """Test that merge resolution applies field-level selections."""
        conflict_id = uuid4()
        entity_id = uuid4()
        user_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.entity_type = "contact"
        mock_conflict.entity_id = entity_id
        mock_conflict.resolved_at = None
        mock_conflict.npd_data = {"name": "NPD Name", "email": "npd@example.com"}
        mock_conflict.monday_data = {
            "name": "Monday Name",
            "email": "monday@example.com",
        }
        mock_conflict.conflict_fields = ["name", "email"]

        mock_contact = MagicMock()
        mock_contact.id = entity_id
        mock_contact.name = "NPD Name"
        mock_contact.email = "npd@example.com"
        mock_contact.sync_status = RecordSyncStatus.CONFLICT

        mock_db = AsyncMock()
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_conflict
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_contact

        mock_db.execute.side_effect = [mock_result1, mock_result2]
        mock_db.flush = AsyncMock()

        mock_sync_contact_to_monday.return_value = None

        service = ConflictService(mock_db)
        result = await service.resolve(
            conflict_id=conflict_id,
            resolution_type=ConflictResolutionType.MERGE,
            resolved_by_id=user_id,
            merge_selections={"name": "npd", "email": "monday"},
        )

        assert result is not None
        assert mock_conflict.resolution_type == "merge"
        # name should be kept as NPD (not changed)
        # email should be updated to Monday value
        assert mock_contact.email == "monday@example.com"
        mock_sync_contact_to_monday.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_already_resolved_conflict_returns_existing(self):
        """Test that already resolved conflict is returned without changes."""
        conflict_id = uuid4()
        user_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.resolved_at = datetime.now(UTC)  # Already resolved
        mock_conflict.resolution_type = "keep_npd"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conflict
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        result = await service.resolve(
            conflict_id=conflict_id,
            resolution_type=ConflictResolutionType.KEEP_NPD,
            resolved_by_id=user_id,
        )

        assert result is not None
        assert result.resolution_type == "keep_npd"
        # Flush should not be called since we returned early
        mock_db.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_missing_conflict_returns_none(self):
        """Test that missing conflict returns None."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        result = await service.resolve(
            conflict_id=uuid4(),
            resolution_type=ConflictResolutionType.KEEP_NPD,
            resolved_by_id=uuid4(),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_merge_without_selections_raises_error(self):
        """Test that merge without merge_selections raises ValueError."""
        conflict_id = uuid4()
        entity_id = uuid4()
        user_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.entity_type = "contact"
        mock_conflict.entity_id = entity_id
        mock_conflict.resolved_at = None
        mock_conflict.conflict_fields = ["name"]

        mock_contact = MagicMock()
        mock_contact.id = entity_id

        mock_db = AsyncMock()
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_conflict
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_contact

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        service = ConflictService(mock_db)

        with pytest.raises(ValueError, match="merge_selections"):
            await service.resolve(
                conflict_id=conflict_id,
                resolution_type=ConflictResolutionType.MERGE,
                resolved_by_id=user_id,
                merge_selections=None,  # Missing!
            )


class TestGetConflictStats:
    """Tests for get_conflict_stats method."""

    @pytest.mark.asyncio
    async def test_get_conflict_stats_returns_counts(self):
        """Test that stats returns correct counts."""
        mock_db = AsyncMock()
        # Return 5 unresolved, then 3 resolved
        mock_db.scalar.side_effect = [5, 3]

        service = ConflictService(mock_db)
        stats = await service.get_conflict_stats()

        assert stats["unresolved"] == 5
        assert stats["resolved"] == 3
        assert stats["total"] == 8


class TestGetEntity:
    """Tests for _get_entity helper method."""

    @pytest.mark.asyncio
    async def test_get_entity_returns_contact(self):
        """Test that _get_entity returns contact for contact type."""
        entity_id = uuid4()
        mock_contact = MagicMock()
        mock_contact.id = entity_id

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_contact
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        result = await service._get_entity("contact", entity_id)

        assert result is not None
        assert result.id == entity_id

    @pytest.mark.asyncio
    async def test_get_entity_returns_organization(self):
        """Test that _get_entity returns organization for organization type."""
        entity_id = uuid4()
        mock_org = MagicMock()
        mock_org.id = entity_id

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        result = await service._get_entity("organization", entity_id)

        assert result is not None
        assert result.id == entity_id

    @pytest.mark.asyncio
    async def test_get_entity_returns_none_for_unknown_type(self):
        """Test that _get_entity returns None for unknown type."""
        mock_db = AsyncMock()

        service = ConflictService(mock_db)
        result = await service._get_entity("unknown", uuid4())

        assert result is None


class TestApplyKeepMonday:
    """Tests for _apply_keep_monday helper method."""

    @pytest.mark.asyncio
    async def test_apply_keep_monday_handles_nested_values(self):
        """Test that nested Monday.com values are handled correctly."""
        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = uuid4()
        mock_conflict.entity_type = "contact"
        mock_conflict.monday_data = {
            "email": {"email": "test@example.com", "text": "test@example.com"},
            "name": "Plain Name",
        }
        mock_conflict.conflict_fields = ["email", "name"]

        mock_contact = MagicMock()
        mock_contact.id = uuid4()
        mock_contact.email = "old@example.com"
        mock_contact.name = "Old Name"

        mock_db = AsyncMock()

        service = ConflictService(mock_db)
        await service._apply_keep_monday(mock_conflict, mock_contact)

        # Nested email value should be extracted
        assert mock_contact.email == "test@example.com"
        # Plain value should be applied directly
        assert mock_contact.name == "Plain Name"


class TestBulkResolve:
    """Tests for bulk_resolve method."""

    @pytest.mark.asyncio
    async def test_bulk_resolve_processes_multiple_conflicts(self):
        """Test that bulk_resolve processes multiple conflicts."""
        conflict_id_1 = uuid4()
        conflict_id_2 = uuid4()
        entity_id_1 = uuid4()
        entity_id_2 = uuid4()
        user_id = uuid4()

        # Create mock conflicts
        mock_conflict_1 = MagicMock(spec=SyncConflict)
        mock_conflict_1.id = conflict_id_1
        mock_conflict_1.entity_type = "contact"
        mock_conflict_1.entity_id = entity_id_1
        mock_conflict_1.resolved_at = None
        mock_conflict_1.npd_data = {"name": "NPD 1"}
        mock_conflict_1.monday_data = {"name": "Monday 1"}
        mock_conflict_1.conflict_fields = ["name"]

        mock_conflict_2 = MagicMock(spec=SyncConflict)
        mock_conflict_2.id = conflict_id_2
        mock_conflict_2.entity_type = "contact"
        mock_conflict_2.entity_id = entity_id_2
        mock_conflict_2.resolved_at = None
        mock_conflict_2.npd_data = {"name": "NPD 2"}
        mock_conflict_2.monday_data = {"name": "Monday 2"}
        mock_conflict_2.conflict_fields = ["name"]

        mock_contact_1 = MagicMock()
        mock_contact_1.id = entity_id_1
        mock_contact_1.name = "NPD 1"

        mock_contact_2 = MagicMock()
        mock_contact_2.id = entity_id_2
        mock_contact_2.name = "NPD 2"

        mock_db = AsyncMock()
        # Mock results for first conflict
        mock_result_1 = MagicMock()
        mock_result_1.scalar_one_or_none.return_value = mock_conflict_1
        mock_result_entity_1 = MagicMock()
        mock_result_entity_1.scalar_one_or_none.return_value = mock_contact_1
        # Mock results for second conflict
        mock_result_2 = MagicMock()
        mock_result_2.scalar_one_or_none.return_value = mock_conflict_2
        mock_result_entity_2 = MagicMock()
        mock_result_entity_2.scalar_one_or_none.return_value = mock_contact_2

        mock_db.execute.side_effect = [
            mock_result_1,
            mock_result_entity_1,
            mock_result_2,
            mock_result_entity_2,
        ]
        mock_db.flush = AsyncMock()

        service = ConflictService(mock_db)
        results = await service.bulk_resolve(
            conflict_ids=[conflict_id_1, conflict_id_2],
            resolution_type=ConflictResolutionType.KEEP_MONDAY,
            resolved_by_id=user_id,
        )

        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is True
        assert results[0]["conflict_id"] == conflict_id_1
        assert results[1]["conflict_id"] == conflict_id_2

    @pytest.mark.asyncio
    async def test_bulk_resolve_rejects_merge_resolution_type(self):
        """Test that bulk_resolve raises error for merge resolution."""
        mock_db = AsyncMock()
        service = ConflictService(mock_db)

        with pytest.raises(ValueError, match="does not support merge"):
            await service.bulk_resolve(
                conflict_ids=[uuid4()],
                resolution_type=ConflictResolutionType.MERGE,
                resolved_by_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_bulk_resolve_handles_not_found_conflicts(self):
        """Test that missing conflicts are marked as failed."""
        conflict_id = uuid4()
        user_id = uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        results = await service.bulk_resolve(
            conflict_ids=[conflict_id],
            resolution_type=ConflictResolutionType.KEEP_NPD,
            resolved_by_id=user_id,
        )

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "not found" in results[0]["error"].lower()

    @pytest.mark.asyncio
    async def test_bulk_resolve_continues_on_individual_failure(self):
        """Test that bulk_resolve continues processing after individual failure."""
        conflict_id_1 = uuid4()
        conflict_id_2 = uuid4()
        entity_id_2 = uuid4()
        user_id = uuid4()

        # First conflict will fail (not found)
        # Second conflict will succeed
        mock_conflict_2 = MagicMock(spec=SyncConflict)
        mock_conflict_2.id = conflict_id_2
        mock_conflict_2.entity_type = "contact"
        mock_conflict_2.entity_id = entity_id_2
        mock_conflict_2.resolved_at = None
        mock_conflict_2.npd_data = {"name": "NPD"}
        mock_conflict_2.monday_data = {"name": "Monday"}
        mock_conflict_2.conflict_fields = ["name"]

        mock_contact_2 = MagicMock()
        mock_contact_2.id = entity_id_2
        mock_contact_2.name = "NPD"

        mock_db = AsyncMock()
        mock_result_1 = MagicMock()
        mock_result_1.scalar_one_or_none.return_value = None  # Not found
        mock_result_2 = MagicMock()
        mock_result_2.scalar_one_or_none.return_value = mock_conflict_2
        mock_result_entity_2 = MagicMock()
        mock_result_entity_2.scalar_one_or_none.return_value = mock_contact_2

        mock_db.execute.side_effect = [
            mock_result_1,  # First conflict not found
            mock_result_2,
            mock_result_entity_2,  # Second conflict found
        ]
        mock_db.flush = AsyncMock()

        service = ConflictService(mock_db)
        results = await service.bulk_resolve(
            conflict_ids=[conflict_id_1, conflict_id_2],
            resolution_type=ConflictResolutionType.KEEP_MONDAY,
            resolved_by_id=user_id,
        )

        assert len(results) == 2
        assert results[0]["success"] is False
        assert results[1]["success"] is True


class TestFieldWhitelistValidation:
    """Tests for field whitelist security validation."""

    @pytest.mark.asyncio
    async def test_apply_keep_monday_skips_invalid_field(self):
        """Test that _apply_keep_monday skips fields not in whitelist."""
        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = uuid4()
        mock_conflict.entity_type = "contact"
        # Include both valid and invalid fields
        mock_conflict.monday_data = {
            "email": "test@example.com",
            "id": "malicious-id",  # Dangerous - should be skipped
            "__dict__": {},  # Dangerous - should be skipped
            "created_at": "2024-01-01",  # System field - should be skipped
        }
        mock_conflict.conflict_fields = ["email", "id", "__dict__", "created_at"]

        mock_contact = MagicMock()
        mock_contact.id = uuid4()
        mock_contact.email = "old@example.com"

        mock_db = AsyncMock()

        service = ConflictService(mock_db)
        await service._apply_keep_monday(mock_conflict, mock_contact)

        # Valid email field should be updated
        assert mock_contact.email == "test@example.com"

        # Verify setattr was NOT called for dangerous fields
        # The id attribute should remain as the MagicMock's uuid4, not "malicious-id"
        assert mock_contact.id != "malicious-id"

    @pytest.mark.asyncio
    async def test_apply_merge_skips_invalid_field(self):
        """Test that _apply_merge skips fields not in whitelist."""
        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = uuid4()
        mock_conflict.entity_type = "organization"
        mock_conflict.monday_data = {
            "name": "New Org Name",
            "id": "malicious-id",  # Should be skipped
            "_sa_instance_state": {},  # SQLAlchemy internal - should be skipped
        }
        mock_conflict.conflict_fields = ["name", "id", "_sa_instance_state"]

        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.name = "Old Org Name"

        mock_db = AsyncMock()

        service = ConflictService(mock_db)
        with patch("app.services.sync_service.sync_organization_to_monday"):
            await service._apply_merge(
                mock_conflict,
                mock_org,
                merge_selections={
                    "name": "monday",
                    "id": "monday",  # Attacker trying to change ID
                    "_sa_instance_state": "monday",
                },
            )

        # Valid name field should be updated
        assert mock_org.name == "New Org Name"

        # Dangerous fields should NOT have been set
        assert mock_org.id != "malicious-id"

    @pytest.mark.asyncio
    async def test_valid_contact_fields_still_work(self):
        """Test that valid fields in whitelist are applied correctly."""
        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = uuid4()
        mock_conflict.entity_type = "contact"
        mock_conflict.monday_data = {
            "email": "new@example.com",
            "phone": "555-1234",
            "notes": "Updated notes",
        }
        mock_conflict.conflict_fields = ["email", "phone", "notes"]

        mock_contact = MagicMock()
        mock_contact.id = uuid4()
        mock_contact.email = "old@example.com"
        mock_contact.phone = "555-0000"
        mock_contact.notes = "Old notes"

        mock_db = AsyncMock()

        service = ConflictService(mock_db)
        await service._apply_keep_monday(mock_conflict, mock_contact)

        # All valid fields should be updated
        assert mock_contact.email == "new@example.com"
        assert mock_contact.phone == "555-1234"
        assert mock_contact.notes == "Updated notes"

    @pytest.mark.asyncio
    async def test_valid_organization_fields_still_work(self):
        """Test that valid organization fields in whitelist are applied."""
        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = uuid4()
        mock_conflict.entity_type = "organization"
        mock_conflict.monday_data = {
            "name": "Acme Corp",
            "notes": "Important client",
            "address_city": "New York",
        }
        mock_conflict.conflict_fields = ["name", "notes", "address_city"]

        mock_org = MagicMock()
        mock_org.id = uuid4()
        mock_org.name = "Old Name"
        mock_org.notes = "Old notes"
        mock_org.address_city = "Boston"

        mock_db = AsyncMock()

        service = ConflictService(mock_db)
        await service._apply_keep_monday(mock_conflict, mock_org)

        # All valid fields should be updated
        assert mock_org.name == "Acme Corp"
        assert mock_org.notes == "Important client"
        assert mock_org.address_city == "New York"
