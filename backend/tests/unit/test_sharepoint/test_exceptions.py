"""Tests for SharePoint exception classes."""

from app.core.sharepoint.exceptions import (
    SharePointAuthenticationError,
    SharePointError,
    SharePointNotFoundError,
    SharePointPermissionError,
    SharePointRateLimitError,
    SharePointUploadError,
)


class TestSharePointExceptions:
    """Test SharePoint exception hierarchy and attributes."""

    def test_base_exception_is_exception(self):
        """SharePointError inherits from Exception."""
        error = SharePointError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_authentication_error_inherits_from_base(self):
        """SharePointAuthenticationError inherits from SharePointError."""
        error = SharePointAuthenticationError("auth failed")
        assert isinstance(error, SharePointError)
        assert isinstance(error, Exception)

    def test_rate_limit_error_with_retry_after(self):
        """SharePointRateLimitError stores retry_after_seconds."""
        error = SharePointRateLimitError("rate limited", retry_after_seconds=30)
        assert isinstance(error, SharePointError)
        assert error.retry_after_seconds == 30
        assert str(error) == "rate limited"

    def test_rate_limit_error_without_retry_after(self):
        """SharePointRateLimitError works without retry_after_seconds."""
        error = SharePointRateLimitError("rate limited")
        assert error.retry_after_seconds is None

    def test_not_found_error_inherits_from_base(self):
        """SharePointNotFoundError inherits from SharePointError."""
        error = SharePointNotFoundError("file not found")
        assert isinstance(error, SharePointError)

    def test_permission_error_inherits_from_base(self):
        """SharePointPermissionError inherits from SharePointError."""
        error = SharePointPermissionError("access denied")
        assert isinstance(error, SharePointError)

    def test_upload_error_with_details(self):
        """SharePointUploadError stores upload details."""
        error = SharePointUploadError(
            "upload failed",
            filename="test.pdf",
            bytes_uploaded=1024,
        )
        assert isinstance(error, SharePointError)
        assert error.filename == "test.pdf"
        assert error.bytes_uploaded == 1024

    def test_upload_error_without_details(self):
        """SharePointUploadError works without optional details."""
        error = SharePointUploadError("upload failed")
        assert error.filename is None
        assert error.bytes_uploaded is None

    def test_catch_all_sharepoint_errors(self):
        """All SharePoint errors can be caught with base class."""
        errors = [
            SharePointError("base"),
            SharePointAuthenticationError("auth"),
            SharePointRateLimitError("rate"),
            SharePointNotFoundError("not found"),
            SharePointPermissionError("permission"),
            SharePointUploadError("upload"),
        ]
        for error in errors:
            try:
                raise error
            except SharePointError as e:
                assert e is error  # Caught correctly
