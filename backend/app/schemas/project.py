"""Project Pydantic schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.project import ProjectLocation, ProjectStatus
from app.schemas.contact import ContactResponse
from app.schemas.organization import OrganizationResponse
from app.schemas.tag import TagResponse
from app.schemas.user import UserResponse


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    status: ProjectStatus = ProjectStatus.APPROVED
    start_date: date
    end_date: date | None = None
    location: ProjectLocation = ProjectLocation.HEADQUARTERS
    location_other: str | None = Field(None, max_length=255)
    billing_amount: Decimal | None = Field(None, ge=0)
    invoice_count: int | None = Field(None, ge=0)
    billing_recipient: str | None = None
    billing_notes: str | None = None
    pm_notes: str | None = None
    monday_url: str | None = None
    monday_board_id: str | None = Field(None, max_length=50)
    jira_url: str | None = None
    gitlab_url: str | None = None
    milestone_version: str | None = Field(None, max_length=255)
    run_number: str | None = Field(None, max_length=100)
    engagement_period: str | None = Field(None, max_length=100)

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: date | None, info) -> date | None:
        """Validate end_date is after start_date."""
        if v is not None and "start_date" in info.data:
            start = info.data["start_date"]
            if start and v < start:
                raise ValueError("end_date must be after start_date")
        return v

    @field_validator("location_other", mode="before")
    @classmethod
    def validate_location_other(cls, v: str | None, info) -> str | None:
        """Clear location_other if location is not 'other'."""
        if "location" in info.data and info.data["location"] != ProjectLocation.OTHER:
            return None
        return v


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""

    organization_id: UUID
    contact_ids: list[UUID] = Field(..., min_length=1)
    primary_contact_id: UUID
    tag_ids: list[UUID] = Field(..., min_length=1)

    @field_validator("primary_contact_id")
    @classmethod
    def validate_primary_contact(cls, v: UUID, info) -> UUID:
        """Validate primary_contact_id is in contact_ids."""
        if "contact_ids" in info.data and v not in info.data["contact_ids"]:
            raise ValueError("primary_contact_id must be in contact_ids")
        return v


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: str | None = Field(None, min_length=1, max_length=255)
    organization_id: UUID | None = None
    description: str | None = Field(None, min_length=1)
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    location: ProjectLocation | None = None
    location_other: str | None = None
    contact_ids: list[UUID] | None = Field(None, min_length=1)
    primary_contact_id: UUID | None = None
    tag_ids: list[UUID] | None = Field(None, min_length=1)
    billing_amount: Decimal | None = Field(None, ge=0)
    invoice_count: int | None = Field(None, ge=0)
    billing_recipient: str | None = None
    billing_notes: str | None = None
    pm_notes: str | None = None
    monday_url: str | None = None
    monday_board_id: str | None = Field(None, max_length=50)
    jira_url: str | None = None
    gitlab_url: str | None = None
    milestone_version: str | None = Field(None, max_length=255)
    run_number: str | None = Field(None, max_length=100)
    engagement_period: str | None = Field(None, max_length=100)


class ProjectContactResponse(ContactResponse):
    """Contact response with is_primary flag."""

    is_primary: bool = False


class ProjectSummary(BaseModel):
    """Minimal project info for lists and references."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    organization_name: str
    status: ProjectStatus
    start_date: date


class ProjectResponse(BaseModel):
    """Project response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    organization: OrganizationResponse
    owner: UserResponse
    description: str
    status: ProjectStatus
    start_date: date
    end_date: date | None = None
    location: ProjectLocation
    location_other: str | None = None
    tags: list[TagResponse] = []
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectResponse):
    """Detailed project response with all fields."""

    contacts: list[ProjectContactResponse] = []
    billing_amount: Decimal | None = None
    invoice_count: int | None = None
    billing_recipient: str | None = None
    billing_notes: str | None = None
    pm_notes: str | None = None
    monday_url: str | None = None
    monday_board_id: str | None = None
    jira_url: str | None = None
    gitlab_url: str | None = None
    milestone_version: str | None = None
    run_number: str | None = None
    engagement_period: str | None = None
    created_by: UserResponse
    updated_by: UserResponse


class DismissProjectTagSuggestionRequest(BaseModel):
    """Request to dismiss a tag suggestion for all project documents."""

    tag_id: UUID
