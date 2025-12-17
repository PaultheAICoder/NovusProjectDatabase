"""Create api_tokens table for personal access tokens.

Revision ID: 023
Revises: 022
Create Date: 2025-12-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "023"
down_revision: str | None = "022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create api_tokens table
    op.create_table(
        "api_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_prefix", sa.String(8), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_api_tokens_user_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes for efficient lookups
    op.create_index(
        "ix_api_tokens_user_id",
        "api_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_api_tokens_token_hash",
        "api_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_api_tokens_token_prefix",
        "api_tokens",
        ["token_prefix"],
    )


def downgrade() -> None:
    op.drop_index("ix_api_tokens_token_prefix", table_name="api_tokens")
    op.drop_index("ix_api_tokens_token_hash", table_name="api_tokens")
    op.drop_index("ix_api_tokens_user_id", table_name="api_tokens")
    op.drop_table("api_tokens")
