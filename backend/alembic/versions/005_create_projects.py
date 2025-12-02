"""Create projects table.

Revision ID: 005
Revises: 004
Create Date: 2025-12-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define enum as module-level to avoid auto-creation
projectstatus_enum = postgresql.ENUM(
    "approved", "active", "on_hold", "completed", "cancelled",
    name="projectstatus",
    create_type=False,
)


def upgrade() -> None:
    # Create enum type first
    projectstatus_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            projectstatus_enum,
            nullable=False,
            server_default="approved",
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(255), nullable=False),
        # Billing fields
        sa.Column("billing_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("invoice_count", sa.Integer(), nullable=True),
        sa.Column("billing_recipient", sa.String(255), nullable=True),
        sa.Column("billing_notes", sa.Text(), nullable=True),
        # Other metadata
        sa.Column("pm_notes", sa.Text(), nullable=True),
        sa.Column("monday_url", sa.String(500), nullable=True),
        sa.Column("jira_url", sa.String(500), nullable=True),
        sa.Column("gitlab_url", sa.String(500), nullable=True),
        # Audit fields
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_start_date", "projects", ["start_date"])


def downgrade() -> None:
    op.drop_index("ix_projects_start_date", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("projects")
    projectstatus_enum.drop(op.get_bind(), checkfirst=True)
