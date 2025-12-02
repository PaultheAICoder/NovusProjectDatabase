"""Admin API endpoints (requires admin role)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, DbSession
from app.models import Tag, TagType
from app.models.document import Document
from app.models.organization import Organization
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.schemas.tag import (
    PopularTagResponse,
    StructuredTagCreate,
    TagMergeRequest,
    TagMergeResponse,
    TagResponse,
    TagUpdate,
)
from app.services.tag_suggester import TagSuggester

router = APIRouter(prefix="/admin", tags=["admin"])


# ============== Tag Management (Admin Only) ==============


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_structured_tag(
    data: StructuredTagCreate,
    db: DbSession,
    admin_user: AdminUser,
) -> TagResponse:
    """Create a structured tag (technology, domain, or test_type). Admin only."""
    if data.type == TagType.FREEFORM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /api/v1/tags endpoint to create freeform tags",
        )

    # Check for duplicates
    suggester = TagSuggester(db)
    duplicate = await suggester.check_duplicate(data.name, data.type)

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A similar tag '{duplicate.name}' already exists in {duplicate.type.value}",
        )

    tag = Tag(
        name=data.name,
        type=data.type,
        created_by=admin_user.id,
    )
    db.add(tag)

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag '{data.name}' already exists",
        )

    return TagResponse.model_validate(tag)


@router.patch("/tags/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: UUID,
    data: TagUpdate,
    db: DbSession,
    admin_user: AdminUser,
) -> TagResponse:
    """Update a tag (name or type). Admin only."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    if data.name is not None:
        # Check for duplicate name
        suggester = TagSuggester(db)
        target_type = data.type if data.type is not None else tag.type
        duplicate = await suggester.check_duplicate(data.name, target_type)
        if duplicate and duplicate.id != tag_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A similar tag '{duplicate.name}' already exists",
            )
        tag.name = data.name

    if data.type is not None:
        tag.type = data.type

    await db.flush()
    return TagResponse.model_validate(tag)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> None:
    """Delete a tag. Admin only. Also removes all project associations."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    await db.execute(delete(Tag).where(Tag.id == tag_id))


@router.post("/tags/merge", response_model=TagMergeResponse)
async def merge_tags(
    data: TagMergeRequest,
    db: DbSession,
    admin_user: AdminUser,
) -> TagMergeResponse:
    """
    Merge one tag into another. Admin only.

    All projects with the source tag will be updated to use the target tag.
    The source tag will be deleted.
    """
    # Verify both tags exist
    source_result = await db.execute(select(Tag).where(Tag.id == data.source_tag_id))
    source_tag = source_result.scalar_one_or_none()

    target_result = await db.execute(select(Tag).where(Tag.id == data.target_tag_id))
    target_tag = target_result.scalar_one_or_none()

    if not source_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source tag not found",
        )

    if not target_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target tag not found",
        )

    if source_tag.id == target_tag.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and target tags must be different",
        )

    suggester = TagSuggester(db)
    merged_count = await suggester.merge_tags(
        source_tag_id=data.source_tag_id,
        target_tag_id=data.target_tag_id,
    )

    return TagMergeResponse(
        merged_count=merged_count,
        target_tag=TagResponse.model_validate(target_tag),
    )


# ============== Statistics (Admin Only) ==============


@router.get("/stats")
async def get_overview_statistics(
    db: DbSession,
    admin_user: AdminUser,
) -> dict:
    """Get overview statistics for the dashboard. Admin only."""
    # Count projects by status
    project_counts = {}
    for status in ProjectStatus:
        count = await db.scalar(
            select(func.count()).select_from(Project).where(Project.status == status)
        )
        project_counts[status.value] = count or 0

    total_projects = sum(project_counts.values())

    # Count organizations
    org_count = await db.scalar(select(func.count()).select_from(Organization))

    # Count users
    user_count = await db.scalar(select(func.count()).select_from(User))

    # Count documents
    doc_count = await db.scalar(select(func.count()).select_from(Document))

    # Count tags by type
    tag_counts = {}
    for tag_type in TagType:
        count = await db.scalar(
            select(func.count()).select_from(Tag).where(Tag.type == tag_type)
        )
        tag_counts[tag_type.value] = count or 0

    total_tags = sum(tag_counts.values())

    return {
        "projects": {
            "total": total_projects,
            "by_status": project_counts,
        },
        "organizations": org_count or 0,
        "users": user_count or 0,
        "documents": doc_count or 0,
        "tags": {
            "total": total_tags,
            "by_type": tag_counts,
        },
    }
