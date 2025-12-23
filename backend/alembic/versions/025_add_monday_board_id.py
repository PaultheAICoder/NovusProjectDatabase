"""Add monday_board_id to projects table.

Revision ID: 025
Revises: 024
Create Date: 2025-12-23

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "025"
down_revision: str | None = "024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("monday_board_id", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "monday_board_id")
