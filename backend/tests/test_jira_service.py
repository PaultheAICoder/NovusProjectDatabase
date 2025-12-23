"""Tests for Jira integration service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.jira import JiraConnectionStatus
from app.services.jira_service import (
    JiraAPIError,
    JiraAuthenticationError,
    JiraNotFoundError,
    JiraRateLimitError,
    JiraService,
)


class TestJiraServiceConfiguration:
    """Tests for JiraService configuration."""

    @patch("app.services.jira_service.settings")
    def test_is_configured_true(self, mock_settings):
        """Test is_configured returns True when all settings are set."""
        mock_settings.is_jira_configured = True
        mock_settings.jira_base_url = "https://test.atlassian.net"
        service = JiraService()
        assert service.is_configured is True

    @patch("app.services.jira_service.settings")
    def test_is_configured_false(self, mock_settings):
        """Test is_configured returns False when settings are missing."""
        mock_settings.is_jira_configured = False
        service = JiraService()
        assert service.is_configured is False


class TestJiraUrlParsing:
    """Tests for URL parsing."""

    @pytest.fixture
    def service(self):
        """Create JiraService instance."""
        with patch("app.services.jira_service.settings") as mock_settings:
            mock_settings.jira_base_url = "https://test.atlassian.net"
            mock_settings.jira_user_email = "test@example.com"
            mock_settings.jira_api_token = "test-token"
            yield JiraService()

    def test_parse_browse_url(self, service):
        """Test parsing standard browse URL."""
        result = service.parse_jira_url("https://company.atlassian.net/browse/PROJ-123")
        assert result is not None
        assert result.base_url == "https://company.atlassian.net"
        assert result.project_key == "PROJ"
        assert result.issue_key == "PROJ-123"

    def test_parse_browse_url_lowercase(self, service):
        """Test parsing URL with lowercase issue key."""
        result = service.parse_jira_url("https://company.atlassian.net/browse/proj-456")
        assert result is not None
        assert result.project_key == "PROJ"
        assert result.issue_key == "PROJ-456"

    def test_parse_project_url(self, service):
        """Test parsing project URL."""
        result = service.parse_jira_url(
            "https://company.atlassian.net/jira/software/projects/PROJ/boards/1"
        )
        assert result is not None
        assert result.project_key == "PROJ"
        assert result.issue_key is None

    def test_parse_simple_project_url(self, service):
        """Test parsing simple project URL."""
        result = service.parse_jira_url("https://company.atlassian.net/projects/ABC")
        assert result is not None
        assert result.project_key == "ABC"

    def test_parse_invalid_url(self, service):
        """Test parsing invalid URL returns None."""
        result = service.parse_jira_url("https://example.com/not-jira")
        assert result is None

    def test_parse_issue_key_direct(self, service):
        """Test parsing direct issue key."""
        result = service.parse_issue_key("PROJ-123")
        assert result is not None
        assert result == ("PROJ", "PROJ-123")

    def test_parse_issue_key_from_url(self, service):
        """Test parsing issue key from URL."""
        result = service.parse_issue_key("https://company.atlassian.net/browse/ABC-456")
        assert result is not None
        assert result == ("ABC", "ABC-456")

    def test_parse_issue_key_invalid(self, service):
        """Test parsing invalid issue key returns None."""
        result = service.parse_issue_key("not-valid")
        assert result is None

    def test_parse_issue_key_lowercase(self, service):
        """Test parsing lowercase issue key normalizes to uppercase."""
        result = service.parse_issue_key("proj-789")
        assert result is not None
        assert result == ("PROJ", "PROJ-789")

    def test_parse_issue_key_with_whitespace(self, service):
        """Test parsing issue key with leading/trailing whitespace."""
        result = service.parse_issue_key("  PROJ-123  ")
        assert result is not None
        assert result == ("PROJ", "PROJ-123")


class TestJiraServiceAPI:
    """Tests for Jira API operations."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch("app.services.jira_service.settings") as mock:
            mock.is_jira_configured = True
            mock.jira_base_url = "https://test.atlassian.net"
            mock.jira_user_email = "test@example.com"
            mock.jira_api_token = "test-token"
            yield mock

    @pytest.fixture
    def service(self, mock_settings):  # noqa: ARG002
        """Create JiraService instance."""
        return JiraService()

    @pytest.mark.asyncio
    async def test_get_issue_success(self, service):
        """Test fetching issue successfully."""
        mock_response = {
            "id": "10001",
            "key": "PROJ-123",
            "fields": {
                "summary": "Test Issue",
                "status": {
                    "id": "1",
                    "name": "In Progress",
                    "statusCategory": {"key": "indeterminate"},
                },
                "issuetype": {"id": "10001", "name": "Story"},
                "assignee": {
                    "accountId": "abc123",
                    "displayName": "John Doe",
                    "emailAddress": "john@example.com",
                },
                "reporter": None,
                "created": "2025-01-15T10:00:00.000+0000",
                "updated": "2025-01-16T11:00:00.000+0000",
            },
        }

        with patch.object(service, "_request", return_value=mock_response):
            issue = await service.get_issue("PROJ-123")

        assert issue is not None
        assert issue.key == "PROJ-123"
        assert issue.summary == "Test Issue"
        assert issue.status.name == "In Progress"
        assert issue.issue_type.name == "Story"
        assert issue.assignee is not None
        assert issue.assignee.display_name == "John Doe"

    @pytest.mark.asyncio
    async def test_get_issue_not_found(self, service):
        """Test handling issue not found."""
        with patch.object(
            service, "_request", side_effect=JiraNotFoundError("Not found")
        ):
            issue = await service.get_issue("PROJ-999")

        assert issue is None

    @pytest.mark.asyncio
    async def test_get_issue_not_configured(self, mock_settings, service):
        """Test get_issue returns None when not configured."""
        mock_settings.is_jira_configured = False

        issue = await service.get_issue("PROJ-123")
        assert issue is None

    @pytest.mark.asyncio
    async def test_get_issue_invalid_key(self, service):
        """Test get_issue returns None for invalid key."""
        issue = await service.get_issue("not-a-valid-key")
        assert issue is None

    @pytest.mark.asyncio
    async def test_get_issue_from_url(self, service):
        """Test get_issue accepts URL as input."""
        mock_response = {
            "id": "10001",
            "key": "PROJ-123",
            "fields": {
                "summary": "Test Issue",
                "status": {"id": "1", "name": "Open", "statusCategory": {"key": "new"}},
                "issuetype": {"id": "10001", "name": "Bug"},
                "assignee": None,
                "reporter": None,
                "created": None,
                "updated": None,
            },
        }

        with patch.object(service, "_request", return_value=mock_response):
            issue = await service.get_issue(
                "https://test.atlassian.net/browse/PROJ-123"
            )

        assert issue is not None
        assert issue.key == "PROJ-123"

    @pytest.mark.asyncio
    async def test_get_project_success(self, service):
        """Test fetching project successfully."""
        mock_response = {
            "id": "10000",
            "key": "PROJ",
            "name": "Test Project",
        }

        with patch.object(service, "_request", return_value=mock_response):
            project = await service.get_project("PROJ")

        assert project is not None
        assert project.key == "PROJ"
        assert project.name == "Test Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, service):
        """Test handling project not found."""
        with patch.object(
            service, "_request", side_effect=JiraNotFoundError("Not found")
        ):
            project = await service.get_project("NONEXISTENT")

        assert project is None

    @pytest.mark.asyncio
    async def test_get_project_not_configured(self, mock_settings, service):
        """Test get_project returns None when not configured."""
        mock_settings.is_jira_configured = False

        project = await service.get_project("PROJ")
        assert project is None

    @pytest.mark.asyncio
    async def test_validate_connection_success(self, service):
        """Test successful connection validation."""
        with patch.object(service, "_request") as mock_request:
            mock_request.side_effect = [
                {"displayName": "Test User"},  # /myself
                {"serverTitle": "Jira Cloud"},  # /serverInfo
            ]

            status = await service.validate_connection()

        assert status.is_connected is True
        assert status.user_display_name == "Test User"
        assert status.server_info == "Jira Cloud"

    @pytest.mark.asyncio
    async def test_validate_connection_auth_failure(self, service):
        """Test connection validation with auth failure."""
        with patch.object(
            service,
            "_request",
            side_effect=JiraAuthenticationError("Invalid credentials"),
        ):
            status = await service.validate_connection()

        assert status.is_connected is False
        assert "Invalid credentials" in status.error

    @pytest.mark.asyncio
    async def test_validate_connection_not_configured(self, mock_settings):
        """Test connection validation when not configured."""
        mock_settings.is_jira_configured = False
        service = JiraService()

        status = await service.validate_connection()

        assert status.is_connected is False
        assert "not configured" in status.error

    @pytest.mark.asyncio
    async def test_validate_connection_api_error(self, service):
        """Test connection validation with generic API error."""
        with patch.object(
            service,
            "_request",
            side_effect=JiraAPIError("Connection timeout"),
        ):
            status = await service.validate_connection()

        assert status.is_connected is False
        assert "Connection failed" in status.error


