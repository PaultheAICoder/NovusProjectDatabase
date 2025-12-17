"""Document processing queue service.

Manages queuing of document processing operations and processes them
with the existing document processing logic.
"""

from datetime import UTC, datetime
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
        """Mark a queue item as failed.

        Note: Retry logic will be added in Phase 3 (#98).
        For now, failures are permanent.

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
        "errors": [],
        "timestamp": datetime.now(UTC).isoformat(),
    }

    async with async_session_maker() as db:
        try:
            service = DocumentQueueService(db)
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

                    # Mark as failed with fresh session
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
                                await error_service.mark_failed(fresh_item, error_str)
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
    )

    return results
