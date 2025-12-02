"""API dependencies for route protection and common parameters."""

from typing import Annotated

from fastapi import Depends

from app.core.auth import (
    get_current_active_user,
    get_current_admin_user,
)
from app.database import DbSession
from app.models.user import User

# Re-export DbSession for convenience
__all__ = [
    "DbSession",
    "CurrentUser",
    "AdminUser",
]

# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(get_current_admin_user)]
