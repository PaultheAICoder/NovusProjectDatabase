"""Create document_processing_queue table for durable document processing.

Revision ID: 022
Revises: 021
Create Date: 2025-12-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create document_processing_queue table
    op.create_table(
        "document_processing_queue",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
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
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_processing_queue_document_id",
            ondelete="CASCADE",
        ),
    )

    # Create indexes
    op.create_index(
        "ix_document_processing_queue_document_id",
        "document_processing_queue",
        ["document_id"],
    )
    op.create_index(
        "ix_document_processing_queue_status",
        "document_processing_queue",
        ["status"],
    )
    op.create_index(
        "ix_document_processing_queue_next_retry",
        "document_processing_queue",
        ["next_retry"],
    )
    op.create_index(
        "ix_document_processing_queue_priority",
        "document_processing_queue",
        ["priority"],
    )
    # Partial composite index for efficient queue polling
    op.create_index(
        "ix_document_processing_queue_pending_retry",
        "document_processing_queue",
        ["status", "next_retry", "priority"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_processing_queue_pending_retry",
        table_name="document_processing_queue",
    )
    op.drop_index(
        "ix_document_processing_queue_priority",
        table_name="document_processing_queue",
    )
    op.drop_index(
        "ix_document_processing_queue_next_retry",
        table_name="document_processing_queue",
    )
    op.drop_index(
        "ix_document_processing_queue_status",
        table_name="document_processing_queue",
    )
    op.drop_index(
        "ix_document_processing_queue_document_id",
        table_name="document_processing_queue",
    )
    op.drop_table("document_processing_queue")
