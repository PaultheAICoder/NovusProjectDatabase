"""Add engagement period field to projects.

Revision ID: 017
Revises: 016
Create Date: 2025-12-16
"""

import sqlalchemy as sa

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("engagement_period", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "engagement_period")
