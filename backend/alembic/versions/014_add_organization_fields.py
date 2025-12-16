"""Add organization fields for billing, address, and inventory.

Revision ID: 014
Revises: 013
Create Date: 2025-12-16

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to organizations table
    op.add_column(
        "organizations",
        sa.Column("billing_contact_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("address_street", sa.String(255), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("address_city", sa.String(100), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("address_state", sa.String(100), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("address_zip", sa.String(20), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("address_country", sa.String(100), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("inventory_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("notes", sa.Text(), nullable=True),
    )

    # Add foreign key constraint for billing_contact_id
    op.create_foreign_key(
        "fk_organizations_billing_contact",
        "organizations",
        "contacts",
        ["billing_contact_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add index for billing_contact_id
    op.create_index(
        "ix_organizations_billing_contact_id",
        "organizations",
        ["billing_contact_id"],
    )


def downgrade() -> None:
    # Drop index first
    op.drop_index("ix_organizations_billing_contact_id", table_name="organizations")

    # Drop foreign key constraint
    op.drop_constraint(
        "fk_organizations_billing_contact", "organizations", type_="foreignkey"
    )

    # Drop columns
    op.drop_column("organizations", "notes")
    op.drop_column("organizations", "inventory_url")
    op.drop_column("organizations", "address_country")
    op.drop_column("organizations", "address_zip")
    op.drop_column("organizations", "address_state")
    op.drop_column("organizations", "address_city")
    op.drop_column("organizations", "address_street")
    op.drop_column("organizations", "billing_contact_id")
