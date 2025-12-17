"""Admin API endpoints (requires admin role)."""

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, DbSession
from app.core.file_utils import read_file_with_size_limit
from app.core.rate_limit import admin_limit, limiter
from app.models import Tag, TagType
from app.models.document import Document
from app.models.monday_sync import (
    MondaySyncLog,
    MondaySyncType,
    SyncQueueDirection,
    SyncQueueStatus,
)
from app.models.organization import Organization
from app.models.project import Project, ProjectStatus
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.schemas.import_ import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportRowsValidateRequest,
    ImportRowsValidateResponse,
)
from app.schemas.monday import (
    AutoResolutionRuleCreate,
    AutoResolutionRuleListResponse,
    AutoResolutionRuleReorderRequest,
    AutoResolutionRuleResponse,
    AutoResolutionRuleUpdate,
    BulkConflictResolveRequest,
    BulkConflictResolveResponse,
    BulkResolveResult,
    ConflictListResponse,
    ConflictResolutionType,
    ConflictResolveRequest,
    MondayBoardInfo,
    MondayBoardsResponse,
    MondayConfigResponse,
    MondaySyncLogResponse,
    MondaySyncStatusResponse,
    MondaySyncTriggerRequest,
    SyncConflictResponse,
    SyncQueueItemResponse,
    SyncQueueListResponse,
    SyncQueueStatsResponse,
)
from app.schemas.search import SavedSearchResponse
from app.schemas.tag import (
    StructuredTagCreate,
    TagMergeRequest,
    TagMergeResponse,
    TagResponse,
    TagUpdate,
)
from app.services.auto_resolution_service import AutoResolutionService
from app.services.conflict_service import ConflictService
from app.services.import_service import ImportService
from app.services.monday_service import (
    MondayService,
    get_default_contact_field_mapping,
    get_default_org_field_mapping,
)
from app.services.sync_queue_service import SyncQueueService
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


@router.get("/tags/{tag_id}/usage")
@limiter.limit(admin_limit)
async def get_tag_usage(
    request: Request,
    tag_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> dict:
    """Get usage count for a specific tag. Admin only."""
    from app.models.project import ProjectTag

    # Verify tag exists
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    # Count projects using this tag
    count = await db.scalar(
        select(func.count()).select_from(ProjectTag).where(ProjectTag.tag_id == tag_id)
    )

    return {"tag_id": str(tag_id), "usage_count": count or 0}


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
    for proj_status in ProjectStatus:
        count = await db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.status == proj_status)
        )
        project_counts[proj_status.value] = count or 0

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
    db: DbSession,
    admin_user: AdminUser,
    file: UploadFile = File(...),
    include_suggestions: bool = Query(
        default=True, description="Include AI suggestions for missing fields"
    ),
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

    # Validate file size and read content (streaming to prevent memory exhaustion)
    # Use 10MB limit for CSV imports (should be much smaller than document uploads)
    import_max_size = 10 * 1024 * 1024  # 10MB
    content = await read_file_with_size_limit(
        file=file,
        max_size_bytes=import_max_size,
    )
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
        user_id=admin_user.id,
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


