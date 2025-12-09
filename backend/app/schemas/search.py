"""Search Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectStatus
from app.schemas.project import ProjectResponse


class SearchRequest(BaseModel):
    """Search request parameters."""

    q: str = Field(default="", description="Search query string")
    status: list[ProjectStatus] | None = Field(
        default=None, description="Filter by project status"
    )
    organization_id: UUID | None = Field(
        default=None, description="Filter by organization"
    )
    tag_ids: list[UUID] | None = Field(default=None, description="Filter by tags")
    owner_id: UUID | None = Field(default=None, description="Filter by owner")
    sort_by: str = Field(
        default="relevance",
        description="Sort field: relevance, name, start_date, updated_at",
    )
    sort_order: str = Field(default="desc", description="Sort order: asc or desc")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class SearchResultItem(ProjectResponse):
    """A single search result with optional relevance info."""

    pass


class SearchResponse(BaseModel):
    """Search response with results and metadata."""

    items: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    query: str


class SearchSuggestion(BaseModel):
    """Search suggestion item."""

    text: str
    type: str = "project"


class SearchSuggestionsResponse(BaseModel):
    """Search suggestions response."""

    suggestions: list[SearchSuggestion]


# ============== Saved Searches ==============


class SavedSearchFilters(BaseModel):
    """Filters stored in a saved search."""

    status: list[str] | None = None
    organization_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    owner_id: UUID | None = None
    sort_by: str | None = None
    sort_order: str | None = None


class SavedSearchCreate(BaseModel):
    """Schema for creating a saved search."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    query: str | None = None
    filters: SavedSearchFilters = Field(default_factory=SavedSearchFilters)


class SavedSearchUpdate(BaseModel):
    """Schema for updating a saved search."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    query: str | None = None
    filters: SavedSearchFilters | None = None


class SavedSearchResponse(BaseModel):
    """Saved search response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    query: str | None
    filters: dict
    is_global: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class SavedSearchListResponse(BaseModel):
    """List of saved searches."""

    my_searches: list[SavedSearchResponse]
    global_searches: list[SavedSearchResponse]
