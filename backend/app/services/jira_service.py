"""Jira integration service."""

import base64
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ExternalServiceError
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

if TYPE_CHECKING:
    from app.models.jira_link import ProjectJiraLink

logger = get_logger(__name__)
settings = get_settings()


class JiraAPIError(ExternalServiceError):
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

    def is_cache_stale(self, link: "ProjectJiraLink") -> bool:
        """Check if a link's cache is stale based on TTL.

        Args:
            link: ProjectJiraLink to check

        Returns:
            True if cache is stale or missing, False if fresh
        """
        if link.cached_at is None:
            return True

        age_seconds = (datetime.now(UTC) - link.cached_at).total_seconds()
        return age_seconds > settings.jira_cache_ttl

    async def refresh_jira_link(
        self,
        link: "ProjectJiraLink",
        db: AsyncSession,
    ) -> bool:
        """Refresh cached status for a single Jira link.

        Args:
            link: ProjectJiraLink to refresh
            db: Database session

        Returns:
            True if refresh succeeded, False otherwise
        """
        if not self.is_configured:
            logger.warning("jira_not_configured")
            return False

        try:
            issue = await self.get_issue(link.issue_key)
            if issue:
                link.cached_status = issue.status.name
                link.cached_summary = issue.summary
                link.cached_at = datetime.now(UTC)
                await db.flush()
                logger.info(
                    "jira_link_refreshed",
                    issue_key=link.issue_key,
                    status=issue.status.name,
                )
                return True
            else:
                logger.warning(
                    "jira_issue_not_found_for_link",
                    issue_key=link.issue_key,
                )
                return False
        except JiraAPIError as e:
            logger.error(
                "jira_link_refresh_failed",
                issue_key=link.issue_key,
                error=str(e),
            )
            return False

    async def refresh_project_jira_statuses(
        self,
        project_id: UUID,
        db: AsyncSession,
    ) -> dict:
        """Refresh all Jira link statuses for a project.

        Args:
            project_id: UUID of the project
            db: Database session

        Returns:
            Dict with refresh results
        """
        from app.models.jira_link import ProjectJiraLink

        result = await db.execute(
            select(ProjectJiraLink).where(ProjectJiraLink.project_id == project_id)
        )
        links = result.scalars().all()

        results = {
            "total": len(links),
            "refreshed": 0,
            "failed": 0,
            "errors": [],
        }

        for link in links:
            success = await self.refresh_jira_link(link, db)
            if success:
                results["refreshed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(link.issue_key)

        return results


async def refresh_all_jira_statuses() -> dict:
    """Refresh all stale Jira link statuses.

    This function is designed to be called from a cron endpoint.
    It creates its own database session.

    Returns:
        Dict with processing results
    """
    from app.database import async_session_maker
    from app.models.jira_link import ProjectJiraLink

    logger.info("jira_refresh_started")

    results = {
        "status": "success",
        "total_links": 0,
        "stale_links": 0,
        "refreshed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
        "timestamp": datetime.now(UTC).isoformat(),
    }

    service = JiraService()
    if not service.is_configured:
        results["status"] = "skipped"
        results["errors"].append("Jira not configured")
        logger.info("jira_refresh_skipped_not_configured")
        return results

    try:
        async with async_session_maker() as db:
            # Get all Jira links
            result = await db.execute(select(ProjectJiraLink))
            links = result.scalars().all()
            results["total_links"] = len(links)

            for link in links:
                if service.is_cache_stale(link):
                    results["stale_links"] += 1
                    success = await service.refresh_jira_link(link, db)
                    if success:
                        results["refreshed"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(link.issue_key)
                else:
                    results["skipped"] += 1

            await db.commit()
    except JiraRateLimitError as e:
        results["status"] = "error"
        results["errors"].append(f"Rate limited: {e}")
        logger.error(
            "jira_refresh_rate_limited",
            error=str(e),
            retry_after=e.retry_after_seconds,
            exc_info=True,
        )
    except JiraAPIError as e:
        results["status"] = "error"
        results["errors"].append(str(e))
        logger.error(
            "jira_refresh_api_error",
            error=str(e),
            exc_info=True,
        )
    except Exception as e:
        results["status"] = "error"
        results["errors"].append(str(e))
        logger.exception("jira_refresh_error", error=str(e))
    finally:
        await service.close()

    logger.info(
        "jira_refresh_complete",
        refreshed=results["refreshed"],
        failed=results["failed"],
        skipped=results["skipped"],
    )

    return results
