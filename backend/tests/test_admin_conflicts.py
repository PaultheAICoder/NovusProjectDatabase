"""Tests for admin conflict management endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.monday_sync import SyncConflict
from app.schemas.monday import (
    BulkConflictResolveRequest,
    BulkConflictResolveResponse,
    BulkResolveResult,
    ConflictListResponse,
    ConflictResolutionType,
    ConflictResolveRequest,
    SyncConflictResponse,
)
from app.services.conflict_service import ConflictService


class TestConflictServiceIntegration:
    """Integration tests for ConflictService with endpoint logic."""

    @pytest.mark.asyncio
    async def test_list_conflicts_returns_paginated_results(self):
        """Test that list_unresolved returns paginated conflict list."""
        conflict_id = uuid4()
        entity_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.entity_type = "contact"
        mock_conflict.entity_id = entity_id
        mock_conflict.monday_item_id = "123456"
        mock_conflict.npd_data = {"name": "NPD Name"}
        mock_conflict.monday_data = {"name": "Monday Name"}
        mock_conflict.conflict_fields = ["name"]
        mock_conflict.detected_at = datetime.now(UTC)
        mock_conflict.resolved_at = None
        mock_conflict.resolution_type = None
        mock_conflict.resolved_by_id = None

        mock_db = AsyncMock()
        # Mock count query
        mock_db.scalar.return_value = 1
        # Mock results query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_conflict]
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        conflicts, total = await service.list_unresolved(
            page=1,
            page_size=20,
            entity_type=None,
        )

        assert total == 1
        assert len(conflicts) == 1
        assert conflicts[0].entity_type == "contact"

        # Verify can create response
        response = ConflictListResponse(
            items=[SyncConflictResponse.model_validate(c) for c in conflicts],
            total=total,
            page=1,
            page_size=20,
            has_more=False,
        )
        assert isinstance(response, ConflictListResponse)

    @pytest.mark.asyncio
    async def test_list_conflicts_filters_by_entity_type(self):
        """Test that entity_type filter is passed to service."""
        mock_db = AsyncMock()
        mock_db.scalar.return_value = 0
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        conflicts, total = await service.list_unresolved(
            page=1,
            page_size=20,
            entity_type="organization",
        )

        assert total == 0
        assert len(conflicts) == 0


class TestGetConflictLogic:
    """Tests for get_sync_conflict endpoint logic."""

    @pytest.mark.asyncio
    async def test_get_conflict_returns_details(self):
        """Test that get_by_id returns conflict details."""
        conflict_id = uuid4()
        entity_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.entity_type = "contact"
        mock_conflict.entity_id = entity_id
        mock_conflict.monday_item_id = "123456"
        mock_conflict.npd_data = {"name": "NPD Name"}
        mock_conflict.monday_data = {"name": "Monday Name"}
        mock_conflict.conflict_fields = ["name"]
        mock_conflict.detected_at = datetime.now(UTC)
        mock_conflict.resolved_at = None
        mock_conflict.resolution_type = None
        mock_conflict.resolved_by_id = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conflict
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        conflict = await service.get_by_id(conflict_id)

        assert conflict is not None
        assert conflict.entity_type == "contact"

        # Verify can create response
        response = SyncConflictResponse.model_validate(conflict)
        assert isinstance(response, SyncConflictResponse)

    @pytest.mark.asyncio
    async def test_get_conflict_returns_none_when_not_found(self):
        """Test that get_by_id returns None for missing conflict."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = ConflictService(mock_db)
        conflict = await service.get_by_id(uuid4())

        assert conflict is None


