"""Field whitelists for safe dynamic attribute access.

These whitelists prevent mass assignment vulnerabilities by explicitly
listing which fields can be set via setattr() in sync and update operations.

Security Note:
    Fields like 'id', 'created_at', 'created_by', '_sa_instance_state', etc.
    are intentionally excluded to prevent unauthorized modification of
    system-managed attributes.
"""

# Contact fields that can be safely set from Monday.com sync or API updates
# Matches fields in ContactUpdate Pydantic schema
CONTACT_SYNC_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "email",
        "phone",
        "role_title",
        "notes",
        "monday_url",
        "sync_enabled",
    }
)

# Organization fields that can be safely set from Monday.com sync or API updates
# Matches fields in OrganizationUpdate Pydantic schema
ORGANIZATION_SYNC_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "aliases",
        "notes",
        "address_street",
        "address_city",
        "address_state",
        "address_zip",
        "address_country",
        "billing_contact_id",
        "inventory_url",
        "sync_enabled",
    }
)

# Project fields that can be safely set from API updates
# Matches fields in ProjectUpdate Pydantic schema (excluding relation fields)
PROJECT_UPDATE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "organization_id",
        "description",
        "status",
        "visibility",
        "start_date",
        "end_date",
        "location",
        "location_other",
        "billing_amount",
        "invoice_count",
        "billing_recipient",
        "billing_notes",
        "pm_notes",
        "monday_url",
        "monday_board_id",
        "jira_url",
        "gitlab_url",
        "milestone_version",
        "run_number",
        "engagement_period",
    }
)

# Valid sort columns for project list endpoint
# Defense-in-depth: validates sort_by parameter even though FastAPI Query enum constrains it
PROJECT_SORT_COLUMNS: frozenset[str] = frozenset(
    {
        "name",
        "start_date",
        "updated_at",
    }
)
