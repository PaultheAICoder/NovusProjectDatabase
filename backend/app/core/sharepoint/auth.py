"""MSAL token management for SharePoint/Graph API authentication.

Provides token acquisition with automatic caching and refresh for:
- Delegated (OBO) flow: User-initiated file operations
- App-only flow: Background jobs (migration, document processing)

MSAL handles token caching automatically via its TokenCache.
Tokens are refreshed before expiry when using acquire_token_silent.
"""

from typing import Any

import msal

from app.config import get_settings
from app.core.logging import get_logger
from app.core.sharepoint.exceptions import SharePointAuthenticationError

logger = get_logger(__name__)

# Graph API scopes for SharePoint file operations
GRAPH_DEFAULT_SCOPE = ["https://graph.microsoft.com/.default"]
GRAPH_FILES_SCOPE = ["https://graph.microsoft.com/Files.ReadWrite.All"]


class SharePointAuthService:
    """MSAL-based authentication service for SharePoint/Graph API.

    Manages token acquisition and caching for both delegated and
    app-only authentication flows.

    Attributes:
        _msal_app: MSAL ConfidentialClientApplication instance
        _settings: Application settings
    """

    def __init__(self) -> None:
        """Initialize MSAL client with SharePoint configuration.

        The MSAL ConfidentialClientApplication is created lazily when
        the service is instantiated. Token caching is handled by MSAL's
        internal TokenCache which persists tokens in memory.
        """
        self._settings = get_settings()
        self._msal_app: msal.ConfidentialClientApplication | None = None

        if self.is_configured:
            self._msal_app = self._create_msal_app()
            logger.info(
                "sharepoint_auth_initialized",
                tenant_id=(
                    self._settings.sharepoint_tenant_id[:8] + "..."
                    if self._settings.sharepoint_tenant_id
                    else "not_set"
                ),
            )
        else:
            logger.warning(
                "sharepoint_auth_not_configured",
                reason="missing_required_settings",
            )

    def _create_msal_app(self) -> msal.ConfidentialClientApplication:
        """Create and configure MSAL ConfidentialClientApplication.

        Uses the SharePoint-specific client credentials if set,
        otherwise falls back to the Azure AD credentials.

        Returns:
            Configured MSAL ConfidentialClientApplication
        """
        # Use SharePoint-specific credentials or fall back to Azure AD credentials
        client_id = (
            self._settings.sharepoint_client_id or self._settings.azure_ad_client_id
        )
        client_secret = (
            self._settings.sharepoint_client_secret
            or self._settings.azure_ad_client_secret
        )
        tenant_id = (
            self._settings.sharepoint_tenant_id or self._settings.azure_ad_tenant_id
        )

        authority = f"https://login.microsoftonline.com/{tenant_id}"

        logger.debug(
            "sharepoint_msal_app_creating",
            authority=authority,
            client_id=client_id[:8] + "..." if client_id else "not_set",
        )

        return msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=authority,
        )

    async def get_app_token(self) -> str:
        """Acquire access token using client credentials (app-only flow).

        Used for background operations without user context.
        First attempts to retrieve a cached token, then falls back
        to acquiring a new token from Azure AD.

        Returns:
            Access token string

        Raises:
            SharePointAuthenticationError: If token acquisition fails or
                SharePoint is not configured
        """
        if not self.is_configured or self._msal_app is None:
            logger.error(
                "sharepoint_app_token_failed",
                reason="not_configured",
            )
            raise SharePointAuthenticationError(
                "SharePoint authentication is not configured"
            )

        logger.debug("sharepoint_app_token_acquiring")

        # Try to get cached token first
        result = self._msal_app.acquire_token_silent(
            scopes=GRAPH_DEFAULT_SCOPE,
            account=None,
        )

        if result and "access_token" in result:
            logger.debug(
                "sharepoint_app_token_cached",
                expires_in=result.get("expires_in"),
            )
            return self._handle_auth_result(result, "app_only")

        # No cached token, acquire new one
        logger.debug("sharepoint_app_token_acquiring_new")
        result = self._msal_app.acquire_token_for_client(
            scopes=GRAPH_DEFAULT_SCOPE,
        )

        return self._handle_auth_result(result, "app_only")

    async def get_delegated_token(self, user_assertion: str) -> str:
        """Acquire access token using on-behalf-of flow.

        Used for operations in user context. The user_assertion is the
        access token from the user's Azure AD session.

        Args:
            user_assertion: User's access token from Azure AD

        Returns:
            Access token string with delegated permissions

        Raises:
            SharePointAuthenticationError: If token acquisition fails or
                SharePoint is not configured
        """
        if not self.is_configured or self._msal_app is None:
            logger.error(
                "sharepoint_delegated_token_failed",
                reason="not_configured",
            )
            raise SharePointAuthenticationError(
                "SharePoint authentication is not configured"
            )

        if not user_assertion:
            logger.error(
                "sharepoint_delegated_token_failed",
                reason="missing_user_assertion",
            )
            raise SharePointAuthenticationError(
                "User assertion token is required for delegated authentication"
            )

        logger.debug("sharepoint_delegated_token_acquiring")

        # Acquire token using on-behalf-of flow
        result = self._msal_app.acquire_token_on_behalf_of(
            user_assertion=user_assertion,
            scopes=GRAPH_FILES_SCOPE,
        )

        return self._handle_auth_result(result, "delegated")

    def _handle_auth_result(
        self,
        result: dict[str, Any] | None,
        flow_type: str,
    ) -> str:
        """Process MSAL authentication result.

        Args:
            result: MSAL result dictionary containing access_token or error
            flow_type: "app_only" or "delegated" for logging

        Returns:
            Access token string

        Raises:
            SharePointAuthenticationError: If result is None or contains error
        """
        if result is None:
            logger.error(
                f"sharepoint_{flow_type}_token_failed",
                reason="null_result",
            )
            raise SharePointAuthenticationError(
                f"Failed to acquire {flow_type} token: no result from MSAL"
            )

        if "error" in result:
            error_code = result.get("error", "unknown")
            error_description = result.get("error_description", "No description")

            logger.error(
                f"sharepoint_{flow_type}_token_failed",
                error_code=error_code,
                error_description=error_description[:100],
            )
            raise SharePointAuthenticationError(
                f"Failed to acquire {flow_type} token: {error_code} - {error_description}"
            )

        access_token = result.get("access_token")
        if not access_token:
            logger.error(
                f"sharepoint_{flow_type}_token_failed",
                reason="missing_access_token",
            )
            raise SharePointAuthenticationError(
                f"Failed to acquire {flow_type} token: access_token not in response"
            )

        logger.info(
            f"sharepoint_{flow_type}_token_acquired",
            expires_in=result.get("expires_in"),
            token_type=result.get("token_type"),
        )

        return access_token

    @property
    def is_configured(self) -> bool:
        """Check if SharePoint authentication is properly configured.

        Returns:
            True if all required settings are present, False otherwise
        """
        return self._settings.is_sharepoint_configured


# Module-level singleton for efficiency
_auth_service: SharePointAuthService | None = None


def get_sharepoint_auth() -> SharePointAuthService:
    """Get the SharePoint authentication service singleton.

    Returns:
        SharePointAuthService instance
    """
    global _auth_service
    if _auth_service is None:
        _auth_service = SharePointAuthService()
    return _auth_service


def reset_sharepoint_auth() -> None:
    """Reset the SharePoint authentication service singleton.

    Used primarily for testing to ensure clean state between tests.
    """
    global _auth_service
    _auth_service = None
