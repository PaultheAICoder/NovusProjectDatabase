"""Project Jira Link SQLAlchemy model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


class ProjectJiraLink(Base):
    """Jira link model for storing multiple Jira references per project."""

    __tablename__ = "project_jira_links"

    __table_args__ = (
        UniqueConstraint("project_id", "issue_key", name="uq_project_jira_link"),
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
    issue_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    project_key: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    link_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="related",
    )
    cached_status: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    cached_summary: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    cached_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="jira_links",
    )

    def __repr__(self) -> str:
        return f"<ProjectJiraLink {self.issue_key}>"
