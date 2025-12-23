"""Contact Pydantic schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.organization import OrganizationResponse


class ProjectSummaryForContact(BaseModel):
    """Minimal project info for contact detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    organization_name: str
    status: str  # Use str to avoid circular import with ProjectStatus
    start_date: date
    end_date: date | None = None
    is_primary: bool = False


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
    sync_enabled: bool | None = None


class ContactResponse(ContactBase):
    """Contact response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime
    monday_id: str | None = None
    monday_last_synced: datetime | None = None
    sync_status: str = "disabled"
    sync_enabled: bool = False
    sync_direction: str = "none"


class ContactWithOrganization(ContactResponse):
    """Contact response with organization details."""

    organization: OrganizationResponse


class ContactDetail(ContactWithOrganization):
    """Detailed contact response with related projects."""

    project_count: int = 0
    projects: list[ProjectSummaryForContact] = []


class ContactSyncResponse(BaseModel):
    """Response for manual sync trigger."""

    model_config = ConfigDict(from_attributes=True)

    contact_id: UUID
    sync_triggered: bool
    message: str
    monday_id: str | None = None
