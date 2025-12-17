"""Monday.com sync models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MondaySyncStatus(str, Enum):
    """Sync job status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class MondaySyncType(str, Enum):
    """Type of sync operation."""

    ORGANIZATIONS = "organizations"
    CONTACTS = "contacts"


class RecordSyncStatus(str, Enum):
    """Sync status for individual records."""

    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"
    DISABLED = "disabled"


class SyncDirection(str, Enum):
    """Sync direction for records."""

    BIDIRECTIONAL = "bidirectional"
    NPD_TO_MONDAY = "npd_to_monday"
    MONDAY_TO_NPD = "monday_to_npd"
    NONE = "none"


class MondaySyncLog(Base):
    """Log of Monday.com sync operations."""

    __tablename__ = "monday_sync_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    sync_type: Mapped[MondaySyncType] = mapped_column(
        SAEnum(MondaySyncType, native_enum=False),
        nullable=False,
    )
    status: Mapped[MondaySyncStatus] = mapped_column(
        SAEnum(MondaySyncStatus, native_enum=False),
        nullable=False,
        default=MondaySyncStatus.PENDING,
    )
    board_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    items_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    items_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    items_updated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    items_skipped: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    triggered_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Store field mapping used for this sync
    field_mapping: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<MondaySyncLog {self.sync_type.value} {self.status.value}>"


class SyncConflict(Base):
    """Record of sync conflicts between NPD and Monday.com."""

    __tablename__ = "sync_conflicts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),  # 'contact' or 'organization'
        nullable=False,
        index=True,
    )
    entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    monday_item_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    npd_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    monday_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    conflict_fields: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolution_type: Mapped[str | None] = mapped_column(
        String(50),  # 'npd_wins', 'monday_wins', 'merged', 'manual'
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<SyncConflict {self.entity_type} {self.entity_id}>"
