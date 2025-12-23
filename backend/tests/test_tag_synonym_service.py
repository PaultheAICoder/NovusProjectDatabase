"""Tests for TagSynonymService."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models import Tag, TagSynonym, TagType
from app.models.project import ProjectTag
from app.schemas.tag import TagSynonymCreate
from app.services.tag_synonym_service import TagSynonymService


class TestGetSynonyms:
    """Tests for get_synonyms method (transitive closure)."""

    @pytest.mark.asyncio
    async def test_get_synonyms_returns_direct_synonyms(self):
        """Test that direct synonyms are returned."""
        tag_a_id = uuid4()
        tag_b_id = uuid4()

        mock_tag_b = MagicMock(spec=Tag)
        mock_tag_b.id = tag_b_id
        mock_tag_b.name = "Tag B"
        mock_tag_b.type = TagType.FREEFORM

        mock_synonym = MagicMock(spec=TagSynonym)
        mock_synonym.tag_id = tag_a_id
        mock_synonym.synonym_tag_id = tag_b_id

        mock_db = AsyncMock()

        # First query returns the synonym record for tag_a
        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.all.return_value = [mock_synonym]

        # Second query returns the tag_b
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_tag_b

        # Third query returns no more synonyms (for tag_b)
        mock_result3 = MagicMock()
        mock_result3.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_result1, mock_result2, mock_result3]

        service = TagSynonymService(mock_db)
        synonyms = await service.get_synonyms(tag_a_id)

        assert len(synonyms) == 1
        assert synonyms[0].id == tag_b_id

    @pytest.mark.asyncio
    async def test_get_synonyms_transitive_closure(self):
        """Test that transitive synonyms are returned (A~B, B~C -> A gets both B and C)."""
        tag_a_id = uuid4()
        tag_b_id = uuid4()
        tag_c_id = uuid4()

        # A~B synonym
        mock_synonym_ab = MagicMock(spec=TagSynonym)
        mock_synonym_ab.tag_id = tag_a_id
        mock_synonym_ab.synonym_tag_id = tag_b_id

        # B~C synonym
        mock_synonym_bc = MagicMock(spec=TagSynonym)
        mock_synonym_bc.tag_id = tag_b_id
        mock_synonym_bc.synonym_tag_id = tag_c_id

        mock_tag_b = MagicMock(spec=Tag)
        mock_tag_b.id = tag_b_id
        mock_tag_b.name = "Tag B"
        mock_tag_b.type = TagType.FREEFORM

        mock_tag_c = MagicMock(spec=Tag)
        mock_tag_c.id = tag_c_id
        mock_tag_c.name = "Tag C"
        mock_tag_c.type = TagType.FREEFORM

        mock_db = AsyncMock()

        # First query: synonyms of A -> returns A~B
        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.all.return_value = [mock_synonym_ab]

        # Second query: fetch tag B
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_tag_b

        # Third query: synonyms of B -> returns B~C (and A~B again but A is visited)
        mock_result3 = MagicMock()
        mock_result3.scalars.return_value.all.return_value = [
            mock_synonym_ab,
            mock_synonym_bc,
        ]

        # Fourth query: fetch tag C
        mock_result4 = MagicMock()
        mock_result4.scalar_one_or_none.return_value = mock_tag_c

        # Fifth query: synonyms of C -> returns B~C but B is visited
        mock_result5 = MagicMock()
        mock_result5.scalars.return_value.all.return_value = [mock_synonym_bc]

        mock_db.execute.side_effect = [
            mock_result1,
            mock_result2,
            mock_result3,
            mock_result4,
            mock_result5,
        ]

        service = TagSynonymService(mock_db)
        synonyms = await service.get_synonyms(tag_a_id)

        assert len(synonyms) == 2
        synonym_ids = {s.id for s in synonyms}
        assert tag_b_id in synonym_ids
        assert tag_c_id in synonym_ids

    @pytest.mark.asyncio
    async def test_get_synonyms_handles_cycles(self):
        """Test that cycles don't cause infinite loops (A~B, B~C, C~A)."""
        tag_a_id = uuid4()
        tag_b_id = uuid4()
        tag_c_id = uuid4()

        # Create cycle: A~B, B~C, C~A
        mock_synonym_ab = MagicMock(spec=TagSynonym)
        mock_synonym_ab.tag_id = tag_a_id
        mock_synonym_ab.synonym_tag_id = tag_b_id

        mock_synonym_bc = MagicMock(spec=TagSynonym)
        mock_synonym_bc.tag_id = tag_b_id
        mock_synonym_bc.synonym_tag_id = tag_c_id

        mock_synonym_ca = MagicMock(spec=TagSynonym)
        mock_synonym_ca.tag_id = tag_c_id
        mock_synonym_ca.synonym_tag_id = tag_a_id

        mock_tag_b = MagicMock(spec=Tag)
        mock_tag_b.id = tag_b_id

        mock_tag_c = MagicMock(spec=Tag)
        mock_tag_c.id = tag_c_id

        mock_db = AsyncMock()

        # First: synonyms of A -> A~B, C~A
        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.all.return_value = [
            mock_synonym_ab,
            mock_synonym_ca,
        ]

        # Fetch B
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_tag_b

        # Fetch C
        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = mock_tag_c

        # Synonyms of B -> A~B (A visited), B~C
        mock_result4 = MagicMock()
        mock_result4.scalars.return_value.all.return_value = [
            mock_synonym_ab,
            mock_synonym_bc,
        ]

        # Synonyms of C -> B~C (B visited), C~A (A visited)
        mock_result5 = MagicMock()
        mock_result5.scalars.return_value.all.return_value = [
            mock_synonym_bc,
            mock_synonym_ca,
        ]

        mock_db.execute.side_effect = [
            mock_result1,
            mock_result2,
            mock_result3,
            mock_result4,
            mock_result5,
        ]

        service = TagSynonymService(mock_db)
        synonyms = await service.get_synonyms(tag_a_id)

        # Should complete without infinite loop and return B and C
        assert len(synonyms) == 2
        synonym_ids = {s.id for s in synonyms}
        assert tag_b_id in synonym_ids
        assert tag_c_id in synonym_ids

    @pytest.mark.asyncio
    async def test_get_synonyms_empty_for_no_synonyms(self):
        """Test that empty list returned when tag has no synonyms."""
        tag_id = uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = TagSynonymService(mock_db)
        synonyms = await service.get_synonyms(tag_id)

        assert synonyms == []


