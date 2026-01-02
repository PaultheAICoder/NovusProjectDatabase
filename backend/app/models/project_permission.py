"""Project permission SQLAlchemy model for ACL-based access control."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.team import Team
    from app.models.user import User


class PermissionLevel(str, enum.Enum):
    """Permission level for project access."""

    VIEWER = "viewer"
    EDITOR = "editor"
    OWNER = "owner"


class ProjectVisibility(str, enum.Enum):
    """Project visibility setting."""

    PUBLIC = "public"
    RESTRICTED = "restricted"


class ProjectPermission(Base):
    """Project permission model for ACL-based access grants.

    Stores explicit permissions for users or teams on restricted projects.
    Either user_id OR team_id must be set, but not both (enforced by CHECK constraint).
    """

    __tablename__ = "project_permissions"

    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND team_id IS NULL) OR "
            "(user_id IS NULL AND team_id IS NOT NULL)",
            name="ck_project_permissions_user_or_team",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    team_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    permission_level: Mapped[PermissionLevel] = mapped_column(
        Enum(
            PermissionLevel,
            name="permissionlevel",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    granted_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="permissions",
    )
    user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[user_id],
    )
    team: Mapped["Team | None"] = relationship(
        "Team",
        foreign_keys=[team_id],
    )
    granter: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[granted_by],
    )

    def __repr__(self) -> str:
        target = f"user:{self.user_id}" if self.user_id else f"team:{self.team_id}"
        return f"<ProjectPermission {target} {self.permission_level.value}>"
