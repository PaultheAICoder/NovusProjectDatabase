"""Tests for tag synonym admin API endpoints and schemas."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import Tag, TagSynonym, TagType
from app.schemas.tag import (
    TagResponse,
    TagSynonymCreate,
    TagSynonymDetail,
    TagSynonymImportRequest,
    TagSynonymImportResponse,
    TagSynonymListResponse,
    TagWithSynonyms,
)
from app.services.tag_synonym_service import TagSynonymService


class TestTagSynonymSchemas:
    """Tests for tag synonym Pydantic schemas."""

    def test_synonym_create_schema_valid(self):
        """Test valid synonym create schema."""
        tag_id = uuid4()
        synonym_tag_id = uuid4()

        data = TagSynonymCreate(
            tag_id=tag_id,
            synonym_tag_id=synonym_tag_id,
            confidence=0.9,
        )

        assert data.tag_id == tag_id
        assert data.synonym_tag_id == synonym_tag_id
        assert data.confidence == 0.9

    def test_synonym_create_schema_default_confidence(self):
        """Test that confidence defaults to 1.0."""
        tag_id = uuid4()
        synonym_tag_id = uuid4()

        data = TagSynonymCreate(
            tag_id=tag_id,
            synonym_tag_id=synonym_tag_id,
        )

        assert data.confidence == 1.0

    def test_synonym_create_schema_confidence_range(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TagSynonymCreate(
                tag_id=uuid4(),
                synonym_tag_id=uuid4(),
                confidence=1.5,  # Invalid: > 1.0
            )

        with pytest.raises(ValidationError):
            TagSynonymCreate(
                tag_id=uuid4(),
                synonym_tag_id=uuid4(),
                confidence=-0.1,  # Invalid: < 0.0
            )

    def test_synonym_list_response_schema(self):
        """Test list response schema structure."""
        tag_id = uuid4()
        synonym_tag_id = uuid4()
        user_id = uuid4()
        now = datetime.now(UTC)

        # Build nested TagResponse objects for detail
        tag_response = TagResponse(
            id=tag_id,
            name="BLE",
            type=TagType.TECHNOLOGY,
        )
        synonym_tag_response = TagResponse(
            id=synonym_tag_id,
            name="Bluetooth Low Energy",
            type=TagType.TECHNOLOGY,
        )

        item = TagSynonymDetail(
            id=uuid4(),
            tag_id=tag_id,
            synonym_tag_id=synonym_tag_id,
            confidence=1.0,
            created_at=now,
            created_by=user_id,
            tag=tag_response,
            synonym_tag=synonym_tag_response,
        )

        response = TagSynonymListResponse(
            items=[item],
            total=1,
            page=1,
            page_size=20,
            has_more=False,
        )

        assert response.total == 1
        assert len(response.items) == 1
        assert response.items[0].tag.name == "BLE"
        assert response.items[0].synonym_tag.name == "Bluetooth Low Energy"

    def test_synonym_import_request_schema(self):
        """Test import request schema structure."""
        synonyms = [
            TagSynonymCreate(tag_id=uuid4(), synonym_tag_id=uuid4()),
            TagSynonymCreate(tag_id=uuid4(), synonym_tag_id=uuid4()),
        ]

        data = TagSynonymImportRequest(synonyms=synonyms)

        assert len(data.synonyms) == 2

    def test_synonym_import_response_schema(self):
        """Test import response schema structure."""
        response = TagSynonymImportResponse(
            total_requested=10,
            created=8,
            skipped=2,
        )

        assert response.total_requested == 10
        assert response.created == 8
        assert response.skipped == 2

    def test_tag_with_synonyms_schema(self):
        """Test tag with synonyms response schema."""
        tag_id = uuid4()
        synonym1_id = uuid4()
        synonym2_id = uuid4()

        data = TagWithSynonyms(
            id=tag_id,
            name="Python",
            type=TagType.TECHNOLOGY,
            synonyms=[
                TagResponse(id=synonym1_id, name="Python3", type=TagType.TECHNOLOGY),
                TagResponse(id=synonym2_id, name="Py", type=TagType.TECHNOLOGY),
            ],
        )

        assert data.id == tag_id
        assert data.name == "Python"
        assert len(data.synonyms) == 2


class TestTagSynonymEndpointLogic:
    """Tests for tag synonym API endpoint logic and service integration."""

    @pytest.mark.asyncio
    async def test_list_synonyms_returns_paginated_response(self):
        """Test listing synonyms returns paginated data."""
        synonym_id = uuid4()
        tag_id = uuid4()
        synonym_tag_id = uuid4()
        user_id = uuid4()
        now = datetime.now(UTC)

        mock_tag = MagicMock(spec=Tag)
        mock_tag.id = tag_id
        mock_tag.name = "BLE"
        mock_tag.type = TagType.TECHNOLOGY

        mock_synonym_tag = MagicMock(spec=Tag)
        mock_synonym_tag.id = synonym_tag_id
        mock_synonym_tag.name = "Bluetooth Low Energy"
        mock_synonym_tag.type = TagType.TECHNOLOGY

        mock_synonym = MagicMock(spec=TagSynonym)
        mock_synonym.id = synonym_id
        mock_synonym.tag_id = tag_id
        mock_synonym.synonym_tag_id = synonym_tag_id
        mock_synonym.confidence = 1.0
        mock_synonym.created_at = now
        mock_synonym.created_by = user_id
        mock_synonym.tag = mock_tag
        mock_synonym.synonym_tag = mock_synonym_tag

        mock_db = AsyncMock()
        # Count returns 1
        mock_db.scalar.return_value = 1
        # Execute returns synonym list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_synonym]
        mock_db.execute.return_value = mock_result

        # Validate the response schema works
        response = TagSynonymListResponse(
            items=[TagSynonymDetail.model_validate(mock_synonym)],
            total=1,
            page=1,
            page_size=20,
            has_more=False,
        )

        assert response.total == 1
        assert len(response.items) == 1
        assert response.items[0].tag.name == "BLE"

    @pytest.mark.asyncio
    async def test_get_tag_synonyms_returns_tag_with_synonyms(self):
        """Test getting a specific tag with all its synonyms."""
        tag_id = uuid4()
        synonym_id = uuid4()

        mock_tag = MagicMock(spec=Tag)
        mock_tag.id = tag_id
        mock_tag.name = "Python"
        mock_tag.type = TagType.TECHNOLOGY

        mock_synonym_tag = MagicMock(spec=Tag)
        mock_synonym_tag.id = synonym_id
        mock_synonym_tag.name = "Python3"
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
        assert result.name == "Python"
        assert len(result.synonyms) == 1
        assert result.synonyms[0].name == "Python3"

    @pytest.mark.asyncio
    async def test_get_tag_synonyms_returns_none_for_missing_tag(self):
        """Test that None returned when tag not found."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TagSynonymService(mock_db)
        result = await service.get_tag_with_synonyms(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_create_synonym_success(self):
        """Test successful synonym creation via service."""
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
    async def test_create_synonym_fails_for_self_reference(self):
        """Test that self-synonym returns None."""
        tag_id = uuid4()

        mock_db = AsyncMock()
        service = TagSynonymService(mock_db)

        result = await service.add_synonym(tag_id, tag_id)

        assert result is None
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_synonym_fails_for_duplicate(self):
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

    @pytest.mark.asyncio
    async def test_delete_synonym_success(self):
        """Test successful synonym deletion."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result

        service = TagSynonymService(mock_db)
        result = await service.remove_synonym(uuid4(), uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_synonym_returns_false_when_not_found(self):
        """Test that False returned when relationship doesn't exist."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        service = TagSynonymService(mock_db)
        result = await service.remove_synonym(uuid4(), uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_import_synonyms_success(self):
        """Test bulk import synonyms via service."""
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

        # Verify response schema works
        response = TagSynonymImportResponse(
            total_requested=len(synonyms),
            created=result,
            skipped=len(synonyms) - result,
        )
        assert response.total_requested == 2
        assert response.created == 2
        assert response.skipped == 0


class TestTagSynonymModelFields:
    """Tests for TagSynonym model field definitions."""

    def test_tag_synonym_has_tag_id_column(self):
        """TagSynonym model should have tag_id column."""
        columns = [c.name for c in TagSynonym.__table__.columns]
        assert "tag_id" in columns

    def test_tag_synonym_has_synonym_tag_id_column(self):
        """TagSynonym model should have synonym_tag_id column."""
        columns = [c.name for c in TagSynonym.__table__.columns]
        assert "synonym_tag_id" in columns

    def test_tag_synonym_has_confidence_column(self):
        """TagSynonym model should have confidence column."""
        columns = [c.name for c in TagSynonym.__table__.columns]
        assert "confidence" in columns

    def test_tag_synonym_has_created_at(self):
        """TagSynonym model should have created_at column."""
        columns = [c.name for c in TagSynonym.__table__.columns]
        assert "created_at" in columns

    def test_tag_synonym_has_created_by(self):
        """TagSynonym model should have created_by column."""
        columns = [c.name for c in TagSynonym.__table__.columns]
        assert "created_by" in columns
