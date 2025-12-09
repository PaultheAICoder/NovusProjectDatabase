"""Tag SQLAlchemy model."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TagType(str, enum.Enum):
    """Tag type enum."""

    TECHNOLOGY = "technology"
    DOMAIN = "domain"
    TEST_TYPE = "test_type"
    FREEFORM = "freeform"


class Tag(Base):
    """Tag model for project classification."""

    __tablename__ = "tags"

    __table_args__ = (UniqueConstraint("name", "type", name="uq_tag_name_type"),)

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    type: Mapped[TagType] = mapped_column(
        Enum(
            TagType,
            name="tagtype",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    creator: Mapped["User | None"] = relationship("User")
    project_tags: Mapped[list["ProjectTag"]] = relationship(
        "ProjectTag",
        back_populates="tag",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name} ({self.type.value})>"


# Forward references
from app.models.project import ProjectTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