class TestAddSynonym:
    """Tests for add_synonym method."""

    @pytest.mark.asyncio
    async def test_add_synonym_creates_relationship(self):
        """Test successful synonym creation."""
        tag_id = uuid4()
        synonym_tag_id = uuid4()
        user_id = uuid4()

        mock_tag1 = MagicMock(spec=Tag)
        mock_tag2 = MagicMock(spec=Tag)

        mock_db = AsyncMock()
        # Mock tag existence checks
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_tag1
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_tag2
        # Mock existing check (none found)
        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_result1, mock_result2, mock_result3]
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = TagSynonymService(mock_db)
        result = await service.add_synonym(
            tag_id, synonym_tag_id, confidence=1.0, created_by=user_id
        )

        assert result is not None
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_synonym_rejects_self_synonym(self):
        """Test that self-synonym returns None."""
        tag_id = uuid4()

        mock_db = AsyncMock()
        service = TagSynonymService(mock_db)

        result = await service.add_synonym(tag_id, tag_id)

        assert result is None
        # No database operations should be called
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_synonym_returns_none_for_missing_first_tag(self):
        """Test that missing first tag returns None."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TagSynonymService(mock_db)
        result = await service.add_synonym(uuid4(), uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_add_synonym_returns_none_for_missing_second_tag(self):
        """Test that missing second tag returns None."""
        mock_tag1 = MagicMock(spec=Tag)

        mock_db = AsyncMock()
        # First tag exists
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_tag1
        # Second tag does not exist
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        service = TagSynonymService(mock_db)
        result = await service.add_synonym(uuid4(), uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_add_synonym_returns_none_for_existing_relationship(self):
        """Test that duplicate relationship returns None."""
        tag_id = uuid4()
        synonym_tag_id = uuid4()

        mock_tag1 = MagicMock(spec=Tag)
        mock_tag2 = MagicMock(spec=Tag)
        mock_existing_synonym = MagicMock(spec=TagSynonym)

        mock_db = AsyncMock()
        # Both tags exist
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_tag1
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_tag2
        # Existing relationship found
        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = mock_existing_synonym

        mock_db.execute.side_effect = [mock_result1, mock_result2, mock_result3]

        service = TagSynonymService(mock_db)
        result = await service.add_synonym(tag_id, synonym_tag_id)

        assert result is None


class TestRemoveSynonym:
    """Tests for remove_synonym method."""

    @pytest.mark.asyncio
    async def test_remove_synonym_deletes_relationship(self):
        """Test successful synonym removal."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result

        service = TagSynonymService(mock_db)
        result = await service.remove_synonym(uuid4(), uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_synonym_returns_false_when_not_found(self):
        """Test that False returned when relationship doesn't exist."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        service = TagSynonymService(mock_db)
        result = await service.remove_synonym(uuid4(), uuid4())

        assert result is False


class TestMergeTags:
    """Tests for merge_tags method."""

    @pytest.mark.asyncio
    async def test_merge_tags_rejects_same_tag(self):
        """Test that merging tag with itself returns 0."""
        tag_id = uuid4()

        mock_db = AsyncMock()
        service = TagSynonymService(mock_db)

        result = await service.merge_tags(tag_id, tag_id)

        assert result == 0
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_merge_tags_transfers_synonyms(self):
        """Test that source tag synonyms are transferred to target."""
        source_id = uuid4()
        target_id = uuid4()
        synonym_id = uuid4()
        user_id = uuid4()

        # Source has synonym that target doesn't have
        mock_source_synonym_tag = MagicMock(spec=Tag)
        mock_source_synonym_tag.id = synonym_id

        mock_db = AsyncMock()

        # Mock get_synonyms for source: returns synonym_id
        mock_result1 = MagicMock()
        mock_source_synonym_record = MagicMock(spec=TagSynonym)
        mock_source_synonym_record.tag_id = source_id
        mock_source_synonym_record.synonym_tag_id = synonym_id
        mock_result1.scalars.return_value.all.return_value = [
            mock_source_synonym_record
        ]

        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_source_synonym_tag

        mock_result3 = MagicMock()
        mock_result3.scalars.return_value.all.return_value = []

        # Mock get_synonyms for target: returns empty
        mock_result4 = MagicMock()
        mock_result4.scalars.return_value.all.return_value = []

        # Mock add_synonym calls (tag exists check + no existing synonym)
        mock_result5 = MagicMock()
        mock_result5.scalar_one_or_none.return_value = MagicMock(spec=Tag)
        mock_result6 = MagicMock()
        mock_result6.scalar_one_or_none.return_value = MagicMock(spec=Tag)
        mock_result7 = MagicMock()
        mock_result7.scalar_one_or_none.return_value = None

        # Mock ProjectTag queries
        mock_result8 = MagicMock()
        mock_result8.all.return_value = []  # target has no projects
        mock_result9 = MagicMock()
        mock_result9.scalars.return_value.all.return_value = (
            []
        )  # source has no projects

        # Mock delete source tag
        mock_result10 = MagicMock()

        mock_db.execute.side_effect = [
            mock_result1,
            mock_result2,
            mock_result3,
            mock_result4,
            mock_result5,
            mock_result6,
            mock_result7,
            mock_result8,
            mock_result9,
            mock_result10,
        ]
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = TagSynonymService(mock_db)
        result = await service.merge_tags(source_id, target_id, created_by=user_id)

        # Should have called db.add for the new synonym
        assert mock_db.add.called
        # No project updates (no source associations)
        assert result == 0

    @pytest.mark.asyncio
    async def test_merge_tags_updates_project_associations(self):
        """Test that project associations are transferred."""
        source_id = uuid4()
        target_id = uuid4()
        project_id = uuid4()

        mock_db = AsyncMock()

        # Mock get_synonyms for source and target: both empty
        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.all.return_value = []
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []

        # Mock ProjectTag queries
        mock_result3 = MagicMock()
        mock_result3.all.return_value = []  # target has no projects

        # Source has one project association
        mock_project_tag = MagicMock(spec=ProjectTag)
        mock_project_tag.project_id = project_id
        mock_project_tag.tag_id = source_id
        mock_result4 = MagicMock()
        mock_result4.scalars.return_value.all.return_value = [mock_project_tag]

        # Update result
        mock_result5 = MagicMock()
        mock_result5.rowcount = 1

        # Delete source tag result
        mock_result6 = MagicMock()

        mock_db.execute.side_effect = [
            mock_result1,
            mock_result2,
            mock_result3,
            mock_result4,
            mock_result5,
            mock_result6,
        ]
        mock_db.flush = AsyncMock()

        service = TagSynonymService(mock_db)
        result = await service.merge_tags(source_id, target_id)

        # One project should be updated
        assert result == 1


class TestBulkImportSynonyms:
    """Tests for bulk_import_synonyms method."""

    @pytest.mark.asyncio
    async def test_bulk_import_creates_multiple_synonyms(self):
        """Test that multiple synonyms are created."""
        tag1_id = uuid4()
        tag2_id = uuid4()
        tag3_id = uuid4()
        user_id = uuid4()

        synonyms = [
            TagSynonymCreate(tag_id=tag1_id, synonym_tag_id=tag2_id),
            TagSynonymCreate(tag_id=tag2_id, synonym_tag_id=tag3_id),
        ]

        mock_tag = MagicMock(spec=Tag)

        mock_db = AsyncMock()

        # For each synonym, we need: tag1 exists, tag2 exists, no existing relationship
        mock_tag_exists = MagicMock()
        mock_tag_exists.scalar_one_or_none.return_value = mock_tag
        mock_no_existing = MagicMock()
        mock_no_existing.scalar_one_or_none.return_value = None

        # 2 synonyms * 3 queries each = 6 execute calls
        mock_db.execute.side_effect = [
            mock_tag_exists,
            mock_tag_exists,
            mock_no_existing,
            mock_tag_exists,
            mock_tag_exists,
            mock_no_existing,
        ]
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = TagSynonymService(mock_db)
        result = await service.bulk_import_synonyms(synonyms, created_by=user_id)

        assert result == 2
        assert mock_db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_bulk_import_skips_duplicates(self):
        """Test that duplicates are skipped, not errored."""
        tag1_id = uuid4()
        tag2_id = uuid4()

        synonyms = [
            TagSynonymCreate(tag_id=tag1_id, synonym_tag_id=tag2_id),
            TagSynonymCreate(tag_id=tag1_id, synonym_tag_id=tag2_id),  # Duplicate
        ]

        mock_tag = MagicMock(spec=Tag)
        mock_existing = MagicMock(spec=TagSynonym)

        mock_db = AsyncMock()

        # First synonym creates
        mock_tag_exists = MagicMock()
        mock_tag_exists.scalar_one_or_none.return_value = mock_tag
        mock_no_existing = MagicMock()
        mock_no_existing.scalar_one_or_none.return_value = None
        mock_existing_found = MagicMock()
        mock_existing_found.scalar_one_or_none.return_value = mock_existing

        mock_db.execute.side_effect = [
            mock_tag_exists,
            mock_tag_exists,
            mock_no_existing,  # First creates
            mock_tag_exists,
            mock_tag_exists,
            mock_existing_found,  # Second finds existing
        ]
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = TagSynonymService(mock_db)
        result = await service.bulk_import_synonyms(synonyms)

        assert result == 1  # Only one created, second was skipped
        assert mock_db.add.call_count == 1

    @pytest.mark.asyncio
    async def test_bulk_import_returns_correct_count(self):
        """Test that count reflects only successful creates."""
        tag1_id = uuid4()
        tag2_id = uuid4()

        # One valid, one self-reference
        synonyms = [
            TagSynonymCreate(tag_id=tag1_id, synonym_tag_id=tag2_id),
            TagSynonymCreate(tag_id=tag1_id, synonym_tag_id=tag1_id),  # Self-ref
        ]

        mock_tag = MagicMock(spec=Tag)

        mock_db = AsyncMock()

        # First synonym creates
        mock_tag_exists = MagicMock()
        mock_tag_exists.scalar_one_or_none.return_value = mock_tag
        mock_no_existing = MagicMock()
        mock_no_existing.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [
            mock_tag_exists,
            mock_tag_exists,
            mock_no_existing,
            # Second is self-ref, no queries made
        ]
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = TagSynonymService(mock_db)
        result = await service.bulk_import_synonyms(synonyms)

        assert result == 1


class TestGetTagWithSynonyms:
    """Tests for get_tag_with_synonyms method."""

    @pytest.mark.asyncio
    async def test_get_tag_with_synonyms_returns_tag_and_synonyms(self):
        """Test that tag and all synonyms are returned."""
        tag_id = uuid4()
        synonym_id = uuid4()

        mock_tag = MagicMock(spec=Tag)
        mock_tag.id = tag_id
        mock_tag.name = "Main Tag"
        mock_tag.type = TagType.TECHNOLOGY

        mock_synonym_tag = MagicMock(spec=Tag)
        mock_synonym_tag.id = synonym_id
        mock_synonym_tag.name = "Synonym Tag"
        mock_synonym_tag.type = TagType.TECHNOLOGY

        mock_db = AsyncMock()

        # Get main tag
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_tag

        # Get synonyms - synonym record
        mock_synonym_record = MagicMock(spec=TagSynonym)
        mock_synonym_record.tag_id = tag_id
        mock_synonym_record.synonym_tag_id = synonym_id
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [mock_synonym_record]

        # Fetch synonym tag
        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = mock_synonym_tag

        # No more synonyms for the synonym
        mock_result4 = MagicMock()
        mock_result4.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [
            mock_result1,
            mock_result2,
            mock_result3,
            mock_result4,
        ]

        service = TagSynonymService(mock_db)
        result = await service.get_tag_with_synonyms(tag_id)

        assert result is not None
        assert result.id == tag_id
        assert result.name == "Main Tag"
        assert len(result.synonyms) == 1
        assert result.synonyms[0].id == synonym_id

    @pytest.mark.asyncio
    async def test_get_tag_with_synonyms_returns_none_for_missing_tag(self):
        """Test that None is returned when tag not found."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TagSynonymService(mock_db)
        result = await service.get_tag_with_synonyms(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_tag_with_synonyms_returns_empty_list_when_no_synonyms(self):
        """Test that empty synonyms list returned when tag has no synonyms."""
        tag_id = uuid4()

        mock_tag = MagicMock(spec=Tag)
        mock_tag.id = tag_id
        mock_tag.name = "Lone Tag"
        mock_tag.type = TagType.FREEFORM

        mock_db = AsyncMock()

        # Get main tag
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_tag

        # No synonyms
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        service = TagSynonymService(mock_db)
        result = await service.get_tag_with_synonyms(tag_id)

        assert result is not None
        assert result.id == tag_id
        assert result.synonyms == []
