"""Auto-resolution rule management and execution service.

Manages auto-resolution rules and applies them during conflict detection
to automatically resolve matching conflicts without manual intervention.
"""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.monday_sync import (
    AutoResolutionRule,
    PreferredSource,
)

logger = get_logger(__name__)


class AutoResolutionService:
    """Service for managing auto-resolution rules."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_rules(self) -> tuple[list[AutoResolutionRule], int]:
        """Get all rules ordered by priority (highest first).

        Returns:
            Tuple of (rules list, total count)
        """
        # Get total count
        total = (
            await self.db.scalar(select(func.count()).select_from(AutoResolutionRule))
            or 0
        )

        # Get rules ordered by priority descending
        result = await self.db.execute(
            select(AutoResolutionRule).order_by(
                AutoResolutionRule.priority.desc(), AutoResolutionRule.created_at
            )
        )
        rules = list(result.scalars().all())

        return rules, total

    async def get_by_id(self, rule_id: UUID) -> AutoResolutionRule | None:
        """Get a rule by ID."""
        result = await self.db.execute(
            select(AutoResolutionRule).where(AutoResolutionRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        entity_type: str,
        preferred_source: PreferredSource,
        field_name: str | None = None,
        is_enabled: bool = True,
        priority: int = 0,
        created_by_id: UUID | None = None,
    ) -> AutoResolutionRule:
        """Create a new auto-resolution rule."""
        rule = AutoResolutionRule(
            name=name,
            entity_type=entity_type,
            field_name=field_name,
            preferred_source=preferred_source,
            is_enabled=is_enabled,
            priority=priority,
            created_by_id=created_by_id,
        )
        self.db.add(rule)
        await self.db.flush()

        logger.info(
            "auto_resolution_rule_created",
            rule_id=str(rule.id),
            name=name,
            entity_type=entity_type,
            field_name=field_name,
            preferred_source=preferred_source.value,
        )

        return rule

    async def update(
        self,
        rule_id: UUID,
        name: str | None = None,
        entity_type: str | None = None,
        field_name: str | None = None,
        preferred_source: PreferredSource | None = None,
        is_enabled: bool | None = None,
        priority: int | None = None,
    ) -> AutoResolutionRule | None:
        """Update an existing rule."""
        rule = await self.get_by_id(rule_id)
        if not rule:
            return None

        if name is not None:
            rule.name = name
        if entity_type is not None:
            rule.entity_type = entity_type
        if field_name is not None:
            rule.field_name = field_name
        if preferred_source is not None:
            rule.preferred_source = preferred_source
        if is_enabled is not None:
            rule.is_enabled = is_enabled
        if priority is not None:
            rule.priority = priority

        await self.db.flush()

        logger.info(
            "auto_resolution_rule_updated",
            rule_id=str(rule_id),
        )

        return rule

    async def delete(self, rule_id: UUID) -> bool:
        """Delete a rule. Returns True if deleted, False if not found."""
        rule = await self.get_by_id(rule_id)
        if not rule:
            return False

        await self.db.delete(rule)
        await self.db.flush()

        logger.info(
            "auto_resolution_rule_deleted",
            rule_id=str(rule_id),
        )

        return True

    async def reorder(self, rule_ids: list[UUID]) -> list[AutoResolutionRule]:
        """Reorder rules by setting priorities based on position.

        First rule in list gets highest priority.
        """
        for i, rule_id in enumerate(rule_ids):
            # Higher index = lower priority (first item = highest)
            priority = len(rule_ids) - i
            await self.db.execute(
                update(AutoResolutionRule)
                .where(AutoResolutionRule.id == rule_id)
                .values(priority=priority)
            )

        await self.db.flush()

        # Return updated rules
        rules_list, _ = await self.list_rules()
        return rules_list

    async def find_matching_rule(
        self,
        entity_type: str,
        field_name: str | None = None,
    ) -> AutoResolutionRule | None:
        """Find the highest-priority matching rule for an entity/field.

        Matching logic:
        1. Field-specific rules take precedence over entity-wide rules
        2. Among matching rules, highest priority wins
        3. Only enabled rules are considered

        Args:
            entity_type: 'contact' or 'organization'
            field_name: Optional specific field name

        Returns:
            Matching rule or None
        """
        # Build query for enabled rules that match
        # Priority: field-specific > entity-wide > wildcard
        base_query = (
            select(AutoResolutionRule)
            .where(AutoResolutionRule.is_enabled == True)  # noqa: E712
            .order_by(AutoResolutionRule.priority.desc())
        )

        # Try field-specific rule first
        if field_name:
            field_query = base_query.where(
                AutoResolutionRule.entity_type.in_([entity_type, "*"]),
                AutoResolutionRule.field_name == field_name,
            )
            result = await self.db.execute(field_query)
            rule = result.scalar_first()
            if rule:
                return rule

        # Try entity-wide rule (field_name is null)
        entity_query = base_query.where(
            AutoResolutionRule.entity_type.in_([entity_type, "*"]),
            AutoResolutionRule.field_name.is_(None),
        )
        result = await self.db.execute(entity_query)
        return result.scalar_first()

    async def try_auto_resolve(
        self,
        entity_type: str,
        entity_id: UUID,
        conflict_fields: list[str],
        npd_data: dict,  # noqa: ARG002 - kept for future audit logging
        monday_data: dict,  # noqa: ARG002 - kept for future audit logging
        resolved_by_id: UUID | None = None,  # noqa: ARG002 - kept for future audit
    ) -> tuple[bool, AutoResolutionRule | None, str | None]:
        """Attempt to auto-resolve a conflict using matching rules.

        Args:
            entity_type: 'contact' or 'organization'
            entity_id: UUID of the entity
            conflict_fields: List of fields in conflict
            npd_data: NPD field values
            monday_data: Monday field values
            resolved_by_id: Optional user ID for audit (usually None for auto)

        Returns:
            Tuple of (was_auto_resolved, matching_rule, resolution_type)
        """
        # Check each conflict field for a matching rule
        for field in conflict_fields:
            rule = await self.find_matching_rule(entity_type, field)
            if rule:
                resolution_type = (
                    "keep_npd"
                    if rule.preferred_source == PreferredSource.NPD
                    else "keep_monday"
                )

                logger.info(
                    "auto_resolution_rule_matched",
                    entity_type=entity_type,
                    entity_id=str(entity_id),
                    field=field,
                    rule_id=str(rule.id),
                    rule_name=rule.name,
                    preferred_source=rule.preferred_source.value,
                )

                return True, rule, resolution_type

        # Check for entity-wide rule
        rule = await self.find_matching_rule(entity_type, None)
        if rule:
            resolution_type = (
                "keep_npd"
                if rule.preferred_source == PreferredSource.NPD
                else "keep_monday"
            )

            logger.info(
                "auto_resolution_rule_matched",
                entity_type=entity_type,
                entity_id=str(entity_id),
                field="(entity-wide)",
                rule_id=str(rule.id),
                rule_name=rule.name,
                preferred_source=rule.preferred_source.value,
            )

            return True, rule, resolution_type

        return False, None, None
