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

    # Synonym relationships (bidirectional)
    synonyms_as_tag: Mapped[list["TagSynonym"]] = relationship(
        "TagSynonym",
        foreign_keys="TagSynonym.tag_id",
        back_populates="tag",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    synonyms_as_synonym: Mapped[list["TagSynonym"]] = relationship(
        "TagSynonym",
        foreign_keys="TagSynonym.synonym_tag_id",
        back_populates="synonym_tag",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name} ({self.type.value})>"


class TagSynonym(Base):
    """Synonym relationship between two tags.

    Represents that tag_id and synonym_tag_id are synonyms.
    The relationship is symmetric - if A is a synonym of B, then B is a synonym of A.
    Uses confidence score to distinguish manual (1.0) vs AI-suggested (<1.0) synonyms.
    """

    __tablename__ = "tag_synonyms"

    __table_args__ = (
        UniqueConstraint("tag_id", "synonym_tag_id", name="uq_tag_synonym_pair"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tag_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    synonym_tag_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(
        nullable=False,
        default=1.0,  # 1.0 = manual, <1.0 = AI-suggested
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
    tag: Mapped["Tag"] = relationship(
        "Tag",
        foreign_keys=[tag_id],
        back_populates="synonyms_as_tag",
        lazy="selectin",
    )
    synonym_tag: Mapped["Tag"] = relationship(
        "Tag",
        foreign_keys=[synonym_tag_id],
        back_populates="synonyms_as_synonym",
        lazy="selectin",
    )
    creator: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<TagSynonym {self.tag_id} <-> {self.synonym_tag_id}>"


# Forward references
from app.models.project import ProjectTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
