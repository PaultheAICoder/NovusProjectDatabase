"""Tests for admin sync queue management endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.monday_sync import (
    SyncQueue,
    SyncQueueDirection,
    SyncQueueOperation,
    SyncQueueStatus,
)
from app.schemas.monday import (
    SyncQueueItemResponse,
    SyncQueueListResponse,
    SyncQueueStatsResponse,
)
from app.services.sync_queue_service import SyncQueueService


class TestSyncQueueServiceGetAllItems:
    """Tests for SyncQueueService.get_all_items method."""

    @pytest.mark.asyncio
    async def test_get_all_items_returns_paginated_results(self):
        """Test that get_all_items returns paginated queue items."""
        queue_id = uuid4()
        entity_id = uuid4()

        mock_queue_item = MagicMock(spec=SyncQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.entity_type = "contact"
        mock_queue_item.entity_id = entity_id
        mock_queue_item.direction = SyncQueueDirection.TO_MONDAY
        mock_queue_item.operation = SyncQueueOperation.UPDATE
        mock_queue_item.status = SyncQueueStatus.PENDING
        mock_queue_item.attempts = 1
        mock_queue_item.max_attempts = 5
        mock_queue_item.last_attempt = datetime.now(UTC)
        mock_queue_item.next_retry = datetime.now(UTC) + timedelta(minutes=5)
        mock_queue_item.error_message = "Connection error"
        mock_queue_item.created_at = datetime.now(UTC)

        mock_db = AsyncMock()
        mock_db.scalar.return_value = 1
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_queue_item]
        mock_db.execute.return_value = mock_result

        service = SyncQueueService(mock_db)
        items, total = await service.get_all_items(page=1, page_size=20)

        assert total == 1
        assert len(items) == 1
        assert items[0].entity_type == "contact"
        assert items[0].status == SyncQueueStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_all_items_filters_by_entity_type(self):
        """Test that entity_type filter is applied correctly."""
        mock_db = AsyncMock()
        mock_db.scalar.return_value = 0
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = SyncQueueService(mock_db)
        items, total = await service.get_all_items(
            page=1,
            page_size=20,
            entity_type="organization",
        )

        assert total == 0
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_get_all_items_filters_by_status(self):
        """Test that status filter is applied correctly."""
        mock_db = AsyncMock()
        mock_db.scalar.return_value = 0
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = SyncQueueService(mock_db)
        items, total = await service.get_all_items(
            page=1,
            page_size=20,
            status=SyncQueueStatus.FAILED,
        )

        assert total == 0
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_get_all_items_filters_by_direction(self):
        """Test that direction filter is applied correctly."""
        mock_db = AsyncMock()
        mock_db.scalar.return_value = 0
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = SyncQueueService(mock_db)
        items, total = await service.get_all_items(
            page=1,
            page_size=20,
            direction=SyncQueueDirection.TO_NPD,
        )

        assert total == 0
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_get_all_items_pagination(self):
        """Test that pagination works correctly."""
        mock_db = AsyncMock()
        mock_db.scalar.return_value = 50  # Total 50 items

        mock_items = []
        for _ in range(10):
            mock_item = MagicMock(spec=SyncQueue)
            mock_item.id = uuid4()
            mock_item.entity_type = "contact"
            mock_item.entity_id = uuid4()
            mock_item.direction = SyncQueueDirection.TO_MONDAY
            mock_item.operation = SyncQueueOperation.UPDATE
            mock_item.status = SyncQueueStatus.PENDING
            mock_item.attempts = 1
            mock_item.max_attempts = 5
            mock_item.last_attempt = datetime.now(UTC)
            mock_item.next_retry = datetime.now(UTC)
            mock_item.error_message = None
            mock_item.created_at = datetime.now(UTC)
            mock_items.append(mock_item)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_db.execute.return_value = mock_result

        service = SyncQueueService(mock_db)
        items, total = await service.get_all_items(page=2, page_size=10)

        assert total == 50
        assert len(items) == 10


class TestSyncQueueServiceStats:
    """Tests for SyncQueueService.get_queue_stats method."""

    @pytest.mark.asyncio
    async def test_get_queue_stats_returns_counts(self):
        """Test that stats returns counts by status."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        # Mock the result rows
        mock_rows = [
            MagicMock(status=SyncQueueStatus.PENDING, count=5),
            MagicMock(status=SyncQueueStatus.FAILED, count=3),
            MagicMock(status=SyncQueueStatus.COMPLETED, count=10),
        ]
        mock_result.all.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        service = SyncQueueService(mock_db)
        stats = await service.get_queue_stats()

        assert stats["pending"] == 5
        assert stats["failed"] == 3
        assert stats["completed"] == 10
        assert stats["in_progress"] == 0


