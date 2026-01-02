"""SharePoint integration for file storage.

This package provides SharePoint Online integration via Microsoft Graph API
for storing and retrieving documents as an alternative to local file storage.

Modules:
    - exceptions: SharePoint-specific exception classes
    - auth: MSAL token management for Azure AD authentication
    - client: Graph API client wrapper (future)
    - adapter: StorageBackend implementation (future)
"""

from app.core.sharepoint.auth import (
    GRAPH_DEFAULT_SCOPE,
    GRAPH_FILES_SCOPE,
    SharePointAuthService,
    get_sharepoint_auth,
    reset_sharepoint_auth,
)
from app.core.sharepoint.exceptions import (
    SharePointAuthenticationError,
    SharePointError,
    SharePointNotFoundError,
    SharePointPermissionError,
    SharePointRateLimitError,
    SharePointUploadError,
)

__all__ = [
    # Exceptions
    "SharePointError",
    "SharePointAuthenticationError",
    "SharePointRateLimitError",
    "SharePointNotFoundError",
    "SharePointPermissionError",
    "SharePointUploadError",
    # Auth
    "SharePointAuthService",
    "get_sharepoint_auth",
    "reset_sharepoint_auth",
    "GRAPH_DEFAULT_SCOPE",
    "GRAPH_FILES_SCOPE",
]
