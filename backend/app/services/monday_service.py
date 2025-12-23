"""Monday.com integration service."""

import asyncio
import json
import random
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.monday_sync import (
    MondaySyncLog,
    MondaySyncStatus,
    MondaySyncType,
    RecordSyncStatus,
    SyncConflict,
    SyncDirection,
)
from app.models.organization import Organization

logger = get_logger(__name__)
settings = get_settings()

MONDAY_API_URL = "https://api.monday.com/v2"


class MondayAPIError(Exception):
    """Base exception for Monday.com API errors."""

    pass


class MondayRateLimitError(MondayAPIError):
    """Raised when Monday.com API rate limit is hit."""

    def __init__(self, message: str, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


# Column ID mappings for contacts board (Monday column ID -> NPD field name)
# Used by inbound webhook sync
CONTACT_COLUMN_MAPPING = {
    "email": "email",
    "phone": "phone",
    "role_title": "role_title",
    "notes": "notes",
}

# Column ID mappings for organizations board (Monday column ID -> NPD field name)
# Used by inbound webhook sync
ORG_COLUMN_MAPPING = {
    "notes": "notes",
    "address": "address",  # Special handling required to parse into components
}


def get_default_contact_field_mapping() -> dict[str, str]:
    """Get default field mapping for contact manual sync (NPD field -> Monday column ID).

    Returns dict mapping NPD field names to Monday column IDs.
    These defaults assume standard Monday column IDs that match the field names.
    Override by configuring column IDs in environment or UI.
    """
    return {
        "email": "email",
        "phone": "phone",
        "role_title": "role_title",
        "notes": "notes",
        "organization_name": "organization",
    }


def get_default_org_field_mapping() -> dict[str, str]:
    """Get default field mapping for organization manual sync (NPD field -> Monday column ID).

    Returns dict mapping NPD field names to Monday column IDs.
    These defaults assume standard Monday column IDs that match the field names.
    Override by configuring column IDs in environment or UI.
    """
    return {
        "notes": "notes",
    }


class MondayColumnParser:
    """Utility class for parsing Monday.com webhook column values back to NPD fields."""

    @staticmethod
    def parse_email(value: dict | None) -> str | None:
        """Parse email column value from webhook.

        Email columns come as {"email": "x@y.com", "text": "x@y.com"}
        """
        if not value:
            return None
        if isinstance(value, dict):
            return value.get("email") or value.get("text")
        return None

    @staticmethod
    def parse_phone(value: dict | None) -> str | None:
        """Parse phone column value from webhook.

        Phone columns come as {"phone": "+12025550169", "countryShortName": "US"}
        """
        if not value:
            return None
        if isinstance(value, dict):
            return value.get("phone")
        return None

    @staticmethod
    def parse_text(value: Any) -> str | None:
        """Parse text column value from webhook.

        Text columns may come as {"text": "value"} or just a string.
        """
        if value is None:
            return None
        if isinstance(value, dict):
            return value.get("value") or value.get("text")
        return str(value)


class MondayColumnFormatter:
    """Utility class for formatting Monday.com column values."""

    @staticmethod
    def format_email(email: str, display_text: str | None = None) -> dict[str, str]:
        """Format email column value.

        Monday.com email columns require both 'email' and 'text' fields.
        """
        return {
            "email": email,
            "text": display_text or email,
        }

    @staticmethod
    def format_phone(phone: str, country_code: str = "US") -> dict[str, str]:
        """Format phone column value.

        Monday.com phone columns require 'phone' and 'countryShortName' (ISO-2).
        """
        return {
            "phone": phone,
            "countryShortName": country_code.upper(),
        }

    @staticmethod
    def format_text(value: str) -> str:
        """Format text column value (simple string)."""
        return value

    @staticmethod
    def format_status(label: str) -> dict[str, str]:
        """Format status column value."""
        return {"label": label}

    @staticmethod
    def format_date(value: datetime | str) -> str:
        """Format date column value (YYYY-MM-DD string)."""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        return value


class MondayService:
    """Service for Monday.com API integration."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        """Check if Monday.com API is configured."""
        return bool(settings.monday_api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=MONDAY_API_URL,
                headers={
                    "Authorization": settings.monday_api_key,
                    "API-Version": settings.monday_api_version,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _execute_query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query against Monday API."""
        client = await self._get_client()

        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await client.post("", json=payload)
        response.raise_for_status()

        data = response.json()
        if "errors" in data:
            raise ValueError(f"Monday API error: {data['errors']}")

        return data.get("data", {})

    async def _execute_with_retry(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> dict[str, Any]:
        """Execute GraphQL query with exponential backoff retry on rate limits.

        Args:
            query: GraphQL query/mutation string
            variables: Query variables
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds (doubles each retry)

        Returns:
            Response data from Monday API

        Raises:
            MondayAPIError: If all retries fail
        """
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                return await self._execute_query(query, variables)
            except ValueError as e:
                error_str = str(e)

                # Check if this is a rate limit error
                if (
                    "rate limit" in error_str.lower()
                    or "complexity" in error_str.lower()
                ):
                    if attempt < max_retries:
                        # Calculate delay with jitter
                        delay = base_delay * (2**attempt) + random.uniform(0, 1)
                        logger.warning(
                            "monday_rate_limit_retry",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay_seconds=delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise MondayRateLimitError(
                            f"Rate limit exceeded after {max_retries} retries"
                        )

                # Non-rate-limit error - don't retry
                last_error = e
                break

        if last_error:
            raise MondayAPIError(f"Monday API error: {last_error}")

        raise MondayAPIError("Unexpected error in retry logic")

    async def get_boards(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get list of accessible boards."""
        query = """
        query ($limit: Int!) {
            boards(limit: $limit) {
                id
                name
                columns {
                    id
                    title
                    type
                }
            }
        }
        """

        data = await self._execute_query(query, {"limit": limit})
        return data.get("boards", [])

    async def search_monday_contacts(
        self,
        board_id: str,
        query: str,
        search_columns: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search for contacts in a Monday.com board by column values.

        Uses items_page_by_column_values GraphQL query to search for items
        where specified columns contain the search query.

        Args:
            board_id: Monday board ID to search
            query: Search term to match
            search_columns: Column IDs to search (defaults to ["name", "email"])
            limit: Maximum number of results (default 10, max 50)

        Returns:
            Dict with 'items', 'cursor', 'has_more' keys

        Raises:
            MondayAPIError: If search fails
            MondayRateLimitError: If rate limit exceeded after retries
        """
        if not search_columns:
            search_columns = ["name", "email"]

        # Clamp limit to reasonable range
        limit = max(1, min(limit, 50))

        # Build columns query parameter
        # Note: items_page_by_column_values searches for exact matches in columns
        # We search each column separately to find partial matches
        columns = [
            {"column_id": col_id, "column_values": [query]} for col_id in search_columns
        ]

        graphql_query = """
        query search_contacts(
            $board_id: ID!,
            $limit: Int!,
            $columns: [ItemsPageByColumnValuesQuery!]!
        ) {
            items_page_by_column_values(
                board_id: $board_id,
                limit: $limit,
                columns: $columns
            ) {
                cursor
                items {
                    id
                    name
                    column_values {
                        id
                        text
                        value
                    }
                }
            }
        }
        """

        variables = {
            "board_id": board_id,
            "limit": limit,
            "columns": columns,
        }

        data = await self._execute_with_retry(graphql_query, variables)

        result = data.get("items_page_by_column_values", {})
        items = result.get("items", [])
        cursor = result.get("cursor")

        logger.info(
            "monday_contact_search_completed",
            board_id=board_id,
            query=query,
            columns=search_columns,
            results_count=len(items),
        )

        return {
            "items": items,
            "cursor": cursor,
            "has_more": cursor is not None,
        }

    def _parse_contact_from_item(
        self,
        item: dict[str, Any],
        board_id: str,
    ) -> dict[str, Any]:
        """Parse a Monday item into contact match structure.

        Args:
            item: Monday item dict with id, name, column_values
            board_id: Board ID for reference

        Returns:
            Dict with contact fields extracted from item
        """
        contact = {
            "monday_id": str(item["id"]),
            "name": item.get("name", ""),
            "board_id": board_id,
            "email": None,
            "phone": None,
            "role_title": None,
            "organization": None,
        }

        # Extract fields from column values
        for col in item.get("column_values", []):
            col_id = col.get("id", "")
            text = col.get("text", "")

            if col_id == "email" and text:
                contact["email"] = text
            elif col_id == "phone" and text:
                contact["phone"] = text
            elif col_id == "role_title" and text:
                contact["role_title"] = text
            elif col_id == "organization" and text:
                contact["organization"] = text

        return contact

    async def get_board_items(
        self, board_id: str, limit: int = 100, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get items from a board with pagination.

        Returns tuple of (items, next_cursor).
        """
        if cursor:
            query = """
            query ($cursor: String!, $limit: Int!) {
                next_items_page(cursor: $cursor, limit: $limit) {
                    cursor
                    items {
                        id
                        name
                        column_values {
                            id
                            text
                            value
                        }
                    }
                }
            }
            """
            data = await self._execute_query(query, {"cursor": cursor, "limit": limit})
            page = data.get("next_items_page", {})
        else:
            query = """
            query ($boardId: [ID!]!, $limit: Int!) {
                boards(ids: $boardId) {
                    items_page(limit: $limit) {
                        cursor
                        items {
                            id
                            name
                            column_values {
                                id
                                text
                                value
                            }
                        }
                    }
                }
            }
            """
            data = await self._execute_query(
                query, {"boardId": [board_id], "limit": limit}
            )
            boards = data.get("boards", [])
            page = boards[0].get("items_page", {}) if boards else {}

        items = page.get("items", [])
        next_cursor = page.get("cursor")

        return items, next_cursor

    async def create_item(
        self,
        board_id: str,
        item_name: str,
        column_values: dict[str, Any] | None = None,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new item in a Monday.com board.

        Args:
            board_id: The board ID to create the item in
            item_name: Name of the new item
            column_values: Dict mapping column IDs to formatted values
            group_id: Optional group ID to place the item in

        Returns:
            Dict with 'id' and 'name' of created item

        Raises:
            MondayAPIError: If creation fails
        """
        # Build column_values JSON string if provided
        column_values_str = json.dumps(column_values) if column_values else None

        mutation = """
        mutation create_item(
            $board_id: ID!,
            $item_name: String!,
            $column_values: JSON,
            $group_id: String
        ) {
            create_item(
                board_id: $board_id,
                item_name: $item_name,
                column_values: $column_values,
                group_id: $group_id
            ) {
                id
                name
            }
        }
        """

        variables: dict[str, Any] = {
            "board_id": board_id,
            "item_name": item_name,
        }

        if column_values_str:
            variables["column_values"] = column_values_str
        if group_id:
            variables["group_id"] = group_id

        data = await self._execute_with_retry(mutation, variables)

        created_item = data.get("create_item", {})

        logger.info(
            "monday_item_created",
            board_id=board_id,
            item_id=created_item.get("id"),
            item_name=item_name,
        )

        return created_item

    async def update_item(
        self,
        board_id: str,
        item_id: str,
        column_values: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing item in Monday.com.

        Args:
            board_id: The board ID containing the item
            item_id: The item ID to update
            column_values: Dict mapping column IDs to formatted values

        Returns:
            Dict with 'id' and 'name' of updated item

        Raises:
            MondayAPIError: If update fails
        """
        column_values_str = json.dumps(column_values)

        mutation = """
        mutation change_multiple_column_values(
            $board_id: ID!,
            $item_id: ID!,
            $column_values: JSON!
        ) {
            change_multiple_column_values(
                board_id: $board_id,
                item_id: $item_id,
                column_values: $column_values
            ) {
                id
                name
            }
        }
        """

        variables = {
            "board_id": board_id,
            "item_id": item_id,
            "column_values": column_values_str,
        }

        data = await self._execute_with_retry(mutation, variables)

        updated_item = data.get("change_multiple_column_values", {})

        logger.info(
            "monday_item_updated",
            board_id=board_id,
            item_id=item_id,
            updated_fields=list(column_values.keys()),
        )

        return updated_item

    async def delete_item(
        self,
        item_id: str,
    ) -> dict[str, Any]:
        """Delete an item from Monday.com.

        Args:
            item_id: The item ID to delete

        Returns:
            Dict with 'id' of deleted item

        Raises:
            MondayAPIError: If deletion fails
        """
        mutation = """
        mutation delete_item($item_id: ID!) {
            delete_item(item_id: $item_id) {
                id
            }
        }
        """

        variables = {"item_id": item_id}

        data = await self._execute_with_retry(mutation, variables)

        deleted_item = data.get("delete_item", {})

        logger.info(
            "monday_item_deleted",
            item_id=item_id,
        )

        return deleted_item

    async def sync_organizations(
        self,
        board_id: str,
        field_mapping: dict[str, str],
        triggered_by: UUID,
    ) -> MondaySyncLog:
        """
        Sync organizations from a Monday board.

        Args:
            board_id: Monday board ID
            field_mapping: Dict mapping Monday column IDs to NPD fields
                Expected NPD fields: 'name', 'aliases', 'notes'
            triggered_by: User ID who triggered the sync

        Returns:
            MondaySyncLog with results
        """
        # Create sync log
        sync_log = MondaySyncLog(
            sync_type=MondaySyncType.ORGANIZATIONS,
            status=MondaySyncStatus.IN_PROGRESS,
            board_id=board_id,
            triggered_by=triggered_by,
            field_mapping=field_mapping,
        )
        self.db.add(sync_log)
        await self.db.flush()

        try:
            items_processed = 0
            items_created = 0
            items_updated = 0
            items_skipped = 0

            cursor = None
            while True:
                items, cursor = await self.get_board_items(board_id, cursor=cursor)

                for item in items:
                    items_processed += 1

                    # Extract name from item
                    name = item.get("name", "").strip()
                    if not name:
                        items_skipped += 1
                        continue

                    # Check for existing org by monday_id or name
                    monday_id = str(item["id"])

                    existing = await self._find_organization(monday_id, name)

                    if existing:
                        # Update existing org
                        existing.monday_id = monday_id
                        existing.monday_last_synced = datetime.now(UTC)
                        # Update other fields based on mapping
                        self._apply_field_mapping(existing, item, field_mapping)
                        items_updated += 1
                    else:
                        # Create new org
                        org = Organization(
                            name=name,
                            monday_id=monday_id,
                            monday_last_synced=datetime.now(UTC),
                        )
                        self._apply_field_mapping(org, item, field_mapping)
                        self.db.add(org)
                        items_created += 1

                if not cursor:
                    break

            # Update sync log
            sync_log.status = MondaySyncStatus.COMPLETED
            sync_log.completed_at = datetime.now(UTC)
            sync_log.items_processed = items_processed
            sync_log.items_created = items_created
            sync_log.items_updated = items_updated
            sync_log.items_skipped = items_skipped

        except Exception as e:
            logger.error("monday_org_sync_failed", error=str(e))
            sync_log.status = MondaySyncStatus.FAILED
            sync_log.completed_at = datetime.now(UTC)
            sync_log.error_message = str(e)
            raise

        return sync_log

    async def sync_contacts(
        self,
        board_id: str,
        field_mapping: dict[str, str],
        triggered_by: UUID,
    ) -> MondaySyncLog:
        """
        Sync contacts from a Monday board.

        Args:
            board_id: Monday board ID
            field_mapping: Dict mapping Monday column IDs to NPD fields
                Expected NPD fields: 'name', 'email', 'organization_name',
                    'role_title', 'phone', 'notes'
            triggered_by: User ID who triggered the sync

        Returns:
            MondaySyncLog with results
        """
        sync_log = MondaySyncLog(
            sync_type=MondaySyncType.CONTACTS,
            status=MondaySyncStatus.IN_PROGRESS,
            board_id=board_id,
            triggered_by=triggered_by,
            field_mapping=field_mapping,
        )
        self.db.add(sync_log)
        await self.db.flush()

        try:
            items_processed = 0
            items_created = 0
            items_updated = 0
            items_skipped = 0

            cursor = None
            while True:
                items, cursor = await self.get_board_items(board_id, cursor=cursor)

                for item in items:
                    items_processed += 1

                    # Extract required fields
                    name = item.get("name", "").strip()
                    email = self._get_column_value(item, field_mapping.get("email", ""))
                    org_name = self._get_column_value(
                        item, field_mapping.get("organization_name", "")
                    )

                    if not name or not email:
                        items_skipped += 1
                        continue

                    # Find or create organization
                    org = await self._find_or_create_organization(org_name)
                    if not org:
                        items_skipped += 1
                        continue

                    monday_id = str(item["id"])

                    # Check for existing contact by email in org
                    existing = await self._find_contact(monday_id, email, org.id)

                    if existing:
                        existing.monday_id = monday_id
                        existing.monday_last_synced = datetime.now(UTC)
                        self._apply_contact_field_mapping(existing, item, field_mapping)
                        items_updated += 1
                    else:
                        contact = Contact(
                            name=name,
                            email=email,
                            organization_id=org.id,
                            monday_id=monday_id,
                            monday_last_synced=datetime.now(UTC),
                        )
                        self._apply_contact_field_mapping(contact, item, field_mapping)
                        self.db.add(contact)
                        items_created += 1

                if not cursor:
                    break

            sync_log.status = MondaySyncStatus.COMPLETED
            sync_log.completed_at = datetime.now(UTC)
            sync_log.items_processed = items_processed
            sync_log.items_created = items_created
            sync_log.items_updated = items_updated
            sync_log.items_skipped = items_skipped

        except Exception as e:
            logger.error("monday_contact_sync_failed", error=str(e))
            sync_log.status = MondaySyncStatus.FAILED
            sync_log.completed_at = datetime.now(UTC)
            sync_log.error_message = str(e)
            raise

        return sync_log

    async def get_sync_status(self) -> dict[str, Any]:
        """Get current sync status and recent logs."""
        # Get last org sync
        last_org = await self.db.scalar(
            select(MondaySyncLog)
            .where(MondaySyncLog.sync_type == MondaySyncType.ORGANIZATIONS)
            .order_by(MondaySyncLog.started_at.desc())
            .limit(1)
        )

        # Get last contact sync
        last_contact = await self.db.scalar(
            select(MondaySyncLog)
            .where(MondaySyncLog.sync_type == MondaySyncType.CONTACTS)
            .order_by(MondaySyncLog.started_at.desc())
            .limit(1)
        )

        # Get recent logs
        recent = await self.db.scalars(
            select(MondaySyncLog).order_by(MondaySyncLog.started_at.desc()).limit(10)
        )

        return {
            "is_configured": self.is_configured,
            "last_org_sync": last_org,
            "last_contact_sync": last_contact,
            "recent_logs": list(recent.all()),
        }

    async def _find_organization(
        self, monday_id: str, name: str
    ) -> Organization | None:
        """Find org by monday_id first, then by name."""
        # First try monday_id
        result = await self.db.execute(
            select(Organization).where(Organization.monday_id == monday_id)
        )
        org = result.scalar_one_or_none()
        if org:
            return org

        # Fall back to name match
        result = await self.db.execute(
            select(Organization).where(func.lower(Organization.name) == name.lower())
        )
        return result.scalar_one_or_none()

    async def _find_or_create_organization(self, name: str) -> Organization | None:
        """Find organization by name or create if doesn't exist."""
        if not name:
            return None

        result = await self.db.execute(
            select(Organization).where(func.lower(Organization.name) == name.lower())
        )
        org = result.scalar_one_or_none()

        if not org:
            org = Organization(name=name)
            self.db.add(org)
            await self.db.flush()

        return org

    async def _find_contact(
        self, monday_id: str, email: str, org_id: UUID
    ) -> Contact | None:
        """Find contact by monday_id first, then by email+org."""
        # First try monday_id
        result = await self.db.execute(
            select(Contact).where(Contact.monday_id == monday_id)
        )
        contact = result.scalar_one_or_none()
        if contact:
            return contact

        # Fall back to email+org match
        result = await self.db.execute(
            select(Contact).where(
                func.lower(Contact.email) == email.lower(),
                Contact.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    def _get_column_value(self, item: dict[str, Any], column_id: str) -> str:
        """Extract text value from a column."""
        if not column_id:
            return ""
        for col in item.get("column_values", []):
            if col["id"] == column_id:
                return col.get("text", "") or ""
        return ""

    def _apply_field_mapping(
        self, org: Organization, item: dict[str, Any], mapping: dict[str, str]
    ) -> None:
        """Apply field mapping to organization."""
        if "notes" in mapping:
            notes = self._get_column_value(item, mapping["notes"])
            if notes:
                org.notes = notes

    def _apply_contact_field_mapping(
        self, contact: Contact, item: dict[str, Any], mapping: dict[str, str]
    ) -> None:
        """Apply field mapping to contact."""
        if "role_title" in mapping:
            role = self._get_column_value(item, mapping["role_title"])
            if role:
                contact.role_title = role

        if "phone" in mapping:
            phone = self._get_column_value(item, mapping["phone"])
            if phone:
                contact.phone = phone

        if "notes" in mapping:
            notes = self._get_column_value(item, mapping["notes"])
            if notes:
                contact.notes = notes

    # --- Inbound Sync Methods (Monday -> NPD) ---

    async def process_monday_create(
        self,
        board_id: str,
        monday_item_id: str,
        item_name: str,
        board_type: str,
    ) -> dict[str, Any]:
        """Process a create_item event from Monday.com.

        Creates a new record in NPD if it doesn't already exist.

        Args:
            board_id: Monday.com board ID
            monday_item_id: Monday.com item (pulse) ID
            item_name: Name of the created item
            board_type: "contacts" or "organizations"

        Returns:
            Dict with action result
        """
        logger.info(
            "process_monday_create_started",
            board_id=board_id,
            monday_item_id=monday_item_id,
            item_name=item_name,
            board_type=board_type,
        )

        if board_type == "contacts":
            # Check if already exists
            existing = await self.db.execute(
                select(Contact).where(Contact.monday_id == monday_item_id)
            )
            if existing.scalar_one_or_none():
                logger.debug(
                    "contact_already_exists_skipping", monday_item_id=monday_item_id
                )
                return {"action": "skipped", "reason": "already_exists"}

            # For contacts, we need email and org - log and skip
            # A subsequent update event will fill in fields
            logger.warning(
                "contact_create_needs_full_item_data",
                monday_item_id=monday_item_id,
                message="Contact creation from webhook requires fetching full item data",
            )
            return {
                "action": "skipped",
                "reason": "contact_requires_email_and_org",
                "message": "Create events need full item fetch - use update events for field sync",
            }

        elif board_type == "organizations":
            # Check if already exists
            existing = await self.db.execute(
                select(Organization).where(Organization.monday_id == monday_item_id)
            )
            if existing.scalar_one_or_none():
                logger.debug(
                    "organization_already_exists_skipping",
                    monday_item_id=monday_item_id,
                )
                return {"action": "skipped", "reason": "already_exists"}

            # Organizations just need a name
            org = Organization(
                name=item_name,
                monday_id=monday_item_id,
                monday_last_synced=datetime.now(UTC),
                sync_status=RecordSyncStatus.SYNCED,
                sync_enabled=True,
                sync_direction=SyncDirection.BIDIRECTIONAL,
            )
            self.db.add(org)
            await self.db.flush()

            logger.info(
                "organization_created_from_monday",
                organization_id=str(org.id),
                monday_item_id=monday_item_id,
                name=item_name,
            )

            return {
                "action": "created",
                "entity_id": str(org.id),
                "entity_type": "organization",
            }

        return {"action": "skipped", "reason": f"unknown_board_type:{board_type}"}

    async def process_monday_update(
        self,
        board_id: str,
        monday_item_id: str,
        column_id: str,
        new_value: dict | None,
        previous_value: dict | None,  # noqa: ARG002
        board_type: str,
    ) -> dict[str, Any]:
        """Process a change_column_value event from Monday.com.

        Updates the corresponding NPD field. Detects conflicts if the NPD
        record was modified more recently than the last sync.

        Args:
            board_id: Monday.com board ID
            monday_item_id: Monday.com item (pulse) ID
            column_id: The column that was changed
            new_value: New value object from webhook
            previous_value: Previous value object from webhook (reserved for conflict UI)
            board_type: "contacts" or "organizations"

        Returns:
            Dict with action result
        """
        logger.info(
            "process_monday_update_started",
            board_id=board_id,
            monday_item_id=monday_item_id,
            column_id=column_id,
            board_type=board_type,
        )

        if board_type == "contacts":
            result = await self.db.execute(
                select(Contact).where(Contact.monday_id == monday_item_id)
            )
            record = result.scalar_one_or_none()
            entity_type = "contact"
            column_mapping = CONTACT_COLUMN_MAPPING
        elif board_type == "organizations":
            result = await self.db.execute(
                select(Organization).where(Organization.monday_id == monday_item_id)
            )
            record = result.scalar_one_or_none()
            entity_type = "organization"
            column_mapping = ORG_COLUMN_MAPPING
        else:
            return {"action": "skipped", "reason": f"unknown_board_type:{board_type}"}

        if not record:
            logger.debug(
                "record_not_found_for_monday_update",
                monday_item_id=monday_item_id,
                board_type=board_type,
            )
            return {"action": "skipped", "reason": "record_not_found"}

        # Check if sync is enabled
        if not record.sync_enabled:
            logger.debug("sync_disabled_for_record", monday_item_id=monday_item_id)
            return {"action": "skipped", "reason": "sync_disabled"}

        # Check sync direction - skip if sync is NPD to Monday only
        if record.sync_direction in (SyncDirection.NPD_TO_MONDAY, SyncDirection.NONE):
            logger.debug(
                "sync_direction_prevents_inbound",
                monday_item_id=monday_item_id,
                sync_direction=record.sync_direction.value,
            )
            return {
                "action": "skipped",
                "reason": f"sync_direction:{record.sync_direction.value}",
            }

        # Conflict detection: if record was modified in NPD after last sync from Monday
        if record.monday_last_synced and record.updated_at > record.monday_last_synced:
            logger.warning(
                "potential_sync_conflict_detected",
                monday_item_id=monday_item_id,
                entity_type=entity_type,
                entity_id=str(record.id),
                npd_updated_at=record.updated_at.isoformat(),
                monday_last_synced=record.monday_last_synced.isoformat(),
            )

            # Get the NPD value for the conflicting field
            npd_field_value = None
            if column_id in column_mapping:
                npd_field = column_mapping[column_id]
                if hasattr(record, npd_field):
                    npd_field_value = getattr(record, npd_field)

            # Check for auto-resolution rule
            from app.services.auto_resolution_service import AutoResolutionService

            auto_resolve_service = AutoResolutionService(self.db)
            can_auto_resolve, rule, resolution_type = (
                await auto_resolve_service.try_auto_resolve(
                    entity_type=entity_type,
                    entity_id=record.id,
                    conflict_fields=[column_id],
                    npd_data={column_id: npd_field_value},
                    monday_data={column_id: new_value},
                )
            )

            if can_auto_resolve and resolution_type and rule:
                # Auto-resolve the conflict
                if resolution_type == "keep_npd":
                    # Keep NPD data, push to Monday (existing behavior in _apply_keep_npd)
                    # For simplicity, we just skip the Monday update and keep NPD value
                    logger.info(
                        "auto_resolved_conflict_keep_npd",
                        entity_type=entity_type,
                        entity_id=str(record.id),
                        rule_id=str(rule.id),
                        field=column_id,
                    )
                    # Don't update NPD, Monday will be updated on next outbound sync
                    return {
                        "action": "auto_resolved",
                        "entity_id": str(record.id),
                        "entity_type": entity_type,
                        "resolution": "keep_npd",
                        "rule_id": str(rule.id),
                    }
                else:  # keep_monday
                    # Apply Monday data to NPD
                    parsed_value = self._parse_webhook_column_value(
                        column_id, new_value
                    )
                    if column_id in column_mapping:
                        npd_field = column_mapping[column_id]
                        if hasattr(record, npd_field):
                            setattr(record, npd_field, parsed_value)

                    record.sync_status = RecordSyncStatus.SYNCED
                    record.monday_last_synced = datetime.now(UTC)
                    await self.db.flush()

                    logger.info(
                        "auto_resolved_conflict_keep_monday",
                        entity_type=entity_type,
                        entity_id=str(record.id),
                        rule_id=str(rule.id),
                        field=column_id,
                    )
                    return {
                        "action": "auto_resolved",
                        "entity_id": str(record.id),
                        "entity_type": entity_type,
                        "resolution": "keep_monday",
                        "rule_id": str(rule.id),
                    }

            # No auto-resolution rule, create conflict record (existing code)
            conflict = SyncConflict(
                entity_type=entity_type,
                entity_id=record.id,
                monday_item_id=monday_item_id,
                npd_data={column_id: npd_field_value},
                monday_data={column_id: new_value},
                conflict_fields=[column_id],
            )
            self.db.add(conflict)

            # Set status to conflict
            record.sync_status = RecordSyncStatus.CONFLICT
            await self.db.flush()

            return {
                "action": "conflict",
                "entity_id": str(record.id),
                "entity_type": entity_type,
                "conflict_id": str(conflict.id),
            }

        # Parse the new value and update the field
        parsed_value = self._parse_webhook_column_value(column_id, new_value)

        # Map column_id to NPD field and update
        if column_id in column_mapping:
            npd_field = column_mapping[column_id]
            if hasattr(record, npd_field):
                setattr(record, npd_field, parsed_value)
            else:
                logger.debug(
                    "npd_field_not_found_on_record",
                    column_id=column_id,
                    npd_field=npd_field,
                    entity_type=entity_type,
                )
                return {"action": "skipped", "reason": f"field_not_found:{npd_field}"}
        else:
            # Column not mapped - could be the name field which uses pulseName
            logger.debug(
                "column_not_mapped",
                column_id=column_id,
                entity_type=entity_type,
            )
            return {"action": "skipped", "reason": f"unmapped_column:{column_id}"}

        # Update sync status and timestamp
        record.sync_status = RecordSyncStatus.SYNCED
        record.monday_last_synced = datetime.now(UTC)
        await self.db.flush()

        logger.info(
            "record_updated_from_monday",
            entity_type=entity_type,
            entity_id=str(record.id),
            column_id=column_id,
        )

        return {
            "action": "updated",
            "entity_id": str(record.id),
            "entity_type": entity_type,
            "field": column_id,
        }

    async def process_monday_delete(
        self,
        board_id: str,
        monday_item_id: str,
        board_type: str,
    ) -> dict[str, Any]:
        """Process an item_deleted event from Monday.com.

        Instead of deleting the NPD record, we clear the monday_id and
        set sync_status to DISABLED. This preserves the NPD data while
        breaking the sync link.

        Args:
            board_id: Monday.com board ID
            monday_item_id: Monday.com item (pulse) ID
            board_type: "contacts" or "organizations"

        Returns:
            Dict with action result
        """
        logger.info(
            "process_monday_delete_started",
            board_id=board_id,
            monday_item_id=monday_item_id,
            board_type=board_type,
        )

        if board_type == "contacts":
            result = await self.db.execute(
                select(Contact).where(Contact.monday_id == monday_item_id)
            )
            record = result.scalar_one_or_none()
            entity_type = "contact"
        elif board_type == "organizations":
            result = await self.db.execute(
                select(Organization).where(Organization.monday_id == monday_item_id)
            )
            record = result.scalar_one_or_none()
            entity_type = "organization"
        else:
            return {"action": "skipped", "reason": f"unknown_board_type:{board_type}"}

        if not record:
            logger.debug(
                "record_not_found_for_monday_delete",
                monday_item_id=monday_item_id,
                board_type=board_type,
            )
            return {"action": "skipped", "reason": "record_not_found"}

        # Clear monday link and disable sync
        entity_id = record.id
        record.monday_id = None
        record.sync_status = RecordSyncStatus.DISABLED
        record.sync_enabled = False
        await self.db.flush()

        logger.info(
            "record_unlinked_from_monday",
            entity_type=entity_type,
            entity_id=str(entity_id),
            monday_item_id=monday_item_id,
        )

        return {
            "action": "unlinked",
            "entity_id": str(entity_id),
            "entity_type": entity_type,
            "message": "Monday item deleted - NPD record preserved with sync disabled",
        }

    def _parse_webhook_column_value(self, column_id: str, value: dict | None) -> Any:
        """Parse a webhook column value based on column type."""
        if value is None:
            return None

        # Handle different column types
        if column_id == "email":
            return MondayColumnParser.parse_email(value)
        elif column_id == "phone":
            return MondayColumnParser.parse_phone(value)
        else:
            return MondayColumnParser.parse_text(value)
