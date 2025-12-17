"""Tests for sync_queue_service functions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.monday_sync import (
    SyncQueueDirection,
    SyncQueueOperation,
    SyncQueueStatus,
)
from app.services.sync_queue_service import (
    BACKOFF_SCHEDULE_MINUTES,
    SyncQueueService,
    calculate_next_retry,
    process_sync_queue,
)


class TestCalculateNextRetry:
    """Tests for calculate_next_retry function."""

    def test_first_attempt_uses_first_backoff(self):
        """Test that attempt 1 uses BACKOFF_SCHEDULE_MINUTES[1]."""
        result = calculate_next_retry(1)
        expected_delay = timedelta(minutes=BACKOFF_SCHEDULE_MINUTES[1])
        # Allow 1 second tolerance
        assert (
            abs(
                (result - datetime.now(UTC)).total_seconds()
                - expected_delay.total_seconds()
            )
            < 1
        )

    def test_max_attempt_uses_last_backoff(self):
        """Test that attempts beyond schedule use last value."""
        result = calculate_next_retry(100)
        expected_delay = timedelta(minutes=BACKOFF_SCHEDULE_MINUTES[-1])
        assert (
            abs(
                (result - datetime.now(UTC)).total_seconds()
                - expected_delay.total_seconds()
            )
            < 1
        )

    def test_each_attempt_increases_backoff(self):
        """Test that backoff increases with attempts."""
        results = [
            calculate_next_retry(i) for i in range(len(BACKOFF_SCHEDULE_MINUTES))
        ]
        for i in range(1, len(results)):
            # Each result should be >= previous (non-decreasing)
            assert results[i] >= results[i - 1]

    def test_zero_attempt_immediate_retry(self):
        """Test that attempt 0 uses immediate retry (0 minutes)."""
        result = calculate_next_retry(0)
        expected_delay = timedelta(minutes=BACKOFF_SCHEDULE_MINUTES[0])
        assert (
            abs(
                (result - datetime.now(UTC)).total_seconds()
                - expected_delay.total_seconds()
            )
            < 1
        )


class TestSyncQueueServiceEnqueue:
    """Tests for SyncQueueService.enqueue method."""

    @pytest.mark.asyncio
    async def test_creates_new_queue_item(self):
        """Test that enqueue creates a new item when none exists."""
        mock_db = AsyncMock()
        # No existing item
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = SyncQueueService(mock_db)
        entity_id = uuid4()

        await service.enqueue(
            entity_type="contact",
            entity_id=entity_id,
            direction=SyncQueueDirection.TO_MONDAY,
            operation=SyncQueueOperation.CREATE,
            error_message="API timeout",
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        # Verify the added item has correct attributes
        added_item = mock_db.add.call_args[0][0]
        assert added_item.entity_type == "contact"
        assert added_item.entity_id == entity_id
        assert added_item.attempts == 1
        assert added_item.status == SyncQueueStatus.PENDING

    @pytest.mark.asyncio
    async def test_updates_existing_pending_item(self):
        """Test that enqueue updates existing pending item (deduplication)."""
        mock_db = AsyncMock()
        entity_id = uuid4()

        existing_item = MagicMock()
        existing_item.id = uuid4()
        existing_item.entity_type = "contact"
        existing_item.entity_id = entity_id
        existing_item.attempts = 2
        existing_item.status = SyncQueueStatus.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = SyncQueueService(mock_db)

        result = await service.enqueue(
            entity_type="contact",
            entity_id=entity_id,
            direction=SyncQueueDirection.TO_MONDAY,
            operation=SyncQueueOperation.UPDATE,
            error_message="New error",
        )

        # Should not add new item
        mock_db.add.assert_not_called()
        # Should update existing
        assert existing_item.attempts == 3
        assert existing_item.error_message == "New error"
        assert result == existing_item


class TestSyncQueueServiceGetPending:
    """Tests for SyncQueueService.get_pending_items method."""

    @pytest.mark.asyncio
    async def test_returns_due_items(self):
        """Test that get_pending_items returns items due for retry."""
        mock_db = AsyncMock()
        mock_items = [MagicMock(), MagicMock()]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SyncQueueService(mock_db)
        result = await service.get_pending_items(limit=10)

        assert len(result) == 2


class TestSyncQueueServiceMarkMethods:
    """Tests for status update methods."""

    @pytest.mark.asyncio
    async def test_mark_in_progress(self):
        """Test mark_in_progress sets correct status."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.status = SyncQueueStatus.PENDING

        service = SyncQueueService(mock_db)
        await service.mark_in_progress(mock_item)

        assert mock_item.status == SyncQueueStatus.IN_PROGRESS
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_completed(self):
        """Test mark_completed sets correct status."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.entity_type = "contact"
        mock_item.entity_id = uuid4()
        mock_item.attempts = 2
        mock_item.status = SyncQueueStatus.IN_PROGRESS

        service = SyncQueueService(mock_db)
        await service.mark_completed(mock_item)

        assert mock_item.status == SyncQueueStatus.COMPLETED
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_failed_retry_requeues(self):
        """Test mark_failed_retry requeues when under max attempts."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.entity_type = "contact"
        mock_item.entity_id = uuid4()
        mock_item.attempts = 2
        mock_item.max_attempts = 5
        mock_item.status = SyncQueueStatus.IN_PROGRESS

        service = SyncQueueService(mock_db)
        result = await service.mark_failed_retry(mock_item, "Error")

        assert result is True  # Requeued
        assert mock_item.attempts == 3
        assert mock_item.status == SyncQueueStatus.PENDING
        assert mock_item.next_retry is not None

    @pytest.mark.asyncio
    async def test_mark_failed_retry_fails_at_max(self):
        """Test mark_failed_retry marks failed at max attempts."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.entity_type = "contact"
        mock_item.entity_id = uuid4()
        mock_item.attempts = 4
        mock_item.max_attempts = 5
        mock_item.status = SyncQueueStatus.IN_PROGRESS

        service = SyncQueueService(mock_db)
        result = await service.mark_failed_retry(mock_item, "Final error")

        assert result is False  # Not requeued
        assert mock_item.attempts == 5
        assert mock_item.status == SyncQueueStatus.FAILED


class TestSyncQueueServiceManualRetry:
    """Tests for SyncQueueService.manual_retry method."""

    @pytest.mark.asyncio
    async def test_manual_retry_resets_failed_item(self):
        """Test manual_retry resets a failed item for retry."""
        mock_db = AsyncMock()
        queue_id = uuid4()

        mock_item = MagicMock()
        mock_item.id = queue_id
        mock_item.status = SyncQueueStatus.FAILED
        mock_item.attempts = 5

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = SyncQueueService(mock_db)
        result = await service.manual_retry(queue_id, reset_attempts=True)

        assert result == mock_item
        assert mock_item.status == SyncQueueStatus.PENDING
        assert mock_item.attempts == 0
        assert mock_item.error_message is None

    @pytest.mark.asyncio
    async def test_manual_retry_returns_none_for_missing(self):
        """Test manual_retry returns None when item not found."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SyncQueueService(mock_db)
        result = await service.manual_retry(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_manual_retry_preserves_attempts_when_not_reset(self):
        """Test manual_retry preserves attempts when reset_attempts=False."""
        mock_db = AsyncMock()
        queue_id = uuid4()

        mock_item = MagicMock()
        mock_item.id = queue_id
        mock_item.status = SyncQueueStatus.FAILED
        mock_item.attempts = 5

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = SyncQueueService(mock_db)
        result = await service.manual_retry(queue_id, reset_attempts=False)

        assert result == mock_item
        assert mock_item.status == SyncQueueStatus.PENDING
        assert mock_item.attempts == 5  # Not reset


class TestSyncQueueServiceGetQueueStats:
    """Tests for SyncQueueService.get_queue_stats method."""

    @pytest.mark.asyncio
    async def test_get_queue_stats(self):
        """Test get_queue_stats returns correct counts."""
        mock_db = AsyncMock()

        # Mock the aggregation result
        mock_rows = [
            MagicMock(status=SyncQueueStatus.PENDING, count=3),
            MagicMock(status=SyncQueueStatus.IN_PROGRESS, count=1),
            MagicMock(status=SyncQueueStatus.COMPLETED, count=10),
            MagicMock(status=SyncQueueStatus.FAILED, count=2),
        ]

        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = SyncQueueService(mock_db)
        stats = await service.get_queue_stats()

        assert stats["pending"] == 3
        assert stats["in_progress"] == 1
        assert stats["completed"] == 10
        assert stats["failed"] == 2


class TestProcessSyncQueue:
    """Tests for process_sync_queue function."""

    @pytest.mark.asyncio
    @patch("app.services.sync_queue_service.async_session_maker")
    async def test_returns_empty_when_no_pending(self, mock_session_maker):
        """Test process_sync_queue returns zeros when no pending items."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        result = await process_sync_queue()

        assert result["status"] == "success"
        assert result["items_processed"] == 0

    @pytest.mark.asyncio
    @patch("app.services.sync_service.sync_contact_to_monday")
    @patch("app.services.sync_queue_service.async_session_maker")
    async def test_processes_contact_sync_successfully(
        self, mock_session_maker, mock_sync_contact
    ):
        """Test successful processing of contact sync queue item."""
        mock_sync_contact.return_value = None  # Success

        entity_id = uuid4()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.entity_type = "contact"
        mock_item.entity_id = entity_id
        mock_item.direction = SyncQueueDirection.TO_MONDAY
        mock_item.status = SyncQueueStatus.PENDING

        # Setup mock sessions
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item]
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        result = await process_sync_queue()

        mock_sync_contact.assert_called_once_with(entity_id)
        assert result["items_processed"] == 1
        assert result["items_succeeded"] == 1

    @pytest.mark.asyncio
    @patch("app.services.sync_service.sync_organization_to_monday")
    @patch("app.services.sync_queue_service.async_session_maker")
    async def test_processes_organization_sync_successfully(
        self, mock_session_maker, mock_sync_org
    ):
        """Test successful processing of organization sync queue item."""
        mock_sync_org.return_value = None  # Success

        entity_id = uuid4()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.entity_type = "organization"
        mock_item.entity_id = entity_id
        mock_item.direction = SyncQueueDirection.TO_MONDAY
        mock_item.status = SyncQueueStatus.PENDING

        # Setup mock sessions
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item]
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        result = await process_sync_queue()

        mock_sync_org.assert_called_once_with(entity_id)
        assert result["items_processed"] == 1
        assert result["items_succeeded"] == 1

    @pytest.mark.asyncio
    @patch("app.services.sync_service.sync_contact_to_monday")
    @patch("app.services.sync_queue_service.async_session_maker")
    async def test_handles_sync_failure(self, mock_session_maker, mock_sync_contact):
        """Test that sync failures are handled and item is requeued."""
        mock_sync_contact.side_effect = Exception("Monday API error")

        entity_id = uuid4()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.entity_type = "contact"
        mock_item.entity_id = entity_id
        mock_item.direction = SyncQueueDirection.TO_MONDAY
        mock_item.status = SyncQueueStatus.PENDING
        mock_item.attempts = 1
        mock_item.max_attempts = 5

        # Setup mock sessions
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_item]
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.flush = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        result = await process_sync_queue()

        assert result["items_processed"] == 1
        assert result["items_failed"] == 1
        assert len(result["errors"]) == 1


class TestBackoffSchedule:
    """Tests for backoff schedule constants."""

    def test_backoff_schedule_values(self):
        """Verify the backoff schedule has expected values."""
        assert len(BACKOFF_SCHEDULE_MINUTES) == 5
        assert BACKOFF_SCHEDULE_MINUTES[0] == 0
        assert BACKOFF_SCHEDULE_MINUTES[1] == 1
        assert BACKOFF_SCHEDULE_MINUTES[2] == 5
        assert BACKOFF_SCHEDULE_MINUTES[3] == 15
        assert BACKOFF_SCHEDULE_MINUTES[4] == 60

    def test_backoff_schedule_increasing(self):
        """Verify backoff schedule is non-decreasing."""
        for i in range(1, len(BACKOFF_SCHEDULE_MINUTES)):
            assert (
                BACKOFF_SCHEDULE_MINUTES[i] >= BACKOFF_SCHEDULE_MINUTES[i - 1]
            ), f"Backoff should be non-decreasing at index {i}"
