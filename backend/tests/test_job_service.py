"""Tests for job_service functions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.job import JobStatus, JobType
from app.services.job_service import (
    BACKOFF_SCHEDULE_MINUTES,
    JobService,
    calculate_next_retry,
    is_retryable_error,
    process_job_queue,
)


class TestJobServiceCreate:
    """Tests for JobService.create_job method."""

    @pytest.mark.asyncio
    async def test_creates_new_job(self):
        """Test that create_job creates a new job when none exists."""
        mock_db = AsyncMock()
        # No existing item
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = JobService(mock_db)

        await service.create_job(
            job_type=JobType.JIRA_REFRESH,
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        added_job = mock_db.add.call_args[0][0]
        assert added_job.job_type == JobType.JIRA_REFRESH
        assert added_job.status == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_returns_existing_pending_job(self):
        """Test that create_job returns existing pending job (deduplication)."""
        mock_db = AsyncMock()

        existing_job = MagicMock()
        existing_job.id = uuid4()
        existing_job.job_type = JobType.JIRA_REFRESH
        existing_job.status = JobStatus.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_job
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = JobService(mock_db)

        result = await service.create_job(
            job_type=JobType.JIRA_REFRESH,
        )

        # Should not add new job
        mock_db.add.assert_not_called()
        assert result == existing_job

    @pytest.mark.asyncio
    async def test_creates_job_with_priority(self):
        """Test that create_job respects priority parameter."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = JobService(mock_db)

        await service.create_job(
            job_type=JobType.BULK_IMPORT,
            priority=10,
        )

        added_job = mock_db.add.call_args[0][0]
        assert added_job.priority == 10
        assert added_job.job_type == JobType.BULK_IMPORT

    @pytest.mark.asyncio
    async def test_creates_job_without_deduplication(self):
        """Test that create_job skips deduplication when disabled."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = JobService(mock_db)

        # Should not call execute to check for existing
        await service.create_job(
            job_type=JobType.JIRA_REFRESH,
            deduplicate=False,
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_job_with_entity_reference(self):
        """Test that create_job stores entity reference correctly."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = JobService(mock_db)
        entity_id = uuid4()

        await service.create_job(
            job_type=JobType.DOCUMENT_PROCESSING,
            entity_type="document",
            entity_id=entity_id,
        )

        added_job = mock_db.add.call_args[0][0]
        assert added_job.entity_type == "document"
        assert added_job.entity_id == entity_id


