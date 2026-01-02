"""Add ACL tables for project-level access control.

Revision ID: 030
Revises: 029
Create Date: 2026-01-02

Creates:
- teams table: Maps Azure AD groups to internal teams
- team_members table: Junction for team membership
- project_permissions table: ACL grants for users/teams on projects
- visibility column on projects table

All existing projects get visibility='public' by default for backward compatibility.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "030"
down_revision: str | None = "029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ACL tables and add visibility column to projects."""
    # 1. Create permissionlevel enum
    permissionlevel_enum = postgresql.ENUM(
        "viewer",
        "editor",
        "owner",
        name="permissionlevel",
        create_type=False,
    )
    permissionlevel_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create projectvisibility enum
    projectvisibility_enum = postgresql.ENUM(
        "public",
        "restricted",
        name="projectvisibility",
        create_type=False,
    )
    projectvisibility_enum.create(op.get_bind(), checkfirst=True)

    # 3. Create teams table
    op.create_table(
        "teams",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("azure_ad_group_id", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_teams_azure_ad_group_id",
        "teams",
        ["azure_ad_group_id"],
        unique=True,
    )

    # 4. Create team_members table
    op.create_table(
        "team_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name="fk_team_members_team_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_team_members_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])

    # 5. Create project_permissions table
    op.create_table(
        "project_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "permission_level",
            postgresql.ENUM(
                "viewer",
                "editor",
                "owner",
                name="permissionlevel",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_permissions_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_project_permissions_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name="fk_project_permissions_team_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name="fk_project_permissions_granted_by",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND team_id IS NULL) OR "
            "(user_id IS NULL AND team_id IS NOT NULL)",
            name="ck_project_permissions_user_or_team",
        ),
    )
    op.create_index(
        "ix_project_permissions_project_id",
        "project_permissions",
        ["project_id"],
    )
    op.create_index(
        "ix_project_permissions_user_id",
        "project_permissions",
        ["user_id"],
    )
    op.create_index(
        "ix_project_permissions_team_id",
        "project_permissions",
        ["team_id"],
    )

    # 6. Add visibility column to projects table
    op.add_column(
        "projects",
        sa.Column(
            "visibility",
            postgresql.ENUM(
                "public",
                "restricted",
                name="projectvisibility",
                create_type=False,
            ),
            nullable=False,
            server_default="public",
        ),
    )
    op.create_index("ix_projects_visibility", "projects", ["visibility"])


def downgrade() -> None:
    """Remove ACL tables and visibility column."""
    # Reverse order of creation
    op.drop_index("ix_projects_visibility", table_name="projects")
    op.drop_column("projects", "visibility")

    op.drop_index("ix_project_permissions_team_id", table_name="project_permissions")
    op.drop_index("ix_project_permissions_user_id", table_name="project_permissions")
    op.drop_index("ix_project_permissions_project_id", table_name="project_permissions")
    op.drop_table("project_permissions")

    op.drop_index("ix_team_members_user_id", table_name="team_members")
    op.drop_index("ix_team_members_team_id", table_name="team_members")
    op.drop_table("team_members")

    op.drop_index("ix_teams_azure_ad_group_id", table_name="teams")
    op.drop_table("teams")

    # Drop enums
    postgresql.ENUM(name="projectvisibility").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="permissionlevel").drop(op.get_bind(), checkfirst=True)
