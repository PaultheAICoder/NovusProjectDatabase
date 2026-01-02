"""Project permission Pydantic schemas for ACL-based access control."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.project_permission import PermissionLevel, ProjectVisibility


class ProjectPermissionCreate(BaseModel):
    """Schema for creating a project permission grant."""

    user_id: UUID | None = None
    team_id: UUID | None = None
    permission_level: PermissionLevel

    @model_validator(mode="after")
    def validate_user_or_team(self) -> "ProjectPermissionCreate":
        """Ensure exactly one of user_id or team_id is provided."""
        if self.user_id is None and self.team_id is None:
            raise ValueError("Either user_id or team_id must be provided")
        if self.user_id is not None and self.team_id is not None:
            raise ValueError("Only one of user_id or team_id can be provided")
        return self


class ProjectPermissionUpdate(BaseModel):
    """Schema for updating a project permission (level only)."""

    permission_level: PermissionLevel


class ProjectPermissionResponse(BaseModel):
    """Project permission response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    user_id: UUID | None = None
    team_id: UUID | None = None
    permission_level: PermissionLevel
    granted_by: UUID | None = None
    granted_at: datetime


class ProjectVisibilityUpdate(BaseModel):
    """Schema for updating project visibility."""

    visibility: ProjectVisibility


class ProjectPermissionListResponse(BaseModel):
    """List of project permissions."""

    items: list[ProjectPermissionResponse]
    total: int
