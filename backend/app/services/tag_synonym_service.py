"""Tag synonym service for managing synonym relationships.

Provides CRUD operations for tag synonyms with transitive closure support.
If A~B and B~C, then get_synonyms(A) returns {B, C}.

Transitive Closure Algorithm:
- Graph representation: Tags are nodes, TagSynonym records are bidirectional edges
- Algorithm: Breadth-First Search (BFS) from the starting tag
- Handles: Self-reference prevention (A~A not allowed), cycles (via visited set),
           large synonym networks (iterative BFS avoids stack overflow)
- Performance note: For very large synonym networks with thousands of connected tags,
                   consider adding caching (e.g., Redis) in future versions.
"""

from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Tag, TagSynonym
from app.models.project import ProjectTag
from app.schemas.tag import TagResponse, TagSynonymCreate, TagWithSynonyms

logger = get_logger(__name__)


class TagSynonymService:
    """Service for managing tag synonym relationships."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session.

        Args:
            db: AsyncSession for database operations
        """
        self.db = db

    async def get_synonyms(self, tag_id: UUID) -> list[Tag]:
        """Get all synonyms for a tag (transitive closure).

        Uses BFS to traverse the synonym graph and find all transitively
        connected tags. If A~B and B~C, returns both B and C for get_synonyms(A).

        Args:
            tag_id: The tag to find synonyms for

        Returns:
            List of all transitively connected tags (excluding the input tag)

        Note:
            For large synonym networks, consider implementing caching
            as this method queries the database for each level of the graph.
        """
        # BFS to find all connected tags
        visited: set[UUID] = {tag_id}
        queue: list[UUID] = [tag_id]
        synonyms: list[Tag] = []

        while queue:
            current_id = queue.pop(0)

            # Find direct synonyms (both directions since relationship is symmetric)
            result = await self.db.execute(
                select(TagSynonym).where(
                    (TagSynonym.tag_id == current_id)
                    | (TagSynonym.synonym_tag_id == current_id)
                )
            )
            synonym_records = result.scalars().all()

            for record in synonym_records:
                # Get the "other" tag in the relationship
                other_id = (
                    record.synonym_tag_id
                    if record.tag_id == current_id
                    else record.tag_id
                )

                if other_id not in visited:
                    visited.add(other_id)
                    queue.append(other_id)

                    # Fetch the actual tag
                    tag_result = await self.db.execute(
                        select(Tag).where(Tag.id == other_id)
                    )
                    tag = tag_result.scalar_one_or_none()
                    if tag:
                        synonyms.append(tag)

        return synonyms

    async def add_synonym(
        self,
        tag_id: UUID,
        synonym_tag_id: UUID,
        confidence: float = 1.0,
        created_by: UUID | None = None,
    ) -> TagSynonym | None:
        """Create a synonym relationship between two tags.

        The relationship is symmetric - if A~B, then B~A is implied.
        Only one record is stored.

        Args:
            tag_id: First tag ID
            synonym_tag_id: Second tag ID (synonym of first)
            confidence: Confidence score (1.0 = manual, <1.0 = AI-suggested)
            created_by: User who created the relationship

        Returns:
            TagSynonym record if created, None if already exists or tags are same
        """
        if tag_id == synonym_tag_id:
            logger.warning("cannot_create_self_synonym", tag_id=str(tag_id))
            return None

        # Verify both tags exist
        tag1_result = await self.db.execute(select(Tag).where(Tag.id == tag_id))
        tag2_result = await self.db.execute(select(Tag).where(Tag.id == synonym_tag_id))

        if not tag1_result.scalar_one_or_none() or not tag2_result.scalar_one_or_none():
            logger.warning(
                "synonym_tag_not_found",
                tag_id=str(tag_id),
                synonym_tag_id=str(synonym_tag_id),
            )
            return None

        # Check if relationship already exists (either direction)
        existing = await self.db.execute(
            select(TagSynonym).where(
                (
                    (TagSynonym.tag_id == tag_id)
                    & (TagSynonym.synonym_tag_id == synonym_tag_id)
                )
                | (
                    (TagSynonym.tag_id == synonym_tag_id)
                    & (TagSynonym.synonym_tag_id == tag_id)
                )
            )
        )
        if existing.scalar_one_or_none():
            logger.debug(
                "synonym_already_exists",
                tag_id=str(tag_id),
                synonym_tag_id=str(synonym_tag_id),
            )
            return None

        # Create new synonym relationship
        synonym = TagSynonym(
            tag_id=tag_id,
            synonym_tag_id=synonym_tag_id,
            confidence=confidence,
            created_by=created_by,
        )
        self.db.add(synonym)
        await self.db.flush()

        logger.info(
            "synonym_created",
            tag_id=str(tag_id),
            synonym_tag_id=str(synonym_tag_id),
            confidence=confidence,
        )

        return synonym

    async def remove_synonym(
        self,
        tag_id: UUID,
        synonym_tag_id: UUID,
    ) -> bool:
        """Remove a synonym relationship between two tags.

        Args:
            tag_id: First tag ID
            synonym_tag_id: Second tag ID

        Returns:
            True if relationship was removed, False if not found
        """
        # Delete relationship (check both directions since storage order may vary)
        result = await self.db.execute(
            delete(TagSynonym).where(
                (
                    (TagSynonym.tag_id == tag_id)
                    & (TagSynonym.synonym_tag_id == synonym_tag_id)
                )
                | (
                    (TagSynonym.tag_id == synonym_tag_id)
                    & (TagSynonym.synonym_tag_id == tag_id)
                )
            )
        )

        deleted = result.rowcount > 0

        if deleted:
            logger.info(
                "synonym_removed",
                tag_id=str(tag_id),
                synonym_tag_id=str(synonym_tag_id),
            )

        return deleted

    async def merge_tags(
        self,
        source_id: UUID,
        target_id: UUID,
        created_by: UUID | None = None,
    ) -> int:
        """Merge source tag into target tag, preserving synonym relationships.

        All project associations are moved from source to target.
        All synonym relationships from source are transferred to target.
        The source tag is then deleted.

        Args:
            source_id: Tag to merge from (will be deleted)
            target_id: Tag to merge into (will be kept)
            created_by: User performing the merge

        Returns:
            Number of projects updated
        """
        if source_id == target_id:
            logger.warning("cannot_merge_same_tag", tag_id=str(source_id))
            return 0

        # Get all synonyms of source tag (before merge)
        source_synonyms = await self.get_synonyms(source_id)
        source_synonym_ids = {s.id for s in source_synonyms}

        # Get all synonyms of target tag
        target_synonyms = await self.get_synonyms(target_id)
        target_synonym_ids = {s.id for s in target_synonyms}

        # Find synonyms to transfer (source synonyms not already target synonyms)
        # Exclude target_id since we don't want target to be its own synonym
        synonyms_to_transfer = source_synonym_ids - target_synonym_ids - {target_id}

        # Create new synonym relationships for target
        for syn_id in synonyms_to_transfer:
            await self.add_synonym(
                target_id, syn_id, confidence=1.0, created_by=created_by
            )

        # Update ProjectTag references
        # Get existing associations for target tag
        target_stmt = select(ProjectTag.project_id).where(
            ProjectTag.tag_id == target_id
        )
        result = await self.db.execute(target_stmt)
        existing_project_ids = {row[0] for row in result.all()}

        # Get associations for source tag
        source_stmt = select(ProjectTag).where(ProjectTag.tag_id == source_id)
        result = await self.db.execute(source_stmt)
        source_associations = result.scalars().all()

        updated_count = 0

        for assoc in source_associations:
            if assoc.project_id in existing_project_ids:
                # Project already has target tag, just delete source association
                await self.db.execute(
                    delete(ProjectTag).where(
                        ProjectTag.project_id == assoc.project_id,
                        ProjectTag.tag_id == source_id,
                    )
                )
            else:
                # Update to point to target tag
                await self.db.execute(
                    update(ProjectTag)
                    .where(
                        ProjectTag.project_id == assoc.project_id,
                        ProjectTag.tag_id == source_id,
                    )
                    .values(tag_id=target_id)
                )
                updated_count += 1

        # Delete source tag (cascades to TagSynonym via FK)
        await self.db.execute(delete(Tag).where(Tag.id == source_id))

        logger.info(
            "tags_merged",
            source_id=str(source_id),
            target_id=str(target_id),
            projects_updated=updated_count,
            synonyms_transferred=len(synonyms_to_transfer),
        )

        return updated_count

    async def bulk_import_synonyms(
        self,
        synonyms: list[TagSynonymCreate],
        created_by: UUID | None = None,
    ) -> int:
        """Bulk import synonym relationships.

        Skips duplicates and invalid entries (non-existent tags, self-synonyms).

        Args:
            synonyms: List of TagSynonymCreate objects
            created_by: User performing the import

        Returns:
            Number of synonyms successfully created
        """
        created_count = 0

        for syn in synonyms:
            result = await self.add_synonym(
                tag_id=syn.tag_id,
                synonym_tag_id=syn.synonym_tag_id,
                confidence=syn.confidence,
                created_by=created_by,
            )
            if result:
                created_count += 1

        logger.info(
            "synonyms_bulk_imported",
            total_requested=len(synonyms),
            created=created_count,
            skipped=len(synonyms) - created_count,
        )

        return created_count

    async def get_tag_with_synonyms(self, tag_id: UUID) -> TagWithSynonyms | None:
        """Get a tag with all its synonyms attached.

        Args:
            tag_id: The tag ID to fetch

        Returns:
            TagWithSynonyms or None if tag not found
        """
        result = await self.db.execute(select(Tag).where(Tag.id == tag_id))
        tag = result.scalar_one_or_none()

        if not tag:
            return None

        synonyms = await self.get_synonyms(tag_id)

        return TagWithSynonyms(
            id=tag.id,
            name=tag.name,
            type=tag.type,
            synonyms=[TagResponse.model_validate(s) for s in synonyms],
        )
