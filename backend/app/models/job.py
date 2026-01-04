"""Background job processing models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobStatus(str, Enum):
    """Status of a background job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    """Type of background job."""

    DOCUMENT_PROCESSING = "document_processing"
    EMBEDDING_GENERATION = "embedding_generation"
    MONDAY_SYNC = "monday_sync"
    JIRA_REFRESH = "jira_refresh"
    BULK_IMPORT = "bulk_import"
    AUDIT_CLEANUP = "audit_cleanup"
    TEAM_SYNC = "team_sync"


class Job(Base):
    """Background job with status tracking and retry logic.

    This is a unified job queue that can handle various job types
    with built-in retry logic, exponential backoff, and error tracking.
    """

    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    job_type: Mapped[JobType] = mapped_column(
        SAEnum(JobType, native_enum=False),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, native_enum=False),
        nullable=False,
        default=JobStatus.PENDING,
        index=True,
    )

    # Generic entity reference (optional)
    entity_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    entity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )

    # Job configuration and result
    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    result: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Retry logic
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )
    last_attempt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_retry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_context: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Audit
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Composite indexes for efficient job queue polling
    __table_args__ = (
        Index(
            "ix_jobs_status_next_retry",
            "status",
            "next_retry",
        ),
        Index(
            "ix_jobs_status_priority_created",
            "status",
            "priority",
            "created_at",
        ),
        Index(
            "ix_jobs_job_type_status",
            "job_type",
            "status",
        ),
    )

    def __repr__(self) -> str:
        return f"<Job {self.job_type.value} {self.status.value}>"
