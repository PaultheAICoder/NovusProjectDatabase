"""Contact SQLAlchemy model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Computed,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Contact(Base):
    """Contact model for individuals at client organizations."""

    __tablename__ = "contacts"

    __table_args__ = (
        UniqueConstraint("email", "organization_id", name="uq_contact_email_org"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    monday_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    monday_id: Mapped[str | None] = mapped_column(
        String(50),  # Monday item IDs are numeric strings
        nullable=True,
        index=True,  # Not unique - same person could be in multiple orgs
    )
    monday_last_synced: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Full-text search vector (generated column)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(name, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(email, '')), 'B') || "
            "setweight(to_tsvector('english', coalesce(role_title, '')), 'C')",
            persisted=True,
        ),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="contacts",
        foreign_keys=[organization_id],
    )
    project_contacts: Mapped[list["ProjectContact"]] = relationship(
        "ProjectContact",
        back_populates="contact",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Contact {self.name} ({self.email})>"


# Forward references
from app.models.organization import Organization  # noqa: E402, F401
from app.models.project import ProjectContact  # noqa: E402, F401
