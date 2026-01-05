"""Admin API endpoints (requires admin role)."""

from uuid import UUID

import httpx
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession
from app.core.file_utils import read_file_with_size_limit
from app.core.logging import get_logger
from app.core.rate_limit import admin_limit, limiter
from app.models import Tag, TagSynonym, TagType
from app.models.document import Document
from app.models.document_queue import DocumentQueueStatus
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
from app.schemas.document_queue import (
    DocumentQueueItemResponse,
    DocumentQueueListResponse,
    DocumentQueueStatsResponse,
)
from app.schemas.import_ import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportRowsValidateRequest,
    ImportRowsValidateResponse,
)
from app.schemas.job import JobListResponse, JobResponse, JobStatsResponse
from app.schemas.metrics import (
    CacheMetrics,
    DatabaseMetrics,
    EndpointMetrics,
    ErrorRateMetrics,
    SystemMetricsResponse,
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
    MondayContactMatch,
    MondayContactSearchResponse,
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
    TagSynonymCreate,
    TagSynonymDetail,
    TagSynonymImportRequest,
    TagSynonymImportResponse,
    TagSynonymListResponse,
    TagUpdate,
    TagWithSynonyms,
)
from app.services.audit_service import AuditService
from app.services.auto_resolution_service import AutoResolutionService
from app.services.cache_service import (
    get_dashboard_cache,
    invalidate_tag_cache,
)
from app.services.conflict_service import ConflictService
from app.services.document_queue_service import DocumentQueueService
from app.services.import_service import ImportService
from app.services.job_service import JobService
from app.services.monday_service import (
    MondayAPIError,
    MondayRateLimitError,
    MondayService,
    get_default_contact_field_mapping,
    get_default_org_field_mapping,
)
from app.services.sync_queue_service import SyncQueueService
from app.services.tag_suggester import TagSuggester
from app.services.tag_synonym_service import TagSynonymService

