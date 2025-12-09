"""User Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, computed_field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    display_name: str


class UserResponse(UserBase):
    """User response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: UserRole

    @computed_field
    @property
    def is_admin(self) -> bool:
        """Computed field indicating admin status."""
        return self.role == UserRole.ADMIN


class UserDetail(UserResponse):
    """Detailed user response schema."""

    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None
