"""Sync queue service for retry mechanism.

Manages queuing of failed sync operations and processes them
with exponential backoff.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.database import async_session_maker
from app.models.monday_sync import (
    SyncQueue,
    SyncQueueDirection,
    SyncQueueOperation,
    SyncQueueStatus,
)

logger = get_logger(__name__)
settings = get_settings()

# Exponential backoff schedule in minutes
# Attempt 1: Immediate (initial failure queued)
# Attempt 2: +1 minute
# Attempt 3: +5 minutes
# Attempt 4: +15 minutes
# Attempt 5: +60 minutes (1 hour)
BACKOFF_SCHEDULE_MINUTES = [0, 1, 5, 15, 60]


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


class SyncQueueService:
    """Service for managing sync queue operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue(
        self,
        entity_type: str,
        entity_id: UUID,
        direction: SyncQueueDirection,
        operation: SyncQueueOperation,
        error_message: str | None = None,
        payload: dict | None = None,
    ) -> SyncQueue:
        """Add a sync operation to the queue.

        Handles deduplication - if an item for the same entity/direction
        is already pending, updates it instead of creating a duplicate.

        Args:
            entity_type: 'contact' or 'organization'
            entity_id: UUID of the entity
            direction: TO_MONDAY or TO_NPD
            operation: CREATE, UPDATE, or DELETE
            error_message: Optional error from the failed attempt
            payload: Optional JSON data for the operation

        Returns:
            The created or updated SyncQueue item
        """
        # Check for existing pending item for same entity/direction
        result = await self.db.execute(
            select(SyncQueue).where(
                and_(
                    SyncQueue.entity_type == entity_type,
                    SyncQueue.entity_id == entity_id,
                    SyncQueue.direction == direction,
                    SyncQueue.status.in_(
                        [
                            SyncQueueStatus.PENDING,
                            SyncQueueStatus.IN_PROGRESS,
                        ]
                    ),
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing item - increment attempts, update error
            existing.attempts += 1
            existing.last_attempt = datetime.now(UTC)
            existing.next_retry = calculate_next_retry(existing.attempts)
            existing.error_message = error_message
            existing.status = SyncQueueStatus.PENDING
            if payload:
                existing.payload = payload

            logger.info(
                "sync_queue_item_updated",
                queue_id=str(existing.id),
                entity_type=entity_type,
                entity_id=str(entity_id),
                attempts=existing.attempts,
            )

            await self.db.flush()
            return existing

        # Create new queue item
        queue_item = SyncQueue(
            entity_type=entity_type,
            entity_id=entity_id,
            direction=direction,
            operation=operation,
            payload=payload,
            status=SyncQueueStatus.PENDING,
            attempts=1,  # First attempt already failed
            last_attempt=datetime.now(UTC),
            next_retry=calculate_next_retry(1),
            error_message=error_message,
        )
        self.db.add(queue_item)
        await self.db.flush()

        logger.info(
            "sync_queue_item_created",
            queue_id=str(queue_item.id),
            entity_type=entity_type,
            entity_id=str(entity_id),
            direction=direction.value,
            operation=operation.value,
        )

        return queue_item

    async def get_pending_items(self, limit: int = 50) -> list[SyncQueue]:
        """Get pending items that are due for retry.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of pending SyncQueue items
        """
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(SyncQueue)
            .where(
                and_(
                    SyncQueue.status == SyncQueueStatus.PENDING,
                    SyncQueue.next_retry <= now,
                )
            )
            .order_by(SyncQueue.next_retry.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_failed_items(self, limit: int = 100) -> list[SyncQueue]:
        """Get items that have failed permanently (max retries exceeded).

        Args:
            limit: Maximum number of items to return

        Returns:
            List of failed SyncQueue items
        """
        result = await self.db.execute(
            select(SyncQueue)
            .where(SyncQueue.status == SyncQueueStatus.FAILED)
            .order_by(SyncQueue.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_in_progress(self, queue_item: SyncQueue) -> None:
        """Mark a queue item as in progress."""
        queue_item.status = SyncQueueStatus.IN_PROGRESS
        await self.db.flush()

    async def mark_completed(self, queue_item: SyncQueue) -> None:
        """Mark a queue item as completed (remove from queue)."""
        queue_item.status = SyncQueueStatus.COMPLETED
        await self.db.flush()

        logger.info(
            "sync_queue_item_completed",
            queue_id=str(queue_item.id),
            entity_type=queue_item.entity_type,
            entity_id=str(queue_item.entity_id),
            total_attempts=queue_item.attempts,
        )

    async def mark_failed_retry(
        self, queue_item: SyncQueue, error_message: str
    ) -> bool:
        """Mark a queue item for retry or as failed if max attempts reached.

        Args:
            queue_item: The queue item to update
            error_message: Error from the failed attempt

        Returns:
            True if requeued for retry, False if marked as permanently failed
        """
        queue_item.attempts += 1
        queue_item.last_attempt = datetime.now(UTC)
        queue_item.error_message = error_message

        if queue_item.attempts >= queue_item.max_attempts:
            queue_item.status = SyncQueueStatus.FAILED
            queue_item.next_retry = None

            logger.warning(
                "sync_queue_item_max_retries",
                queue_id=str(queue_item.id),
                entity_type=queue_item.entity_type,
                entity_id=str(queue_item.entity_id),
                total_attempts=queue_item.attempts,
                error=error_message,
            )
            await self.db.flush()
            return False

        queue_item.status = SyncQueueStatus.PENDING
        queue_item.next_retry = calculate_next_retry(queue_item.attempts)

        logger.info(
            "sync_queue_item_requeued",
            queue_id=str(queue_item.id),
            entity_type=queue_item.entity_type,
            entity_id=str(queue_item.entity_id),
            attempts=queue_item.attempts,
            next_retry=queue_item.next_retry.isoformat(),
        )
        await self.db.flush()
        return True

    async def manual_retry(
        self, queue_item_id: UUID, reset_attempts: bool = False
    ) -> SyncQueue | None:
        """Manually retry a failed queue item.

        Args:
            queue_item_id: ID of the queue item
            reset_attempts: If True, reset attempts to 0

        Returns:
            Updated queue item or None if not found
        """
        result = await self.db.execute(
            select(SyncQueue).where(SyncQueue.id == queue_item_id)
        )
        queue_item = result.scalar_one_or_none()

        if not queue_item:
            return None

        if reset_attempts:
            queue_item.attempts = 0

        queue_item.status = SyncQueueStatus.PENDING
        queue_item.next_retry = datetime.now(UTC)
        queue_item.error_message = None

        logger.info(
            "sync_queue_item_manual_retry",
            queue_id=str(queue_item.id),
            reset_attempts=reset_attempts,
        )

        await self.db.flush()
        return queue_item

    async def get_queue_stats(self) -> dict:
        """Get queue statistics.

        Returns:
            Dict with counts by status
        """
        result = await self.db.execute(
            select(
                SyncQueue.status,
                func.count(SyncQueue.id).label("count"),
            ).group_by(SyncQueue.status)
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
        entity_type: str | None = None,
        direction: SyncQueueDirection | None = None,
        status: SyncQueueStatus | None = None,
    ) -> tuple[list[SyncQueue], int]:
        """Get all queue items with filtering and pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            entity_type: Filter by entity type ('contact' or 'organization')
            direction: Filter by sync direction
            status: Filter by status

        Returns:
            Tuple of (list of queue items, total count)
        """
        # Build base query with filters
        filters = []
        if entity_type:
            filters.append(SyncQueue.entity_type == entity_type)
        if direction:
            filters.append(SyncQueue.direction == direction)
        if status:
            filters.append(SyncQueue.status == status)

        base_query = select(SyncQueue)
        count_query = select(func.count(SyncQueue.id))

        if filters:
            base_query = base_query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        # Get total count
        total = await self.db.scalar(count_query) or 0

        # Get paginated items
        offset = (page - 1) * page_size
        result = await self.db.execute(
            base_query.order_by(SyncQueue.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())

        return items, total


async def process_sync_queue() -> dict:
    """Process pending sync queue items.

    This function is designed to be called from a cron endpoint.
    It creates its own database session.

    Returns:
        Dict with processing results
    """
    # Import sync functions here to avoid circular imports
    from app.services.sync_service import (
        sync_contact_to_monday,
        sync_organization_to_monday,
    )

    logger.info("sync_queue_processing_started")

    results = {
        "status": "success",
        "items_processed": 0,
        "items_succeeded": 0,
        "items_failed": 0,
        "items_requeued": 0,
        "items_max_retries": 0,
        "errors": [],
        "timestamp": datetime.now(UTC).isoformat(),
    }

    async with async_session_maker() as db:
        try:
            service = SyncQueueService(db)
            pending_items = await service.get_pending_items(limit=50)

            if not pending_items:
                logger.info("sync_queue_no_pending_items")
                return results

            logger.info("sync_queue_items_found", count=len(pending_items))

            for item in pending_items:
                results["items_processed"] += 1

                try:
                    await service.mark_in_progress(item)
                    await db.commit()

                    # Execute the sync based on direction and entity type
                    success = False
                    error_msg = None

                    if item.direction == SyncQueueDirection.TO_MONDAY:
                        if item.entity_type == "contact":
                            # Call sync function - it handles its own session
                            await sync_contact_to_monday(item.entity_id)
                            success = True
                        elif item.entity_type == "organization":
                            await sync_organization_to_monday(item.entity_id)
                            success = True
                        else:
                            error_msg = f"Unknown entity type: {item.entity_type}"

                    elif item.direction == SyncQueueDirection.TO_NPD:
                        # TO_NPD direction would be handled by webhook processing
                        # Queue items for this direction would be for retry
                        # of webhook processing
                        error_msg = (
                            "TO_NPD direction not implemented in queue processor"
                        )
                    else:
                        error_msg = f"Unknown direction: {item.direction}"

                    # Re-fetch item with fresh session to update
                    async with async_session_maker() as update_db:
                        update_service = SyncQueueService(update_db)
                        result = await update_db.execute(
                            select(SyncQueue).where(SyncQueue.id == item.id)
                        )
                        fresh_item = result.scalar_one_or_none()

                        if fresh_item:
                            if success:
                                await update_service.mark_completed(fresh_item)
                                results["items_succeeded"] += 1
                            else:
                                requeued = await update_service.mark_failed_retry(
                                    fresh_item, error_msg or "Unknown error"
                                )
                                if requeued:
                                    results["items_requeued"] += 1
                                else:
                                    results["items_max_retries"] += 1

                        await update_db.commit()

                except Exception as e:
                    error_str = str(e)
                    results["items_failed"] += 1
                    results["errors"].append(f"Item {item.id}: {error_str[:100]}")

                    logger.exception(
                        "sync_queue_item_processing_error",
                        queue_id=str(item.id),
                        error=error_str,
                    )

                    # Try to mark as failed with fresh session
                    try:
                        async with async_session_maker() as error_db:
                            error_service = SyncQueueService(error_db)
                            result = await error_db.execute(
                                select(SyncQueue).where(SyncQueue.id == item.id)
                            )
                            fresh_item = result.scalar_one_or_none()
                            if fresh_item:
                                await error_service.mark_failed_retry(
                                    fresh_item, error_str
                                )
                            await error_db.commit()
                    except Exception as inner_e:
                        logger.exception(
                            "sync_queue_failed_to_mark_error",
                            queue_id=str(item.id),
                            inner_error=str(inner_e),
                        )

        except Exception as e:
            results["status"] = "error"
            results["errors"].append(f"Queue processing error: {str(e)}")
            logger.exception("sync_queue_processing_error", error=str(e))

    if results["items_failed"] > 0 and results["items_succeeded"] > 0:
        results["status"] = "partial"
    elif results["items_failed"] > 0:
        results["status"] = "error"

    logger.info(
        "sync_queue_processing_completed",
        processed=results["items_processed"],
        succeeded=results["items_succeeded"],
        failed=results["items_failed"],
        requeued=results["items_requeued"],
    )

    return results
