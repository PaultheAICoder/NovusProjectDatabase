"""Audit Log SQLAlchemy model for tracking entity changes."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditAction(str, enum.Enum):
    """Audit action type enum."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ARCHIVE = "archive"


class AuditLog(Base):
    """Audit log model for tracking changes to entities.

    Stores who changed what, when, and the before/after values for key fields.
    Supports Projects, Contacts, Organizations, Documents, and Tags.
    """

    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(
            AuditAction,
            name="auditaction",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # Allow null for system-triggered changes
    )
    changed_fields: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Format: {"field_name": {"old": value, "new": value}}',
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",  # Column name in DB is "metadata"
        JSONB,
        nullable=True,
        comment="Additional context: IP address, user agent, etc.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    user: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<AuditLog {self.entity_type}:{self.entity_id} {self.action.value}>"
