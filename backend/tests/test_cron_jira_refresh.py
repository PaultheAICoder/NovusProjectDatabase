"""Tests for Jira refresh cron endpoint."""

from unittest.mock import AsyncMock, patch

import pytest


class TestJiraRefreshCronEndpoint:
    """Tests for GET /api/v1/cron/jira-refresh."""

    @pytest.mark.asyncio
    async def test_returns_unauthorized_without_token(self):
        """Should return 401 without valid token."""
        from fastapi import HTTPException

        from app.api.cron import process_jira_refresh_endpoint

        with pytest.raises(HTTPException) as exc_info:
            await process_jira_refresh_endpoint(authorization=None)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_unauthorized_with_invalid_token(self):
        """Should return 401 with invalid token."""
        from fastapi import HTTPException

        from app.api.cron import process_jira_refresh_endpoint

        with patch("app.api.cron.settings") as mock_settings:
            mock_settings.cron_secret = "correct-secret"

            with pytest.raises(HTTPException) as exc_info:
                await process_jira_refresh_endpoint(
                    authorization="Bearer wrong-secret",
                )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_success_with_valid_token(self):
        """Should call refresh_all_jira_statuses with valid token."""
        from app.api.cron import process_jira_refresh_endpoint

        mock_result = {
            "status": "success",
            "total_links": 5,
            "stale_links": 2,
            "refreshed": 2,
            "failed": 0,
            "skipped": 3,
            "errors": [],
            "timestamp": "2025-01-15T10:00:00+00:00",
        }

        with (
            patch("app.api.cron.verify_cron_secret", return_value=True),
            patch(
                "app.api.cron.refresh_all_jira_statuses",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await process_jira_refresh_endpoint(
                authorization="Bearer test-secret",
            )

        assert result.status == "success"
        assert result.total_links == 5
        assert result.stale_links == 2
        assert result.refreshed == 2
        assert result.failed == 0
        assert result.skipped == 3

    @pytest.mark.asyncio
    async def test_returns_skipped_when_not_configured(self):
        """Should return skipped when Jira not configured."""
        from app.api.cron import process_jira_refresh_endpoint

        mock_result = {
            "status": "skipped",
            "total_links": 0,
            "stale_links": 0,
            "refreshed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": ["Jira not configured"],
            "timestamp": "2025-01-15T10:00:00+00:00",
        }

        with (
            patch("app.api.cron.verify_cron_secret", return_value=True),
            patch(
                "app.api.cron.refresh_all_jira_statuses",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            result = await process_jira_refresh_endpoint(
                authorization="Bearer test-secret",
            )

        assert result.status == "skipped"
        assert "Jira not configured" in result.errors

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Should return error result when exception occurs."""
        from app.api.cron import process_jira_refresh_endpoint

        with (
            patch("app.api.cron.verify_cron_secret", return_value=True),
            patch(
                "app.api.cron.refresh_all_jira_statuses",
                new_callable=AsyncMock,
                side_effect=Exception("Database connection failed"),
            ),
        ):
            result = await process_jira_refresh_endpoint(
                authorization="Bearer test-secret",
            )

        assert result.status == "error"
        assert "Database connection failed" in result.errors


class TestRefreshAllJiraStatuses:
    """Tests for refresh_all_jira_statuses function."""

    @pytest.mark.asyncio
    async def test_returns_skipped_when_not_configured(self):
        """Should return skipped when Jira is not configured."""
        from app.services.jira_service import refresh_all_jira_statuses

        with patch("app.services.jira_service.settings") as mock_settings:
            mock_settings.is_jira_configured = False
            mock_settings.jira_base_url = ""

            result = await refresh_all_jira_statuses()

        assert result["status"] == "skipped"
        assert "Jira not configured" in result["errors"]

    def test_refresh_all_jira_statuses_function_exists(self):
        """refresh_all_jira_statuses function should exist and be callable."""
        from app.services.jira_service import refresh_all_jira_statuses

        assert callable(refresh_all_jira_statuses)
