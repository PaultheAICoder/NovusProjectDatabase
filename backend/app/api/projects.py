"""Project CRUD API endpoints."""

import csv
import io
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import crud_limit, limiter
from app.models import (
    Contact,
    Organization,
    Project,
    ProjectContact,
    ProjectLocation,
    ProjectStatus,
    ProjectTag,
    Tag,
)
from app.models.document import Document
from app.schemas.base import PaginatedResponse
from app.schemas.import_ import AutofillRequest, AutofillResponse
from app.schemas.project import (
    DismissProjectTagSuggestionRequest,
    ProjectCreate,
    ProjectDetail,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.tag import TagResponse
from app.services.import_service import ImportService
from app.services.search_cache import invalidate_search_cache

router = APIRouter(prefix="/projects", tags=["projects"])


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
    query = _build_project_query()

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

    # Tag filter - projects must have ALL specified tags
    if tag_ids:
        for tag_id in tag_ids:
            query = query.where(
                Project.id.in_(
                    select(ProjectTag.project_id).where(ProjectTag.tag_id == tag_id)
                )
            )

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

    # Soft delete - set status to cancelled
    project.status = ProjectStatus.CANCELLED
    project.updated_by = current_user.id
    await db.flush()

    # Invalidate search cache
    await invalidate_search_cache()


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
    query = _build_project_query()

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
