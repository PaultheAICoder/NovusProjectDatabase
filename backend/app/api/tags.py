"""Tag API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.logging import get_logger
from app.core.rate_limit import crud_limit, limiter
from app.models import Tag, TagType
from app.schemas.base import PaginatedResponse
from app.schemas.tag import (
    CooccurrenceTagsResponse,
    CooccurrenceTagSuggestion,
    PopularTagResponse,
    TagCreate,
    TagListResponse,
    TagResponse,
    TagSuggestion,
    TagSuggestionsResponse,
)
from app.services.audit_service import AuditService
from app.services.cache_service import get_tag_cache, invalidate_tag_cache
from app.services.tag_suggester import TagSuggester

logger = get_logger(__name__)

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=TagListResponse)
@limiter.limit(crud_limit)
async def list_tags(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    type: TagType | None = None,
    search: str | None = None,
) -> TagListResponse:
    """List all tags grouped by type."""
    # Generate cache key from parameters
    cache = get_tag_cache()
    cache_key = f"list:{type.value if type else 'all'}:{search or ''}"

    # Check cache first
    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug("tag_list_cache_hit", cache_key=cache_key)
        return TagListResponse(**cached)

    # Cache miss - query database
    query = select(Tag)

    if type:
        query = query.where(Tag.type == type)

    if search:
        query = query.where(Tag.name.ilike(f"%{search}%"))

    query = query.order_by(Tag.type, Tag.name)
    result = await db.execute(query)
    tags = result.scalars().all()

    # Group by type
    grouped: dict[str, list[dict]] = {
        "technology": [],
        "domain": [],
        "test_type": [],
        "freeform": [],
    }

    for tag in tags:
        tag_dict = TagResponse.model_validate(tag).model_dump(mode="json")
        grouped[tag.type.value].append(tag_dict)

    # Store in cache
    await cache.set(cache_key, grouped)
    logger.debug("tag_list_cache_miss", cache_key=cache_key)

    return TagListResponse(**grouped)


@router.get("/list", response_model=PaginatedResponse[TagResponse])
@limiter.limit(crud_limit)
async def list_tags_flat(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: TagType | None = None,
    search: str | None = None,
) -> PaginatedResponse[TagResponse]:
    """List tags with pagination and optional search (flat list, not grouped)."""
    from sqlalchemy import func

    # Generate cache key from parameters
    cache = get_tag_cache()
    cache_key = (
        f"flat:{type.value if type else 'all'}:{search or ''}:{page}:{page_size}"
    )

    # Check cache first
    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug("tag_flat_cache_hit", cache_key=cache_key)
        return PaginatedResponse(**cached)

    # Cache miss - query database
    query = select(Tag)

    if type:
        query = query.where(Tag.type == type)

    if search:
        query = query.where(Tag.name.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.order_by(Tag.name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    tags = result.scalars().all()

    response_data = {
        "items": [
            TagResponse.model_validate(tag).model_dump(mode="json") for tag in tags
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }

    # Store in cache
    await cache.set(cache_key, response_data)
    logger.debug("tag_flat_cache_miss", cache_key=cache_key)

    return PaginatedResponse(**response_data)


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(crud_limit)
async def create_freeform_tag(
    request: Request,
    data: TagCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TagResponse:
    """Create a freeform tag (any user can create)."""
    # Check for duplicates using TagSuggester
    suggester = TagSuggester(db)
    duplicate = await suggester.check_duplicate(data.name, TagType.FREEFORM)

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A similar tag '{duplicate.name}' already exists",
        )

    tag = Tag(
        name=data.name,
        type=TagType.FREEFORM,
        created_by=current_user.id,
    )
    db.add(tag)

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag '{data.name}' already exists as a freeform tag",
        )

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_create(
        entity_type="tag",
        entity_id=tag.id,
        entity_data=AuditService.serialize_entity(tag),
        user_id=current_user.id,
    )

    # Invalidate tag cache
    await invalidate_tag_cache()

    return TagResponse.model_validate(tag)


@router.get("/suggest", response_model=TagSuggestionsResponse)
@limiter.limit(crud_limit)
async def suggest_tags(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    query: str = Query(..., min_length=2, description="Search query for tag names"),
    type: TagType | None = Query(default=None, description="Filter by tag type"),
    include_fuzzy: bool = Query(
        default=True, description="Include fuzzy matches with suggestions"
    ),
    limit: int = Query(default=10, ge=1, le=50),
) -> TagSuggestionsResponse:
    """
    Suggest existing tags based on partial input with fuzzy matching.

    Returns tags ordered by relevance with optional "Did you mean X?" hints
    for fuzzy matches (helps catch typos).
    """
    suggester = TagSuggester(db)
    results = await suggester.suggest_tags(
        query=query,
        tag_type=type,
        limit=limit,
        include_fuzzy=include_fuzzy,
    )

    suggestions = [
        TagSuggestion(
            tag=TagResponse.model_validate(tag),
            score=score,
            suggestion=hint,
        )
        for tag, score, hint in results
    ]

    return TagSuggestionsResponse(suggestions=suggestions)


@router.get("/popular", response_model=list[PopularTagResponse])
@limiter.limit(crud_limit)
async def get_popular_tags(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    type: TagType | None = Query(default=None, description="Filter by tag type"),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[PopularTagResponse]:
    """Get the most frequently used tags."""
    suggester = TagSuggester(db)
    results = await suggester.get_popular_tags(tag_type=type, limit=limit)

    return [
        PopularTagResponse(
            tag=TagResponse.model_validate(tag),
            usage_count=count,
        )
        for tag, count in results
    ]


@router.get("/cooccurrence", response_model=CooccurrenceTagsResponse)
@limiter.limit(crud_limit)
async def get_cooccurrence_suggestions(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    tag_ids: str = Query(
        ...,
        description="Comma-separated list of selected tag UUIDs",
        examples=[
            "550e8400-e29b-41d4-a716-446655440000,550e8400-e29b-41d4-a716-446655440001"
        ],
    ),
    limit: int = Query(default=5, ge=1, le=20),
) -> CooccurrenceTagsResponse:
    """
    Get tag suggestions based on co-occurrence with selected tags.

    Returns tags that frequently appear in the same projects as the
    selected tags, ordered by co-occurrence frequency. Use this to
    implement "You might also want:" suggestions.
    """
    # Parse comma-separated UUIDs
    try:
        parsed_ids = [UUID(tid.strip()) for tid in tag_ids.split(",") if tid.strip()]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format in tag_ids",
        )

    if not parsed_ids:
        return CooccurrenceTagsResponse(suggestions=[], selected_tag_ids=[])

    suggester = TagSuggester(db)
    results = await suggester.get_cooccurrence_suggestions(
        selected_tag_ids=parsed_ids,
        limit=limit,
    )

    suggestions = [
        CooccurrenceTagSuggestion(
            tag=TagResponse.model_validate(tag),
            co_occurrence_count=count,
        )
        for tag, count in results
    ]

    return CooccurrenceTagsResponse(
        suggestions=suggestions,
        selected_tag_ids=parsed_ids,
    )


@router.get("/{tag_id}", response_model=TagResponse)
@limiter.limit(crud_limit)
async def get_tag(
    request: Request,
    tag_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> TagResponse:
    """Get a single tag by ID."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    return TagResponse.model_validate(tag)
