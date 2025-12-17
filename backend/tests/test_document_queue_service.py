"""Tests for document_queue_service functions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.document_queue import (
    DocumentQueueOperation,
    DocumentQueueStatus,
)
from app.services.document_queue_service import (
    BACKOFF_SCHEDULE_MINUTES,
    DocumentQueueService,
    calculate_next_retry,
    is_retryable_error,
    process_document_queue,
)


class TestDocumentQueueServiceEnqueue:
    """Tests for DocumentQueueService.enqueue method."""

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

        service = DocumentQueueService(mock_db)
        document_id = uuid4()

        await service.enqueue(
            document_id=document_id,
            operation=DocumentQueueOperation.PROCESS,
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        added_item = mock_db.add.call_args[0][0]
        assert added_item.document_id == document_id
        assert added_item.status == DocumentQueueStatus.PENDING
        assert added_item.operation == DocumentQueueOperation.PROCESS

    @pytest.mark.asyncio
    async def test_returns_existing_pending_item(self):
        """Test that enqueue returns existing pending item (deduplication)."""
        mock_db = AsyncMock()
        document_id = uuid4()

        existing_item = MagicMock()
        existing_item.id = uuid4()
        existing_item.document_id = document_id
        existing_item.status = DocumentQueueStatus.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_item
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DocumentQueueService(mock_db)

        result = await service.enqueue(
            document_id=document_id,
            operation=DocumentQueueOperation.PROCESS,
        )

        # Should not add new item
        mock_db.add.assert_not_called()
        assert result == existing_item

    @pytest.mark.asyncio
    async def test_creates_item_with_priority(self):
        """Test that enqueue respects priority parameter."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = DocumentQueueService(mock_db)
        document_id = uuid4()

        await service.enqueue(
            document_id=document_id,
            operation=DocumentQueueOperation.REPROCESS,
            priority=10,
        )

        added_item = mock_db.add.call_args[0][0]
        assert added_item.priority == 10
        assert added_item.operation == DocumentQueueOperation.REPROCESS


