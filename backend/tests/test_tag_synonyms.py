"""Tests for TagSynonym model and schemas."""

from datetime import datetime
from uuid import uuid4

import pytest

from app.models import TagSynonym
from app.schemas.tag import (
    TagSynonymCreate,
    TagSynonymResponse,
)


class TestTagSynonymSchemas:
    """Tests for TagSynonym Pydantic schemas."""

    def test_tag_synonym_create_schema(self):
        """TagSynonymCreate should validate required fields."""
        tag_id = uuid4()
        synonym_id = uuid4()

        data = TagSynonymCreate(
            tag_id=tag_id,
            synonym_tag_id=synonym_id,
            confidence=1.0,
        )

        assert data.tag_id == tag_id
        assert data.synonym_tag_id == synonym_id
        assert data.confidence == 1.0

    def test_tag_synonym_create_default_confidence(self):
        """TagSynonymCreate should default confidence to 1.0."""
        data = TagSynonymCreate(
            tag_id=uuid4(),
            synonym_tag_id=uuid4(),
        )

        assert data.confidence == 1.0

    def test_tag_synonym_create_ai_suggested_confidence(self):
        """TagSynonymCreate should allow confidence < 1.0 for AI suggestions."""
        data = TagSynonymCreate(
            tag_id=uuid4(),
            synonym_tag_id=uuid4(),
            confidence=0.85,
        )

        assert data.confidence == 0.85

    def test_tag_synonym_create_confidence_validation(self):
        """TagSynonymCreate should reject invalid confidence values."""
        with pytest.raises(ValueError):
            TagSynonymCreate(
                tag_id=uuid4(),
                synonym_tag_id=uuid4(),
                confidence=1.5,  # Invalid: > 1.0
            )

        with pytest.raises(ValueError):
            TagSynonymCreate(
                tag_id=uuid4(),
                synonym_tag_id=uuid4(),
                confidence=-0.1,  # Invalid: < 0.0
            )

    def test_tag_synonym_response_schema(self):
        """TagSynonymResponse should validate response data."""
        synonym_id = uuid4()
        tag_id = uuid4()
        synonym_tag_id = uuid4()
        user_id = uuid4()
        now = datetime.now()

        data = TagSynonymResponse(
            id=synonym_id,
            tag_id=tag_id,
            synonym_tag_id=synonym_tag_id,
            confidence=0.9,
            created_at=now,
            created_by=user_id,
        )

        assert data.id == synonym_id
        assert data.tag_id == tag_id
        assert data.synonym_tag_id == synonym_tag_id
        assert data.confidence == 0.9
        assert data.created_at == now
        assert data.created_by == user_id


class TestTagSynonymModelFields:
    """Tests for TagSynonym model field definitions."""

    def test_tag_synonym_has_id_column(self):
        """TagSynonym model should have id column."""
        columns = [c.name for c in TagSynonym.__table__.columns]
        assert "id" in columns

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

    def test_tag_synonym_has_created_by_column(self):
        """TagSynonym model should have created_by column."""
        columns = [c.name for c in TagSynonym.__table__.columns]
        assert "created_by" in columns

    def test_tag_synonym_has_created_at_column(self):
        """TagSynonym model should have created_at column."""
        columns = [c.name for c in TagSynonym.__table__.columns]
        assert "created_at" in columns

    def test_tag_synonym_table_name(self):
        """TagSynonym should have correct table name."""
        assert TagSynonym.__tablename__ == "tag_synonyms"

    def test_tag_synonym_has_unique_constraint(self):
        """TagSynonym should have unique constraint on tag pair."""
        constraints = [c.name for c in TagSynonym.__table__.constraints]
        assert "uq_tag_synonym_pair" in constraints
