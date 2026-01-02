"""API dependencies for route protection and common parameters."""

from typing import Annotated

from fastapi import Depends

from app.core.auth import (
    get_current_active_user,
    get_current_admin_user,
)
from app.core.permissions import (
    get_project_with_permission,
    require_project_editor,
    require_project_owner,
    require_project_viewer,
)
from app.database import DbSession, get_db
from app.models.project import Project
from app.models.project_permission import PermissionLevel
from app.models.user import User

# Re-export for convenience
__all__ = [
    "DbSession",
    "CurrentUser",
    "AdminUser",
    "ProjectViewer",
    "ProjectEditor",
    "ProjectOwner",
    "get_db",
    "get_current_user",
    "get_project_with_permission",
    "require_project_viewer",
    "require_project_editor",
    "require_project_owner",
    "PermissionLevel",
]

# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(get_current_admin_user)]

# Permission-based project access type aliases
ProjectViewer = Annotated[Project, Depends(require_project_viewer)]
ProjectEditor = Annotated[Project, Depends(require_project_editor)]
ProjectOwner = Annotated[Project, Depends(require_project_owner)]

# Alias for backwards compatibility
get_current_user = get_current_active_user