class TestResolveConflictLogic:
    """Tests for resolve_sync_conflict endpoint logic."""

    @pytest.mark.asyncio
    @patch("app.services.sync_service.sync_contact_to_monday")
    async def test_resolve_conflict_keep_npd(self, mock_sync):
        """Test resolving conflict with keep_npd."""
        conflict_id = uuid4()
        entity_id = uuid4()
        user_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.entity_type = "contact"
        mock_conflict.entity_id = entity_id
        mock_conflict.monday_item_id = "123456"
        mock_conflict.npd_data = {"name": "NPD Name"}
        mock_conflict.monday_data = {"name": "Monday Name"}
        mock_conflict.conflict_fields = ["name"]
        mock_conflict.detected_at = datetime.now(UTC)
        mock_conflict.resolved_at = None
        mock_conflict.resolution_type = None
        mock_conflict.resolved_by_id = None

        mock_contact = MagicMock()
        mock_contact.id = entity_id

        mock_db = AsyncMock()
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_conflict
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_contact

        mock_db.execute.side_effect = [mock_result1, mock_result2]
        mock_db.flush = AsyncMock()

        mock_sync.return_value = None

        service = ConflictService(mock_db)
        result = await service.resolve(
            conflict_id=conflict_id,
            resolution_type=ConflictResolutionType.KEEP_NPD,
            resolved_by_id=user_id,
        )

        assert result is not None
        assert result.resolution_type == "keep_npd"

        # Verify can create response
        # Set the required attributes that were updated
        mock_conflict.resolved_at = datetime.now(UTC)
        mock_conflict.resolution_type = "keep_npd"
        mock_conflict.resolved_by_id = user_id
        response = SyncConflictResponse.model_validate(mock_conflict)
        assert isinstance(response, SyncConflictResponse)

    @pytest.mark.asyncio
    async def test_resolve_conflict_keep_monday(self):
        """Test resolving conflict with keep_monday."""
        conflict_id = uuid4()
        entity_id = uuid4()
        user_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.entity_type = "contact"
        mock_conflict.entity_id = entity_id
        mock_conflict.monday_item_id = "123456"
        mock_conflict.npd_data = {"name": "NPD Name"}
        mock_conflict.monday_data = {"name": "Monday Name"}
        mock_conflict.conflict_fields = ["name"]
        mock_conflict.detected_at = datetime.now(UTC)
        mock_conflict.resolved_at = None
        mock_conflict.resolution_type = None
        mock_conflict.resolved_by_id = None

        mock_contact = MagicMock()
        mock_contact.id = entity_id
        mock_contact.name = "NPD Name"

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
        assert result.resolution_type == "keep_monday"
        # Entity should be updated
        assert mock_contact.name == "Monday Name"

    @pytest.mark.asyncio
    @patch("app.services.sync_service.sync_contact_to_monday")
    async def test_resolve_conflict_merge(self, mock_sync):
        """Test resolving conflict with merge."""
        conflict_id = uuid4()
        entity_id = uuid4()
        user_id = uuid4()

        mock_conflict = MagicMock(spec=SyncConflict)
        mock_conflict.id = conflict_id
        mock_conflict.entity_type = "contact"
        mock_conflict.entity_id = entity_id
        mock_conflict.monday_item_id = "123456"
        mock_conflict.npd_data = {"name": "NPD Name", "email": "npd@test.com"}
        mock_conflict.monday_data = {"name": "Monday Name", "email": "monday@test.com"}
        mock_conflict.conflict_fields = ["name", "email"]
        mock_conflict.detected_at = datetime.now(UTC)
        mock_conflict.resolved_at = None
        mock_conflict.resolution_type = None
        mock_conflict.resolved_by_id = None

        mock_contact = MagicMock()
        mock_contact.id = entity_id
        mock_contact.name = "NPD Name"
        mock_contact.email = "npd@test.com"

        mock_db = AsyncMock()
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_conflict
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_contact

        mock_db.execute.side_effect = [mock_result1, mock_result2]
        mock_db.flush = AsyncMock()

        mock_sync.return_value = None

        service = ConflictService(mock_db)
        result = await service.resolve(
            conflict_id=conflict_id,
            resolution_type=ConflictResolutionType.MERGE,
            resolved_by_id=user_id,
            merge_selections={"name": "npd", "email": "monday"},
        )

        assert result is not None
        assert result.resolution_type == "merge"
        # email should be updated, name stays the same
        assert mock_contact.email == "monday@test.com"

    @pytest.mark.asyncio
    async def test_resolve_conflict_returns_none_when_not_found(self):
        """Test that resolve returns None for missing conflict."""
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
        """Test that merge without selections raises ValueError."""
        conflict_id = uuid4()
        entity_id = uuid4()

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
                resolved_by_id=uuid4(),
                merge_selections=None,
            )


