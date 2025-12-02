"""Contact Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.organization import OrganizationResponse


class ContactBase(BaseModel):
    """Base contact schema."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    role_title: str | None = None
    phone: str | None = None
    notes: str | None = None
    monday_url: str | None = None


class ContactCreate(ContactBase):
    """Schema for creating a contact."""

    organization_id: UUID


class ContactUpdate(BaseModel):
    """Schema for updating a contact."""

    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    role_title: str | None = None
    phone: str | None = None
    notes: str | None = None
    monday_url: str | None = None


class ContactResponse(ContactBase):
    """Contact response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime


class ContactWithOrganization(ContactResponse):
    """Contact response with organization details."""

    organization: OrganizationResponse


class ContactDetail(ContactWithOrganization):
    """Detailed contact response with related projects."""

    pass  # Will include projects list when needed
