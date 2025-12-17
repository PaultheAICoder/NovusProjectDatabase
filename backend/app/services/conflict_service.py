"""Conflict detection and resolution service for Monday.com sync.

Manages sync conflicts between NPD and Monday.com, providing methods
to list, view, and resolve conflicts.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.monday_sync import RecordSyncStatus, SyncConflict
from app.models.organization import Organization
from app.schemas.monday import ConflictResolutionType

logger = get_logger(__name__)
settings = get_settings()


class ConflictService:
    """Service for managing sync conflicts between NPD and Monday.com."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_unresolved(
        self,
        page: int = 1,
        page_size: int = 20,
        entity_type: str | None = None,
    ) -> tuple[list[SyncConflict], int]:
        """Get paginated list of unresolved conflicts.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            entity_type: Optional filter by 'contact' or 'organization'

        Returns:
            Tuple of (conflicts list, total count)
        """
        # Build base query for unresolved conflicts
        base_query = select(SyncConflict).where(SyncConflict.resolved_at.is_(None))

        if entity_type:
            base_query = base_query.where(SyncConflict.entity_type == entity_type)

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        offset = (page - 1) * page_size
        result = await self.db.execute(
            base_query.order_by(SyncConflict.detected_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        conflicts = list(result.scalars().all())

        return conflicts, total

    async def get_by_id(self, conflict_id: UUID) -> SyncConflict | None:
        """Get a specific conflict by ID.

        Args:
            conflict_id: UUID of the conflict

        Returns:
            SyncConflict or None if not found
        """
        result = await self.db.execute(
            select(SyncConflict).where(SyncConflict.id == conflict_id)
        )
        return result.scalar_one_or_none()

    async def resolve(
        self,
        conflict_id: UUID,
        resolution_type: ConflictResolutionType,
        resolved_by_id: UUID,
        merge_selections: dict[str, str] | None = None,
    ) -> SyncConflict | None:
        """Resolve a sync conflict.

        Args:
            conflict_id: UUID of the conflict to resolve
            resolution_type: How to resolve (keep_npd, keep_monday, merge)
            resolved_by_id: UUID of the user resolving the conflict
            merge_selections: For merge resolution, dict of field -> 'npd'|'monday'

        Returns:
            Updated SyncConflict or None if not found
        """
        conflict = await self.get_by_id(conflict_id)
        if not conflict:
            return None

        if conflict.resolved_at:
            logger.warning(
                "conflict_already_resolved",
                conflict_id=str(conflict_id),
            )
            return conflict

        # Get the entity
        entity = await self._get_entity(conflict.entity_type, conflict.entity_id)
        if not entity:
            logger.error(
                "conflict_entity_not_found",
                conflict_id=str(conflict_id),
                entity_type=conflict.entity_type,
                entity_id=str(conflict.entity_id),
            )
            return None

        # Apply resolution
        if resolution_type == ConflictResolutionType.KEEP_NPD:
            await self._apply_keep_npd(conflict, entity)
        elif resolution_type == ConflictResolutionType.KEEP_MONDAY:
            await self._apply_keep_monday(conflict, entity)
        elif resolution_type == ConflictResolutionType.MERGE:
            if not merge_selections:
                logger.error(
                    "merge_requires_selections",
                    conflict_id=str(conflict_id),
                )
                raise ValueError("Merge resolution requires merge_selections")
            await self._apply_merge(conflict, entity, merge_selections)

        # Mark as resolved
        conflict.resolved_at = datetime.now(UTC)
        conflict.resolution_type = resolution_type.value
        conflict.resolved_by_id = resolved_by_id

        # Update entity sync status
        entity.sync_status = RecordSyncStatus.SYNCED

        await self.db.flush()

        logger.info(
            "conflict_resolved",
            conflict_id=str(conflict_id),
            resolution_type=resolution_type.value,
            resolved_by=str(resolved_by_id),
        )

        return conflict

    async def _get_entity(
        self, entity_type: str, entity_id: UUID
    ) -> Contact | Organization | None:
        """Get the entity associated with a conflict."""
        if entity_type == "contact":
            result = await self.db.execute(
                select(Contact).where(Contact.id == entity_id)
            )
            return result.scalar_one_or_none()
        elif entity_type == "organization":
            result = await self.db.execute(
                select(Organization).where(Organization.id == entity_id)
            )
            return result.scalar_one_or_none()
        return None

    async def _apply_keep_npd(
        self,
        conflict: SyncConflict,
        entity: Contact | Organization,
    ) -> None:
        """Apply keep_npd resolution: push NPD data to Monday.

        Triggers background sync to push NPD data to Monday.com.
        """
        from app.services.sync_service import (
            sync_contact_to_monday,
            sync_organization_to_monday,
        )

        logger.info(
            "applying_keep_npd_resolution",
            conflict_id=str(conflict.id),
            entity_type=conflict.entity_type,
            entity_id=str(entity.id),
        )

        # Trigger sync to Monday.com (this runs in background)
        # We use the sync service which handles all the column mapping
        if conflict.entity_type == "contact":
            await sync_contact_to_monday(entity.id)
        elif conflict.entity_type == "organization":
            await sync_organization_to_monday(entity.id)

    async def _apply_keep_monday(
        self,
        conflict: SyncConflict,
        entity: Contact | Organization,
    ) -> None:
        """Apply keep_monday resolution: update NPD with Monday data."""
        logger.info(
            "applying_keep_monday_resolution",
            conflict_id=str(conflict.id),
            entity_type=conflict.entity_type,
            entity_id=str(entity.id),
        )

        # Apply Monday.com data to NPD entity
        monday_data = conflict.monday_data
        for field in conflict.conflict_fields:
            if field in monday_data and hasattr(entity, field):
                value = monday_data[field]
                # Handle nested values (e.g., {"text": "value"})
                if isinstance(value, dict):
                    value = (
                        value.get("text") or value.get("value") or value.get("email")
                    )
                setattr(entity, field, value)

        # Update sync timestamp
        entity.monday_last_synced = datetime.now(UTC)

    async def _apply_merge(
        self,
        conflict: SyncConflict,
        entity: Contact | Organization,
        merge_selections: dict[str, str],
    ) -> None:
        """Apply merge resolution: apply field-level selections.

        Args:
            conflict: The conflict being resolved
            entity: The NPD entity
            merge_selections: Dict of field_name -> 'npd' or 'monday'
        """
        logger.info(
            "applying_merge_resolution",
            conflict_id=str(conflict.id),
            entity_type=conflict.entity_type,
            entity_id=str(entity.id),
            selections=merge_selections,
        )

        monday_data = conflict.monday_data

        for field, source in merge_selections.items():
            if field not in conflict.conflict_fields:
                continue

            if source == "monday" and field in monday_data:
                value = monday_data[field]
                if isinstance(value, dict):
                    value = (
                        value.get("text") or value.get("value") or value.get("email")
                    )
                if hasattr(entity, field):
                    setattr(entity, field, value)
            # For 'npd' source, the entity already has NPD values, no change needed

        # After merge, sync the merged result to Monday
        from app.services.sync_service import (
            sync_contact_to_monday,
            sync_organization_to_monday,
        )

        entity.monday_last_synced = datetime.now(UTC)

        if conflict.entity_type == "contact":
            await sync_contact_to_monday(entity.id)
        elif conflict.entity_type == "organization":
            await sync_organization_to_monday(entity.id)

    async def get_conflict_stats(self) -> dict:
        """Get conflict statistics.

        Returns:
            Dict with unresolved/resolved counts
        """
        unresolved = (
            await self.db.scalar(
                select(func.count())
                .select_from(SyncConflict)
                .where(SyncConflict.resolved_at.is_(None))
            )
            or 0
        )

        resolved = (
            await self.db.scalar(
                select(func.count())
                .select_from(SyncConflict)
                .where(SyncConflict.resolved_at.is_not(None))
            )
            or 0
        )

        return {
            "unresolved": unresolved,
            "resolved": resolved,
            "total": unresolved + resolved,
        }
