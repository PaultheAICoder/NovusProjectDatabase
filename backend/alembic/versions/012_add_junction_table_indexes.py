"""Add indexes on junction table foreign keys.

Revision ID: 012
Revises: 011
Create Date: 2025-12-09

"""

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ProjectTag indexes - for filtering projects by tag and listing tags for project
    op.create_index(
        "ix_project_tags_tag_id",
        "project_tags",
        ["tag_id"],
    )
    op.create_index(
        "ix_project_tags_project_id",
        "project_tags",
        ["project_id"],
    )

    # ProjectContact indexes - for finding projects for contact and listing contacts for project
    op.create_index(
        "ix_project_contacts_contact_id",
        "project_contacts",
        ["contact_id"],
    )
    op.create_index(
        "ix_project_contacts_project_id",
        "project_contacts",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_contacts_project_id", table_name="project_contacts")
    op.drop_index("ix_project_contacts_contact_id", table_name="project_contacts")
    op.drop_index("ix_project_tags_project_id", table_name="project_tags")
    op.drop_index("ix_project_tags_tag_id", table_name="project_tags")