logger = get_logger(__name__)

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

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_create(
        entity_type="tag",
        entity_id=tag.id,
        entity_data=AuditService.serialize_entity(tag),
        user_id=admin_user.id,
    )

    # Invalidate tag cache
    await invalidate_tag_cache()

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

    # Capture old state for audit
    old_tag_data = AuditService.serialize_entity(tag)

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

    # Audit logging
    audit_service = AuditService(db)
    new_tag_data = AuditService.serialize_entity(tag)
    await audit_service.log_update(
        entity_type="tag",
        entity_id=tag.id,
        old_data=old_tag_data,
        new_data=new_tag_data,
        user_id=admin_user.id,
    )

    # Invalidate tag cache
    await invalidate_tag_cache()

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

    # Capture data for audit before deletion
    tag_data = AuditService.serialize_entity(tag)

    await db.execute(delete(Tag).where(Tag.id == tag_id))

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_delete(
        entity_type="tag",
        entity_id=tag_id,
        entity_data=tag_data,
        user_id=admin_user.id,
    )

    # Invalidate tag cache
    await invalidate_tag_cache()


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

    # Capture source tag data for audit
    source_tag_data = AuditService.serialize_entity(source_tag)

    suggester = TagSuggester(db)
    merged_count = await suggester.merge_tags(
        source_tag_id=data.source_tag_id,
        target_tag_id=data.target_tag_id,
    )

    # Audit logging - record the merge as a special action
    audit_service = AuditService(db)
    await audit_service.log_delete(
        entity_type="tag",
        entity_id=data.source_tag_id,
        entity_data=source_tag_data,
        user_id=admin_user.id,
        metadata={
            "action": "merge",
            "merged_into": str(data.target_tag_id),
            "projects_updated": merged_count,
        },
    )

    # Invalidate tag cache
    await invalidate_tag_cache()

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
    """Get overview statistics for the dashboard. Admin only.

    Optimized to use single GROUP BY queries instead of sequential queries
    for better performance at scale (1000+ projects).

    Results are cached for 5 minutes (TTL-based, no write invalidation).
    """
    # Check cache first
    cache = get_dashboard_cache()
    cache_key = "overview"

    cached = await cache.get(cache_key)
    if cached is not None:
        logger.debug("dashboard_stats_cache_hit")
        return cached

    # Cache miss - query database
    # Optimized: Single query to get all project status counts using GROUP BY
    status_counts_query = select(
        Project.status,
        func.count().label("count"),
    ).group_by(Project.status)
    result = await db.execute(status_counts_query)
    rows = result.all()

    # Convert to dict, ensuring all statuses have a value
    project_counts = {s.value: 0 for s in ProjectStatus}
    for row in rows:
        project_counts[row.status.value] = row.count

    total_projects = sum(project_counts.values())

    # Count organizations
    org_count = await db.scalar(select(func.count()).select_from(Organization))

    # Count users
    user_count = await db.scalar(select(func.count()).select_from(User))

    # Count documents
    doc_count = await db.scalar(select(func.count()).select_from(Document))

    # Optimized: Single query to get all tag type counts using GROUP BY
    tag_counts_query = select(
        Tag.type,
        func.count().label("count"),
    ).group_by(Tag.type)
    tag_result = await db.execute(tag_counts_query)
    tag_rows = tag_result.all()

    # Convert to dict, ensuring all tag types have a value
    tag_counts = {t.value: 0 for t in TagType}
    for row in tag_rows:
        tag_counts[row.type.value] = row.count

    total_tags = sum(tag_counts.values())

    stats_result = {
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

    # Store in cache (5-minute TTL)
    await cache.set(cache_key, stats_result)
    logger.debug("dashboard_stats_cache_miss")

    return stats_result


@router.get("/cache/stats")
@limiter.limit(admin_limit)
async def get_cache_statistics(
    request: Request,
    admin_user: AdminUser,
) -> dict:
    """Get cache statistics for all cache types. Admin only.

    Returns hit/miss rates and configuration info for:
    - Tag cache (1-hour TTL)
    - Organization cache (15-minute TTL)
    - Dashboard cache (5-minute TTL)
    - Search cache (5-minute TTL)
    """
    from app.services.cache_service import (
        get_dashboard_cache,
        get_org_cache,
        get_tag_cache,
    )
    from app.services.search_cache import get_search_cache

    return {
        "tag_cache": get_tag_cache().stats,
        "org_cache": get_org_cache().stats,
        "dashboard_cache": get_dashboard_cache().stats,
        "search_cache": get_search_cache().stats,
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
    except MondayRateLimitError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monday.com API rate limit exceeded. Please try again later.",
        )
    except MondayAPIError as e:
        logger.error(
            "monday_boards_fetch_failed",
            error=str(e),
            exc_info=True,
        )
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

    except MondayRateLimitError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monday.com API rate limit exceeded. Please try again later.",
        )
    except MondayAPIError as e:
        logger.error(
            "monday_sync_failed",
            error=str(e),
            sync_type=data.sync_type.value,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
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


@router.get("/monday/contacts/search", response_model=MondayContactSearchResponse)
@limiter.limit(admin_limit)
async def search_monday_contacts(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
    q: str = Query(..., min_length=1, max_length=255, description="Search query"),
    board_id: str | None = Query(
        None, description="Board ID to search (uses config default if not provided)"
    ),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
) -> MondayContactSearchResponse:
    """Search for contacts in Monday.com. Admin only.

    Searches for contacts in the configured contacts board (or specified board)
    by matching the query against name and email columns.

    Use this to find existing Monday contacts when creating/editing NPD contacts,
    enabling linking to Monday items.
    """
    from app.config import get_settings

    settings = get_settings()
    service = MondayService(db)

    if not service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monday.com API key not configured",
        )

    # Use provided board_id or fall back to config
    target_board_id = board_id or settings.monday_contacts_board_id

    if not target_board_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No contacts board ID configured. Provide board_id parameter or set MONDAY_CONTACTS_BOARD_ID.",
        )

    try:
        result = await service.search_monday_contacts(
            board_id=target_board_id,
            query=q,
            limit=limit,
        )

        # Parse items into MondayContactMatch objects
        matches = [
            MondayContactMatch(
                **service._parse_contact_from_item(item, target_board_id)
            )
            for item in result.get("items", [])
        ]

        return MondayContactSearchResponse(
            matches=matches,
            total_matches=len(matches),
            query=q,
            board_id=target_board_id,
            has_more=result.get("has_more", False),
            cursor=result.get("cursor"),
        )

    except MondayRateLimitError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monday.com API rate limit exceeded. Please try again later.",
        )
    except MondayAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Monday.com API error: {str(e)}",
        )
    finally:
        await service.close()


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


# ============== Document Processing Queue (Admin Only) ==============


