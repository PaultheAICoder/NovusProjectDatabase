"""Search API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.project import ProjectStatus
from app.models.user import User
from app.schemas.search import (
    SearchResponse,
    SearchResultItem,
    SearchSuggestion,
    SearchSuggestionsResponse,
)
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_projects(
    q: str = Query(default="", description="Search query"),
    status: Optional[list[ProjectStatus]] = Query(default=None),
    organization_id: Optional[UUID] = Query(default=None),
    tag_ids: Optional[list[UUID]] = Query(default=None),
    owner_id: Optional[UUID] = Query(default=None),
    sort_by: str = Query(default="relevance"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    """
    Search projects with filters.

    Supports full-text search across project fields with filters for:
    - Status (multiple values allowed)
    - Organization
    - Tags (all specified tags must match)
    - Owner

    Sort options:
    - relevance (default when query provided)
    - name
    - start_date
    - updated_at
    """
    search_service = SearchService(db)

    projects, total = await search_service.search_projects(
        query=q,
        status=status,
        organization_id=organization_id,
        tag_ids=tag_ids,
        owner_id=owner_id,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    # Convert to response models
    items = [SearchResultItem.model_validate(p) for p in projects]

    return SearchResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        query=q,
    )


@router.get("/suggest", response_model=SearchSuggestionsResponse)
async def get_search_suggestions(
    q: str = Query(min_length=2, description="Search query prefix"),
    limit: int = Query(default=10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchSuggestionsResponse:
    """
    Get search suggestions based on query prefix.

    Returns project names matching the query prefix.
    """
    search_service = SearchService(db)
    names = await search_service.get_search_suggestions(q, limit=limit)

    suggestions = [SearchSuggestion(text=name, type="project") for name in names]

    return SearchSuggestionsResponse(suggestions=suggestions)
