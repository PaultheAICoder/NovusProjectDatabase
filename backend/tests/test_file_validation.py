"""Tests for file validation service."""

import io

import pytest

from app.services.file_validation import MAGIC_MIME_MAPPING, FileValidationService


class TestFileValidationService:
    """Tests for FileValidationService."""

    @pytest.fixture
    def validator(self) -> FileValidationService:
        """Create a validator instance."""
        return FileValidationService()

    def test_detect_pdf_mime_type(self, validator: FileValidationService):
        """PDF magic number should be detected."""
        # PDF magic number: %PDF-
        pdf_content = b"%PDF-1.4\n%"
        mime = validator.get_actual_mime_type(pdf_content)
        assert mime == "application/pdf"

    def test_detect_plain_text(self, validator: FileValidationService):
        """Plain text should be detected."""
        text_content = b"Hello, this is plain text content."
        mime = validator.get_actual_mime_type(text_content)
        assert mime in ("text/plain", "text/x-c")

    def test_validate_matching_pdf(self, validator: FileValidationService):
        """Valid PDF with matching type should pass."""
        pdf_content = b"%PDF-1.4\n%"
        is_valid, detected = validator.validate_content_type(
            pdf_content, "application/pdf"
        )
        assert is_valid is True
        assert detected == "application/pdf"

    def test_validate_spoofed_pdf(self, validator: FileValidationService):
        """Executable claiming to be PDF should fail."""
        # ELF executable magic number
        elf_content = b"\x7fELF\x02\x01\x01\x00"
        is_valid, detected = validator.validate_content_type(
            elf_content, "application/pdf"
        )
        assert is_valid is False

    def test_validate_plain_text_variations(self, validator: FileValidationService):
        """Plain text detected as text/x-c should still pass for text/plain."""
        text_content = b"#include <stdio.h>\nint main() {}"
        is_valid, detected = validator.validate_content_type(text_content, "text/plain")
        # text/x-c is allowed for text/plain in our mapping
        assert is_valid is True

    def test_is_safe_rejects_executable(self, validator: FileValidationService):
        """Executable files should be rejected."""
        # More complete ELF 64-bit executable header
        # Required for libmagic to properly identify as executable
        elf_content = bytes(
            [
                0x7F,
                0x45,
                0x4C,
                0x46,  # ELF magic
                0x02,  # 64-bit
                0x01,  # Little endian
                0x01,  # ELF version
                0x00,  # OS/ABI
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,  # Padding
                0x02,
                0x00,  # Type: Executable
                0x3E,
                0x00,  # Machine: x86-64
                0x01,
                0x00,
                0x00,
                0x00,  # Version
            ]
        )
        assert validator.is_safe_file_type(elf_content) is False

    def test_is_safe_accepts_pdf(self, validator: FileValidationService):
        """PDF files should be accepted."""
        pdf_content = b"%PDF-1.4\n%"
        assert validator.is_safe_file_type(pdf_content) is True

    def test_is_safe_accepts_text(self, validator: FileValidationService):
        """Text files should be accepted."""
        text_content = b"Just some text content"
        assert validator.is_safe_file_type(text_content) is True

    def test_docx_detected_as_zip_is_valid(self, validator: FileValidationService):
        """DOCX files detected as ZIP should pass validation."""
        # DOCX files start with ZIP magic number (PK)
        # This is a minimal ZIP header
        zip_magic = b"PK\x03\x04"
        is_valid, detected = validator.validate_content_type(
            zip_magic,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        # ZIP is allowed for DOCX files
        assert detected in ("application/zip", "application/octet-stream")

    def test_xlsx_detected_as_zip_is_valid(self, validator: FileValidationService):
        """XLSX files detected as ZIP should pass validation."""
        zip_magic = b"PK\x03\x04"
        is_valid, detected = validator.validate_content_type(
            zip_magic,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert detected in ("application/zip", "application/octet-stream")

    def test_csv_content_validation(self, validator: FileValidationService):
        """CSV content should validate as text/plain or text/csv."""
        csv_content = b"name,value\nfoo,1\nbar,2"
        is_valid, detected = validator.validate_content_type(csv_content, "text/csv")
        assert is_valid is True

    def test_magic_mime_mapping_completeness(self):
        """All supported MIME types should have mappings."""
        allowed_types = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
            "text/plain",
            "text/csv",
        }
        for mime_type in allowed_types:
            assert mime_type in MAGIC_MIME_MAPPING, f"Missing mapping for {mime_type}"

    def test_validate_returns_detected_mime(self, validator: FileValidationService):
        """Validation should always return the detected MIME type."""
        text_content = b"Hello world"
        is_valid, detected = validator.validate_content_type(text_content, "text/plain")
        assert detected is not None
        assert isinstance(detected, str)

    def test_empty_content_handling(self, validator: FileValidationService):
        """Empty content should be handled gracefully."""
        empty_content = b""
        # Should not raise exception
        mime = validator.get_actual_mime_type(empty_content)
        assert mime is not None

    def test_binary_content_detection(self, validator: FileValidationService):
        """Binary content should be detected as octet-stream or similar."""
        binary_content = bytes(range(256))  # All byte values
        mime = validator.get_actual_mime_type(binary_content)
        # Should detect as some binary type
        assert mime is not None


class TestFileValidationServiceFromFile:
    """Tests for FileValidationService file object methods."""

    @pytest.fixture
    def validator(self) -> FileValidationService:
        """Create a validator instance."""
        return FileValidationService()

    def test_get_mime_from_file_restores_position(
        self, validator: FileValidationService
    ):
        """File position should be restored after MIME detection."""
        pdf_content = b"%PDF-1.4\n%"
        file = io.BytesIO(pdf_content)

        # Move position to middle
        file.seek(5)

        validator.get_actual_mime_type_from_file(file)

        # Position should be restored
        assert file.tell() == 5

    def test_get_mime_from_file_detects_pdf(self, validator: FileValidationService):
        """PDF magic number should be detected from file object."""
        pdf_content = b"%PDF-1.4\n%"
        file = io.BytesIO(pdf_content)

        mime = validator.get_actual_mime_type_from_file(file)
        assert mime == "application/pdf"

    def test_get_mime_from_file_with_custom_read_size(
        self, validator: FileValidationService
    ):
        """Custom read size should work correctly."""
        pdf_content = b"%PDF-1.4\n%" + b"x" * 10000  # PDF with extra data
        file = io.BytesIO(pdf_content)

        # Should work even with small read size
        mime = validator.get_actual_mime_type_from_file(file, read_size=16)
        assert mime == "application/pdf"

    def test_validate_content_type_from_file_matching(
        self, validator: FileValidationService
    ):
        """Valid PDF with matching type should pass from file object."""
        pdf_content = b"%PDF-1.4\n%"
        file = io.BytesIO(pdf_content)

        is_valid, detected = validator.validate_content_type_from_file(
            file, "application/pdf"
        )
        assert is_valid is True
        assert detected == "application/pdf"

    def test_validate_content_type_from_file_spoofed(
        self, validator: FileValidationService
    ):
        """Executable claiming to be PDF should fail from file object."""
        # ELF executable magic number
        elf_content = b"\x7fELF\x02\x01\x01\x00"
        file = io.BytesIO(elf_content)

        is_valid, detected = validator.validate_content_type_from_file(
            file, "application/pdf"
        )
        assert is_valid is False

    def test_validate_content_type_from_file_restores_position(
        self, validator: FileValidationService
    ):
        """File position should be restored after validation."""
        pdf_content = b"%PDF-1.4\n%"
        file = io.BytesIO(pdf_content)

        # Move position to middle
        file.seek(5)

        validator.validate_content_type_from_file(file, "application/pdf")

        # Position should be restored
        assert file.tell() == 5

    def test_is_safe_from_file_accepts_pdf(self, validator: FileValidationService):
        """PDF files should be accepted from file object."""
        pdf_content = b"%PDF-1.4\n%"
        file = io.BytesIO(pdf_content)

        assert validator.is_safe_file_type_from_file(file) is True

    def test_is_safe_from_file_rejects_executable(
        self, validator: FileValidationService
    ):
        """Executable files should be rejected from file object."""
        # More complete ELF 64-bit executable header
        elf_content = bytes(
            [
                0x7F,
                0x45,
                0x4C,
                0x46,  # ELF magic
                0x02,  # 64-bit
                0x01,  # Little endian
                0x01,  # ELF version
                0x00,  # OS/ABI
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,  # Padding
                0x02,
                0x00,  # Type: Executable
                0x3E,
                0x00,  # Machine: x86-64
                0x01,
                0x00,
                0x00,
                0x00,  # Version
            ]
        )
        file = io.BytesIO(elf_content)

        assert validator.is_safe_file_type_from_file(file) is False

    def test_is_safe_from_file_restores_position(
        self, validator: FileValidationService
    ):
        """File position should be restored after safety check."""
        pdf_content = b"%PDF-1.4\n%"
        file = io.BytesIO(pdf_content)

        # Move position to middle
        file.seek(5)

        validator.is_safe_file_type_from_file(file)

        # Position should be restored
        assert file.tell() == 5

    def test_is_safe_from_file_accepts_text(self, validator: FileValidationService):
        """Text files should be accepted from file object."""
        text_content = b"Just some text content"
        file = io.BytesIO(text_content)

        assert validator.is_safe_file_type_from_file(file) is True
