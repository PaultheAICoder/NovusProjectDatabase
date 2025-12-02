"""Tag Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.tag import TagType


class TagBase(BaseModel):
    """Base tag schema."""

    name: str = Field(..., min_length=1, max_length=100)


class TagCreate(TagBase):
    """Schema for creating a freeform tag."""

    pass


class StructuredTagCreate(TagBase):
    """Schema for creating a structured tag (admin only)."""

    type: TagType = Field(..., description="Must be technology, domain, or test_type")


class TagResponse(TagBase):
    """Tag response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: TagType


class TagDetail(TagResponse):
    """Detailed tag response with creation info."""

    created_at: datetime
    created_by: UUID | None = None


class TagListResponse(BaseModel):
    """Tag list grouped by type."""

    technology: list[TagResponse] = []
    domain: list[TagResponse] = []
    test_type: list[TagResponse] = []
    freeform: list[TagResponse] = []
