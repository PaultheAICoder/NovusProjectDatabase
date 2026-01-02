"""Permission-based route protection dependencies for ACL.

These dependencies can be used declaratively on routes to require
specific permission levels on projects.

Example usage:
    @router.get("/{project_id}")
    async def get_project(
        project: Project = Depends(require_project_viewer),
    ):
        return project
"""

from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.database import get_db
from app.models.project import Project
from app.models.project_permission import PermissionLevel
from app.models.user import User
from app.services.permission_service import PermissionService

__all__ = [
    "get_project_with_permission",
    "require_project_viewer",
    "require_project_editor",
    "require_project_owner",
]


async def _get_project_for_permission_check(
    project_id: UUID,
    db: AsyncSession,
) -> Project:
    """Fetch project by ID or raise 404."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def get_project_with_permission(required_level: PermissionLevel):
    """Factory for creating permission-checking dependencies.

    Args:
        required_level: Minimum permission level required to access.

    Returns:
        Dependency function that returns Project if access granted.

    Raises:
        HTTPException 404: If project not found.
        HTTPException 403: If user lacks required permission level.
    """

    async def dependency(
        project_id: UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> Project:
        project = await _get_project_for_permission_check(project_id, db)

        permission_service = PermissionService(db)
        has_access = await permission_service.check_project_access(
            current_user, project, required_level
        )

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {required_level.value} or higher.",
            )

        return project

    return dependency


# Pre-built dependencies for common permission levels
require_project_viewer = get_project_with_permission(PermissionLevel.VIEWER)
require_project_editor = get_project_with_permission(PermissionLevel.EDITOR)
require_project_owner = get_project_with_permission(PermissionLevel.OWNER)
