"""Add composite indexes for V2 query optimization.

Revision ID: 028
Revises: 027
Create Date: 2025-12-23

Index strategy for 1000+ projects scale:
- Composite indexes for common multi-column filters
- Partial indexes for status-based filtering (most queries filter by non-cancelled)
- Updated_at index for default sort order

Note: ix_audit_logs_entity and ix_saved_searches_created_by already exist
from previous migrations, so they are not recreated here.
"""

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index: status + updated_at (common list + sort)
    op.create_index(
        "ix_projects_status_updated_at",
        "projects",
        ["status", "updated_at"],
    )

    # Composite index: organization_id + status (filter by org and status)
    op.create_index(
        "ix_projects_org_status",
        "projects",
        ["organization_id", "status"],
    )

    # Composite index: owner_id + status (filter by owner and status)
    op.create_index(
        "ix_projects_owner_status",
        "projects",
        ["owner_id", "status"],
    )

    # Updated_at for default sort order
    op.create_index(
        "ix_projects_updated_at",
        "projects",
        ["updated_at"],
    )

    # Partial index for active/approved projects (most common queries)
    op.execute("""
        CREATE INDEX ix_projects_active_approved
        ON projects (organization_id, updated_at)
        WHERE status IN ('active', 'approved')
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_projects_active_approved")
    op.drop_index("ix_projects_updated_at", table_name="projects")
    op.drop_index("ix_projects_owner_status", table_name="projects")
    op.drop_index("ix_projects_org_status", table_name="projects")
    op.drop_index("ix_projects_status_updated_at", table_name="projects")
