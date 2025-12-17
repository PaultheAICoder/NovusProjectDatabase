"""Tests to verify enum consistency between SQLAlchemy models and database.

These tests ensure that:
1. Database enum values match what SQLAlchemy expects
2. Model default values match migration defaults
3. Enum member names (used by SAEnum) are consistent

Background:
SQLAlchemy's SAEnum with native_enum=False stores enum MEMBER NAMES (e.g., 'PENDING'),
not enum VALUES (e.g., 'pending'). This test suite catches mismatches early.
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.contact import Contact
from app.models.monday_sync import RecordSyncStatus, SyncDirection
from app.models.organization import Organization


# Database fixture for integration tests
@pytest_asyncio.fixture
async def db():
    """Create async database session for testing."""
    # Use test database URL
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://npd_test:npd_test_2025@localhost:6712/npd_test",
    )
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


class TestEnumConsistency:
    """Test that database enum values match SQLAlchemy expectations."""

    def test_record_sync_status_enum_names_are_uppercase(self):
        """Verify RecordSyncStatus enum names are uppercase (what SAEnum stores)."""
        for member in RecordSyncStatus:
            assert member.name.isupper(), (
                f"RecordSyncStatus.{member.name} should be uppercase. "
                f"SAEnum stores enum NAMES, not values."
            )

    def test_sync_direction_enum_names_are_uppercase(self):
        """Verify SyncDirection enum names are uppercase (what SAEnum stores)."""
        for member in SyncDirection:
            assert member.name.isupper(), (
                f"SyncDirection.{member.name} should be uppercase. "
                f"SAEnum stores enum NAMES, not values."
            )

    def test_record_sync_status_expected_values(self):
        """Verify RecordSyncStatus has expected members."""
        expected = {"SYNCED", "PENDING", "CONFLICT", "DISABLED"}
        actual = {member.name for member in RecordSyncStatus}
        assert actual == expected, (
            f"RecordSyncStatus members changed. "
            f"Expected: {expected}, Got: {actual}. "
            f"Update migration and fix scripts if intentional."
        )

    def test_sync_direction_expected_values(self):
        """Verify SyncDirection has expected members."""
        expected = {"BIDIRECTIONAL", "NPD_TO_MONDAY", "MONDAY_TO_NPD", "NONE"}
        actual = {member.name for member in SyncDirection}
        assert actual == expected, (
            f"SyncDirection members changed. "
            f"Expected: {expected}, Got: {actual}. "
            f"Update migration and fix scripts if intentional."
        )


class TestModelDefaults:
    """Test that model defaults match expected values."""

    def test_organization_sync_status_default(self):
        """Verify Organization sync_status default is PENDING."""
        mapper = inspect(Organization)
        col = mapper.columns["sync_status"]
        assert col.default.arg == RecordSyncStatus.PENDING, (
            f"Organization.sync_status default should be RecordSyncStatus.PENDING, "
            f"got {col.default.arg}"
        )

    def test_organization_sync_direction_default(self):
        """Verify Organization sync_direction default is BIDIRECTIONAL."""
        mapper = inspect(Organization)
        col = mapper.columns["sync_direction"]
        assert col.default.arg == SyncDirection.BIDIRECTIONAL, (
            f"Organization.sync_direction default should be SyncDirection.BIDIRECTIONAL, "
            f"got {col.default.arg}"
        )

    def test_contact_sync_status_default(self):
        """Verify Contact sync_status default is PENDING."""
        mapper = inspect(Contact)
        col = mapper.columns["sync_status"]
        assert col.default.arg == RecordSyncStatus.PENDING, (
            f"Contact.sync_status default should be RecordSyncStatus.PENDING, "
            f"got {col.default.arg}"
        )

    def test_contact_sync_direction_default(self):
        """Verify Contact sync_direction default is BIDIRECTIONAL."""
        mapper = inspect(Contact)
        col = mapper.columns["sync_direction"]
        assert col.default.arg == SyncDirection.BIDIRECTIONAL, (
            f"Contact.sync_direction default should be SyncDirection.BIDIRECTIONAL, "
            f"got {col.default.arg}"
        )


class TestDatabaseEnumValues:
    """Test that actual database values are valid for SQLAlchemy."""

    @pytest.mark.asyncio
    async def test_organization_sync_status_values_valid(self, db: AsyncSession):
        """Verify all organization sync_status values are valid enum names."""
        valid_values = {member.name for member in RecordSyncStatus}

        result = await db.execute(
            text("SELECT DISTINCT sync_status FROM organizations")
        )
        db_values = {row[0] for row in result.fetchall()}

        invalid = db_values - valid_values
        assert not invalid, (
            f"Invalid sync_status values in organizations table: {invalid}. "
            f"Valid values: {valid_values}. "
            f"Run: ./scripts/fix-sync-enum-case.sh"
        )

    @pytest.mark.asyncio
    async def test_organization_sync_direction_values_valid(self, db: AsyncSession):
        """Verify all organization sync_direction values are valid enum names."""
        valid_values = {member.name for member in SyncDirection}

        result = await db.execute(
            text("SELECT DISTINCT sync_direction FROM organizations")
        )
        db_values = {row[0] for row in result.fetchall()}

        invalid = db_values - valid_values
        assert not invalid, (
            f"Invalid sync_direction values in organizations table: {invalid}. "
            f"Valid values: {valid_values}. "
            f"Run: ./scripts/fix-sync-enum-case.sh"
        )

    @pytest.mark.asyncio
    async def test_contact_sync_status_values_valid(self, db: AsyncSession):
        """Verify all contact sync_status values are valid enum names."""
        valid_values = {member.name for member in RecordSyncStatus}

        result = await db.execute(text("SELECT DISTINCT sync_status FROM contacts"))
        db_values = {row[0] for row in result.fetchall()}

        invalid = db_values - valid_values
        assert not invalid, (
            f"Invalid sync_status values in contacts table: {invalid}. "
            f"Valid values: {valid_values}. "
            f"Run: ./scripts/fix-sync-enum-case.sh"
        )

    @pytest.mark.asyncio
    async def test_contact_sync_direction_values_valid(self, db: AsyncSession):
        """Verify all contact sync_direction values are valid enum names."""
        valid_values = {member.name for member in SyncDirection}

        result = await db.execute(text("SELECT DISTINCT sync_direction FROM contacts"))
        db_values = {row[0] for row in result.fetchall()}

        invalid = db_values - valid_values
        assert not invalid, (
            f"Invalid sync_direction values in contacts table: {invalid}. "
            f"Valid values: {valid_values}. "
            f"Run: ./scripts/fix-sync-enum-case.sh"
        )


class TestEnumRoundTrip:
    """Test that enum values can be saved and loaded correctly."""

    @pytest.mark.asyncio
    async def test_organization_enum_roundtrip(self, db: AsyncSession):
        """Verify Organization enums can be saved and loaded."""
        import uuid

        # Create with explicit enum values using raw SQL to avoid model issues
        org_id = uuid.uuid4()
        await db.execute(
            text(
                """
                INSERT INTO organizations (id, name, sync_status, sync_direction)
                VALUES (:id, :name, :sync_status, :sync_direction)
            """
            ),
            {
                "id": str(org_id),
                "name": f"Test Enum Org {uuid.uuid4().hex[:8]}",
                "sync_status": "SYNCED",
                "sync_direction": "NPD_TO_MONDAY",
            },
        )
        await db.commit()

        # Load using SQLAlchemy ORM
        loaded = await db.get(Organization, org_id)

        assert loaded is not None
        assert loaded.sync_status == RecordSyncStatus.SYNCED, (
            f"Expected SYNCED, got {loaded.sync_status}. "
            f"This indicates a case mismatch between DB and model."
        )
        assert loaded.sync_direction == SyncDirection.NPD_TO_MONDAY, (
            f"Expected NPD_TO_MONDAY, got {loaded.sync_direction}. "
            f"This indicates a case mismatch between DB and model."
        )

        # Cleanup
        await db.execute(
            text("DELETE FROM organizations WHERE id = :id"), {"id": str(org_id)}
        )
        await db.commit()

    @pytest.mark.asyncio
    async def test_contact_enum_roundtrip(self, db: AsyncSession):
        """Verify Contact enums can be saved and loaded."""
        import uuid

        # Get an existing organization or create one
        result = await db.execute(text("SELECT id FROM organizations LIMIT 1"))
        row = result.fetchone()
        if row:
            org_id = row[0]
        else:
            org_id = uuid.uuid4()
            await db.execute(
                text("INSERT INTO organizations (id, name) VALUES (:id, :name)"),
                {"id": str(org_id), "name": f"Test Org {uuid.uuid4().hex[:8]}"},
            )
            await db.commit()

        # Create contact with explicit enum values using raw SQL
        contact_id = uuid.uuid4()
        await db.execute(
            text(
                """
                INSERT INTO contacts (id, name, email, organization_id, sync_status, sync_direction)
                VALUES (:id, :name, :email, :org_id, :sync_status, :sync_direction)
            """
            ),
            {
                "id": str(contact_id),
                "name": f"Test Contact {uuid.uuid4().hex[:8]}",
                "email": f"test-{uuid.uuid4().hex[:8]}@example.com",
                "org_id": str(org_id),
                "sync_status": "CONFLICT",
                "sync_direction": "MONDAY_TO_NPD",
            },
        )
        await db.commit()

        # Load using SQLAlchemy ORM
        loaded = await db.get(Contact, contact_id)

        assert loaded is not None
        assert loaded.sync_status == RecordSyncStatus.CONFLICT, (
            f"Expected CONFLICT, got {loaded.sync_status}. "
            f"This indicates a case mismatch between DB and model."
        )
        assert loaded.sync_direction == SyncDirection.MONDAY_TO_NPD, (
            f"Expected MONDAY_TO_NPD, got {loaded.sync_direction}. "
            f"This indicates a case mismatch between DB and model."
        )

        # Cleanup
        await db.execute(
            text("DELETE FROM contacts WHERE id = :id"), {"id": str(contact_id)}
        )
        await db.commit()
