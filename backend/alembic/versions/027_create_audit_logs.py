"""Create audit_logs table for change history tracking.

Revision ID: 027
Revises: 026
Create Date: 2025-12-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "027"
down_revision: str | None = "026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create auditaction enum type
    auditaction_enum = postgresql.ENUM(
        "create",
        "update",
        "delete",
        "archive",
        name="auditaction",
        create_type=False,
    )
    auditaction_enum.create(op.get_bind(), checkfirst=True)

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "action",
            postgresql.ENUM(
                "create",
                "update",
                "delete",
                "archive",
                name="auditaction",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_fields", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_audit_logs_user_id",
            ondelete="SET NULL",
        ),
    )

    # Create indexes for common query patterns
    op.create_index(
        "ix_audit_logs_entity",
        "audit_logs",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_audit_logs_user_id",
        "audit_logs",
        ["user_id"],
    )
    op.create_index(
        "ix_audit_logs_created_at",
        "audit_logs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_table("audit_logs")

    # Drop enum type
    auditaction_enum = postgresql.ENUM(
        "create",
        "update",
        "delete",
        "archive",
        name="auditaction",
    )
    auditaction_enum.drop(op.get_bind(), checkfirst=True)
