"""Tests for import row revalidation.

Enhancement for GitHub Issue #76: Revalidate import preview rows after edits.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.import_ import ImportRowValidateRequest
from app.services.import_service import ImportService


class TestValidateEditedRow:
    """Tests for _validate_edited_row method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def import_service(self, mock_db):
        """Create an import service instance."""
        return ImportService(mock_db)

    @pytest.mark.asyncio
    async def test_valid_row_passes(self, import_service, mock_db):
        """Row with all required fields passes validation."""
        # Mock organization exists
        mock_org = MagicMock()
        mock_db.get.return_value = mock_org

        row = ImportRowValidateRequest(
            row_number=1,
            name="Test Project",
            organization_id=uuid4(),
            start_date="2025-01-15",
            location="headquarters",
        )

        result = await import_service._validate_edited_row(row)

        assert result.is_valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_missing_name_fails(self, import_service, mock_db):
        """Empty name returns error."""
        mock_db.get.return_value = MagicMock()

        row = ImportRowValidateRequest(
            row_number=1,
            name="",
            organization_id=uuid4(),
            start_date="2025-01-15",
            location="headquarters",
        )

        result = await import_service._validate_edited_row(row)

        assert result.is_valid is False
        assert "Name is required" in result.errors

    @pytest.mark.asyncio
    async def test_missing_org_fails(self, import_service, mock_db):  # noqa: ARG002
        """Missing organization_id returns error."""
        row = ImportRowValidateRequest(
            row_number=1,
            name="Test Project",
            organization_id=None,
            start_date="2025-01-15",
            location="headquarters",
        )

        result = await import_service._validate_edited_row(row)

        assert result.is_valid is False
        assert "Organization is required" in result.errors

    @pytest.mark.asyncio
    async def test_invalid_org_fails(self, import_service, mock_db):
        """Non-existent organization_id returns error."""
        mock_db.get.return_value = None  # Org not found

        row = ImportRowValidateRequest(
            row_number=1,
            name="Test Project",
            organization_id=uuid4(),
            start_date="2025-01-15",
            location="headquarters",
        )

        result = await import_service._validate_edited_row(row)

        assert result.is_valid is False
        assert "Selected organization not found" in result.errors

    @pytest.mark.asyncio
    async def test_missing_start_date_fails(self, import_service, mock_db):
        """Missing start_date returns error."""
        mock_db.get.return_value = MagicMock()

        row = ImportRowValidateRequest(
            row_number=1,
            name="Test Project",
            organization_id=uuid4(),
            start_date=None,
            location="headquarters",
        )

        result = await import_service._validate_edited_row(row)

        assert result.is_valid is False
        assert "Start date is required" in result.errors

    @pytest.mark.asyncio
    async def test_invalid_start_date_fails(self, import_service, mock_db):
        """Invalid date format returns error."""
        mock_db.get.return_value = MagicMock()

        row = ImportRowValidateRequest(
            row_number=1,
            name="Test Project",
            organization_id=uuid4(),
            start_date="not-a-date",
            location="headquarters",
        )

        result = await import_service._validate_edited_row(row)

        assert result.is_valid is False
        assert any("Invalid start date format" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_invalid_end_date_fails(self, import_service, mock_db):
        """Invalid end_date format returns error."""
        mock_db.get.return_value = MagicMock()

        row = ImportRowValidateRequest(
            row_number=1,
            name="Test Project",
            organization_id=uuid4(),
            start_date="2025-01-15",
            end_date="invalid",
            location="headquarters",
        )

        result = await import_service._validate_edited_row(row)

        assert result.is_valid is False
        assert any("Invalid end date format" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_missing_location_fails(self, import_service, mock_db):
        """Missing location returns error (required for commit)."""
        mock_db.get.return_value = MagicMock()

        row = ImportRowValidateRequest(
            row_number=1,
            name="Test Project",
            organization_id=uuid4(),
            start_date="2025-01-15",
            location=None,
        )

        result = await import_service._validate_edited_row(row)

        assert result.is_valid is False
        assert "Location is required" in result.errors


class TestValidateEditedRows:
    """Tests for validate_edited_rows batch method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def import_service(self, mock_db):
        """Create an import service instance."""
        return ImportService(mock_db)

    @pytest.mark.asyncio
    async def test_multiple_rows_validated(self, import_service, mock_db):
        """Multiple rows validated and results returned."""
        mock_db.get.return_value = MagicMock()

        rows = [
            ImportRowValidateRequest(
                row_number=1,
                name="Project A",
                organization_id=uuid4(),
                start_date="2025-01-15",
                location="headquarters",
            ),
            ImportRowValidateRequest(
                row_number=2,
                name="",  # Invalid
                organization_id=uuid4(),
                start_date="2025-01-15",
                location="headquarters",
            ),
        ]

        results = await import_service.validate_edited_rows(rows)

        assert len(results) == 2
        assert results[0].row_number == 1
        assert results[0].validation.is_valid is True
        assert results[1].row_number == 2
        assert results[1].validation.is_valid is False

    @pytest.mark.asyncio
    async def test_empty_rows_returns_empty(
        self, import_service, mock_db
    ):  # noqa: ARG002
        """Empty rows list returns empty results."""
        results = await import_service.validate_edited_rows([])
        assert len(results) == 0