class TestJobServiceGetPending:
    """Tests for JobService.get_pending_jobs method."""

    @pytest.mark.asyncio
    async def test_returns_due_jobs(self):
        """Test that get_pending_jobs returns jobs due for processing."""
        mock_db = AsyncMock()
        mock_jobs = [MagicMock(), MagicMock()]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_jobs
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = JobService(mock_db)
        result = await service.get_pending_jobs(limit=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_pending(self):
        """Test that get_pending_jobs returns empty list when no jobs."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = JobService(mock_db)
        result = await service.get_pending_jobs(limit=50)

        assert result == []


class TestJobServiceMarkMethods:
    """Tests for status update methods."""

    @pytest.mark.asyncio
    async def test_mark_in_progress(self):
        """Test mark_in_progress sets correct status."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.status = JobStatus.PENDING

        service = JobService(mock_db)
        await service.mark_in_progress(mock_job)

        assert mock_job.status == JobStatus.IN_PROGRESS
        assert mock_job.started_at is not None
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_completed(self):
        """Test mark_completed sets correct status."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.job_type = JobType.JIRA_REFRESH
        mock_job.status = JobStatus.IN_PROGRESS
        mock_job.attempts = 1

        service = JobService(mock_db)
        await service.mark_completed(mock_job, result={"refreshed": 10})

        assert mock_job.status == JobStatus.COMPLETED
        assert mock_job.completed_at is not None
        assert mock_job.result == {"refreshed": 10}
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_failed(self):
        """Test mark_failed sets correct status and error."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.job_type = JobType.JIRA_REFRESH
        mock_job.status = JobStatus.IN_PROGRESS
        mock_job.attempts = 0

        service = JobService(mock_db)
        await service.mark_failed(mock_job, "Processing error")

        assert mock_job.status == JobStatus.FAILED
        assert mock_job.error_message == "Processing error"
        assert mock_job.attempts == 1
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_failed_truncates_long_error(self):
        """Test mark_failed truncates error messages longer than 500 chars."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.job_type = JobType.JIRA_REFRESH
        mock_job.status = JobStatus.IN_PROGRESS
        mock_job.attempts = 0

        service = JobService(mock_db)
        long_error = "x" * 600
        await service.mark_failed(mock_job, long_error)

        assert len(mock_job.error_message) == 500


class TestJobServiceGetJobStats:
    """Tests for JobService.get_job_stats method."""

    @pytest.mark.asyncio
    async def test_get_job_stats(self):
        """Test get_job_stats returns correct counts."""
        mock_db = AsyncMock()

        # Mock status counts
        status_rows = [
            MagicMock(status=JobStatus.PENDING, count=3),
            MagicMock(status=JobStatus.IN_PROGRESS, count=1),
            MagicMock(status=JobStatus.COMPLETED, count=10),
            MagicMock(status=JobStatus.FAILED, count=2),
        ]

        # Mock type counts
        type_rows = [
            MagicMock(job_type=JobType.JIRA_REFRESH, count=5),
            MagicMock(job_type=JobType.BULK_IMPORT, count=11),
        ]

        call_count = [0]

        def mock_execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:
                result.all.return_value = status_rows
            else:
                result.all.return_value = type_rows
            call_count[0] += 1
            return result

        mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)

        service = JobService(mock_db)
        stats = await service.get_job_stats()

        assert stats["pending"] == 3
        assert stats["in_progress"] == 1
        assert stats["completed"] == 10
        assert stats["failed"] == 2
        assert stats["total"] == 16
        assert stats["by_type"]["jira_refresh"] == 5
        assert stats["by_type"]["bulk_import"] == 11

    @pytest.mark.asyncio
    async def test_get_job_stats_empty(self):
        """Test get_job_stats handles empty queue."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = JobService(mock_db)
        stats = await service.get_job_stats()

        assert stats["pending"] == 0
        assert stats["in_progress"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        assert stats["total"] == 0


class TestProcessJobQueue:
    """Tests for process_job_queue function."""

    @pytest.mark.asyncio
    @patch("app.services.job_service.async_session_maker")
    async def test_returns_empty_when_no_pending(self, mock_session_maker):
        """Test process_job_queue returns zeros when no pending jobs."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_db
        mock_context.__aexit__.return_value = None
        mock_session_maker.return_value = mock_context

        result = await process_job_queue()

        assert result["status"] == "success"
        assert result["jobs_processed"] == 0
        assert result["jobs_succeeded"] == 0
        assert result["jobs_failed"] == 0
        assert result["errors"] == []


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

    def test_rate_limit_is_retryable(self):
        """Test that rate limit errors are retryable."""
        assert is_retryable_error("Rate limit exceeded") is True
        assert is_retryable_error("Too many requests - 429") is True

    def test_not_found_is_non_retryable(self):
        """Test that not found errors are not retryable."""
        assert is_retryable_error("Entity not found") is False
        assert is_retryable_error("Document not found") is False

    def test_invalid_is_non_retryable(self):
        """Test that invalid errors are not retryable."""
        assert is_retryable_error("Invalid configuration") is False
        assert is_retryable_error("Invalid input data") is False

    def test_unknown_errors_default_retryable(self):
        """Test that unknown errors default to retryable."""
        assert is_retryable_error("Some unknown error") is True

    def test_empty_error_is_retryable(self):
        """Test that empty error message is retryable."""
        assert is_retryable_error("") is True
        assert is_retryable_error(None) is True


class TestJobServiceMarkFailedRetry:
    """Tests for JobService.mark_failed_retry method."""

    @pytest.mark.asyncio
    async def test_mark_failed_retry_requeues_retryable_error(self):
        """Test mark_failed_retry requeues when error is retryable."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.job_type = JobType.JIRA_REFRESH
        mock_job.attempts = 2
        mock_job.max_attempts = 5
        mock_job.status = JobStatus.IN_PROGRESS

        service = JobService(mock_db)
        result = await service.mark_failed_retry(mock_job, "Connection timeout")

        assert result is True  # Requeued
        assert mock_job.attempts == 3
        assert mock_job.status == JobStatus.PENDING
        assert mock_job.next_retry is not None

    @pytest.mark.asyncio
    async def test_mark_failed_retry_fails_at_max_attempts(self):
        """Test mark_failed_retry marks failed at max attempts."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.job_type = JobType.JIRA_REFRESH
        mock_job.attempts = 4
        mock_job.max_attempts = 5
        mock_job.status = JobStatus.IN_PROGRESS

        service = JobService(mock_db)
        result = await service.mark_failed_retry(mock_job, "Connection timeout")

        assert result is False  # Not requeued
        assert mock_job.attempts == 5
        assert mock_job.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_mark_failed_retry_fails_immediately_for_non_retryable(self):
        """Test mark_failed_retry fails immediately for non-retryable errors."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.job_type = JobType.JIRA_REFRESH
        mock_job.attempts = 1
        mock_job.max_attempts = 5
        mock_job.status = JobStatus.IN_PROGRESS

        service = JobService(mock_db)
        result = await service.mark_failed_retry(mock_job, "Entity not found")

        assert result is False  # Not requeued (non-retryable)
        assert mock_job.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_mark_failed_retry_stores_error_context(self):
        """Test mark_failed_retry stores error context."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.job_type = JobType.JIRA_REFRESH
        mock_job.attempts = 2
        mock_job.max_attempts = 5
        mock_job.status = JobStatus.IN_PROGRESS

        service = JobService(mock_db)
        error_context = {"traceback": "...", "extra": "data"}
        await service.mark_failed_retry(
            mock_job, "Connection timeout", error_context=error_context
        )

        assert mock_job.error_context == error_context


class TestJobServiceRecoverStuckJobs:
    """Tests for JobService.recover_stuck_jobs method."""

    @pytest.mark.asyncio
    async def test_recovers_stuck_jobs(self):
        """Test that stuck jobs are recovered."""
        mock_db = AsyncMock()
        stuck_job = MagicMock()
        stuck_job.id = uuid4()
        stuck_job.job_type = JobType.JIRA_REFRESH
        stuck_job.status = JobStatus.IN_PROGRESS
        stuck_job.started_at = datetime.now(UTC) - timedelta(minutes=60)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stuck_job]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = JobService(mock_db)
        recovered = await service.recover_stuck_jobs()

        assert recovered == 1
        assert stuck_job.status == JobStatus.PENDING
        assert stuck_job.next_retry is not None

    @pytest.mark.asyncio
    async def test_no_jobs_to_recover(self):
        """Test when no jobs are stuck."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = JobService(mock_db)
        recovered = await service.recover_stuck_jobs()

        assert recovered == 0
        mock_db.flush.assert_not_called()


class TestJobServiceManualRetry:
    """Tests for JobService.manual_retry method."""

    @pytest.mark.asyncio
    async def test_manual_retry_resets_job(self):
        """Test manual_retry resets job to pending."""
        mock_db = AsyncMock()
        job = MagicMock()
        job.id = uuid4()
        job.job_type = JobType.JIRA_REFRESH
        job.status = JobStatus.FAILED
        job.attempts = 5
        job.error_message = "Previous error"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = JobService(mock_db)
        result = await service.manual_retry(job.id, reset_attempts=False)

        assert result == job
        assert job.status == JobStatus.PENDING
        assert job.error_message is None
        assert job.attempts == 5  # Not reset

    @pytest.mark.asyncio
    async def test_manual_retry_resets_attempts(self):
        """Test manual_retry resets attempt count when requested."""
        mock_db = AsyncMock()
        job = MagicMock()
        job.id = uuid4()
        job.job_type = JobType.JIRA_REFRESH
        job.status = JobStatus.FAILED
        job.attempts = 5

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = JobService(mock_db)
        await service.manual_retry(job.id, reset_attempts=True)

        assert job.attempts == 0

    @pytest.mark.asyncio
    async def test_manual_retry_returns_none_for_missing_job(self):
        """Test manual_retry returns None when job not found."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = JobService(mock_db)
        result = await service.manual_retry(uuid4())

        assert result is None


class TestJobServiceCancelJob:
    """Tests for JobService.cancel_job method."""

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self):
        """Test that pending jobs can be cancelled."""
        mock_db = AsyncMock()
        job = MagicMock()
        job.id = uuid4()
        job.job_type = JobType.JIRA_REFRESH
        job.status = JobStatus.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        service = JobService(mock_db)
        result = await service.cancel_job(job.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_cannot_cancel_in_progress_job(self):
        """Test that in-progress jobs cannot be cancelled."""
        mock_db = AsyncMock()
        job = MagicMock()
        job.id = uuid4()
        job.job_type = JobType.JIRA_REFRESH
        job.status = JobStatus.IN_PROGRESS

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = JobService(mock_db)
        result = await service.cancel_job(job.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_returns_false_for_missing_job(self):
        """Test cancel returns False when job not found."""
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = JobService(mock_db)
        result = await service.cancel_job(uuid4())

        assert result is False


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


class TestHandleEmbeddingGeneration:
    """Tests for handle_embedding_generation handler."""

    @pytest.mark.asyncio
    @patch("app.services.embedding_service.EmbeddingService")
    async def test_processes_documents_without_chunks(self, mock_service_class):
        """Test that handler processes documents needing embeddings."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_id = None
        mock_job.payload = None

        # Mock document query result
        mock_doc = MagicMock()
        mock_doc.id = uuid4()
        mock_doc.extracted_text = "Test document content"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_doc]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        # Mock embedding service
        mock_service = MagicMock()
        mock_service.chunk_text.return_value = ["chunk1"]
        mock_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2])
        mock_service_class.return_value = mock_service

        from app.services.job_handlers import handle_embedding_generation

        result = await handle_embedding_generation(mock_job, mock_db)

        assert result["processed"] == 1
        assert result["chunks_created"] >= 1
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_handles_empty_document_list(self):
        """Test that handler handles no documents gracefully."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_id = None
        mock_job.payload = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        from app.services.job_handlers import handle_embedding_generation

        result = await handle_embedding_generation(mock_job, mock_db)

        assert result["processed"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    @patch("app.services.embedding_service.EmbeddingService")
    async def test_processes_specific_document_ids(self, mock_service_class):
        """Test that handler processes specific document IDs when provided."""
        mock_db = AsyncMock()
        doc_id = uuid4()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_id = None
        mock_job.payload = {"document_ids": [str(doc_id)]}

        # Mock document query result
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.extracted_text = "Specific document content"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_doc]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        # Mock embedding service
        mock_service = MagicMock()
        mock_service.chunk_text.return_value = ["chunk1", "chunk2"]
        mock_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_service_class.return_value = mock_service

        from app.services.job_handlers import handle_embedding_generation

        result = await handle_embedding_generation(mock_job, mock_db)

        assert result["processed"] == 1
        assert result["chunks_created"] == 2


class TestHandleBulkImport:
    """Tests for handle_bulk_import handler."""

    @pytest.mark.asyncio
    @patch("app.services.import_service.ImportService")
    async def test_processes_import_rows(self, mock_service_class):
        """Test that handler processes import rows."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        user_id = uuid4()
        org_id = uuid4()
        mock_job.payload = {
            "rows": [
                {
                    "row_number": 1,
                    "name": "Test Project",
                    "organization_id": str(org_id),
                    "start_date": "2024-01-01",
                    "location": "headquarters",
                }
            ],
            "user_id": str(user_id),
            "skip_invalid": True,
        }

        # Mock import service
        from app.schemas.import_ import ImportCommitResult

        mock_service = AsyncMock()
        mock_service.commit_import.return_value = [
            ImportCommitResult(row_number=1, success=True, project_id=uuid4())
        ]
        mock_service_class.return_value = mock_service

        from app.services.job_handlers import handle_bulk_import

        result = await handle_bulk_import(mock_job, mock_db)

        assert result["total"] == 1
        assert result["succeeded"] == 1
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_rows(self):
        """Test that handler raises error for missing rows."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.payload = {"user_id": str(uuid4())}  # Missing rows

        from app.services.job_handlers import handle_bulk_import

        with pytest.raises(ValueError, match="rows"):
            await handle_bulk_import(mock_job, mock_db)

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_user_id(self):
        """Test that handler raises error for missing user_id."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.payload = {"rows": []}  # Missing user_id

        from app.services.job_handlers import handle_bulk_import

        with pytest.raises(ValueError, match="user_id"):
            await handle_bulk_import(mock_job, mock_db)

    @pytest.mark.asyncio
    @patch("app.services.import_service.ImportService")
    async def test_handles_mixed_success_failure(self, mock_service_class):
        """Test that handler handles mixed success/failure results."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        user_id = uuid4()
        org_id = uuid4()
        mock_job.payload = {
            "rows": [
                {
                    "row_number": 1,
                    "name": "Good Project",
                    "organization_id": str(org_id),
                    "start_date": "2024-01-01",
                    "location": "headquarters",
                },
                {
                    "row_number": 2,
                    "name": "Bad Project",
                    "organization_id": str(org_id),
                    "start_date": "2024-01-02",
                    "location": "remote",
                },
            ],
            "user_id": str(user_id),
            "skip_invalid": True,
        }

        # Mock import service with mixed results
        from app.schemas.import_ import ImportCommitResult

        mock_service = AsyncMock()
        mock_service.commit_import.return_value = [
            ImportCommitResult(row_number=1, success=True, project_id=uuid4()),
            ImportCommitResult(row_number=2, success=False, error="Validation failed"),
        ]
        mock_service_class.return_value = mock_service

        from app.services.job_handlers import handle_bulk_import

        result = await handle_bulk_import(mock_job, mock_db)

        assert result["total"] == 2
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1


class TestHandleMondaySync:
    """Tests for handle_monday_sync handler."""

    @pytest.mark.asyncio
    @patch("app.services.monday_service.MondayService")
    async def test_syncs_contacts(self, mock_service_class):
        """Test that handler syncs contacts."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_type = None
        mock_job.entity_id = None
        mock_job.payload = {
            "sync_type": "contacts",
            "board_id": "123456",
            "field_mapping": {"email": "email"},
            "triggered_by": str(uuid4()),
        }

        # Mock sync log result
        from app.models.monday_sync import MondaySyncStatus

        mock_sync_log = MagicMock()
        mock_sync_log.status = MondaySyncStatus.COMPLETED
        mock_sync_log.items_processed = 10
        mock_sync_log.items_created = 5
        mock_sync_log.items_updated = 3
        mock_sync_log.items_skipped = 2
        mock_sync_log.error_message = None

        mock_service = AsyncMock()
        mock_service.sync_contacts.return_value = mock_sync_log
        mock_service.close = AsyncMock()
        mock_service_class.return_value = mock_service

        from app.services.job_handlers import handle_monday_sync

        result = await handle_monday_sync(mock_job, mock_db)

        assert result["sync_type"] == "contacts"
        assert result["items_processed"] == 10
        mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.monday_service.MondayService")
    async def test_syncs_organizations(self, mock_service_class):
        """Test that handler syncs organizations."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_type = None
        mock_job.entity_id = None
        mock_job.payload = {
            "sync_type": "organizations",
            "board_id": "789012",
            "field_mapping": {"notes": "notes"},
            "triggered_by": str(uuid4()),
        }

        # Mock sync log result
        from app.models.monday_sync import MondaySyncStatus

        mock_sync_log = MagicMock()
        mock_sync_log.status = MondaySyncStatus.COMPLETED
        mock_sync_log.items_processed = 20
        mock_sync_log.items_created = 8
        mock_sync_log.items_updated = 10
        mock_sync_log.items_skipped = 2
        mock_sync_log.error_message = None

        mock_service = AsyncMock()
        mock_service.sync_organizations.return_value = mock_sync_log
        mock_service.close = AsyncMock()
        mock_service_class.return_value = mock_service

        from app.services.job_handlers import handle_monday_sync

        result = await handle_monday_sync(mock_job, mock_db)

        assert result["sync_type"] == "organizations"
        assert result["items_processed"] == 20
        mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_sync_type(self):
        """Test that handler raises error for missing sync_type."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_type = None
        mock_job.entity_id = None
        mock_job.payload = {"board_id": "123456", "triggered_by": str(uuid4())}

        from app.services.job_handlers import handle_monday_sync

        with pytest.raises(ValueError, match="sync_type"):
            await handle_monday_sync(mock_job, mock_db)

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_board_id(self):
        """Test that handler raises error for missing board_id."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_type = None
        mock_job.entity_id = None
        mock_job.payload = {"sync_type": "contacts", "triggered_by": str(uuid4())}

        from app.services.job_handlers import handle_monday_sync

        with pytest.raises(ValueError, match="board_id"):
            await handle_monday_sync(mock_job, mock_db)

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_triggered_by(self):
        """Test that handler raises error for missing triggered_by."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_type = None
        mock_job.entity_id = None
        mock_job.payload = {"sync_type": "contacts", "board_id": "123456"}

        from app.services.job_handlers import handle_monday_sync

        with pytest.raises(ValueError, match="triggered_by"):
            await handle_monday_sync(mock_job, mock_db)

    @pytest.mark.asyncio
    @patch("app.services.monday_service.MondayService")
    async def test_raises_error_for_unknown_sync_type(self, mock_service_class):
        """Test that handler raises error for unknown sync_type."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_type = None
        mock_job.entity_id = None
        mock_job.payload = {
            "sync_type": "unknown",
            "board_id": "123456",
            "triggered_by": str(uuid4()),
        }

        mock_service = AsyncMock()
        mock_service.close = AsyncMock()
        mock_service_class.return_value = mock_service

        from app.services.job_handlers import handle_monday_sync

        with pytest.raises(ValueError, match="Unknown sync_type"):
            await handle_monday_sync(mock_job, mock_db)


class TestHandleDocumentProcessing:
    """Tests for handle_document_processing handler."""

    @pytest.mark.asyncio
    @patch("app.core.storage.StorageService")
    @patch(
        "app.services.document_processing_task._process_document_content",
        new_callable=AsyncMock,
    )
    async def test_processes_document(self, mock_process, mock_storage_class):
        """Test that handler processes document."""
        mock_db = AsyncMock()
        doc_id = uuid4()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_id = doc_id

        # Mock document
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.file_path = "/storage/test.pdf"
        mock_doc.extracted_text = "Processed text content"
        mock_doc.processing_status = "completed"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock storage
        mock_storage = MagicMock()
        mock_storage.read = AsyncMock(return_value=b"file content")
        mock_storage_class.return_value = mock_storage

        mock_process.return_value = None

        from app.services.job_handlers import handle_document_processing

        result = await handle_document_processing(mock_job, mock_db)

        assert result["document_id"] == str(doc_id)
        assert result["status"] == "completed"
        mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_error_for_missing_entity_id(self):
        """Test that handler raises error for missing entity_id."""
        mock_db = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_id = None

        from app.services.job_handlers import handle_document_processing

        with pytest.raises(ValueError, match="entity_id"):
            await handle_document_processing(mock_job, mock_db)

    @pytest.mark.asyncio
    async def test_raises_error_for_document_not_found(self):
        """Test that handler raises error when document not found."""
        mock_db = AsyncMock()
        doc_id = uuid4()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_id = doc_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.services.job_handlers import handle_document_processing

        with pytest.raises(ValueError, match="not found"):
            await handle_document_processing(mock_job, mock_db)

    @pytest.mark.asyncio
    @patch("app.core.storage.StorageService")
    async def test_raises_error_for_file_not_found(self, mock_storage_class):
        """Test that handler raises error when file not found in storage."""
        mock_db = AsyncMock()
        doc_id = uuid4()
        mock_job = MagicMock()
        mock_job.id = uuid4()
        mock_job.entity_id = doc_id

        # Mock document
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.file_path = "/storage/missing.pdf"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock storage to raise FileNotFoundError
        mock_storage = MagicMock()
        mock_storage.read = AsyncMock(side_effect=FileNotFoundError("File not found"))
        mock_storage_class.return_value = mock_storage

        from app.services.job_handlers import handle_document_processing

        with pytest.raises(ValueError, match="File not found"):
            await handle_document_processing(mock_job, mock_db)
