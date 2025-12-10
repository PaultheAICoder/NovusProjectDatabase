"""Tests for cron email monitor endpoint."""

from unittest.mock import AsyncMock, patch

import pytest


class TestCronAuthentication:
    """Tests for CRON_SECRET authentication."""

    def test_verify_cron_secret_valid(self):
        """Valid bearer token should pass."""
        from app.api.cron import verify_cron_secret

        with patch("app.api.cron.settings") as mock_settings:
            mock_settings.cron_secret = "test-secret"
            result = verify_cron_secret("Bearer test-secret")

        assert result is True

    def test_verify_cron_secret_invalid(self):
        """Invalid bearer token should fail."""
        from app.api.cron import verify_cron_secret

        with patch("app.api.cron.settings") as mock_settings:
            mock_settings.cron_secret = "test-secret"
            result = verify_cron_secret("Bearer wrong-secret")

        assert result is False

    def test_verify_cron_secret_missing_header(self):
        """Missing authorization should fail."""
        from app.api.cron import verify_cron_secret

        with patch("app.api.cron.settings") as mock_settings:
            mock_settings.cron_secret = "test-secret"
            result = verify_cron_secret(None)

        assert result is False

    def test_verify_cron_secret_not_configured(self):
        """Missing CRON_SECRET config should fail."""
        from app.api.cron import verify_cron_secret

        with patch("app.api.cron.settings") as mock_settings:
            mock_settings.cron_secret = ""
            result = verify_cron_secret("Bearer any-token")

        assert result is False

    def test_verify_cron_secret_wrong_format(self):
        """Non-Bearer format should fail."""
        from app.api.cron import verify_cron_secret

        with patch("app.api.cron.settings") as mock_settings:
            mock_settings.cron_secret = "test-secret"
            result = verify_cron_secret("Basic test-secret")

        assert result is False


class TestExtractSubmitterEmail:
    """Tests for submitter email extraction."""

    def test_extracts_email(self):
        """Email should be extracted from body."""
        from app.api.cron import extract_submitter_email_from_body

        body = "**Submitted by**: John Doe (john@example.com)"
        result = extract_submitter_email_from_body(body)

        assert result == "john@example.com"

    def test_extracts_email_multiline(self):
        """Email should be extracted from multiline body."""
        from app.api.cron import extract_submitter_email_from_body

        body = """## Submitter Information
**Submitted by**: Jane Smith (jane@company.org)
**Project**: Test Project"""
        result = extract_submitter_email_from_body(body)

        assert result == "jane@company.org"

    def test_no_match(self):
        """Missing pattern should return None."""
        from app.api.cron import extract_submitter_email_from_body

        body = "This is just regular text"
        result = extract_submitter_email_from_body(body)

        assert result is None


class TestEmailMonitorEndpoint:
    """Tests for GET /api/v1/cron/email-monitor."""

    @pytest.mark.asyncio
    async def test_returns_unauthorized_without_token(self):
        """Should return 401 without valid token."""
        from fastapi import HTTPException

        from app.api.cron import monitor_emails

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await monitor_emails(
                db=mock_db,
                authorization=None,
            )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_unauthorized_with_invalid_token(self):
        """Should return 401 with invalid token."""
        from fastapi import HTTPException

        from app.api.cron import monitor_emails

        mock_db = AsyncMock()

        with patch("app.api.cron.settings") as mock_settings:
            mock_settings.cron_secret = "correct-secret"

            with pytest.raises(HTTPException) as exc_info:
                await monitor_emails(
                    db=mock_db,
                    authorization="Bearer wrong-secret",
                )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_skipped_when_not_configured(self):
        """Should return skipped when email not configured."""
        from app.api.cron import monitor_emails

        mock_db = AsyncMock()

        with (
            patch("app.api.cron.verify_cron_secret", return_value=True),
            patch("app.api.cron.GraphEmailService") as MockGraphService,
        ):
            mock_service = MockGraphService.return_value
            mock_service.is_configured.return_value = False

            result = await monitor_emails(
                db=mock_db,
                authorization="Bearer test-secret",
            )

        assert result.status == "skipped"
        assert "not configured" in result.skipped_reasons[0].lower()

    @pytest.mark.asyncio
    async def test_returns_error_when_no_github_token(self):
        """Should return error when GitHub token missing."""
        from app.api.cron import monitor_emails

        mock_db = AsyncMock()

        with (
            patch("app.api.cron.verify_cron_secret", return_value=True),
            patch("app.api.cron.GraphEmailService") as MockGraphService,
            patch("app.api.cron.settings") as mock_settings,
        ):
            mock_service = MockGraphService.return_value
            mock_service.is_configured.return_value = True
            mock_settings.github_api_token = ""

            result = await monitor_emails(
                db=mock_db,
                authorization="Bearer test-secret",
            )

        assert result.status == "error"
        assert "GITHUB_API_TOKEN" in result.errors[0]


class TestWebhookSubmitterExtraction:
    """Tests for webhook submitter extraction helper."""

    def test_extracts_submitter_info(self):
        """Should extract name and email from body."""
        from app.api.webhooks import extract_submitter_from_body

        body = "**Submitted by**: John Doe (john@example.com)\nRest of issue..."
        result = extract_submitter_from_body(body)

        assert result is not None
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"

    def test_returns_none_for_no_match(self):
        """Should return None when pattern not found."""
        from app.api.webhooks import extract_submitter_from_body

        body = "This issue has no submitter info"
        result = extract_submitter_from_body(body)

        assert result is None
