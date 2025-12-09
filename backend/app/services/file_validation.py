"""File validation service for verifying file content types via magic numbers."""

import magic

from app.core.logging import get_logger

logger = get_logger(__name__)


# Magic number to MIME type mappings
# Maps claimed MIME types to sets of allowed detected types from libmagic
MAGIC_MIME_MAPPING: dict[str, set[str]] = {
    # PDF
    "application/pdf": {"application/pdf"},
    # Word documents (DOCX files are ZIP archives internally)
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    # Excel documents (XLSX files are ZIP archives internally)
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    },
    # Legacy Excel format (OLE compound document)
    "application/vnd.ms-excel": {
        "application/vnd.ms-excel",
        "application/x-ole-storage",
        "application/CDFV2",
    },
    # Text files (libmagic may detect as various text subtypes)
    "text/plain": {
        "text/plain",
        "text/x-c",
        "text/x-c++",
        "text/x-python",
        "text/x-java",
        "text/x-script.python",
        "application/octet-stream",
    },
    # CSV files (libmagic typically detects as plain text)
    "text/csv": {
        "text/plain",
        "text/csv",
        "application/csv",
        "text/x-csv",
    },
}


class FileValidationService:
    """Service for validating file content against claimed MIME types."""

    def __init__(self) -> None:
        """Initialize the magic library."""
        self._magic = magic.Magic(mime=True)

    def get_actual_mime_type(self, content: bytes) -> str:
        """
        Detect the actual MIME type of file content using magic numbers.

        Args:
            content: File content bytes

        Returns:
            Detected MIME type string
        """
        return self._magic.from_buffer(content)

    def validate_content_type(
        self,
        content: bytes,
        claimed_mime_type: str,
    ) -> tuple[bool, str]:
        """
        Validate that file content matches the claimed MIME type.

        Args:
            content: File content bytes
            claimed_mime_type: The MIME type claimed by the client

        Returns:
            Tuple of (is_valid, detected_mime_type)
        """
        detected_mime = self.get_actual_mime_type(content)

        # Get allowed detected types for the claimed type
        allowed_detected_types = MAGIC_MIME_MAPPING.get(claimed_mime_type, set())

        is_valid = detected_mime in allowed_detected_types

        if not is_valid:
            logger.warning(
                "file_type_mismatch",
                claimed_mime_type=claimed_mime_type,
                detected_mime_type=detected_mime,
            )
        else:
            logger.debug(
                "file_type_validated",
                claimed_mime_type=claimed_mime_type,
                detected_mime_type=detected_mime,
            )

        return is_valid, detected_mime

    def is_safe_file_type(self, content: bytes) -> bool:
        """
        Check if the file content is a safe (non-executable) type.

        Rejects obvious dangerous file types regardless of claimed MIME.

        Args:
            content: File content bytes

        Returns:
            True if file appears safe, False if potentially dangerous
        """
        detected_mime = self.get_actual_mime_type(content)

        # Reject executable and dangerous types
        dangerous_types = {
            "application/x-executable",
            "application/x-msdos-program",
            "application/x-msdownload",
            "application/x-dosexec",
            "application/x-sharedlib",
            "application/x-shellscript",
            "text/x-shellscript",
            "application/x-php",
            "text/x-php",
            "application/javascript",
            "text/javascript",
        }

        if detected_mime in dangerous_types:
            logger.warning(
                "dangerous_file_type_detected",
                detected_mime_type=detected_mime,
            )
            return False

        return True
