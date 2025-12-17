"""API Token SQLAlchemy model for personal access tokens."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class APIToken(Base):
    """API token model for personal access tokens.

    Stores hashed tokens (never plaintext) with optional scopes and expiration.
    The token_prefix allows users to identify tokens without exposing the full value.
    """

    __tablename__ = "api_tokens"

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
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),  # SHA-256 produces 64 hex characters
        nullable=False,
        unique=True,
        index=True,
    )
    token_prefix: Mapped[str] = mapped_column(
        String(8),  # First 8 characters of token for identification
        nullable=False,
        index=True,
    )
    scopes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<APIToken {self.name} {self.token_prefix}...>"
