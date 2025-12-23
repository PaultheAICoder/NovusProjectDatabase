"""Contact CRUD API endpoints."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.core.rate_limit import crud_limit, limiter
from app.models import Contact, Organization
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogWithUser, UserSummary
from app.schemas.base import PaginatedResponse
from app.schemas.contact import (
    ContactCreate,
    ContactDetail,
    ContactResponse,
    ContactSyncResponse,
    ContactUpdate,
    ContactWithOrganization,
    ProjectSummaryForContact,
)
from app.services.audit_service import AuditService
from app.services.sync_service import sync_contact_to_monday

settings = get_settings()

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=PaginatedResponse[ContactWithOrganization])
@limiter.limit(crud_limit)
async def list_contacts(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: UUID | None = None,
    search: str | None = None,
) -> PaginatedResponse[ContactWithOrganization]:
    """List contacts with optional filters."""
    query = select(Contact).options(selectinload(Contact.organization))

    if organization_id:
        query = query.where(Contact.organization_id == organization_id)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            Contact.name.ilike(search_filter) | Contact.email.ilike(search_filter)
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.order_by(Contact.name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    contacts = result.scalars().all()

    return PaginatedResponse(
        items=[ContactWithOrganization.model_validate(c) for c in contacts],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(crud_limit)
async def create_contact(
    request: Request,
    data: ContactCreate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> ContactResponse:
    """Create a new contact."""
    # Verify organization exists
    org_result = await db.execute(
        select(Organization).where(Organization.id == data.organization_id)
    )
    if not org_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not found",
        )

    contact = Contact(
        name=data.name,
        email=data.email,
        organization_id=data.organization_id,
        role_title=data.role_title,
        phone=data.phone,
        notes=data.notes,
        monday_url=data.monday_url,
    )
    db.add(contact)

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact with this email already exists in this organization",
        )

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_create(
        entity_type="contact",
        entity_id=contact.id,
        entity_data=AuditService.serialize_entity(
            contact,
            exclude_fields=["organization", "project_contacts"],
        ),
        user_id=current_user.id,
    )

    # Queue sync to Monday.com if configured
    if settings.is_monday_configured and settings.monday_contacts_board_id:
        background_tasks.add_task(sync_contact_to_monday, contact.id)

    return ContactResponse.model_validate(contact)


@router.get("/{contact_id}", response_model=ContactDetail)
@limiter.limit(crud_limit)
async def get_contact(
    request: Request,
    contact_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ContactDetail:
    """Get contact details with associated projects."""
    from app.models.project import Project, ProjectContact

    result = await db.execute(
        select(Contact)
        .options(
            selectinload(Contact.organization),
            selectinload(Contact.project_contacts)
            .selectinload(ProjectContact.project)
            .selectinload(Project.organization),
        )
        .where(Contact.id == contact_id)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    # Build project summaries from project_contacts
    projects = [
        ProjectSummaryForContact(
            id=pc.project.id,
            name=pc.project.name,
            organization_name=(
                pc.project.organization.name if pc.project.organization else ""
            ),
            status=pc.project.status.value,
            start_date=pc.project.start_date,
            end_date=pc.project.end_date,
            is_primary=pc.is_primary,
        )
        for pc in contact.project_contacts
        if pc.project is not None
    ]

    return ContactDetail(
        id=contact.id,
        name=contact.name,
        email=contact.email,
        organization_id=contact.organization_id,
        role_title=contact.role_title,
        phone=contact.phone,
        notes=contact.notes,
        monday_url=contact.monday_url,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
        monday_id=contact.monday_id,
        monday_last_synced=contact.monday_last_synced,
        sync_status=contact.sync_status.value,
        sync_enabled=contact.sync_enabled,
        sync_direction=contact.sync_direction.value,
        organization=contact.organization,
        project_count=len(projects),
        projects=projects,
    )


@router.put("/{contact_id}", response_model=ContactResponse)
@limiter.limit(crud_limit)
async def update_contact(
    request: Request,
    contact_id: UUID,
    data: ContactUpdate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> ContactResponse:
    """Update a contact."""
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    # Capture old state for audit
    old_contact_data = AuditService.serialize_entity(
        contact,
        exclude_fields=["organization", "project_contacts"],
    )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact with this email already exists in this organization",
        )

    # Audit logging
    audit_service = AuditService(db)
    new_contact_data = AuditService.serialize_entity(
        contact,
        exclude_fields=["organization", "project_contacts"],
    )
    await audit_service.log_update(
        entity_type="contact",
        entity_id=contact.id,
        old_data=old_contact_data,
        new_data=new_contact_data,
        user_id=current_user.id,
    )

    # Queue sync to Monday.com if configured
    if settings.is_monday_configured and settings.monday_contacts_board_id:
        background_tasks.add_task(sync_contact_to_monday, contact.id)

    return ContactResponse.model_validate(contact)


@router.post("/{contact_id}/sync-to-monday", response_model=ContactSyncResponse)
@limiter.limit(crud_limit)
async def sync_contact_to_monday_manual(
    request: Request,
    contact_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> ContactSyncResponse:
    """Manually trigger sync of a contact to Monday.com.

    Use this to push a contact to Monday when automatic sync failed
    or to sync a contact that was created with sync disabled.
    """
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    # Check if Monday is configured
    if not settings.is_monday_configured or not settings.monday_contacts_board_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monday.com integration not configured",
        )

    # Queue sync in background
    background_tasks.add_task(sync_contact_to_monday, contact.id)

    return ContactSyncResponse(
        contact_id=contact.id,
        sync_triggered=True,
        message="Sync to Monday.com has been triggered",
        monday_id=contact.monday_id,
    )


# ============== Contact Audit History ==============


@router.get(
    "/{contact_id}/audit",
    response_model=PaginatedResponse[AuditLogWithUser],
)
@limiter.limit(crud_limit)
async def get_contact_audit_history(
    request: Request,
    contact_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[AuditLogWithUser]:
    """
    Get audit history for a specific contact.

    Shorthand for GET /audit?entity_type=contact&entity_id={contact_id}
    Returns paginated list of audit log entries with user display names.
    """
    # Verify contact exists
    contact = await db.scalar(select(Contact).where(Contact.id == contact_id))
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    # Build query for this contact's audit logs
    query = (
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .where(AuditLog.entity_type == "contact")
        .where(AuditLog.entity_id == contact_id)
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