@router.post("/import/validate-rows", response_model=ImportRowsValidateResponse)
@limiter.limit(admin_limit)
async def validate_import_rows(
    request: Request,
    data: ImportRowsValidateRequest,
    db: DbSession,
    admin_user: AdminUser,
) -> ImportRowsValidateResponse:
    """
    Validate edited import rows without committing.

    Used to revalidate rows after user edits in the preview table.
    Lightweight endpoint that only performs validation checks.
    """
    if not data.rows:
        return ImportRowsValidateResponse(
            results=[],
            valid_count=0,
            invalid_count=0,
        )

    import_service = ImportService(db)
    results = await import_service.validate_edited_rows(data.rows)

    valid_count = sum(1 for r in results if r.validation.is_valid)
    invalid_count = len(results) - valid_count

    return ImportRowsValidateResponse(
        results=results,
        valid_count=valid_count,
        invalid_count=invalid_count,
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


# ============== Monday.com Integration (Admin Only) ==============


@router.get("/monday/status", response_model=MondaySyncStatusResponse)
@limiter.limit(admin_limit)
async def get_monday_sync_status(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
) -> MondaySyncStatusResponse:
    """Get Monday.com sync status and recent logs. Admin only."""
    service = MondayService(db)
    status_data = await service.get_sync_status()

    return MondaySyncStatusResponse(
        is_configured=status_data["is_configured"],
        last_org_sync=(
            MondaySyncLogResponse.model_validate(status_data["last_org_sync"])
            if status_data["last_org_sync"]
            else None
        ),
        last_contact_sync=(
            MondaySyncLogResponse.model_validate(status_data["last_contact_sync"])
            if status_data["last_contact_sync"]
            else None
        ),
        recent_logs=[
            MondaySyncLogResponse.model_validate(log)
            for log in status_data["recent_logs"]
        ],
    )


@router.get("/monday/config", response_model=MondayConfigResponse)
@limiter.limit(admin_limit)
async def get_monday_config(
    request: Request,
    admin_user: AdminUser,
) -> MondayConfigResponse:
    """Get Monday.com configuration status. Admin only."""
    from app.config import get_settings

    settings = get_settings()

    return MondayConfigResponse(
        is_configured=settings.is_monday_configured,
        organizations_board_id=settings.monday_organizations_board_id or None,
        contacts_board_id=settings.monday_contacts_board_id or None,
    )


@router.get("/monday/boards", response_model=MondayBoardsResponse)
@limiter.limit(admin_limit)
async def get_monday_boards(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
) -> MondayBoardsResponse:
    """Get list of accessible Monday.com boards. Admin only."""
    service = MondayService(db)

    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monday.com API key not configured",
        )

    try:
        boards = await service.get_boards()
        return MondayBoardsResponse(
            boards=[
                MondayBoardInfo(
                    id=b["id"],
                    name=b["name"],
                    columns=b.get("columns", []),
                )
                for b in boards
            ]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Monday boards: {str(e)}",
        )
    finally:
        await service.close()


@router.post("/monday/sync", response_model=MondaySyncLogResponse)
@limiter.limit(admin_limit)
async def trigger_monday_sync(
    request: Request,
    data: MondaySyncTriggerRequest,
    db: DbSession,
    admin_user: AdminUser,
) -> MondaySyncLogResponse:
    """Trigger a Monday.com sync operation. Admin only."""
    from app.config import get_settings

    settings = get_settings()
    service = MondayService(db)

    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monday.com API key not configured",
        )

    # Determine board ID
    if data.board_id:
        board_id = data.board_id
    elif data.sync_type == MondaySyncType.ORGANIZATIONS:
        board_id = settings.monday_organizations_board_id
    else:
        board_id = settings.monday_contacts_board_id

    if not board_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No board ID configured for {data.sync_type.value} sync",
        )

    try:
        if data.sync_type == MondaySyncType.ORGANIZATIONS:
            # Use default field mapping for organizations
            field_mapping = get_default_org_field_mapping()
            sync_log = await service.sync_organizations(
                board_id=board_id,
                field_mapping=field_mapping,
                triggered_by=admin_user.id,
            )
        else:
            # Use default field mapping for contacts
            field_mapping = get_default_contact_field_mapping()
            sync_log = await service.sync_contacts(
                board_id=board_id,
                field_mapping=field_mapping,
                triggered_by=admin_user.id,
            )

        return MondaySyncLogResponse.model_validate(sync_log)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )
    finally:
        await service.close()


@router.get("/monday/logs", response_model=list[MondaySyncLogResponse])
@limiter.limit(admin_limit)
async def get_monday_sync_logs(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
    limit: int = Query(20, ge=1, le=100),
) -> list[MondaySyncLogResponse]:
    """Get Monday.com sync logs. Admin only."""
    result = await db.scalars(
        select(MondaySyncLog).order_by(MondaySyncLog.started_at.desc()).limit(limit)
    )

    return [MondaySyncLogResponse.model_validate(log) for log in result.all()]


# ============== Sync Conflict Management (Admin Only) ==============


