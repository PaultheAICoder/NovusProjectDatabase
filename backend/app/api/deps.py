"""API dependencies for route protection and common parameters."""

from typing import Annotated

from fastapi import Depends

from app.core.auth import (
    get_current_active_user,
    get_current_admin_user,
)
from app.database import DbSession, get_db
from app.models.user import User

# Re-export for convenience
__all__ = [
    "DbSession",
    "CurrentUser",
    "AdminUser",
    "get_db",
    "get_current_user",
]

# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(get_current_admin_user)]

# Alias for backwards compatibility
get_current_user = get_current_active_user
