"""Add full-text search indexes.

Revision ID: 008
Revises: 007
Create Date: 2025-12-01

"""

from alembic import op


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tsvector column for full-text search on projects
    op.execute("""
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(location, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(pm_notes, '')), 'D')
        ) STORED
    """)

    # Create GIN index for fast full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_projects_search_vector
        ON projects USING GIN (search_vector)
    """)

    # Add tsvector column for organizations
    op.execute("""
        ALTER TABLE organizations
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(notes, '')), 'B')
        ) STORED
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_organizations_search_vector
        ON organizations USING GIN (search_vector)
    """)

    # Add tsvector column for contacts
    op.execute("""
        ALTER TABLE contacts
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(email, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(role, '')), 'C')
        ) STORED
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contacts_search_vector
        ON contacts USING GIN (search_vector)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_contacts_search_vector")
    op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS search_vector")

    op.execute("DROP INDEX IF EXISTS ix_organizations_search_vector")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS search_vector")

    op.execute("DROP INDEX IF EXISTS ix_projects_search_vector")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS search_vector")