class TestSyncQueueServiceManualRetry:
    """Tests for SyncQueueService.manual_retry method."""

    @pytest.mark.asyncio
    async def test_manual_retry_success(self):
        """Test manual retry resets item to pending."""
        queue_id = uuid4()
        entity_id = uuid4()

        mock_queue_item = MagicMock(spec=SyncQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.entity_type = "contact"
        mock_queue_item.entity_id = entity_id
        mock_queue_item.direction = SyncQueueDirection.TO_MONDAY
        mock_queue_item.operation = SyncQueueOperation.UPDATE
        mock_queue_item.status = SyncQueueStatus.FAILED
        mock_queue_item.attempts = 5
        mock_queue_item.max_attempts = 5
        mock_queue_item.last_attempt = datetime.now(UTC)
        mock_queue_item.next_retry = None
        mock_queue_item.error_message = "Max retries exceeded"
        mock_queue_item.created_at = datetime.now(UTC)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_queue_item
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        service = SyncQueueService(mock_db)
        result = await service.manual_retry(queue_id, reset_attempts=False)

        assert result is not None
        assert result.status == SyncQueueStatus.PENDING
        assert result.next_retry is not None
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_manual_retry_with_reset_attempts(self):
        """Test manual retry resets attempt count when requested."""
        queue_id = uuid4()

        mock_queue_item = MagicMock(spec=SyncQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.entity_type = "contact"
        mock_queue_item.entity_id = uuid4()
        mock_queue_item.direction = SyncQueueDirection.TO_MONDAY
        mock_queue_item.operation = SyncQueueOperation.UPDATE
        mock_queue_item.status = SyncQueueStatus.FAILED
        mock_queue_item.attempts = 5
        mock_queue_item.max_attempts = 5
        mock_queue_item.last_attempt = datetime.now(UTC)
        mock_queue_item.next_retry = None
        mock_queue_item.error_message = "Max retries exceeded"
        mock_queue_item.created_at = datetime.now(UTC)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_queue_item
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        service = SyncQueueService(mock_db)
        result = await service.manual_retry(queue_id, reset_attempts=True)

        assert result is not None
        assert result.attempts == 0

    @pytest.mark.asyncio
    async def test_manual_retry_not_found(self):
        """Test manual retry returns None for missing item."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = SyncQueueService(mock_db)
        result = await service.manual_retry(uuid4())

        assert result is None


class TestSyncQueueSchemas:
    """Tests for sync queue Pydantic schemas."""

    def test_sync_queue_item_response(self):
        """Test SyncQueueItemResponse schema."""
        queue_id = uuid4()
        entity_id = uuid4()
        now = datetime.now(UTC)

        response = SyncQueueItemResponse(
            id=queue_id,
            entity_type="contact",
            entity_id=entity_id,
            direction=SyncQueueDirection.TO_MONDAY,
            operation=SyncQueueOperation.UPDATE,
            status=SyncQueueStatus.PENDING,
            attempts=2,
            max_attempts=5,
            last_attempt=now,
            next_retry=now + timedelta(minutes=5),
            error_message="Connection timeout",
            created_at=now,
        )

        assert response.id == queue_id
        assert response.entity_type == "contact"
        assert response.status == SyncQueueStatus.PENDING
        assert response.attempts == 2

    def test_sync_queue_list_response(self):
        """Test SyncQueueListResponse schema."""
        response = SyncQueueListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            has_more=False,
        )

        assert response.total == 0
        assert response.has_more is False

    def test_sync_queue_stats_response(self):
        """Test SyncQueueStatsResponse schema."""
        response = SyncQueueStatsResponse(
            pending=5,
            in_progress=2,
            completed=100,
            failed=3,
        )

        assert response.pending == 5
        assert response.in_progress == 2
        assert response.completed == 100
        assert response.failed == 3


class TestSyncQueueListResponseValidation:
    """Tests for creating response objects from service output."""

    @pytest.mark.asyncio
    async def test_create_response_from_service_output(self):
        """Test creating SyncQueueListResponse from service items."""
        queue_id = uuid4()
        entity_id = uuid4()
        now = datetime.now(UTC)

        mock_queue_item = MagicMock(spec=SyncQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.entity_type = "organization"
        mock_queue_item.entity_id = entity_id
        mock_queue_item.direction = SyncQueueDirection.TO_NPD
        mock_queue_item.operation = SyncQueueOperation.CREATE
        mock_queue_item.status = SyncQueueStatus.FAILED
        mock_queue_item.attempts = 5
        mock_queue_item.max_attempts = 5
        mock_queue_item.last_attempt = now
        mock_queue_item.next_retry = None
        mock_queue_item.error_message = "API error"
        mock_queue_item.created_at = now

        # Simulate what the endpoint does
        items = [mock_queue_item]
        total = 1
        page = 1
        page_size = 20

        response = SyncQueueListResponse(
            items=[SyncQueueItemResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total,
        )

        assert isinstance(response, SyncQueueListResponse)
        assert len(response.items) == 1
        assert response.items[0].entity_type == "organization"
        assert response.items[0].status == SyncQueueStatus.FAILED
        assert response.has_more is False