class TestConflictStatsLogic:
    """Tests for get_sync_conflict_stats endpoint logic."""

    @pytest.mark.asyncio
    async def test_get_conflict_stats_returns_counts(self):
        """Test that stats endpoint returns conflict counts."""
        mock_db = AsyncMock()
        mock_db.scalar.side_effect = [5, 10]

        service = ConflictService(mock_db)
        stats = await service.get_conflict_stats()

        assert stats["unresolved"] == 5
        assert stats["resolved"] == 10
        assert stats["total"] == 15


class TestConflictResolutionSchemas:
    """Tests for conflict resolution Pydantic schemas."""

    def test_conflict_resolve_request_keep_npd(self):
        """Test ConflictResolveRequest with keep_npd."""
        request = ConflictResolveRequest(
            resolution_type=ConflictResolutionType.KEEP_NPD
        )
        assert request.resolution_type == ConflictResolutionType.KEEP_NPD
        assert request.merge_selections is None

    def test_conflict_resolve_request_keep_monday(self):
        """Test ConflictResolveRequest with keep_monday."""
        request = ConflictResolveRequest(
            resolution_type=ConflictResolutionType.KEEP_MONDAY
        )
        assert request.resolution_type == ConflictResolutionType.KEEP_MONDAY

    def test_conflict_resolve_request_merge_with_selections(self):
        """Test ConflictResolveRequest with merge and selections."""
        request = ConflictResolveRequest(
            resolution_type=ConflictResolutionType.MERGE,
            merge_selections={"name": "npd", "email": "monday"},
        )
        assert request.resolution_type == ConflictResolutionType.MERGE
        assert request.merge_selections["name"] == "npd"
        assert request.merge_selections["email"] == "monday"

    def test_conflict_list_response(self):
        """Test ConflictListResponse schema."""
        response = ConflictListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            has_more=False,
        )
        assert response.total == 0
        assert response.has_more is False

    def test_sync_conflict_response(self):
        """Test SyncConflictResponse schema."""
        conflict_id = uuid4()
        entity_id = uuid4()
        now = datetime.now(UTC)

        response = SyncConflictResponse(
            id=conflict_id,
            entity_type="contact",
            entity_id=entity_id,
            monday_item_id="123456",
            npd_data={"name": "NPD"},
            monday_data={"name": "Monday"},
            conflict_fields=["name"],
            detected_at=now,
            resolved_at=None,
            resolution_type=None,
            resolved_by_id=None,
        )
        assert response.id == conflict_id
        assert response.entity_type == "contact"
        assert response.resolved_by_id is None


class TestBulkResolveEndpointLogic:
    """Tests for bulk_resolve_sync_conflicts endpoint logic."""

    @pytest.mark.asyncio
    async def test_bulk_resolve_returns_response_with_counts(self):
        """Test that bulk resolve returns proper counts."""
        response = BulkConflictResolveResponse(
            total=3,
            succeeded=2,
            failed=1,
            results=[
                BulkResolveResult(conflict_id=uuid4(), success=True, error=None),
                BulkResolveResult(conflict_id=uuid4(), success=True, error=None),
                BulkResolveResult(
                    conflict_id=uuid4(), success=False, error="Not found"
                ),
            ],
        )

        assert response.total == 3
        assert response.succeeded == 2
        assert response.failed == 1
        assert len(response.results) == 3

    def test_bulk_resolve_request_validation(self):
        """Test BulkConflictResolveRequest validates properly."""
        # Valid request
        request = BulkConflictResolveRequest(
            conflict_ids=[uuid4(), uuid4()],
            resolution_type=ConflictResolutionType.KEEP_NPD,
        )
        assert len(request.conflict_ids) == 2

    def test_bulk_resolve_request_rejects_empty_list(self):
        """Test that empty conflict_ids list is rejected."""
        with pytest.raises(ValidationError):
            BulkConflictResolveRequest(
                conflict_ids=[],
                resolution_type=ConflictResolutionType.KEEP_NPD,
            )

    def test_bulk_resolve_request_limits_to_100(self):
        """Test that more than 100 conflict_ids is rejected."""
        with pytest.raises(ValidationError):
            BulkConflictResolveRequest(
                conflict_ids=[uuid4() for _ in range(101)],
                resolution_type=ConflictResolutionType.KEEP_NPD,
            )