@router.get("/document-queue", response_model=DocumentQueueListResponse)
@limiter.limit(admin_limit)
async def list_document_queue(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    queue_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status: 'pending', 'in_progress', 'completed', 'failed'",
    ),
) -> DocumentQueueListResponse:
    """List document queue items with filtering and pagination. Admin only.

    Returns paginated list of document processing queue items.
    """
    # Convert string filter to enum
    status_enum = None
    if queue_status:
        try:
            status_enum = DocumentQueueStatus(queue_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {queue_status}. Must be 'pending', 'in_progress', 'completed', or 'failed'",
            )

    service = DocumentQueueService(db)
    items_with_names, total = await service.get_all_items(
        page=page,
        page_size=page_size,
        status=status_enum,
    )

    # Build response with document names
    response_items = []
    for queue_item, document_name in items_with_names:
        item_dict = {
            "id": queue_item.id,
            "document_id": queue_item.document_id,
            "document_name": document_name,
            "status": queue_item.status,
            "operation": queue_item.operation,
            "attempts": queue_item.attempts,
            "max_attempts": queue_item.max_attempts,
            "error_message": queue_item.error_message,
            "next_retry": queue_item.next_retry,
            "created_at": queue_item.created_at,
            "started_at": queue_item.started_at,
            "completed_at": queue_item.completed_at,
        }
        response_items.append(DocumentQueueItemResponse(**item_dict))

    return DocumentQueueListResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/document-queue/stats", response_model=DocumentQueueStatsResponse)
@limiter.limit(admin_limit)
async def get_document_queue_stats(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
) -> DocumentQueueStatsResponse:
    """Get document queue statistics. Admin only.

    Returns counts of queue items by status.
    """
    service = DocumentQueueService(db)
    stats = await service.get_queue_stats()
    return DocumentQueueStatsResponse(
        pending=stats["pending"],
        in_progress=stats["in_progress"],
        completed=stats["completed"],
        failed=stats["failed"],
        total=stats["pending"]
        + stats["in_progress"]
        + stats["completed"]
        + stats["failed"],
    )


@router.post(
    "/document-queue/{queue_id}/retry",
    response_model=DocumentQueueItemResponse,
)
@limiter.limit(admin_limit)
async def retry_document_queue_item(
    request: Request,
    queue_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
    reset_attempts: bool = Query(
        False, description="If True, reset attempt count to 0"
    ),
) -> DocumentQueueItemResponse:
    """Manually retry a document queue item. Admin only.

    Resets the queue item to pending status so it will be processed
    on the next queue run. Optionally resets the attempt counter.
    """
    service = DocumentQueueService(db)
    queue_item = await service.manual_retry(queue_id, reset_attempts=reset_attempts)

    if not queue_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue item not found",
        )

    # Get document name
    doc_result = await db.execute(
        select(Document.display_name).where(Document.id == queue_item.document_id)
    )
    document_name = doc_result.scalar_one_or_none() or "Unknown"

    return DocumentQueueItemResponse(
        id=queue_item.id,
        document_id=queue_item.document_id,
        document_name=document_name,
        status=queue_item.status,
        operation=queue_item.operation,
        attempts=queue_item.attempts,
        max_attempts=queue_item.max_attempts,
        error_message=queue_item.error_message,
        next_retry=queue_item.next_retry,
        created_at=queue_item.created_at,
        started_at=queue_item.started_at,
        completed_at=queue_item.completed_at,
    )


