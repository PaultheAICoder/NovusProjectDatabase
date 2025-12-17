"""Tests for tags API endpoints and schemas."""

from datetime import datetime
from uuid import uuid4

from app.models import TagType
from app.schemas.tag import TagDetail, TagResponse


class TestTagSchemas:
    """Tests for Tag Pydantic schemas."""

    def test_tag_response_schema(self):
        """TagResponse should validate basic tag data."""
        tag_id = uuid4()

        data = TagResponse(
            id=tag_id,
            name="Test Tag",
            type=TagType.FREEFORM,
        )

        assert data.id == tag_id
        assert data.name == "Test Tag"
        assert data.type == TagType.FREEFORM

    def test_tag_response_with_technology_type(self):
        """TagResponse should validate technology type."""
        tag_id = uuid4()

        data = TagResponse(
            id=tag_id,
            name="Python",
            type=TagType.TECHNOLOGY,
        )

        assert data.type == TagType.TECHNOLOGY

    def test_tag_response_with_domain_type(self):
        """TagResponse should validate domain type."""
        tag_id = uuid4()

        data = TagResponse(
            id=tag_id,
            name="Healthcare",
            type=TagType.DOMAIN,
        )

        assert data.type == TagType.DOMAIN

    def test_tag_response_with_test_type(self):
        """TagResponse should validate test_type type."""
        tag_id = uuid4()

        data = TagResponse(
            id=tag_id,
            name="Unit Testing",
            type=TagType.TEST_TYPE,
        )

        assert data.type == TagType.TEST_TYPE

    def test_tag_detail_schema(self):
        """TagDetail should include created_at and created_by."""
        tag_id = uuid4()
        user_id = uuid4()
        now = datetime.now()

        data = TagDetail(
            id=tag_id,
            name="Test Tag",
            type=TagType.FREEFORM,
            created_at=now,
            created_by=user_id,
        )

        assert data.created_at == now
        assert data.created_by == user_id


class TestTagModelFields:
    """Tests for Tag model field definitions."""

    def test_tag_has_name_column(self):
        """Tag model should have name column."""
        from app.models import Tag

        columns = [c.name for c in Tag.__table__.columns]
        assert "name" in columns

    def test_tag_has_type_column(self):
        """Tag model should have type column."""
        from app.models import Tag

        columns = [c.name for c in Tag.__table__.columns]
        assert "type" in columns

    def test_tag_has_created_at(self):
        """Tag model should have created_at column."""
        from app.models import Tag

        columns = [c.name for c in Tag.__table__.columns]
        assert "created_at" in columns


class TestPaginatedTagsEndpoint:
    """Tests for the paginated tags list endpoint."""

    def test_tag_type_enum_values(self):
        """TagType enum should have expected values."""
        assert TagType.TECHNOLOGY.value == "technology"
        assert TagType.DOMAIN.value == "domain"
        assert TagType.TEST_TYPE.value == "test_type"
        assert TagType.FREEFORM.value == "freeform"

    def test_tag_list_response_structure(self):
        """Verify TagResponse can be created for paginated list."""
        tags = [
            TagResponse(
                id=uuid4(),
                name=f"Tag {i}",
                type=TagType.FREEFORM,
            )
            for i in range(5)
        ]

        assert len(tags) == 5
        assert all(isinstance(t, TagResponse) for t in tags)
        assert all(t.type == TagType.FREEFORM for t in tags)

    def test_tags_sorted_by_name(self):
        """Tags should be sortable by name."""
        tags = [
            TagResponse(
                id=uuid4(),
                name=name,
                type=TagType.FREEFORM,
            )
            for name in ["Zebra", "Apple", "Mango"]
        ]

        sorted_tags = sorted(tags, key=lambda t: t.name)
        assert [t.name for t in sorted_tags] == ["Apple", "Mango", "Zebra"]
