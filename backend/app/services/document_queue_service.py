"""Document processing queue service.

Manages queuing of document processing operations and processes them
with the existing document processing logic.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import async_session_maker
from app.models.document_queue import (
    DocumentProcessingQueue,
    DocumentQueueOperation,
    DocumentQueueStatus,
)

logger = get_logger(__name__)

# Exponential backoff schedule in minutes
# Attempt 1: Immediate (initial failure queued)
# Attempt 2: +1 minute
# Attempt 3: +5 minutes
# Attempt 4: +15 minutes
# Attempt 5: +60 minutes (1 hour)
BACKOFF_SCHEDULE_MINUTES = [0, 1, 5, 15, 60]

# Threshold for detecting stuck items (in minutes)
STUCK_THRESHOLD_MINUTES = 30

# Error classification
RETRYABLE_ERROR_PATTERNS = [
    "timeout",
    "connection refused",
    "embedding service unavailable",
    "temporary failure",
    "service unavailable",
    "503",
    "ConnectionError",
    "TimeoutError",
]

NON_RETRYABLE_ERROR_PATTERNS = [
    "file not found",
    "unsupported file type",
    "invalid content",
    "document not found",
    "unsupported mime type",
    "File not found in storage",
]


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


class DocumentQueueService:
    """Service for managing document processing queue operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue(
        self,
        document_id: UUID,
        operation: DocumentQueueOperation,
        priority: int = 0,
    ) -> DocumentProcessingQueue:
        """Add a document to the processing queue.

        Handles deduplication - if an item for the same document
        is already pending, returns that instead of creating a duplicate.

        Args:
            document_id: UUID of the document to process
            operation: PROCESS or REPROCESS
            priority: Higher priority items processed first (default 0)

        Returns:
            The created or existing DocumentProcessingQueue item
        """
        # Check for existing pending/in_progress item for same document
        result = await self.db.execute(
            select(DocumentProcessingQueue).where(
                and_(
                    DocumentProcessingQueue.document_id == document_id,
                    DocumentProcessingQueue.status.in_(
                        [
                            DocumentQueueStatus.PENDING,
                            DocumentQueueStatus.IN_PROGRESS,
                        ]
                    ),
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(
                "document_queue_item_exists",
                queue_id=str(existing.id),
                document_id=str(document_id),
                status=existing.status.value,
            )
            return existing

        # Create new queue item
        queue_item = DocumentProcessingQueue(
            document_id=document_id,
            operation=operation,
            priority=priority,
            status=DocumentQueueStatus.PENDING,
            next_retry=datetime.now(UTC),  # Ready for immediate processing
        )
        self.db.add(queue_item)
        await self.db.flush()

        logger.info(
            "document_queue_item_created",
            queue_id=str(queue_item.id),
            document_id=str(document_id),
            operation=operation.value,
        )

        return queue_item

    async def get_pending_items(self, limit: int = 50) -> list[DocumentProcessingQueue]:
        """Get pending items that are due for processing.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of pending DocumentProcessingQueue items, ordered by priority then created_at
        """
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(DocumentProcessingQueue)
            .where(
                and_(
                    DocumentProcessingQueue.status == DocumentQueueStatus.PENDING,
                    DocumentProcessingQueue.next_retry <= now,
                )
            )
            .order_by(
                DocumentProcessingQueue.priority.desc(),  # Higher priority first
                DocumentProcessingQueue.created_at.asc(),  # FIFO within same priority
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_in_progress(self, queue_item: DocumentProcessingQueue) -> None:
        """Mark a queue item as in progress."""
        queue_item.status = DocumentQueueStatus.IN_PROGRESS
        queue_item.started_at = datetime.now(UTC)
        await self.db.flush()

    async def mark_completed(self, queue_item: DocumentProcessingQueue) -> None:
        """Mark a queue item as completed."""
        queue_item.status = DocumentQueueStatus.COMPLETED
        queue_item.completed_at = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "document_queue_item_completed",
            queue_id=str(queue_item.id),
            document_id=str(queue_item.document_id),
        )

    async def mark_failed(
        self, queue_item: DocumentProcessingQueue, error_message: str
    ) -> None:
        """Mark a queue item as failed (permanent failure).

        This method is kept for backward compatibility.
        Use mark_failed_retry for retry-aware failure handling.

        Args:
            queue_item: The queue item to update
            error_message: Error from the failed attempt
        """
        queue_item.status = DocumentQueueStatus.FAILED
        queue_item.error_message = error_message[:500] if error_message else None
        queue_item.last_attempt = datetime.now(UTC)
        queue_item.attempts += 1
        await self.db.flush()

        logger.warning(
            "document_queue_item_failed",
            queue_id=str(queue_item.id),
            document_id=str(queue_item.document_id),
            error=error_message[:100] if error_message else None,
        )

    async def mark_failed_retry(
        self, queue_item: DocumentProcessingQueue, error_message: str
    ) -> bool:
        """Mark a queue item for retry or as failed if max attempts reached.

        Uses error classification to determine if the error is retryable.
        Non-retryable errors are marked as failed immediately.

        Args:
            queue_item: The queue item to update
            error_message: Error from the failed attempt

        Returns:
            True if requeued for retry, False if marked as permanently failed
        """
        queue_item.attempts += 1
        queue_item.last_attempt = datetime.now(UTC)
        queue_item.error_message = error_message[:500] if error_message else None

        # Check if error is non-retryable
        if not is_retryable_error(error_message):
            queue_item.status = DocumentQueueStatus.FAILED
            queue_item.next_retry = None

            logger.warning(
                "document_queue_item_non_retryable_error",
                queue_id=str(queue_item.id),
                document_id=str(queue_item.document_id),
                attempts=queue_item.attempts,
                error=error_message[:100] if error_message else None,
            )
            await self.db.flush()
            return False

        # Check if max attempts reached
        if queue_item.attempts >= queue_item.max_attempts:
            queue_item.status = DocumentQueueStatus.FAILED
            queue_item.next_retry = None

            logger.warning(
                "document_queue_item_max_retries",
                queue_id=str(queue_item.id),
                document_id=str(queue_item.document_id),
                total_attempts=queue_item.attempts,
                error=error_message[:100] if error_message else None,
            )
            await self.db.flush()
            return False

        # Requeue for retry
        queue_item.status = DocumentQueueStatus.PENDING
        queue_item.next_retry = calculate_next_retry(queue_item.attempts)

        logger.info(
            "document_queue_item_requeued",
            queue_id=str(queue_item.id),
            document_id=str(queue_item.document_id),
            attempts=queue_item.attempts,
            next_retry=queue_item.next_retry.isoformat(),
        )
        await self.db.flush()
        return True

    async def recover_stuck_items(self) -> int:
        """Find items stuck in in_progress and reset them for retry.

        Items in "in_progress" state for longer than STUCK_THRESHOLD_MINUTES
        are considered stuck and will be reset to pending with immediate retry.

        Returns:
            Number of items recovered
        """
        threshold_time = datetime.now(UTC) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)

        result = await self.db.execute(
            select(DocumentProcessingQueue).where(
                and_(
                    DocumentProcessingQueue.status == DocumentQueueStatus.IN_PROGRESS,
                    DocumentProcessingQueue.started_at < threshold_time,
                )
            )
        )
        stuck_items = list(result.scalars().all())

        recovered_count = 0
        for item in stuck_items:
            item.status = DocumentQueueStatus.PENDING
            item.next_retry = datetime.now(UTC)  # Immediate retry
            item.error_message = (
                f"Recovered from stuck state after {STUCK_THRESHOLD_MINUTES} minutes"
            )

            logger.warning(
                "document_queue_item_stuck_recovered",
                queue_id=str(item.id),
                document_id=str(item.document_id),
                started_at=item.started_at.isoformat() if item.started_at else None,
            )
            recovered_count += 1

        if recovered_count > 0:
            await self.db.flush()

        return recovered_count

    async def get_queue_stats(self) -> dict:
        """Get queue statistics.

        Returns:
            Dict with counts by status
        """
        result = await self.db.execute(
            select(
                DocumentProcessingQueue.status,
                func.count(DocumentProcessingQueue.id).label("count"),
            ).group_by(DocumentProcessingQueue.status)
        )
        stats = {row.status.value: row.count for row in result.all()}

        return {
            "pending": stats.get("pending", 0),
            "in_progress": stats.get("in_progress", 0),
            "completed": stats.get("completed", 0),
            "failed": stats.get("failed", 0),
        }

    async def get_all_items(
        self,
        page: int = 1,
        page_size: int = 20,
        status: DocumentQueueStatus | None = None,
    ) -> tuple[list[tuple[DocumentProcessingQueue, str]], int]:
        """Get all queue items with filtering and pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            status: Filter by status

        Returns:
            Tuple of (list of (queue item, document_name) tuples, total count)
        """
        from app.models.document import Document

        # Build filters
        filters = []
        if status:
            filters.append(DocumentProcessingQueue.status == status)

        # Build count query
        count_query = select(func.count(DocumentProcessingQueue.id))
        if filters:
            count_query = count_query.where(and_(*filters))

        # Get total count
        total = await self.db.scalar(count_query) or 0

        # Build items query with join for document name
        items_query = select(DocumentProcessingQueue, Document.display_name).join(
            Document, DocumentProcessingQueue.document_id == Document.id
        )
        if filters:
            items_query = items_query.where(and_(*filters))

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        items_query = (
            items_query.order_by(DocumentProcessingQueue.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(items_query)
        items = [(row[0], row[1]) for row in result.all()]

        return items, total

    async def manual_retry(
        self, queue_item_id: UUID, reset_attempts: bool = False
    ) -> DocumentProcessingQueue | None:
        """Manually retry a failed queue item.

        Args:
            queue_item_id: ID of the queue item
            reset_attempts: If True, reset attempts to 0

        Returns:
            Updated queue item or None if not found
        """
        result = await self.db.execute(
            select(DocumentProcessingQueue).where(
                DocumentProcessingQueue.id == queue_item_id
            )
        )
        queue_item = result.scalar_one_or_none()

        if not queue_item:
            return None

        if reset_attempts:
            queue_item.attempts = 0

        queue_item.status = DocumentQueueStatus.PENDING
        queue_item.next_retry = datetime.now(UTC)
        queue_item.error_message = None

        logger.info(
            "document_queue_item_manual_retry",
            queue_id=str(queue_item.id),
            document_id=str(queue_item.document_id),
            reset_attempts=reset_attempts,
        )

        await self.db.flush()
        return queue_item

    async def cancel_item(self, queue_item_id: UUID) -> bool:
        """Cancel a pending queue item by removing it.

        Only pending items can be cancelled. In-progress items should
        complete or fail naturally.

        Args:
            queue_item_id: ID of the queue item

        Returns:
            True if item was cancelled, False if not found or not cancellable
        """
        from sqlalchemy import delete

        result = await self.db.execute(
            select(DocumentProcessingQueue).where(
                DocumentProcessingQueue.id == queue_item_id
            )
        )
        queue_item = result.scalar_one_or_none()

        if not queue_item:
            return False

        # Only allow cancelling pending items
        if queue_item.status != DocumentQueueStatus.PENDING:
            return False

        await self.db.execute(
            delete(DocumentProcessingQueue).where(
                DocumentProcessingQueue.id == queue_item_id
            )
        )

        logger.info(
            "document_queue_item_cancelled",
            queue_id=str(queue_item_id),
            document_id=str(queue_item.document_id),
        )

        await self.db.flush()
        return True


async def process_document_queue() -> dict:
    """Process pending document queue items.

    This function is designed to be called from a cron endpoint.
    It creates its own database session.

    Returns:
        Dict with processing results
    """
    # Import here to avoid circular imports
    from app.core.storage import StorageService
    from app.models.document import Document
    from app.services.document_processing_task import _process_document_content

    logger.info("document_queue_processing_started")

    results = {
        "status": "success",
        "items_processed": 0,
        "items_succeeded": 0,
        "items_failed": 0,
        "items_requeued": 0,
        "items_max_retries": 0,
        "items_recovered": 0,
        "errors": [],
        "timestamp": datetime.now(UTC).isoformat(),
    }

    async with async_session_maker() as db:
        try:
            service = DocumentQueueService(db)

            # Recover stuck items first
            recovered = await service.recover_stuck_items()
            results["items_recovered"] = recovered
            if recovered > 0:
                await db.commit()
                logger.info("document_queue_stuck_items_recovered", count=recovered)

            pending_items = await service.get_pending_items(limit=50)

            if not pending_items:
                logger.info("document_queue_no_pending_items")
                return results

            logger.info("document_queue_items_found", count=len(pending_items))

            for item in pending_items:
                results["items_processed"] += 1

                try:
                    await service.mark_in_progress(item)
                    await db.commit()

                    # Process with fresh session for isolation
                    async with async_session_maker() as process_db:
                        # Fetch document
                        doc_result = await process_db.execute(
                            select(Document).where(Document.id == item.document_id)
                        )
                        document = doc_result.scalar_one_or_none()

                        if not document:
                            raise ValueError(f"Document {item.document_id} not found")

                        # Read file content
                        storage = StorageService()
                        try:
                            file_content = await storage.read(document.file_path)
                        except FileNotFoundError:
                            raise ValueError(
                                f"File not found in storage: {document.file_path}"
                            )

                        # Process document content
                        await _process_document_content(
                            process_db, document, file_content
                        )
                        await process_db.commit()

                    # Mark as completed with fresh session
                    async with async_session_maker() as update_db:
                        update_service = DocumentQueueService(update_db)
                        result = await update_db.execute(
                            select(DocumentProcessingQueue).where(
                                DocumentProcessingQueue.id == item.id
                            )
                        )
                        fresh_item = result.scalar_one_or_none()
                        if fresh_item:
                            await update_service.mark_completed(fresh_item)
                        await update_db.commit()

                    results["items_succeeded"] += 1

                except Exception as e:
                    error_str = str(e)
                    results["items_failed"] += 1
                    results["errors"].append(
                        f"Document {item.document_id}: {error_str[:100]}"
                    )

                    logger.exception(
                        "document_queue_item_processing_error",
                        queue_id=str(item.id),
                        document_id=str(item.document_id),
                        error=error_str,
                    )

                    # Mark for retry with fresh session
                    try:
                        async with async_session_maker() as error_db:
                            error_service = DocumentQueueService(error_db)
                            result = await error_db.execute(
                                select(DocumentProcessingQueue).where(
                                    DocumentProcessingQueue.id == item.id
                                )
                            )
                            fresh_item = result.scalar_one_or_none()
                            if fresh_item:
                                requeued = await error_service.mark_failed_retry(
                                    fresh_item, error_str
                                )
                                if requeued:
                                    results["items_requeued"] += 1
                                else:
                                    results["items_max_retries"] += 1
                            await error_db.commit()
                    except Exception as inner_e:
                        logger.exception(
                            "document_queue_failed_to_mark_error",
                            queue_id=str(item.id),
                            inner_error=str(inner_e),
                        )

        except Exception as e:
            results["status"] = "error"
            results["errors"].append(f"Queue processing error: {str(e)}")
            logger.exception("document_queue_processing_error", error=str(e))

    if results["items_failed"] > 0 and results["items_succeeded"] > 0:
        results["status"] = "partial"
    elif results["items_failed"] > 0:
        results["status"] = "error"

    logger.info(
        "document_queue_processing_completed",
        processed=results["items_processed"],
        succeeded=results["items_succeeded"],
        failed=results["items_failed"],
        requeued=results["items_requeued"],
        max_retries=results["items_max_retries"],
        recovered=results["items_recovered"],
    )

    return results
