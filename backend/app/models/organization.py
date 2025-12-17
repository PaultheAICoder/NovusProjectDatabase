"""Organization SQLAlchemy model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Computed, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.monday_sync import RecordSyncStatus, SyncDirection


class Organization(Base):
    """Organization model for client companies."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    aliases: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(255)),
        nullable=True,
    )
    billing_contact_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    address_street: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    address_city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    address_state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    address_zip: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    address_country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    inventory_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    monday_id: Mapped[str | None] = mapped_column(
        String(50),  # Monday item IDs are numeric strings
        nullable=True,
        unique=True,
        index=True,
    )
    monday_last_synced: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sync_status: Mapped[RecordSyncStatus] = mapped_column(
        SAEnum(RecordSyncStatus, native_enum=False),
        nullable=False,
        default=RecordSyncStatus.PENDING,
        index=True,
    )
    sync_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    sync_direction: Mapped[SyncDirection] = mapped_column(
        SAEnum(SyncDirection, native_enum=False),
        nullable=False,
        default=SyncDirection.BIDIRECTIONAL,
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
            "setweight(to_tsvector('english', coalesce(name, '')), 'A')",
            persisted=True,
        ),
        nullable=True,
    )

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact",
        back_populates="organization",
        lazy="selectin",
        foreign_keys="[Contact.organization_id]",
    )
    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="organization",
        lazy="selectin",
    )
    billing_contact: Mapped["Contact | None"] = relationship(
        "Contact",
        foreign_keys=[billing_contact_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name}>"


# Forward references for type hints
from app.models.contact import Contact  # noqa: E402, F401
from app.models.project import Project  # noqa: E402, F401
