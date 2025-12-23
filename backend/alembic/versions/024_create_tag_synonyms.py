"""Create tag_synonyms table for synonym relationships.

Revision ID: 024
Revises: 023
Create Date: 2025-12-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "024"
down_revision: str | None = "023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create tag_synonyms table
    op.create_table(
        "tag_synonyms",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("synonym_tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name="fk_tag_synonyms_tag_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["synonym_tag_id"],
            ["tags.id"],
            name="fk_tag_synonyms_synonym_tag_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_tag_synonyms_created_by",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("tag_id", "synonym_tag_id", name="uq_tag_synonym_pair"),
    )

    # Create indexes for efficient lookups
    op.create_index(
        "ix_tag_synonyms_tag_id",
        "tag_synonyms",
        ["tag_id"],
    )
    op.create_index(
        "ix_tag_synonyms_synonym_tag_id",
        "tag_synonyms",
        ["synonym_tag_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tag_synonyms_synonym_tag_id", table_name="tag_synonyms")
    op.drop_index("ix_tag_synonyms_tag_id", table_name="tag_synonyms")
    op.drop_table("tag_synonyms")
