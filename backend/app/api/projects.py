"""Project CRUD API endpoints."""

import csv
import io
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.logging import get_logger
from app.core.rate_limit import crud_limit, limiter
from app.models import (
    Contact,
    Organization,
    Project,
    ProjectContact,
    ProjectJiraLink,
    ProjectLocation,
    ProjectStatus,
    ProjectTag,
    Tag,
)
from app.models.audit import AuditLog
from app.models.document import Document
from app.schemas.audit import AuditLogWithUser, UserSummary
from app.schemas.base import PaginatedResponse
from app.schemas.import_ import AutofillRequest, AutofillResponse
from app.schemas.jira import (
    JiraRefreshResponse,
    ProjectJiraLinkCreate,
    ProjectJiraLinkResponse,
)
from app.schemas.project import (
    DismissProjectTagSuggestionRequest,
    ProjectCreate,
    ProjectDetail,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.tag import TagResponse
from app.services.audit_service import AuditService
from app.services.import_service import ImportService
from app.services.jira_service import JiraService
from app.services.monday_service import MondayService
from app.services.search_cache import invalidate_search_cache

router = APIRouter(prefix="/projects", tags=["projects"])
logger = get_logger(__name__)


def _build_project_query():
    """Build base query with all required joins."""
    return select(Project).options(
        selectinload(Project.organization),
        selectinload(Project.owner),
        selectinload(Project.project_tags).selectinload(ProjectTag.tag),
        selectinload(Project.project_contacts).selectinload(ProjectContact.contact),
        selectinload(Project.creator),
        selectinload(Project.updater),
    )


def _build_project_list_query():
    """Build optimized query for list operations (excludes contacts/creator/updater)."""
    return select(Project).options(
        selectinload(Project.organization),
        selectinload(Project.owner),
        selectinload(Project.project_tags).selectinload(ProjectTag.tag),
    )


@router.get("", response_model=PaginatedResponse[ProjectResponse])
@limiter.limit(crud_limit)
async def list_projects(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query(default="", description="Search query for text search"),
    status: list[ProjectStatus] | None = Query(None),
    organization_id: UUID | None = None,
    owner_id: UUID | None = None,
    tag_ids: list[UUID] | None = Query(
        None, description="Filter by tag IDs (projects must have ALL specified tags)"
    ),
    sort_by: str = Query("updated_at", enum=["name", "start_date", "updated_at"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
) -> PaginatedResponse[ProjectResponse]:
    """List projects with optional filters."""
    start_time = time.perf_counter()

    query = _build_project_list_query()

    # Text search filter using PostgreSQL full-text search
    if q and q.strip():
        ts_query = func.plainto_tsquery("english", q.strip())
        query = query.where(Project.search_vector.op("@@")(ts_query))

    if status:
        query = query.where(Project.status.in_(status))
    if organization_id:
        query = query.where(Project.organization_id == organization_id)
    if owner_id:
        query = query.where(Project.owner_id == owner_id)

    # Tag filter - projects must have ALL specified tags (using EXISTS for efficiency)
    if tag_ids:
        for tag_id in tag_ids:
            tag_exists = exists(
                select(ProjectTag.project_id).where(
                    ProjectTag.project_id == Project.id,
                    ProjectTag.tag_id == tag_id,
                )
            )
            query = query.where(tag_exists)

    # Get total count
    count_query = select(func.count()).select_from(
        select(Project.id).where(query.whereclause).subquery()
        if query.whereclause is not None
        else Project
    )
    total = await db.scalar(count_query) or 0

    # Apply sorting
    sort_column = getattr(Project, sort_by)
    if sort_order == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    projects = result.scalars().unique().all()

    items = []
    for project in projects:
        tags = [pt.tag for pt in project.project_tags]
        item = ProjectResponse(
            id=project.id,
            name=project.name,
            organization=project.organization,
            owner=project.owner,
            description=project.description,
            status=project.status,
            start_date=project.start_date,
            end_date=project.end_date,
            location=project.location,
            location_other=project.location_other,
            tags=tags,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
        items.append(item)

    # Log performance metrics
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "list_projects_complete",
        total_results=total,
        page=page,
        elapsed_ms=round(elapsed_ms, 2),
        has_text_query=bool(q and q.strip()),
        has_status_filter=bool(status),
        has_org_filter=bool(organization_id),
        has_tag_filter=bool(tag_ids),
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(crud_limit)
async def create_project(
    request: Request,
    data: ProjectCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Create a new project."""
    # Verify organization exists
    org = await db.scalar(
        select(Organization).where(Organization.id == data.organization_id)
    )
    if not org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not found",
        )

    # Verify all contacts exist and belong to the organization
    contact_result = await db.execute(
        select(Contact).where(
            Contact.id.in_(data.contact_ids),
            Contact.organization_id == data.organization_id,
        )
    )
    contacts = contact_result.scalars().all()
    if len(contacts) != len(data.contact_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more contacts not found or do not belong to the selected organization",
        )

    # Verify all tags exist
    tag_result = await db.execute(select(Tag).where(Tag.id.in_(data.tag_ids)))
    tags = tag_result.scalars().all()
    if len(tags) != len(data.tag_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more tags not found",
        )

    # Validate Monday board ID if provided
    if data.monday_board_id:
        monday_service = MondayService(db)
        try:
            if not await monday_service.validate_board_id(data.monday_board_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Monday.com board ID or board not accessible",
                )
        finally:
            await monday_service.close()

    # Create project
    project = Project(
        name=data.name,
        organization_id=data.organization_id,
        owner_id=current_user.id,
        description=data.description,
        status=data.status,
        start_date=data.start_date,
        end_date=data.end_date,
        location=data.location,
        location_other=(
            data.location_other if data.location == ProjectLocation.OTHER else None
        ),
        billing_amount=data.billing_amount,
        invoice_count=data.invoice_count,
        billing_recipient=data.billing_recipient,
        billing_notes=data.billing_notes,
        pm_notes=data.pm_notes,
        monday_url=data.monday_url,
        monday_board_id=data.monday_board_id,
        jira_url=data.jira_url,
        gitlab_url=data.gitlab_url,
        milestone_version=data.milestone_version,
        run_number=data.run_number,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(project)
    await db.flush()

    # Add contacts
    for contact_id in data.contact_ids:
        pc = ProjectContact(
            project_id=project.id,
            contact_id=contact_id,
            is_primary=(contact_id == data.primary_contact_id),
        )
        db.add(pc)

    # Add tags
    for tag_id in data.tag_ids:
        pt = ProjectTag(project_id=project.id, tag_id=tag_id)
        db.add(pt)

    await db.flush()

    # Reload with relationships
    result = await db.execute(_build_project_query().where(Project.id == project.id))
    project = result.scalar_one()

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_create(
        entity_type="project",
        entity_id=project.id,
        entity_data=AuditService.serialize_entity(
            project,
            exclude_fields=[
                "project_tags",
                "project_contacts",
                "organization",
                "owner",
                "creator",
                "updater",
            ],
        ),
        user_id=current_user.id,
    )

    # Invalidate search cache
    await invalidate_search_cache()

    return ProjectResponse(
        id=project.id,
        name=project.name,
        organization=project.organization,
        owner=project.owner,
        description=project.description,
        status=project.status,
        start_date=project.start_date,
        end_date=project.end_date,
        location=project.location,
        location_other=project.location_other,
        tags=[pt.tag for pt in project.project_tags],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/{project_id}", response_model=ProjectDetail)
@limiter.limit(crud_limit)
async def get_project(
    request: Request,
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectDetail:
    """Get project details."""
    result = await db.execute(_build_project_query().where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Build contacts with is_primary flag
    contacts = []
    for pc in project.project_contacts:
        contact_dict = {
            "id": pc.contact.id,
            "name": pc.contact.name,
            "email": pc.contact.email,
            "organization_id": pc.contact.organization_id,
            "role_title": pc.contact.role_title,
            "phone": pc.contact.phone,
            "notes": pc.contact.notes,
            "monday_url": pc.contact.monday_url,
            "created_at": pc.contact.created_at,
            "updated_at": pc.contact.updated_at,
            "is_primary": pc.is_primary,
        }
        contacts.append(contact_dict)

    return ProjectDetail(
        id=project.id,
        name=project.name,
        organization=project.organization,
        owner=project.owner,
        description=project.description,
        status=project.status,
        start_date=project.start_date,
        end_date=project.end_date,
        location=project.location,
        location_other=project.location_other,
        tags=[pt.tag for pt in project.project_tags],
        contacts=contacts,
        billing_amount=project.billing_amount,
        invoice_count=project.invoice_count,
        billing_recipient=project.billing_recipient,
        billing_notes=project.billing_notes,
        pm_notes=project.pm_notes,
        monday_url=project.monday_url,
        monday_board_id=project.monday_board_id,
        jira_url=project.jira_url,
        gitlab_url=project.gitlab_url,
        milestone_version=project.milestone_version,
        run_number=project.run_number,
        created_at=project.created_at,
        updated_at=project.updated_at,
        created_by=project.creator,
        updated_by=project.updater,
    )


@router.put("/{project_id}", response_model=ProjectResponse)
@limiter.limit(crud_limit)
async def update_project(
    request: Request,
    project_id: UUID,
    data: ProjectUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    """Update a project."""
    result = await db.execute(_build_project_query().where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Capture old state for audit
    old_project_data = AuditService.serialize_entity(
        project,
        exclude_fields=[
            "project_tags",
            "project_contacts",
            "organization",
            "owner",
            "creator",
            "updater",
            "search_vector",
        ],
    )
    old_tag_ids = [str(pt.tag_id) for pt in project.project_tags]

    # Validate status transition if status is being changed
    if (
        data.status
        and data.status != project.status
        and not project.can_transition_to(data.status)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from {project.status.value} to {data.status.value}",
        )

    # Validate existing contacts if organization is changing but contacts list not provided
    if (
        data.organization_id
        and data.organization_id != project.organization_id
        and data.contact_ids is None
    ):
        # Get existing contact IDs
        existing_contact_ids = [pc.contact_id for pc in project.project_contacts]
        if existing_contact_ids:
            # Verify existing contacts belong to the new organization
            valid_count = await db.scalar(
                select(func.count()).where(
                    Contact.id.in_(existing_contact_ids),
                    Contact.organization_id == data.organization_id,
                )
            )
            if valid_count != len(existing_contact_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change organization: existing contacts do not belong to the new organization. Please update contacts first.",
                )

    # Validate Monday board ID if being updated
    if (
        data.monday_board_id is not None
        and data.monday_board_id != project.monday_board_id
    ):
        monday_service = MondayService(db)
        try:
            if data.monday_board_id and not await monday_service.validate_board_id(
                data.monday_board_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Monday.com board ID or board not accessible",
                )
        finally:
            await monday_service.close()

    # Update scalar fields
    update_data = data.model_dump(
        exclude_unset=True,
        exclude={"contact_ids", "primary_contact_id", "tag_ids"},
    )
    for field, value in update_data.items():
        setattr(project, field, value)

    # Clear location_other if location is not "other"
    if data.location is not None and data.location != ProjectLocation.OTHER:
        project.location_other = None
    elif data.location == ProjectLocation.OTHER and data.location_other:
        project.location_other = data.location_other

    project.updated_by = current_user.id

    # Update contacts if provided
    if data.contact_ids is not None:
        # Determine which organization to validate against
        # If org is being changed, validate against new org; otherwise use existing
        target_org_id = (
            data.organization_id if data.organization_id else project.organization_id
        )

        # Verify contacts exist AND belong to the organization
        contact_result = await db.execute(
            select(Contact).where(
                Contact.id.in_(data.contact_ids),
                Contact.organization_id == target_org_id,
            )
        )
        contacts = contact_result.scalars().all()
        if len(contacts) != len(data.contact_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more contacts not found or do not belong to the selected organization",
            )

        # Remove old contacts
        for pc in project.project_contacts:
            await db.delete(pc)

        # Add new contacts
        primary_id = data.primary_contact_id
        if primary_id and primary_id not in data.contact_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="primary_contact_id must be in contact_ids",
            )

        for contact_id in data.contact_ids:
            pc = ProjectContact(
                project_id=project.id,
                contact_id=contact_id,
                is_primary=(contact_id == primary_id),
            )
            db.add(pc)

    # Update tags if provided
    if data.tag_ids is not None:
        # Verify tags exist
        tag_result = await db.execute(select(Tag).where(Tag.id.in_(data.tag_ids)))
        tags = tag_result.scalars().all()
        if len(tags) != len(data.tag_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more tags not found",
            )

        # Remove old tags
        for pt in project.project_tags:
            await db.delete(pt)

        # Add new tags
        for tag_id in data.tag_ids:
            pt = ProjectTag(project_id=project.id, tag_id=tag_id)
            db.add(pt)

    await db.flush()

    # Reload with relationships
    result = await db.execute(_build_project_query().where(Project.id == project.id))
    project = result.scalar_one()

    # Audit logging
    audit_service = AuditService(db)
    new_project_data = AuditService.serialize_entity(
        project,
        exclude_fields=[
            "project_tags",
            "project_contacts",
            "organization",
            "owner",
            "creator",
            "updater",
            "search_vector",
        ],
    )
    await audit_service.log_update(
        entity_type="project",
        entity_id=project.id,
        old_data=old_project_data,
        new_data=new_project_data,
        user_id=current_user.id,
    )

    # Log tag changes separately if tags were modified
    if data.tag_ids is not None:
        new_tag_ids = [str(pt.tag_id) for pt in project.project_tags]
        if set(old_tag_ids) != set(new_tag_ids):
            await audit_service.log_update(
                entity_type="project_tags",
                entity_id=project.id,
                old_data={"tag_ids": old_tag_ids},
                new_data={"tag_ids": new_tag_ids},
                user_id=current_user.id,
            )

    # Invalidate search cache
    await invalidate_search_cache()

    return ProjectResponse(
        id=project.id,
        name=project.name,
        organization=project.organization,
        owner=project.owner,
        description=project.description,
        status=project.status,
        start_date=project.start_date,
        end_date=project.end_date,
        location=project.location,
        location_other=project.location_other,
        tags=[pt.tag for pt in project.project_tags],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(crud_limit)
async def delete_project(
    request: Request,
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Cancel a project (soft-delete by setting status to cancelled).

    This does not permanently delete the project. The project will be marked
    as cancelled and hidden from default list views. The project can be
    restored by updating its status via PUT /projects/{project_id}.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Capture state for audit (this is a soft delete via status change)
    old_status = project.status.value

    # Soft delete - set status to cancelled
    project.status = ProjectStatus.CANCELLED
    project.updated_by = current_user.id
    await db.flush()

    # Audit logging - log as status update (soft delete)
    audit_service = AuditService(db)
    await audit_service.log_update(
        entity_type="project",
        entity_id=project.id,
        old_data={"status": old_status},
        new_data={"status": ProjectStatus.CANCELLED.value},
        user_id=current_user.id,
        metadata={"action": "soft_delete"},
    )

    # Invalidate search cache
    await invalidate_search_cache()


@router.get("/monday/boards", response_model=list[dict])
@limiter.limit(crud_limit)
async def list_monday_boards(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> list[dict]:
    """List available Monday.com boards for linking to projects."""
    monday_service = MondayService(db)
    try:
        if not monday_service.is_configured:
            return []
        return await monday_service.get_boards(limit=100)
    finally:
        await monday_service.close()


@router.get("/{project_id}/monday-board")
@limiter.limit(crud_limit)
async def get_project_monday_board(
    request: Request,
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict | None:
    """Get Monday.com board info for a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not project.monday_board_id:
        return None

    monday_service = MondayService(db)
    try:
        board = await monday_service.get_board(project.monday_board_id)
        return board
    finally:
        await monday_service.close()


@router.post("/autofill", response_model=AutofillResponse)
@limiter.limit(crud_limit)
async def autofill_project(
    request: Request,
    data: AutofillRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> AutofillResponse:
    """
    Get AI-suggested field values based on project name and context.

    Uses RAG to analyze similar projects and suggest tags and description.
    """
    import_service = ImportService(db)
    return await import_service.autofill_project(
        name=data.name,
        existing_description=data.existing_description,
        organization_id=data.organization_id,
    )


@router.get("/{project_id}/document-tag-suggestions", response_model=list[TagResponse])
@limiter.limit(crud_limit)
async def get_project_document_tag_suggestions(
    request: Request,
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[TagResponse]:
    """
    Get aggregated tag suggestions from all project documents.

    Returns tags suggested by document analysis that are not already
    assigned to the project and have not been dismissed.
    """
    # Get project with current tags
    project = await db.scalar(
        select(Project)
        .options(selectinload(Project.project_tags))
        .where(Project.id == project_id)
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    current_tag_ids = {pt.tag_id for pt in project.project_tags}

    # Get all documents with suggestions
    doc_result = await db.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.suggested_tag_ids.isnot(None),
        )
    )
    documents = doc_result.scalars().all()

    # Collect all suggested tag IDs (excluding dismissed and current)
    suggested_ids: set[UUID] = set()
    for doc in documents:
        dismissed = set(doc.dismissed_tag_ids or [])
        for tag_id in doc.suggested_tag_ids or []:
            if tag_id not in dismissed and tag_id not in current_tag_ids:
                suggested_ids.add(tag_id)

    if not suggested_ids:
        return []

    # Fetch tag details
    tag_result = await db.execute(select(Tag).where(Tag.id.in_(suggested_ids)))
    tags = tag_result.scalars().all()

    return [TagResponse.model_validate(t) for t in tags]


@router.post(
    "/{project_id}/dismiss-tag-suggestion", status_code=status.HTTP_204_NO_CONTENT
)
@limiter.limit(crud_limit)
async def dismiss_project_tag_suggestion(
    request: Request,
    project_id: UUID,
    data: DismissProjectTagSuggestionRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """
    Dismiss a tag suggestion for all documents in a project.

    The dismissed tag will no longer appear in aggregated suggestions
    for this project. Applies dismissal to all documents that suggest this tag.
    """
    # Verify project exists
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Find all documents with this tag suggestion
    doc_result = await db.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.suggested_tag_ids.contains([data.tag_id]),
        )
    )
    documents = doc_result.scalars().all()

    # Add to dismissed_tag_ids for each document
    for doc in documents:
        dismissed = doc.dismissed_tag_ids or []
        if data.tag_id not in dismissed:
            doc.dismissed_tag_ids = dismissed + [data.tag_id]

    await db.commit()


# ============== Project Jira Links ==============


@router.get("/{project_id}/jira-links", response_model=list[ProjectJiraLinkResponse])
@limiter.limit(crud_limit)
async def list_project_jira_links(
    request: Request,
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ProjectJiraLinkResponse]:
    """List all Jira links for a project."""
    # Verify project exists
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    result = await db.execute(
        select(ProjectJiraLink)
        .where(ProjectJiraLink.project_id == project_id)
        .order_by(ProjectJiraLink.created_at.desc())
    )
    links = result.scalars().all()

    return [
        ProjectJiraLinkResponse(
            id=str(link.id),
            project_id=str(link.project_id),
            issue_key=link.issue_key,
            project_key=link.project_key,
            url=link.url,
            link_type=link.link_type,
            cached_status=link.cached_status,
            cached_summary=link.cached_summary,
            cached_at=link.cached_at,
            created_at=link.created_at,
        )
        for link in links
    ]


@router.post(
    "/{project_id}/jira-links",
    response_model=ProjectJiraLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(crud_limit)
async def create_project_jira_link(
    request: Request,
    project_id: UUID,
    data: ProjectJiraLinkCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectJiraLinkResponse:
    """Add a Jira link to a project.

    Parses the URL to extract issue_key and project_key automatically.
    """
    # Verify project exists
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Parse the Jira URL to extract keys
    jira_service = JiraService()
    parsed = jira_service.parse_jira_url(data.url)

    if not parsed or not parsed.issue_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Jira URL. Expected format: https://company.atlassian.net/browse/PROJ-123",
        )

    # Check for duplicate
    existing = await db.scalar(
        select(ProjectJiraLink).where(
            ProjectJiraLink.project_id == project_id,
            ProjectJiraLink.issue_key == parsed.issue_key,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Jira link {parsed.issue_key} already exists for this project",
        )

    # Create the link
    link = ProjectJiraLink(
        project_id=project_id,
        issue_key=parsed.issue_key,
        project_key=parsed.project_key,
        url=data.url,
        link_type=data.link_type,
    )
    db.add(link)
    await db.flush()

    return ProjectJiraLinkResponse(
        id=str(link.id),
        project_id=str(link.project_id),
        issue_key=link.issue_key,
        project_key=link.project_key,
        url=link.url,
        link_type=link.link_type,
        cached_status=link.cached_status,
        cached_summary=link.cached_summary,
        cached_at=link.cached_at,
        created_at=link.created_at,
    )


@router.delete(
    "/{project_id}/jira-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit(crud_limit)
async def delete_project_jira_link(
    request: Request,
    project_id: UUID,
    link_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Remove a Jira link from a project."""
    link = await db.scalar(
        select(ProjectJiraLink).where(
            ProjectJiraLink.id == link_id,
            ProjectJiraLink.project_id == project_id,
        )
    )

    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jira link not found",
        )

    await db.delete(link)
    await db.flush()


@router.post("/{project_id}/jira/refresh", response_model=JiraRefreshResponse)
@limiter.limit(crud_limit)
async def refresh_project_jira_status(
    request: Request,
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> JiraRefreshResponse:
    """Manually refresh Jira status for all links in a project.

    Fetches current status from Jira API and updates cache.
    """
    # Verify project exists
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    jira_service = JiraService()
    try:
        if not jira_service.is_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Jira integration not configured",
            )

        results = await jira_service.refresh_project_jira_statuses(project_id, db)
        await db.commit()

        return JiraRefreshResponse(
            total=results["total"],
            refreshed=results["refreshed"],
            failed=results["failed"],
            errors=results["errors"],
            timestamp=datetime.now(UTC),
        )
    finally:
        await jira_service.close()


# ============== Project Audit History ==============


@router.get(
    "/{project_id}/audit",
    response_model=PaginatedResponse[AuditLogWithUser],
)
@limiter.limit(crud_limit)
async def get_project_audit_history(
    request: Request,
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[AuditLogWithUser]:
    """
    Get audit history for a specific project.

    Shorthand for GET /audit?entity_type=project&entity_id={project_id}
    Returns paginated list of audit log entries with user display names.
    """
    # Verify project exists
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Build query for this project's audit logs
    query = (
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .where(AuditLog.entity_type == "project")
        .where(AuditLog.entity_id == project_id)
    )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply ordering and pagination
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    audit_logs = result.scalars().all()

    # Build response with user summaries
    items = []
    for log in audit_logs:
        user_summary = None
        if log.user:
            user_summary = UserSummary(
                id=log.user.id,
                display_name=log.user.display_name,
            )

        items.append(
            AuditLogWithUser(
                id=log.id,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                action=log.action,
                user=user_summary,
                changed_fields=log.changed_fields,
                created_at=log.created_at,
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


async def _generate_projects_csv_rows(
    db: AsyncSession,
    query,
    location_labels: dict[ProjectLocation, str],
) -> AsyncGenerator[str, None]:
    """
    Generate CSV rows one at a time for streaming export.

    Uses batched fetching to avoid loading all records into memory at once.
    This fixes memory exhaustion issues when exporting large datasets (Issue #90).
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
            "Billing Amount",
            "Invoice Count",
            "Billing Recipient",
            "Billing Notes",
            "PM Notes",
            "Monday URL",
            "Jira URL",
            "GitLab URL",
            "Milestone/Version",
            "Run Number",
            "Created At",
            "Updated At",
        ]
    )
    yield output.getvalue()

    # Stream data rows in batches to handle relationships
    offset = 0

    while True:
        batch_query = query.offset(offset).limit(BATCH_SIZE)
        result = await db.execute(batch_query)
        projects = result.scalars().unique().all()

        if not projects:
            break

        for project in projects:
            output = io.StringIO()
            writer = csv.writer(output)
            tags = ", ".join(sorted(pt.tag.name for pt in project.project_tags))

            # Format location display
            location_display = location_labels.get(
                project.location, str(project.location.value)
            )
            if project.location == ProjectLocation.OTHER and project.location_other:
                location_display = f"Other ({project.location_other})"

            writer.writerow(
                [
                    project.name,
                    project.organization.name,
                    project.owner.display_name,
                    project.status.value,
                    project.start_date.isoformat() if project.start_date else "",
                    project.end_date.isoformat() if project.end_date else "",
                    location_display,
                    project.description,
                    tags,
                    str(project.billing_amount) if project.billing_amount else "",
                    str(project.invoice_count) if project.invoice_count else "",
                    project.billing_recipient or "",
                    project.billing_notes or "",
                    project.pm_notes or "",
                    project.monday_url or "",
                    project.jira_url or "",
                    project.gitlab_url or "",
                    project.milestone_version or "",
                    project.run_number or "",
                    project.created_at.isoformat() if project.created_at else "",
                    project.updated_at.isoformat() if project.updated_at else "",
                ]
            )
            yield output.getvalue()

        offset += BATCH_SIZE

        # Exit early if we got fewer than batch size (no more records)
        if len(projects) < BATCH_SIZE:
            break


@router.get("/export/csv")
@limiter.limit(crud_limit)
async def export_projects_csv(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    status: list[ProjectStatus] | None = Query(None),
    organization_id: UUID | None = None,
    owner_id: UUID | None = None,
    tag_ids: list[UUID] | None = Query(None),
):
    """
    Export filtered projects to CSV.

    Returns a downloadable CSV file with all project fields.
    Uses streaming to handle large datasets without memory exhaustion (Issue #90).
    """
    # Build query with same filters as list (but NO pagination)
    # Uses optimized list query that only loads organization, owner, and tags
    query = _build_project_list_query()

    if status:
        query = query.where(Project.status.in_(status))
    if organization_id:
        query = query.where(Project.organization_id == organization_id)
    if owner_id:
        query = query.where(Project.owner_id == owner_id)
    if tag_ids:
        # Filter by tags - projects must have at least one of the specified tags
        query = query.where(
            Project.id.in_(
                select(ProjectTag.project_id).where(ProjectTag.tag_id.in_(tag_ids))
            )
        )

    query = query.order_by(Project.name)

    # Location labels for CSV export
    location_labels = {
        ProjectLocation.HEADQUARTERS: "Headquarters",
        ProjectLocation.TEST_HOUSE: "Test House",
        ProjectLocation.REMOTE: "Remote",
        ProjectLocation.CLIENT_SITE: "Client Site",
        ProjectLocation.OTHER: "Other",
    }

    return StreamingResponse(
        _generate_projects_csv_rows(db, query, location_labels),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=projects_export.csv"},
    )
