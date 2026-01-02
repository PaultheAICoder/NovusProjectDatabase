"""Test file generators for integration tests.

Generates test content dynamically to avoid storing large files in repository.
"""


def generate_small_content() -> bytes:
    """Generate small test content (~100 bytes)."""
    return b"Test content for small file.\n" * 5


def generate_medium_content() -> bytes:
    """Generate medium test content (~1MB)."""
    return b"x" * (1024 * 1024)


def generate_large_content_10mb() -> bytes:
    """Generate large test content (10MB)."""
    return b"x" * (10 * 1024 * 1024)


def generate_large_content_50mb() -> bytes:
    """Generate very large test content (50MB)."""
    return b"y" * (50 * 1024 * 1024)


def generate_content_with_special_chars() -> bytes:
    """Generate content with special characters for binary testing."""
    return b"Download test content with special chars: \x00\xff\n\t\r\x1b[0m"