class TestJiraServiceHTTPHandling:
    """Tests for HTTP error handling."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch("app.services.jira_service.settings") as mock:
            mock.is_jira_configured = True
            mock.jira_base_url = "https://test.atlassian.net"
            mock.jira_user_email = "test@example.com"
            mock.jira_api_token = "test-token"
            yield mock

    @pytest.fixture
    def service(self, mock_settings):  # noqa: ARG002
        """Create JiraService instance."""
        return JiraService()

    def test_auth_header_generation(self, service):
        """Test Basic Auth header is correctly generated."""
        header = service._get_auth_header()
        # Base64 of "test@example.com:test-token"
        assert header.startswith("Basic ")
        assert len(header) > 10

    @pytest.mark.asyncio
    async def test_client_initialization(self, service):
        """Test HTTP client is properly initialized."""
        # Mock httpx.AsyncClient to avoid actual network calls
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            await service._get_client()

            # Client should be created
            assert mock_client_class.called
            # Headers should include auth
            call_kwargs = mock_client_class.call_args[1]
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["timeout"] == 30.0

    @pytest.mark.asyncio
    async def test_close_client(self, service):
        """Test HTTP client close."""
        mock_client = AsyncMock()
        service._client = mock_client

        await service.close()

        mock_client.aclose.assert_called_once()
        assert service._client is None


class TestJiraExceptions:
    """Tests for Jira exception classes."""

    def test_jira_api_error(self):
        """Test JiraAPIError can be raised with message."""
        error = JiraAPIError("Test error")
        assert str(error) == "Test error"

    def test_jira_authentication_error(self):
        """Test JiraAuthenticationError inherits from JiraAPIError."""
        error = JiraAuthenticationError("Auth failed")
        assert isinstance(error, JiraAPIError)
        assert str(error) == "Auth failed"

    def test_jira_not_found_error(self):
        """Test JiraNotFoundError inherits from JiraAPIError."""
        error = JiraNotFoundError("Not found")
        assert isinstance(error, JiraAPIError)
        assert str(error) == "Not found"

    def test_jira_rate_limit_error(self):
        """Test JiraRateLimitError with retry_after."""
        error = JiraRateLimitError("Rate limit", retry_after_seconds=60)
        assert isinstance(error, JiraAPIError)
        assert error.retry_after_seconds == 60

    def test_jira_rate_limit_error_no_retry(self):
        """Test JiraRateLimitError without retry_after."""
        error = JiraRateLimitError("Rate limit")
        assert error.retry_after_seconds is None


class TestJiraServiceCustomBaseUrl:
    """Tests for JiraService with custom base URL."""

    @patch("app.services.jira_service.settings")
    def test_custom_base_url(self, mock_settings):
        """Test service accepts custom base URL."""
        mock_settings.jira_base_url = "https://default.atlassian.net"
        mock_settings.jira_user_email = "test@example.com"
        mock_settings.jira_api_token = "test-token"

        service = JiraService(base_url="https://custom.atlassian.net")
        assert service._base_url == "https://custom.atlassian.net"

    @patch("app.services.jira_service.settings")
    def test_default_base_url_from_settings(self, mock_settings):
        """Test service uses settings base URL by default."""
        mock_settings.jira_base_url = "https://settings.atlassian.net"
        mock_settings.jira_user_email = "test@example.com"
        mock_settings.jira_api_token = "test-token"

        service = JiraService()
        assert service._base_url == "https://settings.atlassian.net"


class TestJiraConnectionStatus:
    """Tests for JiraConnectionStatus schema."""

    def test_connection_status_connected(self):
        """Test JiraConnectionStatus for connected state."""
        status = JiraConnectionStatus(
            is_connected=True,
            user_display_name="Test User",
            server_info="Jira Cloud",
        )
        assert status.is_connected is True
        assert status.user_display_name == "Test User"
        assert status.server_info == "Jira Cloud"
        assert status.error is None

    def test_connection_status_disconnected(self):
        """Test JiraConnectionStatus for disconnected state."""
        status = JiraConnectionStatus(
            is_connected=False,
            error="Connection refused",
        )
        assert status.is_connected is False
        assert status.error == "Connection refused"
        assert status.user_display_name is None
        assert status.server_info is None


class TestJiraServiceRefresh:
    """Tests for JiraService refresh methods."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch("app.services.jira_service.settings") as mock:
            mock.is_jira_configured = True
            mock.jira_base_url = "https://test.atlassian.net"
            mock.jira_user_email = "test@example.com"
            mock.jira_api_token = "test-token"
            mock.jira_cache_ttl = 3600  # 1 hour
            yield mock

    @pytest.fixture
    def service(self, mock_settings):  # noqa: ARG002
        """Create JiraService instance."""
        return JiraService()

    @pytest.fixture
    def mock_link(self):
        """Create a mock ProjectJiraLink."""
        link = MagicMock()
        link.issue_key = "PROJ-123"
        link.cached_status = None
        link.cached_summary = None
        link.cached_at = None
        return link

    def test_is_cache_stale_no_cached_at(self, service, mock_link):
        """Cache should be stale if cached_at is None."""
        mock_link.cached_at = None
        assert service.is_cache_stale(mock_link) is True

    def test_is_cache_stale_within_ttl(
        self, service, mock_link, mock_settings  # noqa: ARG002
    ):
        """Cache should be fresh if within TTL."""
        mock_link.cached_at = datetime.now(UTC) - timedelta(seconds=1800)  # 30 min ago
        assert service.is_cache_stale(mock_link) is False

    def test_is_cache_stale_beyond_ttl(
        self, service, mock_link, mock_settings  # noqa: ARG002
    ):
        """Cache should be stale if beyond TTL."""
        mock_link.cached_at = datetime.now(UTC) - timedelta(seconds=7200)  # 2 hours ago
        assert service.is_cache_stale(mock_link) is True

    @pytest.mark.asyncio
    async def test_refresh_jira_link_success(self, service, mock_link):
        """refresh_jira_link should update link fields on success."""
        mock_issue = MagicMock()
        mock_issue.status.name = "In Progress"
        mock_issue.summary = "Test Issue Summary"

        mock_db = AsyncMock()

        with patch.object(service, "get_issue", return_value=mock_issue):
            result = await service.refresh_jira_link(mock_link, mock_db)

        assert result is True
        assert mock_link.cached_status == "In Progress"
        assert mock_link.cached_summary == "Test Issue Summary"
        assert mock_link.cached_at is not None
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_jira_link_not_found(self, service, mock_link):
        """refresh_jira_link should return False if issue not found."""
        mock_db = AsyncMock()

        with patch.object(service, "get_issue", return_value=None):
            result = await service.refresh_jira_link(mock_link, mock_db)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_jira_link_api_error(self, service, mock_link):
        """refresh_jira_link should return False on API error."""
        mock_db = AsyncMock()

        with patch.object(
            service, "get_issue", side_effect=JiraAPIError("Connection failed")
        ):
            result = await service.refresh_jira_link(mock_link, mock_db)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_jira_link_not_configured(self, mock_link):
        """refresh_jira_link should return False when not configured."""
        with patch("app.services.jira_service.settings") as mock_settings:
            mock_settings.is_jira_configured = False
            mock_settings.jira_base_url = ""
            service = JiraService()
            mock_db = AsyncMock()

            result = await service.refresh_jira_link(mock_link, mock_db)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_project_jira_statuses_success(self, service):
        """refresh_project_jira_statuses should update all links."""
        import uuid

        project_id = uuid.uuid4()

        mock_link1 = MagicMock()
        mock_link1.issue_key = "PROJ-1"
        mock_link2 = MagicMock()
        mock_link2.issue_key = "PROJ-2"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_link1, mock_link2]
        mock_db.execute.return_value = mock_result

        with patch.object(service, "refresh_jira_link", return_value=True):
            results = await service.refresh_project_jira_statuses(project_id, mock_db)

        assert results["total"] == 2
        assert results["refreshed"] == 2
        assert results["failed"] == 0
        assert results["errors"] == []

    @pytest.mark.asyncio
    async def test_refresh_project_jira_statuses_partial_failure(self, service):
        """refresh_project_jira_statuses should handle partial failures."""
        import uuid

        project_id = uuid.uuid4()

        mock_link1 = MagicMock()
        mock_link1.issue_key = "PROJ-1"
        mock_link2 = MagicMock()
        mock_link2.issue_key = "PROJ-2"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_link1, mock_link2]
        mock_db.execute.return_value = mock_result

        # First succeeds, second fails
        with patch.object(service, "refresh_jira_link", side_effect=[True, False]):
            results = await service.refresh_project_jira_statuses(project_id, mock_db)

        assert results["total"] == 2
        assert results["refreshed"] == 1
        assert results["failed"] == 1
        assert "PROJ-2" in results["errors"]
