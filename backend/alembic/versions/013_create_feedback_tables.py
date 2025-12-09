"""Create feedback and email_monitor_state tables.

Revision ID: 013
Revises: 012
Create Date: 2025-12-09

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

# Define enum at module level for reuse in upgrade/downgrade
feedbackstatus_enum = postgresql.ENUM(
    "pending",
    "resolved",
    "verified",
    "changes_requested",
    name="feedbackstatus",
    create_type=False,
)


def upgrade() -> None:
    # Create enum type first
    feedbackstatus_enum.create(op.get_bind(), checkfirst=True)

    # Create feedback table
    op.create_table(
        "feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "project_id",
            sa.String(100),
            nullable=False,
            server_default="NovusProjectDatabase",
        ),
        sa.Column("github_issue_number", sa.Integer(), nullable=False),
        sa.Column("github_issue_url", sa.String(500), nullable=False),
        sa.Column(
            "status",
            feedbackstatus_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("notification_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_message_id", sa.String(200), nullable=True),
        sa.Column("response_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_email_id", sa.String(200), nullable=True),
        sa.Column("response_content", sa.Text(), nullable=True),
        sa.Column("follow_up_issue_number", sa.Integer(), nullable=True),
        sa.Column("follow_up_issue_url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_issue_number"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_status", "feedback", ["status"])

    # Create email_monitor_state table (singleton pattern)
    op.create_table(
        "email_monitor_state",
        sa.Column(
            "id",
            sa.String(50),
            nullable=False,
            server_default="singleton",
        ),
        sa.Column(
            "last_check_time",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("ix_feedback_status", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")

    # Drop tables
    op.drop_table("email_monitor_state")
    op.drop_table("feedback")

    # Drop enum type
    feedbackstatus_enum.drop(op.get_bind(), checkfirst=True)
