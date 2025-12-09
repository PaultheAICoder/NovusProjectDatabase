"""Tag API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import crud_limit, limiter
from app.models import Tag, TagType
from app.schemas.tag import (
    PopularTagResponse,
    TagCreate,
    TagListResponse,
    TagResponse,
    TagSuggestion,
    TagSuggestionsResponse,
)
from app.services.tag_suggester import TagSuggester

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
    query = select(Tag)

    if type:
        query = query.where(Tag.type == type)

    if search:
        query = query.where(Tag.name.ilike(f"%{search}%"))

    query = query.order_by(Tag.type, Tag.name)
    result = await db.execute(query)
    tags = result.scalars().all()

    # Group by type
    grouped: dict[str, list[TagResponse]] = {
        "technology": [],
        "domain": [],
        "test_type": [],
        "freeform": [],
    }

    for tag in tags:
        tag_response = TagResponse.model_validate(tag)
        grouped[tag.type.value].append(tag_response)

    return TagListResponse(**grouped)


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
