"""Create auto_resolution_rules table for automatic conflict resolution.

Revision ID: 021
Revises: 72055a44b2df
Create Date: 2025-12-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: str | None = "72055a44b2df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create auto_resolution_rules table
    op.create_table(
        "auto_resolution_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("preferred_source", sa.String(20), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_auto_resolution_rules_created_by_id",
            ondelete="SET NULL",
        ),
    )

    # Create indexes
    op.create_index(
        "ix_auto_resolution_rules_entity_type",
        "auto_resolution_rules",
        ["entity_type"],
    )
    op.create_index(
        "ix_auto_resolution_rules_priority",
        "auto_resolution_rules",
        ["priority"],
    )
    # Partial index for enabled rules (more efficient queries)
    op.create_index(
        "ix_auto_resolution_rules_enabled",
        "auto_resolution_rules",
        ["entity_type", "priority"],
        postgresql_where=sa.text("is_enabled = true"),
    )
    # Composite unique constraint to prevent duplicate rules
    op.create_unique_constraint(
        "uq_auto_resolution_rules_entity_field",
        "auto_resolution_rules",
        ["entity_type", "field_name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_auto_resolution_rules_entity_field",
        "auto_resolution_rules",
        type_="unique",
    )
    op.drop_index("ix_auto_resolution_rules_enabled", table_name="auto_resolution_rules")
    op.drop_index("ix_auto_resolution_rules_priority", table_name="auto_resolution_rules")
    op.drop_index("ix_auto_resolution_rules_entity_type", table_name="auto_resolution_rules")
    op.drop_table("auto_resolution_rules")
