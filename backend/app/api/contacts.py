"""Contact CRUD API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import crud_limit, limiter
from app.models import Contact, Organization
from app.schemas.base import PaginatedResponse
from app.schemas.contact import (
    ContactCreate,
    ContactResponse,
    ContactUpdate,
    ContactWithOrganization,
)

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

    return ContactResponse.model_validate(contact)


@router.get("/{contact_id}", response_model=ContactWithOrganization)
@limiter.limit(crud_limit)
async def get_contact(
    request: Request,
    contact_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ContactWithOrganization:
    """Get contact details."""
    result = await db.execute(
        select(Contact)
        .options(selectinload(Contact.organization))
        .where(Contact.id == contact_id)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    return ContactWithOrganization.model_validate(contact)


@router.put("/{contact_id}", response_model=ContactResponse)
@limiter.limit(crud_limit)
async def update_contact(
    request: Request,
    contact_id: UUID,
    data: ContactUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ContactResponse:
    """Update a contact."""
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
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

    return ContactResponse.model_validate(contact)
