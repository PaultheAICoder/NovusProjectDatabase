"""Search API endpoints."""

import csv
import io
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.core.rate_limit import limiter, search_limit
from app.models.project import Project, ProjectStatus
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.schemas.search import (
    ParsedQueryMetadata,
    SavedSearchCreate,
    SavedSearchListResponse,
    SavedSearchResponse,
    SavedSearchUpdate,
    SearchResponse,
    SearchResultItem,
    SearchSuggestion,
    SearchSuggestionsResponse,
    SemanticSearchFilters,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SummarizationRequest,
    SummarizationResponse,
)
from app.services.nl_query_parser import NLQueryParser
from app.services.search_cache import generate_cache_key, get_search_cache
from app.services.search_service import SearchService
from app.services.summarization_service import SummarizationService

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
@limiter.limit(search_limit)
async def search_projects(
    request: Request,
    q: str = Query(default="", description="Search query"),
    status: list[ProjectStatus] | None = Query(default=None),
    organization_id: UUID | None = Query(default=None),
    tag_ids: list[UUID] | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    sort_by: str = Query(default="relevance"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    no_cache: bool = Query(default=False, description="Bypass cache (admin/testing)"),
    expand_synonyms: bool = Query(
        default=True,
        description="Expand tag filters to include synonym tags (default: true)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    """
    Search projects with filters.

    Results are cached for 5 minutes by default. Use no_cache=true to bypass.

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
    cache = get_search_cache()

    # Generate cache key from search parameters
    cache_key = generate_cache_key(
        query=q,
        status=[s.value for s in status] if status else None,
        organization_id=str(organization_id) if organization_id else None,
        tag_ids=[str(t) for t in tag_ids] if tag_ids else None,
        owner_id=str(owner_id) if owner_id else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        expand_synonyms=expand_synonyms,
    )

    # Check cache (unless bypassed)
    if not no_cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.debug(
                "search_cache_hit",
                cache_key=cache_key[:16],
                cache_stats=cache.stats,
            )
            return SearchResponse(**cached)

    # Cache miss - perform search
    search_service = SearchService(db)

    projects, total, synonym_metadata = await search_service.search_projects(
        query=q,
        status=status,
        organization_id=organization_id,
        tag_ids=tag_ids,
        owner_id=owner_id,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        expand_synonyms=expand_synonyms,
    )

    # Convert to response models
    items = [SearchResultItem.model_validate(p) for p in projects]

    # Build synonym expansion metadata if synonyms were used
    synonym_expansion = None
    if synonym_metadata:
        from app.schemas.search import SynonymExpansionMetadata

        synonym_expansion = SynonymExpansionMetadata(
            original_tags=[UUID(t) for t in synonym_metadata["original_tags"]],
            expanded_tags=[UUID(t) for t in synonym_metadata["expanded_tags"]],
            synonym_matches=synonym_metadata["synonym_matches"],
        )

    response = SearchResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        query=q,
        synonym_expansion=synonym_expansion,
    )

    # Store in cache
    if not no_cache:
        # Serialize response for caching
        response_dict = response.model_dump(mode="json")
        await cache.set(cache_key, response_dict)
        logger.debug(
            "search_cache_miss",
            cache_key=cache_key[:16],
            results_count=len(items),
            cache_stats=cache.stats,
        )

    return response


@router.post("/semantic", response_model=SemanticSearchResponse)
@limiter.limit(search_limit)
async def semantic_search(
    request: Request,
    body: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SemanticSearchResponse:
    """
    Search projects using natural language query.

    The query is parsed by an LLM to extract:
    - Search keywords
    - Time ranges (e.g., "last 2 years")
    - Organizations/clients
    - Technologies
    - Status filters

    Optional filter overrides can be provided to override parsed values.
    Response includes parsed_query metadata showing how the query was interpreted.
    """
    # Parse natural language query
    parser = NLQueryParser(db)
    parse_result = await parser.parse_query(body.query)

    parsed = parse_result.parsed_intent

    # Determine effective filters (overrides take precedence)
    filters = body.filters or SemanticSearchFilters()

    effective_status = (
        filters.status if filters.status is not None else parsed.status or None
    )
    effective_org_id = (
        filters.organization_id
        if filters.organization_id is not None
        else parsed.organization_id
    )
    effective_tag_ids = (
        filters.tag_ids if filters.tag_ids is not None else parsed.tag_ids or None
    )
    effective_owner_id = filters.owner_id

    # Extract date range from parsed intent
    start_date_from = parsed.date_range.start_date if parsed.date_range else None
    start_date_to = parsed.date_range.end_date if parsed.date_range else None

    # Execute search with combined filters
    search_service = SearchService(db)

    projects, total, _synonym_metadata = await search_service.search_projects(
        query=parsed.search_text,
        status=effective_status if effective_status else None,
        organization_id=effective_org_id,
        tag_ids=effective_tag_ids if effective_tag_ids else None,
        owner_id=effective_owner_id,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        sort_by="relevance",
        sort_order="desc",
        page=body.page,
        page_size=body.page_size,
    )

    # Build response
    items = [SearchResultItem.model_validate(p) for p in projects]

    parsed_metadata = ParsedQueryMetadata(
        parsed_intent=parsed,
        fallback_used=parse_result.fallback_used,
        parse_explanation=parse_result.parse_explanation,
    )

    return SemanticSearchResponse(
        items=items,
        total=total,
        page=body.page,
        page_size=body.page_size,
        query=body.query,
        parsed_query=parsed_metadata,
    )


@router.post("/summarize", response_model=SummarizationResponse)
@limiter.limit(search_limit)
async def summarize_search_results(
    request: Request,
    body: SummarizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SummarizationResponse | StreamingResponse:
    """
    Generate an AI summary over search results.

    Uses the query to find relevant projects and documents, then generates
    a natural language summary answering the user's question.

    If stream=True, returns a streaming response with Server-Sent Events.
    """
    summarization_service = SummarizationService(db)

    # Get projects to summarize
    if body.project_ids:
        # Fetch specific projects
        projects = await _fetch_projects_by_ids(db, body.project_ids)
    else:
        # Use semantic search to find relevant projects
        parser = NLQueryParser(db)
        parse_result = await parser.parse_query(body.query)
        search_service = SearchService(db)
        projects, _, _ = await search_service.search_projects(
            query=parse_result.parsed_intent.search_text,
            page=1,
            page_size=10,
        )

    if body.stream:
        # Return streaming response
        return StreamingResponse(
            summarization_service.summarize_stream(
                query=body.query,
                projects=projects,
                max_chunks=body.max_chunks,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # Non-streaming response
    result = await summarization_service.summarize(
        query=body.query,
        projects=projects,
        max_chunks=body.max_chunks,
    )

    return SummarizationResponse(
        summary=result.summary,
        query=body.query,
        context_used=result.context_used,
        truncated=result.truncated,
    )


async def _fetch_projects_by_ids(db: AsyncSession, project_ids: list[UUID]) -> list:
    """Fetch projects by their IDs."""
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Project)
        .options(
            selectinload(Project.organization),
            selectinload(Project.owner),
        )
        .where(Project.id.in_(project_ids))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/suggest", response_model=SearchSuggestionsResponse)
@limiter.limit(search_limit)
async def get_search_suggestions(
    request: Request,
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


async def _generate_search_csv_rows(
    search_service: SearchService,
    query: str,
    status: list[ProjectStatus] | None,
    organization_id: UUID | None,
    tag_ids: list[UUID] | None,
    owner_id: UUID | None,
    sort_by: str,
    sort_order: str,
) -> AsyncGenerator[str, None]:
    """
    Generate CSV rows for search results using streaming.

    Uses batched fetching via pagination to avoid loading all records
    into memory at once. This fixes memory exhaustion issues when
    exporting large datasets (Issue #90).
    """
    BATCH_SIZE = 100

    # Yield header row
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Name",
            "Organization",
            "Owner",
            "Status",
            "Start Date",
            "End Date",
            "Location",
            "Description",
            "Tags",
            "Milestone/Version",
            "Run Number",
            "Engagement Period",
            "Created At",
            "Updated At",
        ]
    )
    yield output.getvalue()

    # Stream results in batches
    page = 1

    while True:
        projects, total, _ = await search_service.search_projects(
            query=query,
            status=status,
            organization_id=organization_id,
            tag_ids=tag_ids,
            owner_id=owner_id,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=BATCH_SIZE,
        )

        if not projects:
            break

        for project in projects:
            output = io.StringIO()
            writer = csv.writer(output)
            tags = (
                ", ".join(sorted(pt.tag.name for pt in project.project_tags))
                if project.project_tags
                else ""
            )
            writer.writerow(
                [
                    project.name,
                    project.organization.name if project.organization else "",
                    project.owner.display_name if project.owner else "",
                    project.status.value if project.status else "",
                    project.start_date.isoformat() if project.start_date else "",
                    project.end_date.isoformat() if project.end_date else "",
                    project.location or "",
                    project.description or "",
                    tags,
                    project.milestone_version or "",
                    project.run_number or "",
                    project.engagement_period or "",
                    project.created_at.isoformat() if project.created_at else "",
                    project.updated_at.isoformat() if project.updated_at else "",
                ]
            )
            yield output.getvalue()

        # Check if we've fetched all results
        if page * BATCH_SIZE >= total:
            break
        page += 1


@router.get("/export/csv")
@limiter.limit(search_limit)
async def export_search_results_csv(
    request: Request,
    q: str = Query(default="", description="Search query"),
    status: list[ProjectStatus] | None = Query(default=None),
    organization_id: UUID | None = Query(default=None),
    tag_ids: list[UUID] | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    sort_by: str = Query(default="relevance"),
    sort_order: str = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export search results to CSV.

    Uses the same filters as the search endpoint but returns all matching
    results as a downloadable CSV file.
    Uses streaming to handle large datasets without memory exhaustion (Issue #90).
    """
    search_service = SearchService(db)

    return StreamingResponse(
        _generate_search_csv_rows(
            search_service=search_service,
            query=q,
            status=status,
            organization_id=organization_id,
            tag_ids=tag_ids,
            owner_id=owner_id,
            sort_by=sort_by,
            sort_order=sort_order,
        ),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=search_results_export.csv"
        },
    )


# ============== Saved Searches ==============


@router.get("/saved", response_model=SavedSearchListResponse)
@limiter.limit(search_limit)
async def list_saved_searches(
    request: Request,
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
        .where(SavedSearch.is_global.is_(True))
        .where(SavedSearch.created_by != current_user.id)
        .order_by(SavedSearch.name)
    )
    global_searches = global_result.scalars().all()

    return SavedSearchListResponse(
        my_searches=[SavedSearchResponse.model_validate(s) for s in my_searches],
        global_searches=[
            SavedSearchResponse.model_validate(s) for s in global_searches
        ],
    )


@router.post(
    "/saved", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(search_limit)
async def create_saved_search(
    request: Request,
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
@limiter.limit(search_limit)
async def get_saved_search(
    request: Request,
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchResponse:
    """Get a saved search by ID."""
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
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
@limiter.limit(search_limit)
async def update_saved_search(
    request: Request,
    search_id: UUID,
    data: SavedSearchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchResponse:
    """Update a saved search."""
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
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
@limiter.limit(search_limit)
async def delete_saved_search(
    request: Request,
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a saved search."""
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
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
