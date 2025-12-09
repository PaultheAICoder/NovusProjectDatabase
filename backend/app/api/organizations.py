"""Organization CRUD API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import crud_limit, limiter
from app.models import Organization, Project
from app.schemas.base import PaginatedResponse
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationDetail,
    OrganizationResponse,
    OrganizationUpdate,
)

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
) -> OrganizationResponse:
    """Create a new organization."""
    org = Organization(
        name=data.name,
        aliases=data.aliases,
    )
    db.add(org)

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization '{data.name}' already exists",
        )

    return OrganizationResponse.model_validate(org)


@router.get("/{organization_id}", response_model=OrganizationDetail)
@limiter.limit(crud_limit)
async def get_organization(
    request: Request,
    organization_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> OrganizationDetail:
    """Get organization details with project count."""
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Get project count
    count_result = await db.execute(
        select(func.count())
        .select_from(Project)
        .where(Project.organization_id == organization_id)
    )
    project_count = count_result.scalar() or 0

    return OrganizationDetail(
        **OrganizationResponse.model_validate(org).model_dump(),
        project_count=project_count,
    )


@router.put("/{organization_id}", response_model=OrganizationResponse)
@limiter.limit(crud_limit)
async def update_organization(
    request: Request,
    organization_id: UUID,
    data: OrganizationUpdate,
    db: DbSession,
    current_user: CurrentUser,
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

    return OrganizationResponse.model_validate(org)
