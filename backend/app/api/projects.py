"""Project CRUD API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import crud_limit, limiter
from app.models import (
    Contact,
    Organization,
    Project,
    ProjectContact,
    ProjectStatus,
    ProjectTag,
    Tag,
)
from app.schemas.base import PaginatedResponse
from app.schemas.import_ import AutofillRequest, AutofillResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectDetail,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.import_service import ImportService

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
    status: list[ProjectStatus] | None = Query(None),
    organization_id: UUID | None = None,
    owner_id: UUID | None = None,
    sort_by: str = Query("updated_at", enum=["name", "start_date", "updated_at"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
) -> PaginatedResponse[ProjectResponse]:
    """List projects with optional filters."""
    query = _build_project_query()

    if status:
        query = query.where(Project.status.in_(status))
    if organization_id:
        query = query.where(Project.organization_id == organization_id)
    if owner_id:
        query = query.where(Project.owner_id == owner_id)

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
        select(Contact).where(Contact.id.in_(data.contact_ids))
    )
    contacts = contact_result.scalars().all()
    if len(contacts) != len(data.contact_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more contacts not found",
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
        billing_amount=data.billing_amount,
        invoice_count=data.invoice_count,
        billing_recipient=data.billing_recipient,
        billing_notes=data.billing_notes,
        pm_notes=data.pm_notes,
        monday_url=data.monday_url,
        jira_url=data.jira_url,
        gitlab_url=data.gitlab_url,
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

    # Update scalar fields
    update_data = data.model_dump(
        exclude_unset=True,
        exclude={"contact_ids", "primary_contact_id", "tag_ids"},
    )
    for field, value in update_data.items():
        setattr(project, field, value)

    project.updated_by = current_user.id

    # Update contacts if provided
    if data.contact_ids is not None:
        # Verify contacts exist
        contact_result = await db.execute(
            select(Contact).where(Contact.id.in_(data.contact_ids))
        )
        contacts = contact_result.scalars().all()
        if len(contacts) != len(data.contact_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more contacts not found",
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
    """Archive/delete a project (soft delete by setting status to cancelled)."""
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
    """
    import csv
    import io

    from fastapi.responses import StreamingResponse

    # Build query with same filters as list
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
    result = await db.execute(query)
    projects = result.scalars().unique().all()

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
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
            "Created At",
            "Updated At",
        ]
    )

    # Data rows
    for project in projects:
        tags = ", ".join(sorted(pt.tag.name for pt in project.project_tags))
        writer.writerow(
            [
                project.name,
                project.organization.name,
                project.owner.display_name,
                project.status.value,
                project.start_date.isoformat() if project.start_date else "",
                project.end_date.isoformat() if project.end_date else "",
                project.location,
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
                project.created_at.isoformat() if project.created_at else "",
                project.updated_at.isoformat() if project.updated_at else "",
            ]
        )

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=projects_export.csv"},
    )
