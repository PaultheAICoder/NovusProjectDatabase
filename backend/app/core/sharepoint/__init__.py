"""SharePoint integration for file storage.

This package provides SharePoint Online integration via Microsoft Graph API
for storing and retrieving documents as an alternative to local file storage.

Modules:
    - exceptions: SharePoint-specific exception classes
    - auth: MSAL token management (future)
    - client: Graph API client wrapper (future)
    - adapter: StorageBackend implementation (future)
"""

from app.core.sharepoint.exceptions import (
    SharePointAuthenticationError,
    SharePointError,
    SharePointNotFoundError,
    SharePointPermissionError,
    SharePointRateLimitError,
    SharePointUploadError,
)

__all__ = [
    "SharePointError",
    "SharePointAuthenticationError",
    "SharePointRateLimitError",
    "SharePointNotFoundError",
    "SharePointPermissionError",
    "SharePointUploadError",
]
