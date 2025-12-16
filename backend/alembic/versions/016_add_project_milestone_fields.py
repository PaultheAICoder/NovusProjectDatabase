"""Add milestone and run number fields to projects.

Revision ID: 016
Revises: 015
Create Date: 2025-12-16
"""

import sqlalchemy as sa

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("milestone_version", sa.String(255), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("run_number", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "run_number")
    op.drop_column("projects", "milestone_version")
