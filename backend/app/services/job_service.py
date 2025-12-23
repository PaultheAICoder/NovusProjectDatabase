"""Background job queue service.

Manages queuing of background jobs and processes them
with retry logic and exponential backoff.
"""

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import async_session_maker
from app.models.job import Job, JobStatus, JobType

logger = get_logger(__name__)

# Exponential backoff schedule in minutes
# Attempt 1: Immediate (initial failure queued)
# Attempt 2: +1 minute
# Attempt 3: +5 minutes
# Attempt 4: +15 minutes
# Attempt 5: +60 minutes (1 hour)
BACKOFF_SCHEDULE_MINUTES = [0, 1, 5, 15, 60]

# Threshold for detecting stuck jobs (in minutes)
STUCK_THRESHOLD_MINUTES = 30

# Error classification
RETRYABLE_ERROR_PATTERNS = [
    "timeout",
    "connection refused",
    "service unavailable",
    "temporary failure",
    "503",
    "ConnectionError",
    "TimeoutError",
    "rate limit",
    "too many requests",
    "429",
]

NON_RETRYABLE_ERROR_PATTERNS = [
    "not found",
    "invalid",
    "unsupported",
    "permission denied",
    "unauthorized",
    "forbidden",
    "404",
    "401",
    "403",
    "configuration error",
]

# Job handler registry
JOB_HANDLERS: dict[
    JobType, Callable[[Job, AsyncSession], Coroutine[Any, Any, dict | None]]
] = {}


def register_job_handler(
    job_type: JobType,
) -> Callable[
    [Callable[[Job, AsyncSession], Coroutine[Any, Any, dict | None]]],
    Callable[[Job, AsyncSession], Coroutine[Any, Any, dict | None]],
]:
    """Decorator to register a job handler.

    Usage:
        @register_job_handler(JobType.JIRA_REFRESH)
        async def handle_jira_refresh(job: Job, db: AsyncSession) -> dict | None:
            # Implementation
            return {"refreshed": 10}
    """

    def decorator(
        func: Callable[[Job, AsyncSession], Coroutine[Any, Any, dict | None]],
    ) -> Callable[[Job, AsyncSession], Coroutine[Any, Any, dict | None]]:
        JOB_HANDLERS[job_type] = func
        return func

    return decorator


def calculate_next_retry(attempts: int) -> datetime:
    """Calculate next retry time based on attempt count.

    Args:
        attempts: Current number of attempts (0-indexed)

    Returns:
        datetime for next retry
    """
    if attempts >= len(BACKOFF_SCHEDULE_MINUTES):
        # Use max backoff for any attempts beyond schedule
        delay_minutes = BACKOFF_SCHEDULE_MINUTES[-1]
    else:
        delay_minutes = BACKOFF_SCHEDULE_MINUTES[attempts]

    return datetime.now(UTC) + timedelta(minutes=delay_minutes)


def is_retryable_error(error_message: str | None) -> bool:
    """Determine if an error is retryable based on the error message.

    Args:
        error_message: The error message string

    Returns:
        True if the error is retryable, False otherwise
    """
    if not error_message:
        return True  # Default to retryable if no message

    error_lower = error_message.lower()

    # Check non-retryable patterns first
    for pattern in NON_RETRYABLE_ERROR_PATTERNS:
        if pattern.lower() in error_lower:
            return False

    # Check retryable patterns
    for pattern in RETRYABLE_ERROR_PATTERNS:
        if pattern.lower() in error_lower:
            return True

    # Default to retryable for unknown errors
    return True


