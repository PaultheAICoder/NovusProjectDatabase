"""add monday sync fields and tables

Revision ID: 018
Revises: a56dbda0e24f
Create Date: 2025-12-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "018"
down_revision: Union[str, None] = "a56dbda0e24f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add monday_id to organizations
    op.add_column(
        "organizations", sa.Column("monday_id", sa.String(50), nullable=True)
    )
    op.add_column(
        "organizations",
        sa.Column("monday_last_synced", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_organizations_monday_id", "organizations", ["monday_id"], unique=True
    )

    # Add monday_id to contacts
    op.add_column("contacts", sa.Column("monday_id", sa.String(50), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("monday_last_synced", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_contacts_monday_id", "contacts", ["monday_id"])

    # Create monday_sync_logs table
    op.create_table(
        "monday_sync_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("sync_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("board_id", sa.String(50), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_processed", sa.Integer, default=0, nullable=False),
        sa.Column("items_created", sa.Integer, default=0, nullable=False),
        sa.Column("items_updated", sa.Integer, default=0, nullable=False),
        sa.Column("items_skipped", sa.Integer, default=0, nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "triggered_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("field_mapping", postgresql.JSONB, nullable=True),
    )
    op.create_index(
        "ix_monday_sync_logs_started_at", "monday_sync_logs", ["started_at"]
    )


def downgrade() -> None:
    op.drop_table("monday_sync_logs")
    op.drop_index("ix_contacts_monday_id", table_name="contacts")
    op.drop_column("contacts", "monday_last_synced")
    op.drop_column("contacts", "monday_id")
    op.drop_index("ix_organizations_monday_id", table_name="organizations")
    op.drop_column("organizations", "monday_last_synced")
    op.drop_column("organizations", "monday_id")
