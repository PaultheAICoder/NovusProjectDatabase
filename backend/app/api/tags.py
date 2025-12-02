"""Tag API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models import Tag, TagType
from app.schemas.tag import (
    StructuredTagCreate,
    TagCreate,
    TagListResponse,
    TagResponse,
)

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=TagListResponse)
async def list_tags(
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
async def create_freeform_tag(
    data: TagCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TagResponse:
    """Create a freeform tag (any user can create)."""
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


@router.get("/suggest")
async def suggest_tags(
    query: str = Query(..., min_length=2),
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> list[TagResponse]:
    """Suggest existing tags based on partial input (fuzzy matching)."""
    # Simple prefix/contains matching for v1
    search_query = select(Tag).where(
        Tag.name.ilike(f"%{query}%")
    ).order_by(Tag.name).limit(10)

    result = await db.execute(search_query)
    tags = result.scalars().all()

    return [TagResponse.model_validate(tag) for tag in tags]
