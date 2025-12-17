"""Tests for import service tag resolution.

Bug fix for GitHub Issue #69: CSV import drops unknown tags instead of creating freeform tags.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.tag import TagType
from app.services.import_service import ImportService


class TestResolveTagsMethod:
    """Tests for _resolve_tags method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def import_service(self, mock_db):
        """Create an import service instance."""
        return ImportService(mock_db)

    @pytest.mark.asyncio
    async def test_resolve_existing_tag_returns_id(self, import_service, mock_db):
        """Existing tags should return their IDs."""
        existing_tag = MagicMock()
        existing_tag.id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_tag
        mock_db.execute.return_value = mock_result

        tag_ids = await import_service._resolve_tags(["Python"])

        assert len(tag_ids) == 1
        assert tag_ids[0] == existing_tag.id

    @pytest.mark.asyncio
    async def test_resolve_unknown_tag_creates_freeform(self, import_service, mock_db):
        """Unknown tags should create freeform tags when create_missing=True."""
        user_id = uuid4()

        # First call returns None (tag not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        await import_service._resolve_tags(
            ["NewTag"], user_id=user_id, create_missing=True
        )

        # Verify tag was added
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

        # Verify the tag was created with correct type
        created_tag = mock_db.add.call_args[0][0]
        assert created_tag.name == "NewTag"
        assert created_tag.type == TagType.FREEFORM
        assert created_tag.created_by == user_id

    @pytest.mark.asyncio
    async def test_resolve_empty_list_returns_empty(self, import_service, mock_db):
        """Empty tag list should return empty list."""
        tag_ids = await import_service._resolve_tags([])
        assert tag_ids == []
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_whitespace_tags_skipped(self, import_service, mock_db):
        """Whitespace-only tag names should be skipped."""
        tag_ids = await import_service._resolve_tags(["  ", "", "\t"])
        assert tag_ids == []
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_case_insensitive(self, import_service, mock_db):
        """Tag resolution should be case-insensitive."""
        existing_tag = MagicMock()
        existing_tag.id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_tag
        mock_db.execute.return_value = mock_result

        tag_ids = await import_service._resolve_tags(["PYTHON"])

        assert len(tag_ids) == 1
        # Verify query was executed (case-insensitive lookup)
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_preview_import_does_not_create_without_flag(
        self, import_service, mock_db
    ):
        """Without create_missing=True, unknown tags should not be created."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        tag_ids = await import_service._resolve_tags(
            ["UnknownTag"], create_missing=False  # Default behavior
        )

        # Should not create tag
        mock_db.add.assert_not_called()
        assert tag_ids == []

    @pytest.mark.asyncio
    async def test_resolve_mixed_existing_and_new_tags(self, import_service, mock_db):
        """Mix of existing and new tags should resolve existing and create new."""
        user_id = uuid4()
        existing_tag = MagicMock()
        existing_tag.id = uuid4()

        # First tag exists, second doesn't
        call_count = 0

        def mock_execute_side_effect(*args):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.scalar_one_or_none.return_value = existing_tag
            else:
                result.scalar_one_or_none.return_value = None
            call_count += 1
            return result

        mock_db.execute.side_effect = mock_execute_side_effect

        tag_ids = await import_service._resolve_tags(
            ["Python", "NewTag"], user_id=user_id, create_missing=True
        )

        # Should have 2 tag IDs
        assert len(tag_ids) == 2
        # First should be the existing tag ID
        assert tag_ids[0] == existing_tag.id
        # Second should be the newly created tag ID
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_strips_whitespace_from_names(self, import_service, mock_db):
        """Tag names should have whitespace stripped before lookup."""
        existing_tag = MagicMock()
        existing_tag.id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_tag
        mock_db.execute.return_value = mock_result

        tag_ids = await import_service._resolve_tags(["  Python  "])

        assert len(tag_ids) == 1
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_creates_tag_without_user_id(self, import_service, mock_db):
        """Tag can be created even without user_id (for backwards compatibility)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        await import_service._resolve_tags(
            ["NewTag"], user_id=None, create_missing=True
        )

        # Tag should still be created
        mock_db.add.assert_called_once()
        created_tag = mock_db.add.call_args[0][0]
        assert created_tag.created_by is None
