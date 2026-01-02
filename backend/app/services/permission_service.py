"""Permission service for ACL-based project access control."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.project import Project
from app.models.project_permission import (
    PermissionLevel,
    ProjectPermission,
    ProjectVisibility,
)
from app.models.team import TeamMember
from app.models.user import User, UserRole

logger = get_logger(__name__)


class PermissionService:
    """Service for checking and resolving project permissions."""

    # Permission level ordering (higher = more access)
    _LEVEL_ORDER = {
        PermissionLevel.VIEWER: 1,
        PermissionLevel.EDITOR: 2,
        PermissionLevel.OWNER: 3,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_permission_level(
        self,
        user: User,
        project: Project,
    ) -> PermissionLevel | None:
        """Get the effective permission level for a user on a project.

        Resolution order:
        1. Admin users always get OWNER level
        2. Public projects grant VIEWER to all authenticated users
        3. Direct user permissions
        4. Team-based permissions (via user's team memberships)
        5. Return highest permission level found, or None if no access

        Args:
            user: The user to check permissions for
            project: The project to check access to

        Returns:
            The highest PermissionLevel found, or None if no access
        """
        # 1. Admin override - always has full access
        if user.role == UserRole.ADMIN:
            logger.debug(
                "permission_admin_override",
                user_id=str(user.id),
                project_id=str(project.id),
            )
            return PermissionLevel.OWNER

        # Start with base level based on visibility
        base_level: PermissionLevel | None = None
        if project.visibility == ProjectVisibility.PUBLIC:
            base_level = PermissionLevel.VIEWER

        # 2. Get direct user permission
        direct_level = await self._get_direct_permission(user.id, project.id)

        # 3. Get team-based permissions
        team_level = await self._resolve_team_permissions(user.id, project.id)

        # 4. Return highest of all levels
        levels = [
            lvl for lvl in [base_level, direct_level, team_level] if lvl is not None
        ]
        if not levels:
            return None

        return max(levels, key=lambda lvl: self._LEVEL_ORDER[lvl])

    async def _get_direct_permission(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> PermissionLevel | None:
        """Get direct permission grant for a user on a project.

        Args:
            user_id: The user's UUID
            project_id: The project's UUID

        Returns:
            PermissionLevel if direct grant exists, None otherwise
        """
        result = await self.db.execute(
            select(ProjectPermission.permission_level).where(
                ProjectPermission.project_id == project_id,
                ProjectPermission.user_id == user_id,
            )
        )
        permission = result.scalar_one_or_none()
        return permission

    async def resolve_team_permissions(
        self,
        user: User,
        project: Project,
    ) -> PermissionLevel | None:
        """Resolve team-based permissions for a user on a project.

        Finds all teams the user belongs to that have permissions on this project,
        and returns the highest permission level among them.

        Args:
            user: The user to check
            project: The project to check

        Returns:
            Highest PermissionLevel from team memberships, or None
        """
        return await self._resolve_team_permissions(user.id, project.id)

    async def _resolve_team_permissions(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> PermissionLevel | None:
        """Internal: resolve team permissions by IDs.

        Query logic:
        1. Find all team_ids where user is a member
        2. Find all project_permissions for those teams on this project
        3. Return the highest permission level
        """
        # Get user's team IDs
        team_result = await self.db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == user_id)
        )
        team_ids = [row[0] for row in team_result.fetchall()]

        if not team_ids:
            return None

        # Get permissions for those teams on this project
        perm_result = await self.db.execute(
            select(ProjectPermission.permission_level).where(
                ProjectPermission.project_id == project_id,
                ProjectPermission.team_id.in_(team_ids),
            )
        )
        levels = [row[0] for row in perm_result.fetchall()]

        if not levels:
            return None

        # Return highest level
        return max(levels, key=lambda lvl: self._LEVEL_ORDER[lvl])

    async def check_project_access(
        self,
        user: User,
        project: Project,
        required_level: PermissionLevel,
    ) -> bool:
        """Check if a user has at least the required permission level on a project.

        Args:
            user: The user to check
            project: The project to check access to
            required_level: Minimum permission level required

        Returns:
            True if user has at least the required level, False otherwise
        """
        effective_level = await self.get_user_permission_level(user, project)

        if effective_level is None:
            logger.debug(
                "permission_check_denied",
                user_id=str(user.id),
                project_id=str(project.id),
                required=required_level.value,
                reason="no_access",
            )
            return False

        has_access = (
            self._LEVEL_ORDER[effective_level] >= self._LEVEL_ORDER[required_level]
        )

        logger.debug(
            "permission_check_result",
            user_id=str(user.id),
            project_id=str(project.id),
            required=required_level.value,
            effective=effective_level.value,
            granted=has_access,
        )

        return has_access

    async def get_accessible_project_ids(
        self,
        user: User,
        minimum_level: PermissionLevel = PermissionLevel.VIEWER,
    ) -> set[UUID]:
        """Get all project IDs the user has access to at the specified minimum level.

        This is optimized for filtering queries - returns all project IDs the user
        can access rather than checking each project individually.

        For admin users, returns empty set (caller should skip filtering entirely).

        Args:
            user: The user to check
            minimum_level: Minimum required permission level (default: VIEWER)

        Returns:
            Set of project UUIDs the user can access
        """
        # Admins can access all projects - return empty set to signal "skip filter"
        if user.role == UserRole.ADMIN:
            logger.debug("accessible_project_ids_admin_skip", user_id=str(user.id))
            return set()  # Empty set = no filtering needed

        accessible_ids: set[UUID] = set()

        # 1. All public projects (if minimum level is VIEWER)
        if minimum_level == PermissionLevel.VIEWER:
            public_result = await self.db.execute(
                select(Project.id).where(Project.visibility == ProjectVisibility.PUBLIC)
            )
            for row in public_result.fetchall():
                accessible_ids.add(row[0])

        # 2. Projects with direct user permission at or above minimum level
        min_order = self._LEVEL_ORDER[minimum_level]
        valid_levels = [
            level for level, order in self._LEVEL_ORDER.items() if order >= min_order
        ]

        direct_result = await self.db.execute(
            select(ProjectPermission.project_id).where(
                ProjectPermission.user_id == user.id,
                ProjectPermission.permission_level.in_(valid_levels),
            )
        )
        for row in direct_result.fetchall():
            accessible_ids.add(row[0])

        # 3. Projects via team membership at or above minimum level
        team_result = await self.db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == user.id)
        )
        team_ids = [row[0] for row in team_result.fetchall()]

        if team_ids:
            team_perm_result = await self.db.execute(
                select(ProjectPermission.project_id).where(
                    ProjectPermission.team_id.in_(team_ids),
                    ProjectPermission.permission_level.in_(valid_levels),
                )
            )
            for row in team_perm_result.fetchall():
                accessible_ids.add(row[0])

        logger.info(
            "accessible_project_ids_resolved",
            user_id=str(user.id),
            minimum_level=minimum_level.value,
            count=len(accessible_ids),
        )

        return accessible_ids

    def is_admin(self, user: User) -> bool:
        """Check if user has admin role.

        Convenience method for callers that need to check admin status
        without performing full permission resolution.

        Args:
            user: The user to check

        Returns:
            True if user has admin role
        """
        return user.role == UserRole.ADMIN

    async def can_manage_permissions(
        self,
        user: User,
        project: Project,
    ) -> bool:
        """Check if user can manage permissions on a project.

        Only project owners and admins can manage permissions.

        Args:
            user: The user to check
            project: The project to check

        Returns:
            True if user can manage permissions
        """
        return await self.check_project_access(user, project, PermissionLevel.OWNER)
