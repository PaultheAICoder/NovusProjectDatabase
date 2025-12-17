"""add resolved_by_id to sync_conflicts

Revision ID: 72055a44b2df
Revises: 020
Create Date: 2025-12-17 02:30:53.148430

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "72055a44b2df"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add resolved_by_id column to sync_conflicts table
    op.add_column(
        "sync_conflicts",
        sa.Column("resolved_by_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_sync_conflicts_resolved_by_id",
        "sync_conflicts",
        "users",
        ["resolved_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_sync_conflicts_resolved_by_id", "sync_conflicts", type_="foreignkey"
    )
    op.drop_column("sync_conflicts", "resolved_by_id")