class TestDocumentQueueServiceGetPending:
    """Tests for DocumentQueueService.get_pending_items method."""

    @pytest.mark.asyncio
    async def test_returns_due_items(self):
        """Test that get_pending_items returns items due for processing."""
        mock_db = AsyncMock()
        mock_items = [MagicMock(), MagicMock()]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DocumentQueueService(mock_db)
        result = await service.get_pending_items(limit=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_pending(self):
        """Test that get_pending_items returns empty list when no items."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DocumentQueueService(mock_db)
        result = await service.get_pending_items(limit=50)

        assert result == []


class TestDocumentQueueServiceMarkMethods:
    """Tests for status update methods."""

    @pytest.mark.asyncio
    async def test_mark_in_progress(self):
        """Test mark_in_progress sets correct status."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.status = DocumentQueueStatus.PENDING

        service = DocumentQueueService(mock_db)
        await service.mark_in_progress(mock_item)

        assert mock_item.status == DocumentQueueStatus.IN_PROGRESS
        assert mock_item.started_at is not None
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_completed(self):
        """Test mark_completed sets correct status."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.document_id = uuid4()
        mock_item.status = DocumentQueueStatus.IN_PROGRESS

        service = DocumentQueueService(mock_db)
        await service.mark_completed(mock_item)

        assert mock_item.status == DocumentQueueStatus.COMPLETED
        assert mock_item.completed_at is not None
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_failed(self):
        """Test mark_failed sets correct status and error."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.document_id = uuid4()
        mock_item.status = DocumentQueueStatus.IN_PROGRESS
        mock_item.attempts = 0

        service = DocumentQueueService(mock_db)
        await service.mark_failed(mock_item, "Processing error")

        assert mock_item.status == DocumentQueueStatus.FAILED
        assert mock_item.error_message == "Processing error"
        assert mock_item.attempts == 1
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_failed_truncates_long_error(self):
        """Test mark_failed truncates error messages longer than 500 chars."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.document_id = uuid4()
        mock_item.status = DocumentQueueStatus.IN_PROGRESS
        mock_item.attempts = 0

        service = DocumentQueueService(mock_db)
        long_error = "x" * 600
        await service.mark_failed(mock_item, long_error)

        assert len(mock_item.error_message) == 500


class TestDocumentQueueServiceGetQueueStats:
    """Tests for DocumentQueueService.get_queue_stats method."""

    @pytest.mark.asyncio
    async def test_get_queue_stats(self):
        """Test get_queue_stats returns correct counts."""
        mock_db = AsyncMock()

        mock_rows = [
            MagicMock(status=DocumentQueueStatus.PENDING, count=3),
            MagicMock(status=DocumentQueueStatus.IN_PROGRESS, count=1),
            MagicMock(status=DocumentQueueStatus.COMPLETED, count=10),
            MagicMock(status=DocumentQueueStatus.FAILED, count=2),
        ]

        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DocumentQueueService(mock_db)
        stats = await service.get_queue_stats()

        assert stats["pending"] == 3
        assert stats["in_progress"] == 1
        assert stats["completed"] == 10
        assert stats["failed"] == 2

    @pytest.mark.asyncio
    async def test_get_queue_stats_empty(self):
        """Test get_queue_stats handles empty queue."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DocumentQueueService(mock_db)
        stats = await service.get_queue_stats()

        assert stats["pending"] == 0
        assert stats["in_progress"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0


class TestProcessDocumentQueue:
    """Tests for process_document_queue function."""

    @pytest.mark.asyncio
    @patch("app.services.document_queue_service.async_session_maker")
    async def test_returns_empty_when_no_pending(self, mock_session_maker):
        """Test process_document_queue returns zeros when no pending items."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        result = await process_document_queue()

        assert result["status"] == "success"
        assert result["items_processed"] == 0
        assert result["items_succeeded"] == 0
        assert result["items_failed"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    @patch("app.services.document_queue_service.async_session_maker")
    @patch("app.core.storage.StorageService")
    @patch("app.services.document_processing_task._process_document_content")
    async def test_processes_pending_items_successfully(
        self, mock_process_content, mock_storage_cls, mock_session_maker
    ):
        """Test process_document_queue processes items successfully."""
        mock_process_content.return_value = None

        document_id = uuid4()
        queue_item_id = uuid4()

        # Create mock queue item
        mock_queue_item = MagicMock()
        mock_queue_item.id = queue_item_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.PENDING

        # Create mock document
        mock_document = MagicMock()
        mock_document.id = document_id
        mock_document.file_path = "test/path/file.pdf"

        # Setup storage mock
        mock_storage = MagicMock()
        mock_storage.read = AsyncMock(return_value=b"file content")
        mock_storage_cls.return_value = mock_storage

        # Setup main session with pending items
        mock_main_db = AsyncMock()
        mock_pending_result = MagicMock()
        mock_pending_result.scalars.return_value.all.return_value = [mock_queue_item]
        mock_main_db.execute = AsyncMock(return_value=mock_pending_result)
        mock_main_db.commit = AsyncMock()

        # Setup process session
        mock_process_db = AsyncMock()
        mock_doc_result = MagicMock()
        mock_doc_result.scalar_one_or_none.return_value = mock_document
        mock_process_db.execute = AsyncMock(return_value=mock_doc_result)
        mock_process_db.commit = AsyncMock()

        # Setup update session
        mock_update_db = AsyncMock()
        mock_update_result = MagicMock()
        mock_update_result.scalar_one_or_none.return_value = mock_queue_item
        mock_update_db.execute = AsyncMock(return_value=mock_update_result)
        mock_update_db.commit = AsyncMock()

        # Track context manager calls
        session_call_count = [0]

        def create_mock_context():
            ctx = AsyncMock()
            if session_call_count[0] == 0:
                ctx.__aenter__.return_value = mock_main_db
            elif session_call_count[0] == 1:
                ctx.__aenter__.return_value = mock_process_db
            else:
                ctx.__aenter__.return_value = mock_update_db
            ctx.__aexit__.return_value = None
            session_call_count[0] += 1
            return ctx

        mock_session_maker.side_effect = create_mock_context

        result = await process_document_queue()

        assert result["status"] == "success"
        assert result["items_processed"] == 1
        assert result["items_succeeded"] == 1
        assert result["items_failed"] == 0

    @pytest.mark.asyncio
    @patch("app.services.document_queue_service.async_session_maker")
    async def test_handles_processing_error(self, mock_session_maker):
        """Test process_document_queue handles errors gracefully."""
        document_id = uuid4()
        queue_item_id = uuid4()

        # Create mock queue item
        mock_queue_item = MagicMock()
        mock_queue_item.id = queue_item_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.PENDING

        # Setup main session with pending items
        mock_main_db = AsyncMock()
        mock_pending_result = MagicMock()
        mock_pending_result.scalars.return_value.all.return_value = [mock_queue_item]
        mock_main_db.execute = AsyncMock(return_value=mock_pending_result)
        mock_main_db.commit = AsyncMock()

        # Setup process session that raises an error
        mock_process_db = AsyncMock()
        mock_doc_result = MagicMock()
        mock_doc_result.scalar_one_or_none.return_value = None  # Document not found
        mock_process_db.execute = AsyncMock(return_value=mock_doc_result)

        # Setup error session
        mock_error_db = AsyncMock()
        mock_error_result = MagicMock()
        mock_error_result.scalar_one_or_none.return_value = mock_queue_item
        mock_error_db.execute = AsyncMock(return_value=mock_error_result)
        mock_error_db.commit = AsyncMock()

        # Track context manager calls
        session_call_count = [0]

        def create_mock_context():
            ctx = AsyncMock()
            if session_call_count[0] == 0:
                ctx.__aenter__.return_value = mock_main_db
            elif session_call_count[0] == 1:
                ctx.__aenter__.return_value = mock_process_db
            else:
                ctx.__aenter__.return_value = mock_error_db
            ctx.__aexit__.return_value = None
            session_call_count[0] += 1
            return ctx

        mock_session_maker.side_effect = create_mock_context

        result = await process_document_queue()

        assert result["status"] == "error"
        assert result["items_processed"] == 1
        assert result["items_succeeded"] == 0
        assert result["items_failed"] == 1
        assert len(result["errors"]) == 1


class TestCalculateNextRetry:
    """Tests for calculate_next_retry function."""

    def test_first_attempt_uses_first_backoff(self):
        """Test that attempt 0 uses immediate retry."""
        result = calculate_next_retry(0)
        expected_delay = timedelta(minutes=BACKOFF_SCHEDULE_MINUTES[0])
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
            assert results[i] >= results[i - 1]


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_timeout_is_retryable(self):
        """Test that timeout errors are retryable."""
        assert is_retryable_error("Connection timeout") is True
        assert is_retryable_error("TimeoutError: API call failed") is True

    def test_connection_errors_are_retryable(self):
        """Test that connection errors are retryable."""
        assert is_retryable_error("Connection refused") is True
        assert is_retryable_error("ConnectionError: server unavailable") is True

    def test_file_not_found_is_non_retryable(self):
        """Test that file not found errors are not retryable."""
        assert is_retryable_error("File not found") is False
        assert is_retryable_error("File not found in storage") is False

    def test_unsupported_type_is_non_retryable(self):
        """Test that unsupported file type errors are not retryable."""
        assert is_retryable_error("Unsupported file type") is False
        assert is_retryable_error("Unsupported MIME type: video/mp4") is False

    def test_unknown_errors_default_retryable(self):
        """Test that unknown errors default to retryable."""
        assert is_retryable_error("Some unknown error") is True

    def test_empty_error_is_retryable(self):
        """Test that empty error message is retryable."""
        assert is_retryable_error("") is True
        assert is_retryable_error(None) is True


class TestDocumentQueueServiceMarkFailedRetry:
    """Tests for DocumentQueueService.mark_failed_retry method."""

    @pytest.mark.asyncio
    async def test_mark_failed_retry_requeues_retryable_error(self):
        """Test mark_failed_retry requeues when error is retryable."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.document_id = uuid4()
        mock_item.attempts = 2
        mock_item.max_attempts = 5
        mock_item.status = DocumentQueueStatus.IN_PROGRESS

        service = DocumentQueueService(mock_db)
        result = await service.mark_failed_retry(mock_item, "Connection timeout")

        assert result is True  # Requeued
        assert mock_item.attempts == 3
        assert mock_item.status == DocumentQueueStatus.PENDING
        assert mock_item.next_retry is not None

    @pytest.mark.asyncio
    async def test_mark_failed_retry_fails_at_max_attempts(self):
        """Test mark_failed_retry marks failed at max attempts."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.document_id = uuid4()
        mock_item.attempts = 4
        mock_item.max_attempts = 5
        mock_item.status = DocumentQueueStatus.IN_PROGRESS

        service = DocumentQueueService(mock_db)
        result = await service.mark_failed_retry(mock_item, "Connection timeout")

        assert result is False  # Not requeued
        assert mock_item.attempts == 5
        assert mock_item.status == DocumentQueueStatus.FAILED

    @pytest.mark.asyncio
    async def test_mark_failed_retry_fails_immediately_for_non_retryable(self):
        """Test mark_failed_retry fails immediately for non-retryable errors."""
        mock_db = AsyncMock()
        mock_item = MagicMock()
        mock_item.id = uuid4()
        mock_item.document_id = uuid4()
        mock_item.attempts = 1
        mock_item.max_attempts = 5
        mock_item.status = DocumentQueueStatus.IN_PROGRESS

        service = DocumentQueueService(mock_db)
        result = await service.mark_failed_retry(mock_item, "File not found")

        assert result is False  # Not requeued (non-retryable)
        assert mock_item.status == DocumentQueueStatus.FAILED


class TestDocumentQueueServiceRecoverStuckItems:
    """Tests for DocumentQueueService.recover_stuck_items method."""

    @pytest.mark.asyncio
    async def test_recovers_stuck_items(self):
        """Test that stuck items are recovered."""
        mock_db = AsyncMock()
        stuck_item = MagicMock()
        stuck_item.id = uuid4()
        stuck_item.document_id = uuid4()
        stuck_item.status = DocumentQueueStatus.IN_PROGRESS
        stuck_item.started_at = datetime.now(UTC) - timedelta(minutes=60)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stuck_item]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = DocumentQueueService(mock_db)
        recovered = await service.recover_stuck_items()

        assert recovered == 1
        assert stuck_item.status == DocumentQueueStatus.PENDING
        assert stuck_item.next_retry is not None

    @pytest.mark.asyncio
    async def test_no_items_to_recover(self):
        """Test when no items are stuck."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = DocumentQueueService(mock_db)
        recovered = await service.recover_stuck_items()

        assert recovered == 0
        mock_db.flush.assert_not_called()


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
