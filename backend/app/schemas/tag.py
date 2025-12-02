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


class TagSuggestion(BaseModel):
    """Tag suggestion with similarity info."""

    tag: TagResponse
    score: float = Field(..., description="Similarity score (0-1)")
    suggestion: str | None = Field(
        default=None, description="Suggestion hint like 'Did you mean X?'"
    )


class TagSuggestionsResponse(BaseModel):
    """Response for tag suggestions."""

    suggestions: list[TagSuggestion]


class TagUpdate(BaseModel):
    """Schema for updating a tag (admin only)."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: TagType | None = Field(default=None)


class TagMergeRequest(BaseModel):
    """Request to merge one tag into another."""

    source_tag_id: UUID = Field(..., description="Tag to merge from (will be deleted)")
    target_tag_id: UUID = Field(..., description="Tag to merge into (will be kept)")


class TagMergeResponse(BaseModel):
    """Response for tag merge operation."""

    merged_count: int = Field(..., description="Number of projects updated")
    target_tag: TagResponse


class PopularTagResponse(BaseModel):
    """Response for popular tags."""

    tag: TagResponse
    usage_count: int
