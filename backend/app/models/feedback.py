"""Feedback SQLAlchemy models."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class FeedbackStatus(str, enum.Enum):
    """Feedback status enum."""

    PENDING = "pending"
    RESOLVED = "resolved"
    VERIFIED = "verified"
    CHANGES_REQUESTED = "changes_requested"


class Feedback(Base):
    """Feedback model tracking user feedback submissions linked to GitHub issues."""

    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        server_default="NovusProjectDatabase",
    )
    github_issue_number: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
    )
    github_issue_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    status: Mapped[FeedbackStatus] = mapped_column(
        Enum(FeedbackStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=FeedbackStatus.PENDING,
        index=True,
    )
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notification_message_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    response_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    response_email_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    response_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    follow_up_issue_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    follow_up_issue_url: Mapped[str | None] = mapped_column(
        String(500),
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

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<Feedback {self.github_issue_number}>"


class EmailMonitorState(Base):
    """Singleton model for tracking email polling state."""

    __tablename__ = "email_monitor_state"

    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        server_default="singleton",
    )
    last_check_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<EmailMonitorState {self.id}>"
