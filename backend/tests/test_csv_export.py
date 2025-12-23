"""Tests for CSV export streaming functionality (GitHub Issue #90).

This module tests that the CSV export endpoints use proper streaming
to avoid memory exhaustion when exporting large datasets.
"""

import csv
import inspect
import io
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.projects import _generate_projects_csv_rows, export_projects_csv
from app.api.search import _generate_search_csv_rows, export_search_results_csv
from app.models.project import ProjectLocation, ProjectStatus


class TestProjectsCSVExportStreaming:
    """Tests for projects CSV export streaming."""

    def test_csv_row_generator_is_async_generator(self):
        """The CSV row generator should be an async generator function."""
        assert inspect.isasyncgenfunction(_generate_projects_csv_rows)

    @pytest.mark.asyncio
    async def test_csv_header_row_yielded_first(self):
        """CSV export should yield header row first."""
        # Mock database session and query
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        mock_query = MagicMock()
        mock_query.offset.return_value.limit.return_value = mock_query

        location_labels = {
            ProjectLocation.HEADQUARTERS: "Headquarters",
            ProjectLocation.TEST_HOUSE: "Test House",
            ProjectLocation.REMOTE: "Remote",
            ProjectLocation.CLIENT_SITE: "Client Site",
            ProjectLocation.OTHER: "Other",
        }

        rows = []
        async for row in _generate_projects_csv_rows(
            mock_db, mock_query, location_labels
        ):
            rows.append(row)
            if len(rows) == 1:
                break

        # First row should be header
        reader = csv.reader(io.StringIO(rows[0]))
        header = next(reader)
        assert "Name" in header
        assert "Organization" in header
        assert "Status" in header
        assert "Tags" in header

    def test_csv_row_generator_uses_batching(self):
        """CSV export should use batched fetching, not .all()."""
        source = inspect.getsource(_generate_projects_csv_rows)

        # Should use offset/limit pattern
        assert "offset" in source.lower() or "BATCH_SIZE" in source
        # Should NOT have page_size=10000 or similar large single fetch
        assert "10000" not in source

    def test_projects_export_no_full_buffer_in_endpoint(self):
        """Projects export endpoint should not create full StringIO buffer."""
        source = inspect.getsource(export_projects_csv)

        # Should NOT have output.getvalue() pattern in the endpoint itself
        # (it's OK in the generator for individual rows)
        assert "iter([output.getvalue()])" not in source


class TestSearchCSVExportStreaming:
    """Tests for search CSV export streaming."""

    def test_search_csv_generator_is_async_generator(self):
        """The search CSV row generator should be an async generator function."""
        assert inspect.isasyncgenfunction(_generate_search_csv_rows)

    @pytest.mark.asyncio
    async def test_search_csv_header_row_yielded_first(self):
        """Search CSV export should yield header row first."""
        # Mock search service
        # Returns (projects, total, synonym_metadata)
        mock_service = AsyncMock()
        mock_service.search_projects.return_value = ([], 0, None)

        rows = []
        async for row in _generate_search_csv_rows(
            search_service=mock_service,
            query="test",
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
        ):
            rows.append(row)
            if len(rows) == 1:
                break

        # First row should be header
        reader = csv.reader(io.StringIO(rows[0]))
        header = next(reader)
        assert "Name" in header
        assert "Organization" in header
        assert "Status" in header

    def test_search_csv_uses_pagination(self):
        """Search CSV export should use pagination, not single large fetch."""
        source = inspect.getsource(_generate_search_csv_rows)

        # Should NOT have page_size=10000
        assert "10000" not in source
        # Should use batched pagination
        assert "BATCH_SIZE" in source or "page_size" in source

    def test_search_export_no_full_buffer_in_endpoint(self):
        """Search export endpoint should not create full StringIO buffer."""
        source = inspect.getsource(export_search_results_csv)

        # Should NOT have iter([output.getvalue()]) pattern (fake streaming)
        assert "iter([output.getvalue()])" not in source