@router.delete(
    "/document-queue/{queue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit(admin_limit)
async def cancel_document_queue_item(
    request: Request,
    queue_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> None:
    """Cancel a pending document queue item. Admin only.

    Removes the item from the queue. Only pending items can be cancelled.
    """
    service = DocumentQueueService(db)
    cancelled = await service.cancel_item(queue_id)

    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue item not found or cannot be cancelled (only pending items can be cancelled)",
        )


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


# ============== Tag Synonym Management (Admin Only) ==============


@router.get("/synonyms", response_model=TagSynonymListResponse)
@limiter.limit(admin_limit)
async def list_tag_synonyms(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TagSynonymListResponse:
    """List all tag synonym relationships with pagination. Admin only."""
    # Count total
    count_query = select(func.count()).select_from(TagSynonym)
    total = await db.scalar(count_query) or 0

    # Fetch with pagination, include related tags
    query = (
        select(TagSynonym)
        .options(selectinload(TagSynonym.tag), selectinload(TagSynonym.synonym_tag))
        .order_by(TagSynonym.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    return TagSynonymListResponse(
        items=[TagSynonymDetail.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/synonyms/{tag_id}", response_model=TagWithSynonyms)
@limiter.limit(admin_limit)
async def get_tag_synonyms(
    request: Request,
    tag_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> TagWithSynonyms:
    """Get a tag with all its synonyms. Admin only."""
    service = TagSynonymService(db)
    result = await service.get_tag_with_synonyms(tag_id)
    if not result:
        raise HTTPException(status_code=404, detail="Tag not found")
    return result


@router.post("/synonyms", response_model=TagSynonymDetail, status_code=201)
@limiter.limit(admin_limit)
async def create_tag_synonym(
    request: Request,
    data: TagSynonymCreate,
    db: DbSession,
    admin_user: AdminUser,
) -> TagSynonymDetail:
    """Create a synonym relationship between two tags. Admin only."""
    service = TagSynonymService(db)
    synonym = await service.add_synonym(
        tag_id=data.tag_id,
        synonym_tag_id=data.synonym_tag_id,
        confidence=data.confidence,
        created_by=admin_user.id,
    )
    if not synonym:
        raise HTTPException(
            status_code=400,
            detail="Cannot create synonym (tags not found, same tag, or already exists)",
        )

    # Re-fetch with full tag details for response
    result = await db.execute(
        select(TagSynonym)
        .where(TagSynonym.id == synonym.id)
        .options(selectinload(TagSynonym.tag), selectinload(TagSynonym.synonym_tag))
    )
    synonym_with_tags = result.scalar_one()
    return TagSynonymDetail.model_validate(synonym_with_tags)


@router.delete("/synonyms/{tag_id}/{synonym_tag_id}", status_code=204)
@limiter.limit(admin_limit)
async def delete_tag_synonym(
    request: Request,
    tag_id: UUID,
    synonym_tag_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> None:
    """Delete a synonym relationship. Admin only."""
    service = TagSynonymService(db)
    deleted = await service.remove_synonym(tag_id, synonym_tag_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Synonym relationship not found")


@router.post("/synonyms/import", response_model=TagSynonymImportResponse)
@limiter.limit(admin_limit)
async def import_tag_synonyms(
    request: Request,
    data: TagSynonymImportRequest,
    db: DbSession,
    admin_user: AdminUser,
) -> TagSynonymImportResponse:
    """Bulk import synonym relationships. Admin only."""
    service = TagSynonymService(db)
    created = await service.bulk_import_synonyms(
        synonyms=data.synonyms,
        created_by=admin_user.id,
    )
    return TagSynonymImportResponse(
        total_requested=len(data.synonyms),
        created=created,
        skipped=len(data.synonyms) - created,
    )


# ============== Background Jobs (Admin Only) ==============


@router.get("/jobs", response_model=JobListResponse)
@limiter.limit(admin_limit)
async def list_jobs(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    job_type: str | None = Query(None, description="Filter by job type"),
    queue_status: str | None = Query(
        None,
        alias="status",
        description="Filter by status: 'pending', 'in_progress', 'completed', 'failed'",
    ),
) -> JobListResponse:
    """List background jobs with filtering and pagination. Admin only.

    Returns paginated list of jobs that can be filtered by job type and status.
    """
    from app.models.job import JobStatus, JobType

    # Convert string filters to enums
    job_type_enum = None
    if job_type:
        try:
            job_type_enum = JobType(job_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid job_type: {job_type}. Valid types: {[t.value for t in JobType]}",
            )

    status_enum = None
    if queue_status:
        try:
            status_enum = JobStatus(queue_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {queue_status}. Must be 'pending', 'in_progress', 'completed', or 'failed'",
            )

    service = JobService(db)
    items, total = await service.get_all_jobs(
        page=page,
        page_size=page_size,
        job_type=job_type_enum,
        status=status_enum,
    )

    return JobListResponse(
        items=[JobResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/jobs/stats", response_model=JobStatsResponse)
@limiter.limit(admin_limit)
async def get_job_stats(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
) -> JobStatsResponse:
    """Get job queue statistics. Admin only.

    Returns counts of jobs by status and by job type.
    """
    service = JobService(db)
    stats = await service.get_job_stats()
    return JobStatsResponse(**stats)


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
@limiter.limit(admin_limit)
async def retry_job(
    request: Request,
    job_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
    reset_attempts: bool = Query(
        False, description="If True, reset attempt count to 0"
    ),
) -> JobResponse:
    """Manually retry a failed job. Admin only.

    Resets the job to pending status so it will be processed
    on the next queue run. Optionally resets the attempt counter.
    """
    service = JobService(db)
    job = await service.manual_retry(job_id, reset_attempts=reset_attempts)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return JobResponse.model_validate(job)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(admin_limit)
async def cancel_job(
    request: Request,
    job_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> None:
    """Cancel a pending job. Admin only.

    Removes the job from the queue. Only pending jobs can be cancelled.
    In-progress, completed, or failed jobs cannot be cancelled.
    """
    service = JobService(db)
    cancelled = await service.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or cannot be cancelled (only pending jobs can be cancelled)",
        )


# ============== Performance Metrics (Admin Only) ==============


@router.get("/metrics", response_model=SystemMetricsResponse)
@limiter.limit(admin_limit)
async def get_system_metrics(
    request: Request,
    admin_user: AdminUser,
    top_endpoints: int = Query(
        20, ge=1, le=100, description="Number of top endpoints to return"
    ),
) -> SystemMetricsResponse:
    """Get comprehensive system performance metrics. Admin only.

    Returns:
    - Request timing percentiles (P50, P95, P99) by endpoint
    - Error rates (4xx and 5xx)
    - Cache statistics
    - Database pool configuration
    """
    from datetime import UTC, datetime

    from app.config import get_settings
    from app.services.cache_service import (
        get_dashboard_cache,
        get_org_cache,
        get_tag_cache,
    )
    from app.services.metrics_service import get_metrics_service
    from app.services.search_cache import get_search_cache

    settings = get_settings()
    metrics = get_metrics_service()

    # Get endpoint metrics
    endpoint_data = metrics.get_endpoint_metrics(top_n=top_endpoints)
    endpoints = [EndpointMetrics(**ep) for ep in endpoint_data]

    # Get error rates
    error_rates = metrics.get_error_rates()

    # Get cache stats
    cache_metrics = CacheMetrics(
        tag_cache=get_tag_cache().stats,
        org_cache=get_org_cache().stats,
        dashboard_cache=get_dashboard_cache().stats,
        search_cache=get_search_cache().stats,
    )

    # Database config
    db_metrics = DatabaseMetrics(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )

    return SystemMetricsResponse(
        collected_at=datetime.now(UTC),
        uptime_seconds=metrics.get_uptime_seconds(),
        request_metrics=ErrorRateMetrics(**error_rates),
        endpoints=endpoints,
        cache=cache_metrics,
        database=db_metrics,
        slow_request_threshold_ms=500.0,
    )


# ============== SharePoint Health (Admin Only) ==============


@router.get("/sharepoint/health")
@limiter.limit(admin_limit)
async def check_sharepoint_health(
    request: Request,
    admin_user: AdminUser,
) -> dict:
    """Check SharePoint connectivity and configuration. Admin only.

    Returns configuration status and attempts to verify connectivity
    by getting an authentication token.
    """
    from app.config import get_settings
    from app.core.sharepoint import (
        SharePointError,
        get_sharepoint_auth,
    )

    settings = get_settings()

    result = {
        "enabled": settings.sharepoint_enabled,
        "configured": settings.is_sharepoint_configured,
        "site_url": settings.sharepoint_site_url or None,
        "drive_id": (
            settings.sharepoint_drive_id[:8] + "..."
            if settings.sharepoint_drive_id
            else None
        ),
        "base_folder": settings.sharepoint_base_folder,
        "auth_status": "not_configured",
        "error": None,
    }

    if not settings.is_sharepoint_configured:
        return result

    # Try to get an auth token to verify connectivity
    try:
        auth = get_sharepoint_auth()
        if auth.is_configured:
            await auth.get_app_token()
            result["auth_status"] = "connected"
        else:
            result["auth_status"] = "misconfigured"
    except SharePointError as e:
        result["auth_status"] = "error"
        result["error"] = str(e)[:200]
        logger.warning(
            "sharepoint_health_check_failed",
            error=str(e),
            exc_info=True,
        )
    except httpx.HTTPError as e:
        result["auth_status"] = "error"
        result["error"] = f"Network error: {str(e)[:200]}"
        logger.warning(
            "sharepoint_health_check_network_error",
            error=str(e),
            exc_info=True,
        )
    except Exception as e:
        result["auth_status"] = "error"
        result["error"] = f"Unexpected error: {str(e)[:200]}"
        logger.warning(
            "sharepoint_health_check_unexpected_error",
            error=str(e),
            exc_info=True,
        )

    return result
