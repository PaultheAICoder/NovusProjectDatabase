"""Create project_jira_links table and migrate existing jira_url data.

Revision ID: 026
Revises: 025
Create Date: 2025-12-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "026"
down_revision: str | None = "025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create project_jira_links table
    op.create_table(
        "project_jira_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_key", sa.String(50), nullable=False),
        sa.Column("project_key", sa.String(20), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("link_type", sa.String(50), nullable=False, server_default="related"),
        sa.Column("cached_status", sa.String(100), nullable=True),
        sa.Column("cached_summary", sa.String(500), nullable=True),
        sa.Column("cached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_jira_links_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", "issue_key", name="uq_project_jira_link"),
    )

    # Create indexes
    op.create_index(
        "ix_project_jira_links_project_id",
        "project_jira_links",
        ["project_id"],
    )
    op.create_index(
        "ix_project_jira_links_issue_key",
        "project_jira_links",
        ["issue_key"],
    )

    # Migrate existing jira_url data
    # This uses raw SQL to parse URLs and extract issue keys
    # Pattern: https://xxx.atlassian.net/browse/PROJ-123
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT id, jira_url
            FROM projects
            WHERE jira_url IS NOT NULL AND jira_url != ''
        """
        )
    )

    for row in result:
        project_id = row[0]
        jira_url = row[1]

        # Extract issue key from URL (e.g., PROJ-123 from .../browse/PROJ-123)
        # Simple regex-like extraction
        if "/browse/" in jira_url:
            parts = jira_url.split("/browse/")
            if len(parts) == 2:
                issue_key = parts[1].split("/")[0].split("?")[0].upper()
                project_key = issue_key.split("-")[0] if "-" in issue_key else issue_key

                conn.execute(
                    sa.text(
                        """
                        INSERT INTO project_jira_links
                        (project_id, issue_key, project_key, url, link_type)
                        VALUES (:project_id, :issue_key, :project_key, :url, 'epic')
                        ON CONFLICT DO NOTHING
                    """
                    ),
                    {
                        "project_id": project_id,
                        "issue_key": issue_key,
                        "project_key": project_key,
                        "url": jira_url,
                    },
                )


def downgrade() -> None:
    op.drop_index("ix_project_jira_links_issue_key", table_name="project_jira_links")
    op.drop_index("ix_project_jira_links_project_id", table_name="project_jira_links")
    op.drop_table("project_jira_links")
