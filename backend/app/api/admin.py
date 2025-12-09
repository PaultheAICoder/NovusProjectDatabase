"""Admin API endpoints (requires admin role)."""

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, DbSession
from app.core.rate_limit import admin_limit, limiter
from app.models import Tag, TagType
from app.models.document import Document
from app.models.organization import Organization
from app.models.project import Project, ProjectStatus
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.schemas.import_ import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
)
from app.schemas.search import SavedSearchResponse
from app.schemas.tag import (
    StructuredTagCreate,
    TagMergeRequest,
    TagMergeResponse,
    TagResponse,
    TagUpdate,
)
from app.services.import_service import ImportService
from app.services.tag_suggester import TagSuggester

router = APIRouter(prefix="/admin", tags=["admin"])


# ============== Tag Management (Admin Only) ==============


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(admin_limit)
async def create_structured_tag(
    request: Request,
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
@limiter.limit(admin_limit)
async def update_tag(
    request: Request,
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
@limiter.limit(admin_limit)
async def delete_tag(
    request: Request,
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
@limiter.limit(admin_limit)
async def merge_tags(
    request: Request,
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
@limiter.limit(admin_limit)
async def get_overview_statistics(
    request: Request,
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


# ============== Bulk Import (Admin Only) ==============


@router.post("/import/preview", response_model=ImportPreviewResponse)
@limiter.limit(admin_limit)
async def preview_import(
    request: Request,
    file: UploadFile = File(...),
    include_suggestions: bool = Query(
        default=True, description="Include AI suggestions for missing fields"
    ),
    db: DbSession = None,
    admin_user: AdminUser = None,
) -> ImportPreviewResponse:
    """
    Upload a CSV file and preview the import with validation and AI suggestions.

    Returns validation errors, warnings, and AI-generated suggestions for each row.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )

    # Read file content
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    # Parse and preview
    import_service = ImportService(db)
    rows, column_mappings = await import_service.preview_import(
        content=content,
        filename=file.filename,
        include_suggestions=include_suggestions,
    )

    valid_rows = sum(1 for r in rows if r.validation.is_valid)
    invalid_rows = len(rows) - valid_rows

    return ImportPreviewResponse(
        filename=file.filename,
        total_rows=len(rows),
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        rows=rows,
        column_mapping=column_mappings,
    )


@router.post("/import/commit", response_model=ImportCommitResponse)
@limiter.limit(admin_limit)
async def commit_import(
    request: Request,
    data: ImportCommitRequest,
    db: DbSession,
    admin_user: AdminUser,
) -> ImportCommitResponse:
    """
    Commit the import, creating projects from the provided rows.

    Rows should have been updated by the user based on the preview response.
    """
    if not data.rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No rows to import",
        )

    import_service = ImportService(db)
    results = await import_service.commit_import(
        rows=data.rows,
        user_id=admin_user.id,
        skip_invalid=data.skip_invalid,
    )

    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    return ImportCommitResponse(
        total=len(results),
        successful=successful,
        failed=failed,
        results=results,
    )


# ============== Saved Searches (Admin Only) ==============


@router.patch(
    "/saved-searches/{search_id}/toggle-global", response_model=SavedSearchResponse
)
@limiter.limit(admin_limit)
async def toggle_saved_search_global(
    request: Request,
    search_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> SavedSearchResponse:
    """
    Toggle a saved search between private and global. Admin only.

    Global searches are visible to all users.
    """
    result = await db.execute(select(SavedSearch).where(SavedSearch.id == search_id))
    saved_search = result.scalar_one_or_none()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    saved_search.is_global = not saved_search.is_global
    await db.flush()

    return SavedSearchResponse.model_validate(saved_search)
