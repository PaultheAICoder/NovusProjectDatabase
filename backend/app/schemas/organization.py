"""Organization Pydantic schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectSummaryForOrg(BaseModel):
    """Minimal project info for organization detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str  # Use str to avoid circular import with ProjectStatus
    start_date: date
    end_date: date | None = None


class ContactSummaryForOrg(BaseModel):
    """Minimal contact info for organization detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role_title: str | None = None


class OrganizationBase(BaseModel):
    """Base organization schema."""

    name: str = Field(..., min_length=1, max_length=255)
    aliases: list[str] | None = None


class OrganizationCreate(OrganizationBase):
    """Schema for creating an organization."""

    pass


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""

    name: str | None = Field(None, min_length=1, max_length=255)
    aliases: list[str] | None = None


class OrganizationResponse(OrganizationBase):
    """Organization response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class OrganizationDetail(OrganizationResponse):
    """Detailed organization response with counts."""

    project_count: int = 0


class OrganizationDetailWithRelations(OrganizationDetail):
    """Organization with nested projects and contacts."""

    projects: list[ProjectSummaryForOrg] = []
    contacts: list[ContactSummaryForOrg] = []
