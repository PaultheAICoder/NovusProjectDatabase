"""Search Pydantic schemas."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

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
