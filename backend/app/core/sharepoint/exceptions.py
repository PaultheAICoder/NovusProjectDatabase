"""SharePoint-specific exception classes.

These exceptions map to common Microsoft Graph API error scenarios
for SharePoint file operations.
"""


class SharePointError(Exception):
    """Base exception for SharePoint operations.

    All SharePoint-related errors should inherit from this class
    to allow catching all SharePoint errors with a single except clause.
    """

    pass


class SharePointAuthenticationError(SharePointError):
    """Raised when SharePoint authentication fails.

    This can occur when:
    - Client credentials are invalid
    - Token refresh fails
    - Insufficient permissions for the requested operation
    """

    pass


class SharePointRateLimitError(SharePointError):
    """Raised when Microsoft Graph API rate limit is exceeded.

    Graph API returns HTTP 429 with Retry-After header.
    The retry_after_seconds attribute indicates when to retry.
    """

    def __init__(self, message: str, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class SharePointNotFoundError(SharePointError):
    """Raised when a requested file or folder does not exist in SharePoint.

    This maps to HTTP 404 responses from Graph API.
    """

    pass


class SharePointPermissionError(SharePointError):
    """Raised when the app lacks permission for the requested operation.

    This maps to HTTP 403 responses from Graph API.
    Distinct from AuthenticationError which is about credential validity.
    """

    pass


class SharePointUploadError(SharePointError):
    """Raised when a file upload operation fails.

    This can occur during:
    - Simple upload (files <= 4MB)
    - Chunked upload session (files > 4MB)
    - Upload session creation
    """

    def __init__(
        self,
        message: str,
        filename: str | None = None,
        bytes_uploaded: int | None = None,
    ):
        super().__init__(message)
        self.filename = filename
        self.bytes_uploaded = bytes_uploaded
