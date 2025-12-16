"""Tag suggestion service with fuzzy matching and deduplication."""

from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag, TagType


class TagSuggester:
    """Service for suggesting tags with fuzzy matching and deduplication."""

    # Minimum similarity score (0-1) for fuzzy matches
    FUZZY_THRESHOLD = 0.6

    def __init__(self, db: AsyncSession):
        self.db = db

    def _similarity(self, a: str, b: str) -> float:
        """Calculate similarity ratio between two strings."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    async def suggest_tags(
        self,
        query: str,
        *,
        tag_type: TagType | None = None,
        limit: int = 10,
        include_fuzzy: bool = True,
    ) -> list[tuple[Tag, float, str | None]]:
        """
        Suggest tags based on query with fuzzy matching.

        Returns list of tuples: (tag, similarity_score, suggestion_reason)
        - suggestion_reason is None for exact/prefix matches
        - suggestion_reason is "Did you mean {exact_name}?" for fuzzy matches
        """
        if not query or len(query) < 2:
            return []

        query_lower = query.lower().strip()

        # Build base query
        stmt = select(Tag)
        if tag_type:
            stmt = stmt.where(Tag.type == tag_type)

        result = await self.db.execute(stmt)
        all_tags = result.scalars().all()

        suggestions: list[tuple[Tag, float, str | None]] = []

        for tag in all_tags:
            tag_name_lower = tag.name.lower()

            # Exact match - highest priority
            if tag_name_lower == query_lower:
                suggestions.append((tag, 1.0, None))
                continue

            # Prefix match - high priority
            if tag_name_lower.startswith(query_lower):
                # Score based on how much of the tag matches
                score = len(query_lower) / len(tag_name_lower)
                suggestions.append((tag, 0.9 + score * 0.1, None))
                continue

            # Contains match - medium priority
            if query_lower in tag_name_lower:
                score = len(query_lower) / len(tag_name_lower)
                suggestions.append((tag, 0.7 + score * 0.2, None))
                continue

            # Fuzzy match - for catching typos
            if include_fuzzy:
                similarity = self._similarity(query_lower, tag_name_lower)
                if similarity >= self.FUZZY_THRESHOLD:
                    suggestions.append((tag, similarity, f"Did you mean '{tag.name}'?"))

        # Sort by score descending
        suggestions.sort(key=lambda x: x[1], reverse=True)

        return suggestions[:limit]

    async def check_duplicate(
        self,
        name: str,
        tag_type: TagType | None = None,
    ) -> Tag | None:
        """
        Check if a tag with similar name already exists.

        Returns the existing tag if found, None otherwise.
        """
        name_lower = name.lower().strip()

        # Check for exact match (case-insensitive)
        stmt = select(Tag).where(func.lower(Tag.name) == name_lower)
        if tag_type:
            stmt = stmt.where(Tag.type == tag_type)

        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Check for very similar names (typo detection)
        stmt = select(Tag)
        if tag_type:
            stmt = stmt.where(Tag.type == tag_type)

        result = await self.db.execute(stmt)
        all_tags = result.scalars().all()

        for tag in all_tags:
            similarity = self._similarity(name, tag.name)
            if similarity >= 0.85:  # Higher threshold for duplicate detection
                return tag

        return None

    async def get_popular_tags(
        self,
        tag_type: TagType | None = None,
        limit: int = 10,
    ) -> list[tuple[Tag, int]]:
        """
        Get most frequently used tags.

        Returns list of tuples: (tag, usage_count)
        """
        from app.models.project import ProjectTag

        # Count tag usage
        stmt = (
            select(Tag, func.count(ProjectTag.project_id).label("usage_count"))
            .outerjoin(ProjectTag, Tag.id == ProjectTag.tag_id)
            .group_by(Tag.id)
            .order_by(func.count(ProjectTag.project_id).desc())
            .limit(limit)
        )

        if tag_type:
            stmt = stmt.where(Tag.type == tag_type)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [(row[0], row[1]) for row in rows]

    async def get_cooccurrence_suggestions(
        self,
        selected_tag_ids: list[UUID],
        limit: int = 5,
    ) -> list[tuple[Tag, int]]:
        """
        Get tag suggestions based on co-occurrence with selected tags.

        Returns tags that frequently appear alongside the selected tags,
        ordered by co-occurrence frequency.

        Returns list of tuples: (tag, co_occurrence_count)
        """
        if not selected_tag_ids:
            return []

        from sqlalchemy.orm import aliased

        from app.models.project import ProjectTag

        # Create aliases for the self-join
        pt1 = aliased(ProjectTag)  # For selected tags
        pt2 = aliased(ProjectTag)  # For co-occurring tags

        # Query: Find tags that appear in the same projects as selected tags
        stmt = (
            select(Tag, func.count(pt1.project_id.distinct()).label("co_count"))
            .join(pt2, pt2.tag_id == Tag.id)  # Join tags to pt2
            .join(pt1, (pt1.project_id == pt2.project_id) & (pt1.tag_id != pt2.tag_id))
            .where(pt1.tag_id.in_(selected_tag_ids))
            .where(~Tag.id.in_(selected_tag_ids))  # Exclude already selected
            .group_by(Tag.id)
            .order_by(func.count(pt1.project_id.distinct()).desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [(row[0], row[1]) for row in rows]

    async def merge_tags(
        self,
        source_tag_id: UUID,
        target_tag_id: UUID,
    ) -> int:
        """
        Merge one tag into another (admin operation).

        Updates all project associations from source to target, then deletes source.
        Returns the number of projects updated.
        """
        from sqlalchemy import delete, update

        from app.models.project import ProjectTag

        # Get existing associations for target tag
        target_stmt = select(ProjectTag.project_id).where(
            ProjectTag.tag_id == target_tag_id
        )
        result = await self.db.execute(target_stmt)
        existing_project_ids = {row[0] for row in result.all()}

        # Get associations for source tag
        source_stmt = select(ProjectTag).where(ProjectTag.tag_id == source_tag_id)
        result = await self.db.execute(source_stmt)
        source_associations = result.scalars().all()

        updated_count = 0

        for assoc in source_associations:
            if assoc.project_id in existing_project_ids:
                # Project already has target tag, just delete source association
                await self.db.execute(
                    delete(ProjectTag).where(
                        ProjectTag.project_id == assoc.project_id,
                        ProjectTag.tag_id == source_tag_id,
                    )
                )
            else:
                # Update to point to target tag
                await self.db.execute(
                    update(ProjectTag)
                    .where(
                        ProjectTag.project_id == assoc.project_id,
                        ProjectTag.tag_id == source_tag_id,
                    )
                    .values(tag_id=target_tag_id)
                )
                updated_count += 1

        # Delete the source tag
        await self.db.execute(delete(Tag).where(Tag.id == source_tag_id))

        return updated_count
