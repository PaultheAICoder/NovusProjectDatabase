"""Test fixtures for .doc file testing.

.doc files use the OLE Compound Document format (same as .xls, .ppt).
For testing purposes, we use minimal binary representations.

NOTE: These are minimal fixtures for testing MIME detection and error handling.
They are NOT full valid .doc files with extractable text.

For integration tests with real text extraction, you need:
1. Create real .doc files using Microsoft Word or LibreOffice
2. Store as git LFS objects in backend/tests/fixtures/sample_files/
3. Or use python-pptx/python-docx libraries if they support .doc

Current fixtures test:
- MIME type detection (magic number validation)
- Error handling (corrupted files)
- Document processor routing

Full extraction tests require Tika + real .doc files.
"""

# OLE Compound Document magic signature (8 bytes)
# This is the header that identifies OLE files (.doc, .xls, .ppt, etc.)
OLE_MAGIC_SIGNATURE = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])

# Minimal OLE header - the first 512 bytes of an OLE compound document
# This is enough for libmagic to detect the file as OLE format
# The header contains the magic signature plus structure information
MINIMAL_OLE_HEADER = OLE_MAGIC_SIGNATURE + bytes(
    [
        0x00,
        0x00,  # Minor version
        0x00,
        0x00,  # Major version (3)
        0xFE,
        0xFF,  # Byte order (little endian)
        0x09,
        0x00,  # Sector size power (512 bytes)
        0x06,
        0x00,  # Mini sector size power (64 bytes)
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,  # Reserved
        0x00,
        0x00,
        0x00,
        0x00,  # Total sectors in FAT
        0xFE,
        0xFF,
        0xFF,
        0xFF,  # First directory sector SecID
        0x00,
        0x00,
        0x00,
        0x00,  # Transaction signature
        0x00,
        0x10,
        0x00,
        0x00,  # Mini stream cutoff size (4096)
        0xFE,
        0xFF,
        0xFF,
        0xFF,  # First mini FAT sector SecID
        0x00,
        0x00,
        0x00,
        0x00,  # Total mini FAT sectors
        0xFE,
        0xFF,
        0xFF,
        0xFF,  # First DIFAT sector SecID
        0x00,
        0x00,
        0x00,
        0x00,  # Total DIFAT sectors
    ]
)


def get_minimal_ole_doc() -> bytes:
    """Return minimal OLE document bytes for MIME detection testing.

    This creates a minimal 512-byte OLE header that is sufficient for
    libmagic to identify the file as an OLE compound document. It is NOT
    a valid .doc file that can be opened in Word - use for MIME detection
    and error handling tests only.

    Returns:
        512 bytes representing a minimal OLE header
    """
    # Pad to 512 bytes (minimum OLE sector size)
    header_padded = MINIMAL_OLE_HEADER + b"\x00" * (512 - len(MINIMAL_OLE_HEADER))
    return header_padded


def get_corrupted_doc() -> bytes:
    """Return truncated/corrupted document bytes.

    This returns a partial OLE magic signature - enough to be recognized
    as attempting to be an OLE file but truncated to be invalid.

    Returns:
        6 bytes of partial OLE magic (corrupted)
    """
    return b"\xD0\xCF\x11\xE0\x00\x00"  # Partial magic, invalid


def get_text_file_claiming_doc_mime() -> bytes:
    """Return plain text bytes for MIME mismatch testing.

    Use this to test scenarios where a file claims to be application/msword
    but is actually plain text.

    Returns:
        Plain text bytes
    """
    return b"This is plain text, not a .doc file"


def get_empty_file() -> bytes:
    """Return empty file bytes.

    Use this to test empty file handling.

    Returns:
        Empty bytes
    """
    return b""


def get_random_binary() -> bytes:
    """Return random binary data that is not a valid document.

    Use this to test handling of completely invalid binary data.

    Returns:
        256 bytes of sequential byte values
    """
    return bytes(range(256))


# Mime type constants for testing
DOC_MIME_TYPE = "application/msword"
OLE_STORAGE_MIME_TYPE = "application/x-ole-storage"
CDFV2_MIME_TYPE = "application/CDFV2"
CDFV2_UNKNOWN_MIME_TYPE = "application/CDFV2-unknown"
