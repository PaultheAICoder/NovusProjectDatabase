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


class CooccurrenceTagSuggestion(BaseModel):
    """Tag suggestion based on co-occurrence with selected tags."""

    tag: TagResponse
    co_occurrence_count: int = Field(
        ..., description="Number of projects where this tag appears with selected tags"
    )


class CooccurrenceTagsResponse(BaseModel):
    """Response for tag co-occurrence suggestions."""

    suggestions: list[CooccurrenceTagSuggestion]
    selected_tag_ids: list[UUID] = Field(
        ..., description="The tag IDs used as input for suggestions"
    )


# Tag Synonym Schemas


class TagSynonymBase(BaseModel):
    """Base schema for tag synonym."""

    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="1.0 = manual, <1.0 = AI-suggested"
    )


class TagSynonymCreate(TagSynonymBase):
    """Schema for creating a tag synonym relationship."""

    tag_id: UUID = Field(..., description="First tag in the synonym pair")
    synonym_tag_id: UUID = Field(..., description="Second tag in the synonym pair")


class TagSynonymResponse(TagSynonymBase):
    """Tag synonym response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tag_id: UUID
    synonym_tag_id: UUID
    created_at: datetime
    created_by: UUID | None = None


class TagSynonymDetail(TagSynonymResponse):
    """Detailed synonym response with full tag information."""

    tag: TagResponse
    synonym_tag: TagResponse


class TagSynonymBulkCreate(BaseModel):
    """Schema for creating multiple synonym relationships at once."""

    synonyms: list[TagSynonymCreate] = Field(..., min_length=1, max_length=100)


class TagWithSynonyms(TagResponse):
    """Tag response with its synonyms included."""

    synonyms: list[TagResponse] = Field(
        default_factory=list, description="All synonymous tags"
    )
