"""Add location enum and location_other field.

Revision ID: 015
Revises: 014
Create Date: 2025-12-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define enum as module-level
projectlocation_enum = postgresql.ENUM(
    "headquarters",
    "test_house",
    "remote",
    "client_site",
    "other",
    name="projectlocation",
    create_type=False,
)

# Mapping of old string values to new enum values
LOCATION_MAPPINGS = {
    "hq": "headquarters",
    "headquarters": "headquarters",
    "head quarters": "headquarters",
    "test house": "test_house",
    "test_house": "test_house",
    "testhouse": "test_house",
    "remote": "remote",
    "wfh": "remote",
    "work from home": "remote",
    "client site": "client_site",
    "client_site": "client_site",
    "on-site": "client_site",
    "onsite": "client_site",
}


def upgrade() -> None:
    # 1. Drop search_vector and its index first (depends on location column)
    op.drop_index("ix_projects_search_vector", table_name="projects")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS search_vector;")

    # 2. Create the enum type
    projectlocation_enum.create(op.get_bind(), checkfirst=True)

    # 3. Add location_other column
    op.add_column(
        "projects",
        sa.Column("location_other", sa.String(255), nullable=True),
    )

    # 4. Add temporary column for new enum values
    op.add_column(
        "projects",
        sa.Column("location_new", projectlocation_enum, nullable=True),
    )

    # 5. Migrate data: map known values, put unknowns in location_other
    conn = op.get_bind()

    # Get all distinct locations
    result = conn.execute(sa.text("SELECT DISTINCT location FROM projects"))
    locations = [row[0] for row in result]

    for old_location in locations:
        old_lower = old_location.lower().strip() if old_location else ""
        new_location = LOCATION_MAPPINGS.get(old_lower, "other")

        if new_location == "other" and old_location:
            # Store original value in location_other
            conn.execute(
                sa.text(
                    """
                    UPDATE projects
                    SET location_new = 'other', location_other = :old_val
                    WHERE location = :old_val
                """
                ),
                {"old_val": old_location},
            )
        else:
            conn.execute(
                sa.text(
                    """
                    UPDATE projects
                    SET location_new = :new_val
                    WHERE location = :old_val
                """
                ),
                {"new_val": new_location, "old_val": old_location},
            )

    # 6. Handle any NULL or empty values
    conn.execute(
        sa.text(
            """
            UPDATE projects
            SET location_new = 'headquarters'
            WHERE location_new IS NULL
        """
        )
    )

    # 7. Drop old column and rename new
    op.drop_column("projects", "location")
    op.alter_column(
        "projects", "location_new", new_column_name="location", nullable=False
    )

    # 8. Add index on location
    op.create_index("ix_projects_location", "projects", ["location"])

    # 9. Recreate search_vector computed column with location_other
    op.execute(
        """
        ALTER TABLE projects ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(location_other, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(pm_notes, '')), 'D')
        ) STORED;
    """
    )

    # 10. Recreate GIN index on search_vector
    op.create_index(
        "ix_projects_search_vector",
        "projects",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    # 1. Drop GIN index on search_vector
    op.drop_index("ix_projects_search_vector", table_name="projects")

    # 2. Add back string location column
    op.add_column(
        "projects",
        sa.Column("location_old", sa.String(255), nullable=True),
    )

    # 3. Migrate data back
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE projects
            SET location_old = CASE
                WHEN location = 'other' THEN COALESCE(location_other, 'Other')
                ELSE location::text
            END
        """
        )
    )

    # 4. Drop enum column, rename old
    op.drop_index("ix_projects_location", table_name="projects")
    op.drop_column("projects", "location")
    op.alter_column(
        "projects", "location_old", new_column_name="location", nullable=False
    )

    # 5. Drop location_other
    op.drop_column("projects", "location_other")

    # 6. Restore original search_vector
    op.execute(
        """
        ALTER TABLE projects DROP COLUMN IF EXISTS search_vector;
    """
    )
    op.execute(
        """
        ALTER TABLE projects ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(location, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(pm_notes, '')), 'D')
        ) STORED;
    """
    )

    # 7. Recreate GIN index on search_vector
    op.create_index(
        "ix_projects_search_vector",
        "projects",
        ["search_vector"],
        postgresql_using="gin",
    )

    # 8. Drop enum type
    projectlocation_enum.drop(op.get_bind(), checkfirst=True)
