"""Create sync_queue table for retry mechanism.

Revision ID: 020
Revises: 019
Create Date: 2025-12-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create sync_queue table
    op.create_table(
        "sync_queue",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("last_attempt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Create indexes
    op.create_index("ix_sync_queue_entity_type", "sync_queue", ["entity_type"])
    op.create_index("ix_sync_queue_entity_id", "sync_queue", ["entity_id"])
    op.create_index("ix_sync_queue_status", "sync_queue", ["status"])
    op.create_index("ix_sync_queue_next_retry", "sync_queue", ["next_retry"])
    # Composite index for efficient queue polling
    op.create_index(
        "ix_sync_queue_pending_retry",
        "sync_queue",
        ["status", "next_retry"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_sync_queue_pending_retry", table_name="sync_queue")
    op.drop_index("ix_sync_queue_next_retry", table_name="sync_queue")
    op.drop_index("ix_sync_queue_status", table_name="sync_queue")
    op.drop_index("ix_sync_queue_entity_id", table_name="sync_queue")
    op.drop_index("ix_sync_queue_entity_type", table_name="sync_queue")
    op.drop_table("sync_queue")
