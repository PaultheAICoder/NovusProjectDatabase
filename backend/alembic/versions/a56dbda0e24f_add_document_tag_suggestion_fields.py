"""add document tag suggestion fields

Revision ID: a56dbda0e24f
Revises: 017
Create Date: 2025-12-16 04:27:45.052314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a56dbda0e24f'
down_revision: Union[str, None] = '017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add suggested_tag_ids and dismissed_tag_ids columns to documents table
    op.add_column(
        'documents',
        sa.Column('suggested_tag_ids', postgresql.ARRAY(sa.UUID()), nullable=True)
    )
    op.add_column(
        'documents',
        sa.Column('dismissed_tag_ids', postgresql.ARRAY(sa.UUID()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('documents', 'dismissed_tag_ids')
    op.drop_column('documents', 'suggested_tag_ids')