class TestCSVExportMemoryEfficiency:
    """Tests verifying memory-efficient export behavior."""

    @pytest.mark.asyncio
    async def test_projects_generator_processes_batches_sequentially(self):
        """Projects generator should process batches one at a time."""
        mock_db = AsyncMock()

        # Create mock projects for two batches
        mock_project = MagicMock()
        mock_project.name = "Test Project"
        mock_project.organization.name = "Test Org"
        mock_project.owner.display_name = "Test User"
        mock_project.status = ProjectStatus.ACTIVE
        mock_project.start_date = None
        mock_project.end_date = None
        mock_project.location = ProjectLocation.HEADQUARTERS
        mock_project.location_other = None
        mock_project.description = "Test description"
        mock_project.project_tags = []
        mock_project.billing_amount = None
        mock_project.invoice_count = None
        mock_project.billing_recipient = None
        mock_project.billing_notes = None
        mock_project.pm_notes = None
        mock_project.monday_url = None
        mock_project.jira_url = None
        mock_project.gitlab_url = None
        mock_project.milestone_version = None
        mock_project.run_number = None
        mock_project.created_at = None
        mock_project.updated_at = None

        # First batch returns 1 project, second batch returns empty (end of data)
        mock_result_1 = MagicMock()
        mock_result_1.scalars.return_value.unique.return_value.all.return_value = [
            mock_project
        ]

        mock_result_2 = MagicMock()
        mock_result_2.scalars.return_value.unique.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_result_1, mock_result_2]

        mock_query = MagicMock()
        mock_query.offset.return_value.limit.return_value = mock_query

        location_labels = {
            ProjectLocation.HEADQUARTERS: "Headquarters",
            ProjectLocation.TEST_HOUSE: "Test House",
            ProjectLocation.REMOTE: "Remote",
            ProjectLocation.CLIENT_SITE: "Client Site",
            ProjectLocation.OTHER: "Other",
        }

        rows = []
        async for row in _generate_projects_csv_rows(
            mock_db, mock_query, location_labels
        ):
            rows.append(row)

        # Should have header + 1 data row
        assert len(rows) == 2

        # Verify the data row contains expected values
        reader = csv.reader(io.StringIO(rows[1]))
        data_row = next(reader)
        assert data_row[0] == "Test Project"
        assert data_row[1] == "Test Org"

    @pytest.mark.asyncio
    async def test_search_generator_processes_pages_sequentially(self):
        """Search generator should process pages one at a time."""
        mock_service = AsyncMock()

        # Create mock project
        mock_project = MagicMock()
        mock_project.name = "Search Result"
        mock_project.organization = MagicMock()
        mock_project.organization.name = "Test Org"
        mock_project.owner = MagicMock()
        mock_project.owner.display_name = "Test User"
        mock_project.status = ProjectStatus.ACTIVE
        mock_project.start_date = None
        mock_project.end_date = None
        mock_project.location = "Headquarters"
        mock_project.description = "Test description"
        mock_project.project_tags = []
        mock_project.milestone_version = None
        mock_project.run_number = None
        mock_project.engagement_period = None
        mock_project.created_at = None
        mock_project.updated_at = None

        # First page returns 1 result with total=1, should stop after
        # Returns (projects, total, synonym_metadata)
        mock_service.search_projects.return_value = ([mock_project], 1, None)

        rows = []
        async for row in _generate_search_csv_rows(
            search_service=mock_service,
            query="test",
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
        ):
            rows.append(row)

        # Should have header + 1 data row
        assert len(rows) == 2

        # Verify the data row contains expected values
        reader = csv.reader(io.StringIO(rows[1]))
        data_row = next(reader)
        assert data_row[0] == "Search Result"

    def test_batch_size_is_reasonable(self):
        """Verify batch sizes are reasonable (not too large)."""
        projects_source = inspect.getsource(_generate_projects_csv_rows)
        search_source = inspect.getsource(_generate_search_csv_rows)

        # Both should use BATCH_SIZE = 100
        assert "BATCH_SIZE = 100" in projects_source
        assert "BATCH_SIZE = 100" in search_source


class TestCSVExportRegressionGuards:
    """Regression tests to prevent reintroduction of memory issues."""

    def test_no_page_size_10000_in_search_export(self):
        """Ensure page_size=10000 is not used in search export."""
        # Check both the endpoint and generator
        endpoint_source = inspect.getsource(export_search_results_csv)
        generator_source = inspect.getsource(_generate_search_csv_rows)

        assert "page_size=10000" not in endpoint_source
        assert "page_size=10000" not in generator_source

    def test_no_full_results_load_in_projects(self):
        """Ensure projects export doesn't load all results at once."""
        endpoint_source = inspect.getsource(export_projects_csv)

        # The endpoint should not have .all() - that's in the generator with batching
        # Check that it doesn't have the old pattern of: result.scalars().unique().all()
        # followed by a for loop over all projects
        assert ".scalars().unique().all()" not in endpoint_source

    def test_streaming_response_uses_generator_not_list(self):
        """Ensure StreamingResponse receives a generator, not a list."""
        projects_source = inspect.getsource(export_projects_csv)
        search_source = inspect.getsource(export_search_results_csv)

        # Should call the generator function, not wrap in iter([...])
        assert "_generate_projects_csv_rows(" in projects_source
        assert "_generate_search_csv_rows(" in search_source

        # Should NOT have the old fake streaming pattern
        assert "iter([" not in projects_source
        assert "iter([" not in search_source
