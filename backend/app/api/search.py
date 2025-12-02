"""Search API endpoints."""

import csv
import io
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.project import ProjectStatus
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.schemas.search import (
    SavedSearchCreate,
    SavedSearchListResponse,
    SavedSearchResponse,
    SavedSearchUpdate,
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


@router.get("/export/csv")
async def export_search_results_csv(
    q: str = Query(default="", description="Search query"),
    status: Optional[list[ProjectStatus]] = Query(default=None),
    organization_id: Optional[UUID] = Query(default=None),
    tag_ids: Optional[list[UUID]] = Query(default=None),
    owner_id: Optional[UUID] = Query(default=None),
    sort_by: str = Query(default="relevance"),
    sort_order: str = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export search results to CSV.

    Uses the same filters as the search endpoint but returns all matching
    results as a downloadable CSV file.
    """
    search_service = SearchService(db)

    # Get all results (no pagination for export)
    projects, total = await search_service.search_projects(
        query=q,
        status=status,
        organization_id=organization_id,
        tag_ids=tag_ids,
        owner_id=owner_id,
        sort_by=sort_by,
        sort_order=sort_order,
        page=1,
        page_size=10000,  # Reasonable max for export
    )

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Name",
        "Organization",
        "Owner",
        "Status",
        "Start Date",
        "End Date",
        "Location",
        "Description",
        "Tags",
        "Created At",
        "Updated At",
    ])

    # Data rows
    for project in projects:
        tags = ", ".join(sorted(pt.tag.name for pt in project.project_tags)) if project.project_tags else ""
        writer.writerow([
            project.name,
            project.organization.name if project.organization else "",
            project.owner.display_name if project.owner else "",
            project.status.value if project.status else "",
            project.start_date.isoformat() if project.start_date else "",
            project.end_date.isoformat() if project.end_date else "",
            project.location or "",
            project.description or "",
            tags,
            project.created_at.isoformat() if project.created_at else "",
            project.updated_at.isoformat() if project.updated_at else "",
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=search_results_export.csv"
        },
    )


# ============== Saved Searches ==============


@router.get("/saved", response_model=SavedSearchListResponse)
async def list_saved_searches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchListResponse:
    """
    List saved searches for the current user.

    Returns:
    - my_searches: Searches created by the current user
    - global_searches: Searches marked as global by admins
    """
    # Get user's own searches
    my_result = await db.execute(
        select(SavedSearch)
        .where(SavedSearch.created_by == current_user.id)
        .order_by(SavedSearch.updated_at.desc())
    )
    my_searches = my_result.scalars().all()

    # Get global searches (excluding own)
    global_result = await db.execute(
        select(SavedSearch)
        .where(SavedSearch.is_global == True)
        .where(SavedSearch.created_by != current_user.id)
        .order_by(SavedSearch.name)
    )
    global_searches = global_result.scalars().all()

    return SavedSearchListResponse(
        my_searches=[SavedSearchResponse.model_validate(s) for s in my_searches],
        global_searches=[SavedSearchResponse.model_validate(s) for s in global_searches],
    )


@router.post(
    "/saved", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED
)
async def create_saved_search(
    data: SavedSearchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchResponse:
    """Create a new saved search."""
    saved_search = SavedSearch(
        name=data.name,
        description=data.description,
        query=data.query,
        filters=data.filters.model_dump(exclude_none=True),
        created_by=current_user.id,
    )
    db.add(saved_search)
    await db.flush()

    return SavedSearchResponse.model_validate(saved_search)


@router.get("/saved/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchResponse:
    """Get a saved search by ID."""
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id)
    )
    saved_search = result.scalar_one_or_none()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    # Check access - must be owner or global
    if not saved_search.is_global and saved_search.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this saved search",
        )

    return SavedSearchResponse.model_validate(saved_search)


@router.patch("/saved/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: UUID,
    data: SavedSearchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchResponse:
    """Update a saved search."""
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id)
    )
    saved_search = result.scalar_one_or_none()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    # Must be owner to update
    if saved_search.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own saved searches",
        )

    # Update fields
    if data.name is not None:
        saved_search.name = data.name
    if data.description is not None:
        saved_search.description = data.description
    if data.query is not None:
        saved_search.query = data.query
    if data.filters is not None:
        saved_search.filters = data.filters.model_dump(exclude_none=True)

    await db.flush()
    return SavedSearchResponse.model_validate(saved_search)


@router.delete("/saved/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a saved search."""
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id)
    )
    saved_search = result.scalar_one_or_none()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    # Must be owner to delete
    if saved_search.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own saved searches",
        )

    await db.delete(saved_search)
