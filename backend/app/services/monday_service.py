"""Monday.com integration service."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.monday_sync import MondaySyncLog, MondaySyncStatus, MondaySyncType
from app.models.organization import Organization

logger = get_logger(__name__)
settings = get_settings()

MONDAY_API_URL = "https://api.monday.com/v2"


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
