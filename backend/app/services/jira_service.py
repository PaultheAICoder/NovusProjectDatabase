"""Jira integration service."""

import base64
import re
from datetime import datetime
from typing import Any

import httpx

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.jira import (
    JiraConnectionStatus,
    JiraIssue,
    JiraIssueType,
    JiraParsedUrl,
    JiraProject,
    JiraStatus,
    JiraUser,
)

logger = get_logger(__name__)
settings = get_settings()


class JiraAPIError(Exception):
    """Base exception for Jira API errors."""

    pass


class JiraAuthenticationError(JiraAPIError):
    """Raised when authentication fails."""

    pass


class JiraNotFoundError(JiraAPIError):
    """Raised when resource is not found."""

    pass


class JiraRateLimitError(JiraAPIError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class JiraService:
    """Service for Jira REST API integration."""

    # URL patterns for parsing Jira URLs
    # Matches: https://company.atlassian.net/browse/PROJ-123
    ISSUE_URL_PATTERN = re.compile(
        r"^(https?://[^/]+)/browse/([A-Z][A-Z0-9]*-\d+)$",
        re.IGNORECASE,
    )
    # Matches: https://company.atlassian.net/jira/software/projects/PROJ/...
    PROJECT_URL_PATTERN = re.compile(
        r"^(https?://[^/]+)(?:/jira)?(?:/software)?/projects?/([A-Z][A-Z0-9]*)",
        re.IGNORECASE,
    )
    # Matches issue key directly: PROJ-123
    ISSUE_KEY_PATTERN = re.compile(r"^([A-Z][A-Z0-9]*)-(\d+)$", re.IGNORECASE)

    def __init__(self, base_url: str | None = None):
        """Initialize Jira service.

        Args:
            base_url: Override base URL (defaults to settings.jira_base_url)
        """
        self._base_url = base_url or settings.jira_base_url
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        """Check if Jira API is configured."""
        return settings.is_jira_configured

    def _get_auth_header(self) -> str:
        """Generate Basic Auth header value."""
        credentials = f"{settings.jira_user_email}:{settings.jira_api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url.rstrip("/"),
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an API request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /rest/api/3/issue/PROJ-123)
            **kwargs: Additional arguments for httpx request

        Returns:
            JSON response as dict

        Raises:
            JiraAuthenticationError: If authentication fails (401)
            JiraNotFoundError: If resource not found (404)
            JiraRateLimitError: If rate limited (429)
            JiraAPIError: For other API errors
        """
        client = await self._get_client()

        try:
            response = await client.request(method, path, **kwargs)

            if response.status_code == 401:
                raise JiraAuthenticationError("Invalid Jira credentials")

            if response.status_code == 403:
                raise JiraAuthenticationError(
                    "Access denied - check API token permissions"
                )

            if response.status_code == 404:
                raise JiraNotFoundError(f"Resource not found: {path}")

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise JiraRateLimitError(
                    "Rate limit exceeded",
                    retry_after_seconds=int(retry_after) if retry_after else None,
                )

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                "jira_api_error",
                status_code=e.response.status_code,
                path=path,
                error=str(e),
            )
            raise JiraAPIError(f"Jira API error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("jira_request_error", path=path, error=str(e))
            raise JiraAPIError(f"Failed to connect to Jira: {e}") from e

    def parse_jira_url(self, url: str) -> JiraParsedUrl | None:
        """Parse a Jira URL to extract project and issue keys.

        Supports various URL formats:
        - https://company.atlassian.net/browse/PROJ-123
        - https://company.atlassian.net/jira/software/projects/PROJ/boards/1
        - https://company.atlassian.net/projects/PROJ

        Args:
            url: Jira URL to parse

        Returns:
            JiraParsedUrl with extracted components, or None if URL not recognized
        """
        url = url.strip()

        # Try issue URL pattern first (most specific)
        match = self.ISSUE_URL_PATTERN.match(url)
        if match:
            base_url, issue_key = match.groups()
            project_key = issue_key.split("-")[0].upper()
            return JiraParsedUrl(
                base_url=base_url,
                project_key=project_key,
                issue_key=issue_key.upper(),
            )

        # Try project URL pattern
        match = self.PROJECT_URL_PATTERN.match(url)
        if match:
            base_url, project_key = match.groups()
            return JiraParsedUrl(
                base_url=base_url,
                project_key=project_key.upper(),
                issue_key=None,
            )

        logger.debug("jira_url_not_recognized", url=url)
        return None

    def parse_issue_key(self, key_or_url: str) -> tuple[str, str] | None:
        """Extract project key and issue number from key or URL.

        Args:
            key_or_url: Issue key (PROJ-123) or full URL

        Returns:
            Tuple of (project_key, issue_key) or None if not valid
        """
        key_or_url = key_or_url.strip()

        # Check if it's a direct issue key
        match = self.ISSUE_KEY_PATTERN.match(key_or_url)
        if match:
            project_key, _ = match.groups()
            return (project_key.upper(), key_or_url.upper())

        # Try parsing as URL
        parsed = self.parse_jira_url(key_or_url)
        if parsed and parsed.issue_key:
            return (parsed.project_key, parsed.issue_key)

        return None

    async def get_issue(self, issue_key: str) -> JiraIssue | None:
        """Fetch issue details from Jira.

        Args:
            issue_key: Issue key (e.g., PROJ-123) or full URL

        Returns:
            JiraIssue with details, or None if not found
        """
        if not self.is_configured:
            logger.warning("jira_not_configured")
            return None

        # Parse if URL was provided
        parsed = self.parse_issue_key(issue_key)
        if not parsed:
            logger.warning("jira_invalid_issue_key", key=issue_key)
            return None

        _, key = parsed

        try:
            data = await self._request(
                "GET",
                f"/rest/api/3/issue/{key}",
                params={
                    "fields": "summary,status,issuetype,assignee,reporter,created,updated",
                },
            )

            fields = data.get("fields", {})

            # Parse status
            status_data = fields.get("status", {})
            status = JiraStatus(
                id=status_data.get("id", ""),
                name=status_data.get("name", "Unknown"),
                category_key=status_data.get("statusCategory", {}).get("key"),
            )

            # Parse issue type
            type_data = fields.get("issuetype", {})
            issue_type = JiraIssueType(
                id=type_data.get("id", ""),
                name=type_data.get("name", "Unknown"),
            )

            # Parse assignee
            assignee = None
            if assignee_data := fields.get("assignee"):
                assignee = JiraUser(
                    account_id=assignee_data.get("accountId"),
                    display_name=assignee_data.get("displayName"),
                    email_address=assignee_data.get("emailAddress"),
                )

            # Parse reporter
            reporter = None
            if reporter_data := fields.get("reporter"):
                reporter = JiraUser(
                    account_id=reporter_data.get("accountId"),
                    display_name=reporter_data.get("displayName"),
                    email_address=reporter_data.get("emailAddress"),
                )

            # Parse timestamps
            created = None
            if created_str := fields.get("created"):
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))

            updated = None
            if updated_str := fields.get("updated"):
                updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))

            return JiraIssue(
                id=data.get("id", ""),
                key=data.get("key", key),
                summary=fields.get("summary", ""),
                status=status,
                issue_type=issue_type,
                assignee=assignee,
                reporter=reporter,
                created=created,
                updated=updated,
                url=f"{self._base_url}/browse/{key}",
            )

        except JiraNotFoundError:
            logger.info("jira_issue_not_found", key=key)
            return None
        except JiraAPIError as e:
            logger.error("jira_get_issue_failed", key=key, error=str(e))
            raise

    async def get_project(self, project_key: str) -> JiraProject | None:
        """Fetch project details from Jira.

        Args:
            project_key: Project key (e.g., PROJ)

        Returns:
            JiraProject with details, or None if not found
        """
        if not self.is_configured:
            logger.warning("jira_not_configured")
            return None

        # Clean the project key
        project_key = project_key.strip().upper()

        try:
            data = await self._request(
                "GET",
                f"/rest/api/3/project/{project_key}",
            )

            return JiraProject(
                id=data.get("id", ""),
                key=data.get("key", project_key),
                name=data.get("name", ""),
            )

        except JiraNotFoundError:
            logger.info("jira_project_not_found", key=project_key)
            return None
        except JiraAPIError as e:
            logger.error("jira_get_project_failed", key=project_key, error=str(e))
            raise

    async def validate_connection(self) -> JiraConnectionStatus:
        """Test API connection and authentication.

        Returns:
            JiraConnectionStatus with connection result
        """
        if not self.is_configured:
            return JiraConnectionStatus(
                is_connected=False,
                error="Jira is not configured. Set JIRA_BASE_URL, JIRA_USER_EMAIL, and JIRA_API_TOKEN.",
            )

        try:
            # Get current user to validate credentials
            user_data = await self._request("GET", "/rest/api/3/myself")

            # Get server info
            server_info = await self._request("GET", "/rest/api/3/serverInfo")

            return JiraConnectionStatus(
                is_connected=True,
                user_display_name=user_data.get("displayName"),
                server_info=server_info.get("serverTitle"),
            )

        except JiraAuthenticationError as e:
            return JiraConnectionStatus(
                is_connected=False,
                error=str(e),
            )
        except JiraAPIError as e:
            return JiraConnectionStatus(
                is_connected=False,
                error=f"Connection failed: {e}",
            )
