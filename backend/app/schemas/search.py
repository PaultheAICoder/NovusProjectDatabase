"""Search Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectStatus
from app.schemas.project import ProjectResponse


class SearchRequest(BaseModel):
    """Search request parameters."""

    q: str = Field(default="", description="Search query string")
    status: Optional[list[ProjectStatus]] = Field(
        default=None, description="Filter by project status"
    )
    organization_id: Optional[UUID] = Field(
        default=None, description="Filter by organization"
    )
    tag_ids: Optional[list[UUID]] = Field(default=None, description="Filter by tags")
    owner_id: Optional[UUID] = Field(default=None, description="Filter by owner")
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

    status: Optional[list[str]] = None
    organization_id: Optional[UUID] = None
    tag_ids: Optional[list[UUID]] = None
    owner_id: Optional[UUID] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None


class SavedSearchCreate(BaseModel):
    """Schema for creating a saved search."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    query: Optional[str] = None
    filters: SavedSearchFilters = Field(default_factory=SavedSearchFilters)


class SavedSearchUpdate(BaseModel):
    """Schema for updating a saved search."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[SavedSearchFilters] = None


class SavedSearchResponse(BaseModel):
    """Saved search response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str]
    query: Optional[str]
    filters: dict
    is_global: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class SavedSearchListResponse(BaseModel):
    """List of saved searches."""

    my_searches: list[SavedSearchResponse]
    global_searches: list[SavedSearchResponse]
