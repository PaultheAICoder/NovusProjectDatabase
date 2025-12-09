"""Project SQLAlchemy model with junction tables."""

import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProjectStatus(str, enum.Enum):
    """Project status enum."""

    APPROVED = "approved"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Valid status transitions
STATUS_TRANSITIONS: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.APPROVED: {ProjectStatus.ACTIVE, ProjectStatus.CANCELLED},
    ProjectStatus.ACTIVE: {
        ProjectStatus.ON_HOLD,
        ProjectStatus.COMPLETED,
        ProjectStatus.CANCELLED,
    },
    ProjectStatus.ON_HOLD: {ProjectStatus.ACTIVE, ProjectStatus.CANCELLED},
    ProjectStatus.COMPLETED: set(),  # Terminal
    ProjectStatus.CANCELLED: set(),  # Terminal
}


class Project(Base):
    """Project model - central entity tracking client work."""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus),
        nullable=False,
        default=ProjectStatus.APPROVED,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    location: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Billing fields
    billing_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    invoice_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    billing_recipient: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    billing_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Other metadata
    pm_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    monday_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    jira_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    gitlab_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    updated_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="projects",
    )
    owner: Mapped["User"] = relationship(
        "User",
        foreign_keys=[owner_id],
    )
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    updater: Mapped["User"] = relationship(
        "User",
        foreign_keys=[updated_by],
    )
    project_contacts: Mapped[list["ProjectContact"]] = relationship(
        "ProjectContact",
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    project_tags: Mapped[list["ProjectTag"]] = relationship(
        "ProjectTag",
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def can_transition_to(self, new_status: ProjectStatus) -> bool:
        """Check if status transition is valid."""
        return new_status in STATUS_TRANSITIONS.get(self.status, set())

    def __repr__(self) -> str:
        return f"<Project {self.name}>"


class ProjectContact(Base):
    """Junction table for Project ↔ Contact (many-to-many)."""

    __tablename__ = "project_contacts"

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    contact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="project_contacts",
    )
    contact: Mapped["Contact"] = relationship(
        "Contact",
        back_populates="project_contacts",
    )


class ProjectTag(Base):
    """Junction table for Project ↔ Tag (many-to-many)."""

    __tablename__ = "project_tags"

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="project_tags",
    )
    tag: Mapped["Tag"] = relationship(
        "Tag",
        back_populates="project_tags",
    )


# Forward references
from app.models.contact import Contact  # noqa: E402, F401
from app.models.document import Document  # noqa: E402, F401
from app.models.organization import Organization  # noqa: E402, F401
from app.models.tag import Tag  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
