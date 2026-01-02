"""Team Pydantic schemas for ACL-based access control."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TeamBase(BaseModel):
    """Base team schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class TeamCreate(TeamBase):
    """Schema for creating a team."""

    azure_ad_group_id: str = Field(..., min_length=1, max_length=255)


class TeamUpdate(BaseModel):
    """Schema for updating a team."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class TeamMemberResponse(BaseModel):
    """Team member response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID
    user_id: UUID
    synced_at: datetime


class TeamResponse(BaseModel):
    """Team response schema (without members)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    azure_ad_group_id: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class TeamDetailResponse(TeamResponse):
    """Detailed team response with members list."""

    members: list[TeamMemberResponse] = []


class TeamListResponse(BaseModel):
    """Paginated list of teams."""

    items: list[TeamResponse]
    total: int
    page: int
    page_size: int
