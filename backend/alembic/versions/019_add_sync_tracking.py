"""Add sync tracking columns and sync_conflicts table.

Revision ID: 019
Revises: 018
Create Date: 2025-12-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add sync_status column to contacts
    # Note: Use uppercase enum NAMES to match SQLAlchemy SAEnum(native_enum=False) behavior
    op.add_column(
        "contacts",
        sa.Column(
            "sync_status",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.create_index("ix_contacts_sync_status", "contacts", ["sync_status"])

    # Add sync_enabled column to contacts
    op.add_column(
        "contacts",
        sa.Column(
            "sync_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # Add sync_direction column to contacts
    op.add_column(
        "contacts",
        sa.Column(
            "sync_direction",
            sa.String(20),
            nullable=False,
            server_default="BIDIRECTIONAL",
        ),
    )

    # Add sync_status column to organizations
    op.add_column(
        "organizations",
        sa.Column(
            "sync_status",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.create_index("ix_organizations_sync_status", "organizations", ["sync_status"])

    # Add sync_enabled column to organizations
    op.add_column(
        "organizations",
        sa.Column(
            "sync_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # Add sync_direction column to organizations
    op.add_column(
        "organizations",
        sa.Column(
            "sync_direction",
            sa.String(20),
            nullable=False,
            server_default="BIDIRECTIONAL",
        ),
    )

    # Update existing records with monday_id to have sync_status = 'SYNCED'
    op.execute(
        """
        UPDATE contacts
        SET sync_status = 'SYNCED'
        WHERE monday_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE organizations
        SET sync_status = 'SYNCED'
        WHERE monday_id IS NOT NULL
        """
    )

    # Create sync_conflicts table
    op.create_table(
        "sync_conflicts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monday_item_id", sa.String(50), nullable=False),
        sa.Column("npd_data", postgresql.JSONB, nullable=False),
        sa.Column("monday_data", postgresql.JSONB, nullable=False),
        sa.Column("conflict_fields", postgresql.ARRAY(sa.String(100)), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_type", sa.String(50), nullable=True),
    )

    # Create indexes on sync_conflicts
    op.create_index("ix_sync_conflicts_entity_type", "sync_conflicts", ["entity_type"])
    op.create_index("ix_sync_conflicts_entity_id", "sync_conflicts", ["entity_id"])
    op.create_index(
        "ix_sync_conflicts_monday_item_id", "sync_conflicts", ["monday_item_id"]
    )
    op.create_index("ix_sync_conflicts_detected_at", "sync_conflicts", ["detected_at"])


def downgrade() -> None:
    # Drop sync_conflicts table and indexes
    op.drop_index("ix_sync_conflicts_detected_at", table_name="sync_conflicts")
    op.drop_index("ix_sync_conflicts_monday_item_id", table_name="sync_conflicts")
    op.drop_index("ix_sync_conflicts_entity_id", table_name="sync_conflicts")
    op.drop_index("ix_sync_conflicts_entity_type", table_name="sync_conflicts")
    op.drop_table("sync_conflicts")

    # Drop columns from organizations
    op.drop_column("organizations", "sync_direction")
    op.drop_column("organizations", "sync_enabled")
    op.drop_index("ix_organizations_sync_status", table_name="organizations")
    op.drop_column("organizations", "sync_status")

    # Drop columns from contacts
    op.drop_column("contacts", "sync_direction")
    op.drop_column("contacts", "sync_enabled")
    op.drop_index("ix_contacts_sync_status", table_name="contacts")
    op.drop_column("contacts", "sync_status")
