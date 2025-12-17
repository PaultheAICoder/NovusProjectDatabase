"""Organization CRUD API endpoints."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.core.rate_limit import crud_limit, limiter
from app.models import Organization
from app.schemas.base import PaginatedResponse
from app.schemas.organization import (
    BillingContactSummary,
    ContactSummaryForOrg,
    OrganizationCreate,
    OrganizationDetailWithRelations,
    OrganizationResponse,
    OrganizationUpdate,
    ProjectSummaryForOrg,
)
from app.services.sync_service import sync_organization_to_monday

settings = get_settings()

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=PaginatedResponse[OrganizationResponse])
@limiter.limit(crud_limit)
async def list_organizations(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
) -> PaginatedResponse[OrganizationResponse]:
    """List organizations with optional search."""
    query = select(Organization)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            Organization.name.ilike(search_filter)
            | Organization.aliases.any(search_filter)
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.order_by(Organization.name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    organizations = result.scalars().all()

    return PaginatedResponse(
        items=[OrganizationResponse.model_validate(org) for org in organizations],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post(
    "", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(crud_limit)
async def create_organization(
    request: Request,
    data: OrganizationCreate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> OrganizationResponse:
    """Create a new organization."""
    org = Organization(
        name=data.name,
        aliases=data.aliases,
        billing_contact_id=data.billing_contact_id,
        address_street=data.address_street,
        address_city=data.address_city,
        address_state=data.address_state,
        address_zip=data.address_zip,
        address_country=data.address_country,
        inventory_url=data.inventory_url,
        notes=data.notes,
    )
    db.add(org)

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization '{data.name}' already exists",
        )

    # Queue sync to Monday.com if configured
    if settings.is_monday_configured and settings.monday_organizations_board_id:
        background_tasks.add_task(sync_organization_to_monday, org.id)

    return OrganizationResponse.model_validate(org)


@router.get("/{organization_id}", response_model=OrganizationDetailWithRelations)
@limiter.limit(crud_limit)
async def get_organization(
    request: Request,
    organization_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> OrganizationDetailWithRelations:
    """Get organization details with projects and contacts."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Organization)
        .options(
            selectinload(Organization.projects),
            selectinload(Organization.contacts),
            selectinload(Organization.billing_contact),
        )
        .where(Organization.id == organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Build project summaries
    projects = [
        ProjectSummaryForOrg(
            id=p.id,
            name=p.name,
            status=p.status.value,
            start_date=p.start_date,
            end_date=p.end_date,
        )
        for p in org.projects
    ]

    # Build contact summaries
    contacts = [
        ContactSummaryForOrg(
            id=c.id,
            name=c.name,
            email=c.email,
            role_title=c.role_title,
        )
        for c in org.contacts
    ]

    # Build billing contact summary if exists
    billing_contact_summary = None
    if org.billing_contact:
        billing_contact_summary = BillingContactSummary(
            id=org.billing_contact.id,
            name=org.billing_contact.name,
            email=org.billing_contact.email,
            role_title=org.billing_contact.role_title,
        )

    return OrganizationDetailWithRelations(
        id=org.id,
        name=org.name,
        aliases=org.aliases,
        billing_contact_id=org.billing_contact_id,
        address_street=org.address_street,
        address_city=org.address_city,
        address_state=org.address_state,
        address_zip=org.address_zip,
        address_country=org.address_country,
        inventory_url=org.inventory_url,
        notes=org.notes,
        created_at=org.created_at,
        updated_at=org.updated_at,
        project_count=len(projects),
        projects=projects,
        contacts=contacts,
        billing_contact=billing_contact_summary,
    )


@router.put("/{organization_id}", response_model=OrganizationResponse)
@limiter.limit(crud_limit)
async def update_organization(
    request: Request,
    organization_id: UUID,
    data: OrganizationUpdate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> OrganizationResponse:
    """Update an organization."""
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name already exists",
        )

    # Queue sync to Monday.com if configured
    if settings.is_monday_configured and settings.monday_organizations_board_id:
        background_tasks.add_task(sync_organization_to_monday, org.id)

    return OrganizationResponse.model_validate(org)