class JobService:
    """Service for managing background job queue operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(
        self,
        job_type: JobType,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        payload: dict | None = None,
        priority: int = 0,
        max_attempts: int = 5,
        created_by: UUID | None = None,
        deduplicate: bool = True,
    ) -> Job:
        """Create a new background job.

        Handles deduplication - if an identical job is already pending,
        returns that instead of creating a duplicate.

        Args:
            job_type: Type of job to create
            entity_type: Optional entity type reference
            entity_id: Optional entity ID reference
            payload: Optional JSON payload for job configuration
            priority: Higher priority jobs processed first (default 0)
            max_attempts: Maximum retry attempts (default 5)
            created_by: User ID who created the job
            deduplicate: If True, check for existing pending job

        Returns:
            The created or existing Job
        """
        if deduplicate:
            # Check for existing pending/in_progress job for same type and entity
            filters = [
                Job.job_type == job_type,
                Job.status.in_([JobStatus.PENDING, JobStatus.IN_PROGRESS]),
            ]

            if entity_type is not None:
                filters.append(Job.entity_type == entity_type)
            if entity_id is not None:
                filters.append(Job.entity_id == entity_id)

            result = await self.db.execute(select(Job).where(and_(*filters)))
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(
                    "job_already_exists",
                    job_id=str(existing.id),
                    job_type=job_type.value,
                    status=existing.status.value,
                )
                return existing

        # Create new job
        job = Job(
            job_type=job_type,
            status=JobStatus.PENDING,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            priority=priority,
            max_attempts=max_attempts,
            created_by=created_by,
            next_retry=datetime.now(UTC),  # Ready for immediate processing
        )
        self.db.add(job)
        await self.db.flush()

        logger.info(
            "job_created",
            job_id=str(job.id),
            job_type=job_type.value,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            priority=priority,
        )

        return job

    async def get_job(self, job_id: UUID) -> Job | None:
        """Get a single job by ID.

        Args:
            job_id: UUID of the job

        Returns:
            Job or None if not found
        """
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def get_pending_jobs(
        self,
        job_type: JobType | None = None,
        limit: int = 50,
    ) -> list[Job]:
        """Get pending jobs that are due for processing.

        Args:
            job_type: Optional filter by job type
            limit: Maximum number of jobs to return

        Returns:
            List of pending Job items, ordered by priority then created_at
        """
        now = datetime.now(UTC)
        filters = [
            Job.status == JobStatus.PENDING,
            Job.next_retry <= now,
        ]

        if job_type:
            filters.append(Job.job_type == job_type)

        result = await self.db.execute(
            select(Job)
            .where(and_(*filters))
            .order_by(
                Job.priority.desc(),  # Higher priority first
                Job.created_at.asc(),  # FIFO within same priority
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_in_progress(self, job: Job) -> None:
        """Mark a job as in progress.

        Args:
            job: The job to update
        """
        job.status = JobStatus.IN_PROGRESS
        job.started_at = datetime.now(UTC)
        await self.db.flush()

    async def mark_completed(self, job: Job, result: dict | None = None) -> None:
        """Mark a job as completed.

        Args:
            job: The job to update
            result: Optional result data to store
        """
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        if result:
            job.result = result
        await self.db.flush()

        logger.info(
            "job_completed",
            job_id=str(job.id),
            job_type=job.job_type.value,
            attempts=job.attempts,
        )

    async def mark_failed(self, job: Job, error_message: str) -> None:
        """Mark a job as failed (permanent failure).

        This method is kept for backward compatibility.
        Use mark_failed_retry for retry-aware failure handling.

        Args:
            job: The job to update
            error_message: Error from the failed attempt
        """
        job.status = JobStatus.FAILED
        job.error_message = error_message[:500] if error_message else None
        job.last_attempt = datetime.now(UTC)
        job.attempts += 1
        job.completed_at = datetime.now(UTC)
        await self.db.flush()

        logger.warning(
            "job_failed",
            job_id=str(job.id),
            job_type=job.job_type.value,
            error=error_message[:100] if error_message else None,
        )

    async def mark_failed_retry(
        self,
        job: Job,
        error_message: str,
        error_context: dict | None = None,
    ) -> bool:
        """Mark a job for retry or as failed if max attempts reached.

        Uses error classification to determine if the error is retryable.
        Non-retryable errors are marked as failed immediately.

        Args:
            job: The job to update
            error_message: Error from the failed attempt
            error_context: Optional structured error context

        Returns:
            True if requeued for retry, False if marked as permanently failed
        """
        job.attempts += 1
        job.last_attempt = datetime.now(UTC)
        job.error_message = error_message[:500] if error_message else None
        if error_context:
            job.error_context = error_context

        # Check if error is non-retryable
        if not is_retryable_error(error_message):
            job.status = JobStatus.FAILED
            job.next_retry = None
            job.completed_at = datetime.now(UTC)

            logger.warning(
                "job_non_retryable_error",
                job_id=str(job.id),
                job_type=job.job_type.value,
                attempts=job.attempts,
                error=error_message[:100] if error_message else None,
            )
            await self.db.flush()
            return False

        # Check if max attempts reached
        if job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED
            job.next_retry = None
            job.completed_at = datetime.now(UTC)

            logger.warning(
                "job_max_retries",
                job_id=str(job.id),
                job_type=job.job_type.value,
                total_attempts=job.attempts,
                error=error_message[:100] if error_message else None,
            )
            await self.db.flush()
            return False

        # Requeue for retry
        job.status = JobStatus.PENDING
        job.next_retry = calculate_next_retry(job.attempts)

        logger.info(
            "job_requeued",
            job_id=str(job.id),
            job_type=job.job_type.value,
            attempts=job.attempts,
            next_retry=job.next_retry.isoformat(),
        )
        await self.db.flush()
        return True

    async def recover_stuck_jobs(self) -> int:
        """Find jobs stuck in in_progress and reset them for retry.

        Jobs in "in_progress" state for longer than STUCK_THRESHOLD_MINUTES
        are considered stuck and will be reset to pending with immediate retry.

        Returns:
            Number of jobs recovered
        """
        threshold_time = datetime.now(UTC) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)

        result = await self.db.execute(
            select(Job).where(
                and_(
                    Job.status == JobStatus.IN_PROGRESS,
                    Job.started_at < threshold_time,
                )
            )
        )
        stuck_jobs = list(result.scalars().all())

        recovered_count = 0
        for job in stuck_jobs:
            job.status = JobStatus.PENDING
            job.next_retry = datetime.now(UTC)  # Immediate retry
            job.error_message = (
                f"Recovered from stuck state after {STUCK_THRESHOLD_MINUTES} minutes"
            )

            logger.warning(
                "job_stuck_recovered",
                job_id=str(job.id),
                job_type=job.job_type.value,
                started_at=job.started_at.isoformat() if job.started_at else None,
            )
            recovered_count += 1

        if recovered_count > 0:
            await self.db.flush()

        return recovered_count

    async def get_job_stats(self) -> dict:
        """Get job queue statistics.

        Returns:
            Dict with counts by status and by job type
        """
        # Get counts by status
        status_result = await self.db.execute(
            select(
                Job.status,
                func.count(Job.id).label("count"),
            ).group_by(Job.status)
        )
        status_stats = {row.status.value: row.count for row in status_result.all()}

        # Get counts by job type
        type_result = await self.db.execute(
            select(
                Job.job_type,
                func.count(Job.id).label("count"),
            ).group_by(Job.job_type)
        )
        type_stats = {row.job_type.value: row.count for row in type_result.all()}

        pending = status_stats.get("pending", 0)
        in_progress = status_stats.get("in_progress", 0)
        completed = status_stats.get("completed", 0)
        failed = status_stats.get("failed", 0)

        return {
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
            "failed": failed,
            "total": pending + in_progress + completed + failed,
            "by_type": type_stats,
        }

    async def get_all_jobs(
        self,
        page: int = 1,
        page_size: int = 20,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
    ) -> tuple[list[Job], int]:
        """Get all jobs with filtering and pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            job_type: Filter by job type
            status: Filter by status

        Returns:
            Tuple of (list of jobs, total count)
        """
        # Build filters
        filters = []
        if job_type:
            filters.append(Job.job_type == job_type)
        if status:
            filters.append(Job.status == status)

        # Build count query
        count_query = select(func.count(Job.id))
        if filters:
            count_query = count_query.where(and_(*filters))

        # Get total count
        total = await self.db.scalar(count_query) or 0

        # Build items query
        items_query = select(Job)
        if filters:
            items_query = items_query.where(and_(*filters))

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        items_query = (
            items_query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)
        )

        result = await self.db.execute(items_query)
        items = list(result.scalars().all())

        return items, total

    async def manual_retry(
        self,
        job_id: UUID,
        reset_attempts: bool = False,
    ) -> Job | None:
        """Manually retry a failed job.

        Args:
            job_id: ID of the job
            reset_attempts: If True, reset attempts to 0

        Returns:
            Updated job or None if not found
        """
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            return None

        if reset_attempts:
            job.attempts = 0

        job.status = JobStatus.PENDING
        job.next_retry = datetime.now(UTC)
        job.error_message = None
        job.error_context = None
        job.completed_at = None

        logger.info(
            "job_manual_retry",
            job_id=str(job.id),
            job_type=job.job_type.value,
            reset_attempts=reset_attempts,
        )

        await self.db.flush()
        return job

    async def cancel_job(self, job_id: UUID) -> bool:
        """Cancel a pending job by removing it.

        Only pending jobs can be cancelled. In-progress jobs should
        complete or fail naturally.

        Args:
            job_id: ID of the job

        Returns:
            True if job was cancelled, False if not found or not cancellable
        """
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            return False

        # Only allow cancelling pending jobs
        if job.status != JobStatus.PENDING:
            return False

        await self.db.execute(delete(Job).where(Job.id == job_id))

        logger.info(
            "job_cancelled",
            job_id=str(job_id),
            job_type=job.job_type.value,
        )

        await self.db.flush()
        return True


async def process_job_queue(job_type: JobType | None = None) -> dict:
    """Process pending jobs in the queue.

    This function is designed to be called from a cron endpoint.
    It creates its own database session.

    Args:
        job_type: Optional filter to process only specific job type

    Returns:
        Dict with processing results
    """
    logger.info(
        "job_queue_processing_started", job_type=job_type.value if job_type else None
    )

    results = {
        "status": "success",
        "jobs_processed": 0,
        "jobs_succeeded": 0,
        "jobs_failed": 0,
        "jobs_requeued": 0,
        "jobs_max_retries": 0,
        "jobs_recovered": 0,
        "errors": [],
        "timestamp": datetime.now(UTC).isoformat(),
    }

    async with async_session_maker() as db:
        try:
            service = JobService(db)

            # Recover stuck jobs first
            recovered = await service.recover_stuck_jobs()
            results["jobs_recovered"] = recovered
            if recovered > 0:
                await db.commit()
                logger.info("job_queue_stuck_jobs_recovered", count=recovered)

            pending_jobs = await service.get_pending_jobs(
                job_type=job_type,
                limit=50,
            )

            if not pending_jobs:
                logger.info("job_queue_no_pending_jobs")
                return results

            logger.info("job_queue_jobs_found", count=len(pending_jobs))

            for job in pending_jobs:
                results["jobs_processed"] += 1

                try:
                    await service.mark_in_progress(job)
                    await db.commit()

                    # Get handler for job type
                    handler = JOB_HANDLERS.get(job.job_type)

                    if not handler:
                        raise ValueError(
                            f"No handler registered for job type: {job.job_type.value}"
                        )

                    # Process with fresh session for isolation
                    async with async_session_maker() as process_db:
                        result = await handler(job, process_db)
                        await process_db.commit()

                    # Mark as completed with fresh session
                    async with async_session_maker() as update_db:
                        update_service = JobService(update_db)
                        fresh_result = await update_db.execute(
                            select(Job).where(Job.id == job.id)
                        )
                        fresh_job = fresh_result.scalar_one_or_none()
                        if fresh_job:
                            await update_service.mark_completed(fresh_job, result)
                        await update_db.commit()

                    results["jobs_succeeded"] += 1

                except Exception as e:
                    error_str = str(e)
                    results["jobs_failed"] += 1
                    results["errors"].append(
                        f"Job {job.id} ({job.job_type.value}): {error_str[:100]}"
                    )

                    logger.exception(
                        "job_processing_error",
                        job_id=str(job.id),
                        job_type=job.job_type.value,
                        error=error_str,
                    )

                    # Mark for retry with fresh session
                    try:
                        async with async_session_maker() as error_db:
                            error_service = JobService(error_db)
                            result = await error_db.execute(
                                select(Job).where(Job.id == job.id)
                            )
                            fresh_job = result.scalar_one_or_none()
                            if fresh_job:
                                requeued = await error_service.mark_failed_retry(
                                    fresh_job, error_str
                                )
                                if requeued:
                                    results["jobs_requeued"] += 1
                                else:
                                    results["jobs_max_retries"] += 1
                            await error_db.commit()
                    except Exception as inner_e:
                        logger.exception(
                            "job_failed_to_mark_error",
                            job_id=str(job.id),
                            inner_error=str(inner_e),
                        )

        except Exception as e:
            results["status"] = "error"
            results["errors"].append(f"Queue processing error: {str(e)}")
            logger.exception("job_queue_processing_error", error=str(e))

    if results["jobs_failed"] > 0 and results["jobs_succeeded"] > 0:
        results["status"] = "partial"
    elif results["jobs_failed"] > 0:
        results["status"] = "error"

    logger.info(
        "job_queue_processing_completed",
        processed=results["jobs_processed"],
        succeeded=results["jobs_succeeded"],
        failed=results["jobs_failed"],
        requeued=results["jobs_requeued"],
        max_retries=results["jobs_max_retries"],
        recovered=results["jobs_recovered"],
    )

    return results
