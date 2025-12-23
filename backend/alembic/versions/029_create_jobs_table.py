"""Create jobs table for unified background job processing.

Revision ID: 029
Revises: 028
Create Date: 2025-12-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "029"
down_revision: str | None = "028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create jobs table."""
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_attempt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "error_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )

    # Create indexes for efficient job queue polling
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_priority", "jobs", ["priority"])
    op.create_index("ix_jobs_next_retry", "jobs", ["next_retry"])
    op.create_index("ix_jobs_status_next_retry", "jobs", ["status", "next_retry"])
    op.create_index(
        "ix_jobs_status_priority_created",
        "jobs",
        ["status", "priority", "created_at"],
    )
    op.create_index("ix_jobs_job_type_status", "jobs", ["job_type", "status"])


def downgrade() -> None:
    """Drop jobs table."""
    op.drop_index("ix_jobs_job_type_status", table_name="jobs")
    op.drop_index("ix_jobs_status_priority_created", table_name="jobs")
    op.drop_index("ix_jobs_status_next_retry", table_name="jobs")
    op.drop_index("ix_jobs_next_retry", table_name="jobs")
    op.drop_index("ix_jobs_priority", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