@router.get("/sync/conflicts", response_model=ConflictListResponse)
@limiter.limit(admin_limit)
async def list_sync_conflicts(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    entity_type: str | None = Query(
        None, description="Filter by entity type: 'contact' or 'organization'"
    ),
) -> ConflictListResponse:
    """List unresolved sync conflicts. Admin only.

    Returns paginated list of conflicts that need manual resolution.
    """
    service = ConflictService(db)
    conflicts, total = await service.list_unresolved(
        page=page,
        page_size=page_size,
        entity_type=entity_type,
    )

    return ConflictListResponse(
        items=[SyncConflictResponse.model_validate(c) for c in conflicts],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/sync/conflicts/stats")
@limiter.limit(admin_limit)
async def get_sync_conflict_stats(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
) -> dict:
    """Get sync conflict statistics. Admin only."""
    service = ConflictService(db)
    return await service.get_conflict_stats()


@router.get("/sync/conflicts/{conflict_id}", response_model=SyncConflictResponse)
@limiter.limit(admin_limit)
async def get_sync_conflict(
    request: Request,
    conflict_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> SyncConflictResponse:
    """Get details of a specific sync conflict. Admin only.

    Returns the conflict with both NPD and Monday.com data versions.
    """
    service = ConflictService(db)
    conflict = await service.get_by_id(conflict_id)

    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conflict not found",
        )

    return SyncConflictResponse.model_validate(conflict)


@router.post(
    "/sync/conflicts/{conflict_id}/resolve",
    response_model=SyncConflictResponse,
)
@limiter.limit(admin_limit)
async def resolve_sync_conflict(
    request: Request,
    conflict_id: UUID,
    data: ConflictResolveRequest,
    db: DbSession,
    admin_user: AdminUser,
) -> SyncConflictResponse:
    """Resolve a sync conflict. Admin only.

    Resolution types:
    - keep_npd: Use NPD data, push to Monday.com
    - keep_monday: Use Monday.com data, update NPD
    - merge: Apply field-level selections (requires merge_selections)
    """
    service = ConflictService(db)

    try:
        conflict = await service.resolve(
            conflict_id=conflict_id,
            resolution_type=data.resolution_type,
            resolved_by_id=admin_user.id,
            merge_selections=data.merge_selections,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conflict not found",
        )

    return SyncConflictResponse.model_validate(conflict)


@router.post(
    "/sync/conflicts/bulk-resolve",
    response_model=BulkConflictResolveResponse,
)
@limiter.limit(admin_limit)
async def bulk_resolve_sync_conflicts(
    request: Request,
    data: BulkConflictResolveRequest,
    db: DbSession,
    admin_user: AdminUser,
) -> BulkConflictResolveResponse:
    """Resolve multiple sync conflicts at once. Admin only.

    Resolution types for bulk:
    - keep_npd: Use NPD data for all, push to Monday.com
    - keep_monday: Use Monday.com data for all, update NPD

    Note: merge resolution is not supported for bulk operations.
    """
    # Validate resolution type
    if data.resolution_type == ConflictResolutionType.MERGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk resolution does not support merge. Use individual resolve for merge operations.",
        )

    service = ConflictService(db)

    try:
        results = await service.bulk_resolve(
            conflict_ids=data.conflict_ids,
            resolution_type=data.resolution_type,
            resolved_by_id=admin_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    succeeded = sum(1 for r in results if r["success"])
    failed = len(results) - succeeded

    return BulkConflictResolveResponse(
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=[
            BulkResolveResult(
                conflict_id=r["conflict_id"],
                success=r["success"],
                error=r["error"],
            )
            for r in results
        ],
    )


# ============== Sync Queue Management (Admin Only) ==============


@router.get("/sync/queue", response_model=SyncQueueListResponse)
@limiter.limit(admin_limit)
async def list_sync_queue(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    entity_type: str | None = Query(
        None, description="Filter by entity type: 'contact' or 'organization'"
    ),
    direction: str | None = Query(
        None, description="Filter by direction: 'to_monday' or 'to_npd'"
    ),
    queue_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status: 'pending', 'in_progress', 'completed', 'failed'",
    ),
) -> SyncQueueListResponse:
    """List sync queue items with filtering and pagination. Admin only.

    Returns paginated list of sync queue items that can be filtered by
    entity type, direction, and status.
    """
    # Convert string filters to enums
    direction_enum = None
    if direction:
        try:
            direction_enum = SyncQueueDirection(direction)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid direction: {direction}. Must be 'to_monday' or 'to_npd'",
            )

    status_enum = None
    if queue_status:
        try:
            status_enum = SyncQueueStatus(queue_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {queue_status}. Must be 'pending', 'in_progress', 'completed', or 'failed'",
            )

    service = SyncQueueService(db)
    items, total = await service.get_all_items(
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        direction=direction_enum,
        status=status_enum,
    )

    return SyncQueueListResponse(
        items=[SyncQueueItemResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/sync/queue/stats", response_model=SyncQueueStatsResponse)
@limiter.limit(admin_limit)
async def get_sync_queue_stats(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
) -> SyncQueueStatsResponse:
    """Get sync queue statistics. Admin only.

    Returns counts of queue items by status.
    """
    service = SyncQueueService(db)
    stats = await service.get_queue_stats()
    return SyncQueueStatsResponse(**stats)


@router.post(
    "/sync/queue/{queue_id}/retry",
    response_model=SyncQueueItemResponse,
)
@limiter.limit(admin_limit)
async def retry_sync_queue_item(
    request: Request,
    queue_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
    reset_attempts: bool = Query(
        False, description="If True, reset attempt count to 0"
    ),
) -> SyncQueueItemResponse:
    """Manually retry a sync queue item. Admin only.

    Resets the queue item to pending status so it will be processed
    on the next queue run. Optionally resets the attempt counter.
    """
    service = SyncQueueService(db)
    item = await service.manual_retry(queue_id, reset_attempts=reset_attempts)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue item not found",
        )

    return SyncQueueItemResponse.model_validate(item)


# ============== Auto-Resolution Rules (Admin Only) ==============


@router.get("/sync/auto-resolution", response_model=AutoResolutionRuleListResponse)
@limiter.limit(admin_limit)
async def list_auto_resolution_rules(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
) -> AutoResolutionRuleListResponse:
    """List all auto-resolution rules ordered by priority. Admin only."""
    service = AutoResolutionService(db)
    rules, total = await service.list_rules()

    return AutoResolutionRuleListResponse(
        rules=[AutoResolutionRuleResponse.model_validate(r) for r in rules],
        total=total,
    )


@router.post(
    "/sync/auto-resolution",
    response_model=AutoResolutionRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(admin_limit)
async def create_auto_resolution_rule(
    request: Request,
    data: AutoResolutionRuleCreate,
    db: DbSession,
    admin_user: AdminUser,
) -> AutoResolutionRuleResponse:
    """Create a new auto-resolution rule. Admin only."""
    service = AutoResolutionService(db)

    rule = await service.create(
        name=data.name,
        entity_type=data.entity_type,
        field_name=data.field_name,
        preferred_source=data.preferred_source,
        is_enabled=data.is_enabled,
        priority=data.priority,
        created_by_id=admin_user.id,
    )

    return AutoResolutionRuleResponse.model_validate(rule)


@router.get(
    "/sync/auto-resolution/{rule_id}",
    response_model=AutoResolutionRuleResponse,
)
@limiter.limit(admin_limit)
async def get_auto_resolution_rule(
    request: Request,
    rule_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> AutoResolutionRuleResponse:
    """Get a specific auto-resolution rule. Admin only."""
    service = AutoResolutionService(db)
    rule = await service.get_by_id(rule_id)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    return AutoResolutionRuleResponse.model_validate(rule)


@router.patch(
    "/sync/auto-resolution/{rule_id}",
    response_model=AutoResolutionRuleResponse,
)
@limiter.limit(admin_limit)
async def update_auto_resolution_rule(
    request: Request,
    rule_id: UUID,
    data: AutoResolutionRuleUpdate,
    db: DbSession,
    admin_user: AdminUser,
) -> AutoResolutionRuleResponse:
    """Update an auto-resolution rule. Admin only."""
    service = AutoResolutionService(db)

    rule = await service.update(
        rule_id=rule_id,
        name=data.name,
        entity_type=data.entity_type,
        field_name=data.field_name,
        preferred_source=data.preferred_source,
        is_enabled=data.is_enabled,
        priority=data.priority,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    return AutoResolutionRuleResponse.model_validate(rule)


@router.delete(
    "/sync/auto-resolution/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit(admin_limit)
async def delete_auto_resolution_rule(
    request: Request,
    rule_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> None:
    """Delete an auto-resolution rule. Admin only."""
    service = AutoResolutionService(db)

    deleted = await service.delete(rule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )


@router.post(
    "/sync/auto-resolution/reorder",
    response_model=AutoResolutionRuleListResponse,
)
@limiter.limit(admin_limit)
async def reorder_auto_resolution_rules(
    request: Request,
    data: AutoResolutionRuleReorderRequest,
    db: DbSession,
    admin_user: AdminUser,
) -> AutoResolutionRuleListResponse:
    """Reorder auto-resolution rules by priority. Admin only.

    First rule in the list gets highest priority.
    """
    service = AutoResolutionService(db)
    rules = await service.reorder(data.rule_ids)

    return AutoResolutionRuleListResponse(
        rules=[AutoResolutionRuleResponse.model_validate(r) for r in rules],
        total=len(rules),
    )
