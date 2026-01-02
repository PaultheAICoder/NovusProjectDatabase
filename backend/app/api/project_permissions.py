"""Project permission management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, ProjectOwner
from app.core.logging import get_logger
from app.core.rate_limit import crud_limit, limiter
from app.models.project_permission import PermissionLevel, ProjectPermission
from app.models.team import Team
from app.models.user import User
from app.schemas.project_permission import (
    ProjectPermissionCreate,
    ProjectPermissionListResponse,
    ProjectPermissionResponse,
    ProjectPermissionUpdate,
    ProjectVisibilityUpdate,
)
from app.services.audit_service import AuditService

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["project-permissions"])


@router.get("/{project_id}/permissions", response_model=ProjectPermissionListResponse)
@limiter.limit(crud_limit)
async def list_project_permissions(
    request: Request,
    project_id: UUID,
    project: ProjectOwner,  # Requires OWNER permission
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectPermissionListResponse:
    """List all permissions for a project. Requires owner access."""
    result = await db.execute(
        select(ProjectPermission)
        .where(ProjectPermission.project_id == project_id)
        .order_by(ProjectPermission.granted_at.desc())
    )
    permissions = result.scalars().all()

    return ProjectPermissionListResponse(
        items=[ProjectPermissionResponse.model_validate(p) for p in permissions],
        total=len(permissions),
    )


@router.post(
    "/{project_id}/permissions",
    response_model=ProjectPermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(crud_limit)
async def create_project_permission(
    request: Request,
    project_id: UUID,
    data: ProjectPermissionCreate,
    project: ProjectOwner,  # Requires OWNER permission
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectPermissionResponse:
    """Grant a new permission on a project. Requires owner access."""
    # Validate user_id exists if provided
    if data.user_id:
        user = await db.scalar(select(User).where(User.id == data.user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found",
            )
        # Check for existing permission for this user
        existing = await db.scalar(
            select(ProjectPermission).where(
                ProjectPermission.project_id == project_id,
                ProjectPermission.user_id == data.user_id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has permission on this project",
            )

    # Validate team_id exists if provided
    if data.team_id:
        team = await db.scalar(select(Team).where(Team.id == data.team_id))
        if not team:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team not found",
            )
        # Check for existing permission for this team
        existing = await db.scalar(
            select(ProjectPermission).where(
                ProjectPermission.project_id == project_id,
                ProjectPermission.team_id == data.team_id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Team already has permission on this project",
            )

    # Create permission
    permission = ProjectPermission(
        project_id=project_id,
        user_id=data.user_id,
        team_id=data.team_id,
        permission_level=data.permission_level,
        granted_by=current_user.id,
    )
    db.add(permission)
    await db.flush()

    # Audit logging
    audit_service = AuditService(db)
    target = f"user:{data.user_id}" if data.user_id else f"team:{data.team_id}"
    await audit_service.log_create(
        entity_type="project_permission",
        entity_id=permission.id,
        entity_data={
            "project_id": str(project_id),
            "target": target,
            "permission_level": data.permission_level.value,
        },
        user_id=current_user.id,
    )

    logger.info(
        "permission_granted",
        project_id=str(project_id),
        target=target,
        level=data.permission_level.value,
        granted_by=str(current_user.id),
    )

    return ProjectPermissionResponse.model_validate(permission)


@router.put(
    "/{project_id}/permissions/{permission_id}",
    response_model=ProjectPermissionResponse,
)
@limiter.limit(crud_limit)
async def update_project_permission(
    request: Request,
    project_id: UUID,
    permission_id: UUID,
    data: ProjectPermissionUpdate,
    project: ProjectOwner,  # Requires OWNER permission
    db: DbSession,
    current_user: CurrentUser,
) -> ProjectPermissionResponse:
    """Update a permission level. Requires owner access."""
    # Fetch permission
    permission = await db.scalar(
        select(ProjectPermission).where(
            ProjectPermission.id == permission_id,
            ProjectPermission.project_id == project_id,
        )
    )
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )

    # Check if this would remove the last owner
    if (
        permission.permission_level == PermissionLevel.OWNER
        and data.permission_level != PermissionLevel.OWNER
    ):
        owner_count = await db.scalar(
            select(func.count()).where(
                ProjectPermission.project_id == project_id,
                ProjectPermission.permission_level == PermissionLevel.OWNER,
            )
        )
        if owner_count is not None and owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last owner. Assign another owner first.",
            )

    # Capture old level for audit
    old_level = permission.permission_level.value

    # Update
    permission.permission_level = data.permission_level
    await db.flush()

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_update(
        entity_type="project_permission",
        entity_id=permission.id,
        old_data={"permission_level": old_level},
        new_data={"permission_level": data.permission_level.value},
        user_id=current_user.id,
    )

    target = (
        f"user:{permission.user_id}"
        if permission.user_id
        else f"team:{permission.team_id}"
    )
    logger.info(
        "permission_updated",
        project_id=str(project_id),
        permission_id=str(permission_id),
        target=target,
        old_level=old_level,
        new_level=data.permission_level.value,
        updated_by=str(current_user.id),
    )

    return ProjectPermissionResponse.model_validate(permission)


@router.delete(
    "/{project_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit(crud_limit)
async def delete_project_permission(
    request: Request,
    project_id: UUID,
    permission_id: UUID,
    project: ProjectOwner,  # Requires OWNER permission
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Revoke a permission. Requires owner access."""
    # Fetch permission
    permission = await db.scalar(
        select(ProjectPermission).where(
            ProjectPermission.id == permission_id,
            ProjectPermission.project_id == project_id,
        )
    )
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )

    # Check if this would remove the last owner
    if permission.permission_level == PermissionLevel.OWNER:
        owner_count = await db.scalar(
            select(func.count()).where(
                ProjectPermission.project_id == project_id,
                ProjectPermission.permission_level == PermissionLevel.OWNER,
            )
        )
        if owner_count is not None and owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last owner. Assign another owner first.",
            )

    # Capture for audit
    target = (
        f"user:{permission.user_id}"
        if permission.user_id
        else f"team:{permission.team_id}"
    )
    perm_level = permission.permission_level.value

    # Delete
    await db.delete(permission)
    await db.flush()

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_delete(
        entity_type="project_permission",
        entity_id=permission_id,
        entity_data={
            "project_id": str(project_id),
            "target": target,
            "permission_level": perm_level,
        },
        user_id=current_user.id,
    )

    logger.info(
        "permission_revoked",
        project_id=str(project_id),
        permission_id=str(permission_id),
        target=target,
        level=perm_level,
        revoked_by=str(current_user.id),
    )


@router.put(
    "/{project_id}/visibility",
    response_model=dict,
)
@limiter.limit(crud_limit)
async def update_project_visibility(
    request: Request,
    project_id: UUID,
    data: ProjectVisibilityUpdate,
    project: ProjectOwner,  # Requires OWNER permission
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Change project visibility. Requires owner access."""
    # Capture old visibility for audit
    old_visibility = project.visibility.value

    # Update
    project.visibility = data.visibility
    await db.flush()

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_update(
        entity_type="project",
        entity_id=project_id,
        old_data={"visibility": old_visibility},
        new_data={"visibility": data.visibility.value},
        user_id=current_user.id,
        metadata={"action": "visibility_change"},
    )

    logger.info(
        "visibility_changed",
        project_id=str(project_id),
        old_visibility=old_visibility,
        new_visibility=data.visibility.value,
        changed_by=str(current_user.id),
    )

    return {
        "project_id": str(project_id),
        "visibility": data.visibility.value,
        "message": f"Visibility changed to {data.visibility.value}",
    }
