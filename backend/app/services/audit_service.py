"""Audit logging service for tracking entity changes."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit import AuditAction, AuditLog

logger = get_logger(__name__)


class AuditService:
    """Service for capturing and recording entity changes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def compute_diff(
        old_data: dict[str, Any],
        new_data: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Compute differences between old and new data.

        Args:
            old_data: Previous state of the entity
            new_data: New state of the entity

        Returns:
            Dict mapping field names to {"old": value, "new": value}
            Only includes fields that actually changed.
        """
        changes: dict[str, dict[str, Any]] = {}
        all_keys = set(old_data.keys()) | set(new_data.keys())

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)

            # Handle comparison of different types gracefully
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}

        return changes

    async def log_create(
        self,
        entity_type: str,
        entity_id: UUID,
        entity_data: dict[str, Any],
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log entity creation.

        Args:
            entity_type: Type of entity ('project', 'contact', etc.)
            entity_id: UUID of the created entity
            entity_data: Data of the created entity (stored in changed_fields as new values)
            user_id: UUID of the user who performed the action
            metadata: Additional context (IP, user agent, etc.)

        Returns:
            Created AuditLog record
        """
        # For creates, show all fields as new values
        changed_fields = {
            key: {"old": None, "new": value}
            for key, value in entity_data.items()
            if value is not None
        }

        audit_log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=AuditAction.CREATE,
            user_id=user_id,
            changed_fields=changed_fields,
            metadata_=metadata,
        )

        self.db.add(audit_log)
        await self.db.flush()
        await self.db.refresh(audit_log)

        logger.info(
            "audit_log_created",
            entity_type=entity_type,
            entity_id=str(entity_id),
            action="create",
            user_id=str(user_id) if user_id else None,
        )

        return audit_log

    async def log_update(
        self,
        entity_type: str,
        entity_id: UUID,
        old_data: dict[str, Any],
        new_data: dict[str, Any],
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog | None:
        """Log entity update.

        Args:
            entity_type: Type of entity ('project', 'contact', etc.)
            entity_id: UUID of the updated entity
            old_data: Previous state of the entity
            new_data: New state of the entity
            user_id: UUID of the user who performed the action
            metadata: Additional context (IP, user agent, etc.)

        Returns:
            Created AuditLog record, or None if no changes detected
        """
        changed_fields = self.compute_diff(old_data, new_data)

        if not changed_fields:
            logger.debug(
                "audit_log_skipped",
                entity_type=entity_type,
                entity_id=str(entity_id),
                reason="no_changes",
            )
            return None

        audit_log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=AuditAction.UPDATE,
            user_id=user_id,
            changed_fields=changed_fields,
            metadata_=metadata,
        )

        self.db.add(audit_log)
        await self.db.flush()
        await self.db.refresh(audit_log)

        logger.info(
            "audit_log_created",
            entity_type=entity_type,
            entity_id=str(entity_id),
            action="update",
            user_id=str(user_id) if user_id else None,
            fields_changed=list(changed_fields.keys()),
        )

        return audit_log

    async def log_delete(
        self,
        entity_type: str,
        entity_id: UUID,
        entity_data: dict[str, Any],
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log entity deletion.

        Args:
            entity_type: Type of entity ('project', 'contact', etc.)
            entity_id: UUID of the deleted entity
            entity_data: Data of the deleted entity (preserved as old values)
            user_id: UUID of the user who performed the action
            metadata: Additional context (IP, user agent, etc.)

        Returns:
            Created AuditLog record
        """
        # For deletes, show all fields as old values being removed
        changed_fields = {
            key: {"old": value, "new": None}
            for key, value in entity_data.items()
            if value is not None
        }

        audit_log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=AuditAction.DELETE,
            user_id=user_id,
            changed_fields=changed_fields,
            metadata_=metadata,
        )

        self.db.add(audit_log)
        await self.db.flush()
        await self.db.refresh(audit_log)

        logger.info(
            "audit_log_created",
            entity_type=entity_type,
            entity_id=str(entity_id),
            action="delete",
            user_id=str(user_id) if user_id else None,
        )

        return audit_log

    @staticmethod
    def serialize_entity(
        entity: Any,
        include_fields: list[str] | None = None,
        exclude_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Serialize a SQLAlchemy model to a JSON-friendly dict.

        Args:
            entity: SQLAlchemy model instance
            include_fields: If provided, only include these fields
            exclude_fields: Fields to exclude (relationships, computed, etc.)

        Returns:
            Dict representation suitable for audit logging
        """
        exclude = set(exclude_fields or [])
        # Default exclusions for common non-serializable fields
        exclude.update(
            {
                "_sa_instance_state",
                "search_vector",  # TSVECTOR not JSON serializable
            }
        )

        result: dict[str, Any] = {}
        for key in dir(entity):
            if key.startswith("_"):
                continue
            if key in exclude:
                continue
            if include_fields and key not in include_fields:
                continue

            try:
                value = getattr(entity, key)
                # Skip methods and relationships
                if callable(value):
                    continue
                # Convert UUIDs to strings
                if isinstance(value, UUID):
                    value = str(value)
                # Convert dates/datetimes to ISO format
                elif hasattr(value, "isoformat"):
                    value = value.isoformat()
                # Convert enums to their value
                elif hasattr(value, "value"):
                    value = value.value
                # Skip non-JSON-serializable types
                elif not isinstance(
                    value, str | int | float | bool | list | dict | type(None)
                ):
                    continue
                result[key] = value
            except (AttributeError, TypeError, ValueError):
                # Skip attributes that can't be accessed or serialized.
                # Some entity attributes may be lazy-loaded relationships,
                # computed properties, or non-serializable types.
                continue

        return result
