"""Integration tests for .doc file extraction via Tika.

These tests require a running Tika container.
Set environment: TIKA_ENABLED=true, TIKA_URL=http://localhost:6706

Run: pytest tests/integration/test_doc_extraction.py -v
Skip: pytest tests/ -m "not integration"
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import get_settings
from app.services.document_processor import DocumentProcessor
from app.services.tika_client import (
    ExtractionResponse,
    ExtractionResult,
    TikaClient,
    TikaCorruptedFileError,
)
from tests.fixtures.doc_fixtures import (
    DOC_MIME_TYPE,
    get_corrupted_doc,
    get_empty_file,
    get_minimal_ole_doc,
    get_text_file_claiming_doc_mime,
)

# Skip all tests if Tika not configured
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not get_settings().is_tika_configured,
        reason="Tika not configured - set TIKA_ENABLED=true",
    ),
]


class TestTikaConnection:
    """Integration tests for Tika connectivity."""

    @pytest.fixture
    def tika_client(self) -> TikaClient:
        """Create a TikaClient instance."""
        return TikaClient()

    @pytest.mark.asyncio
    async def test_tika_health_check_passes(self, tika_client: TikaClient):
        """Tika server should respond to health check."""
        is_healthy = await tika_client.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_tika_extract_returns_response(self, tika_client: TikaClient):
        """Tika should return a valid ExtractionResponse."""
        # Use minimal OLE doc bytes
        ole_bytes = get_minimal_ole_doc()

        response = await tika_client.extract_text(
            content=ole_bytes,
            mime_type=DOC_MIME_TYPE,
            filename="test.doc",
        )

        # Response should be an ExtractionResponse (success or error)
        assert isinstance(response, ExtractionResponse)
        assert response.result in (ExtractionResult.SUCCESS, ExtractionResult.ERROR)


class TestDocExtraction:
    """Integration tests for .doc text extraction."""

    @pytest.fixture
    def document_processor(self) -> DocumentProcessor:
        """Create a DocumentProcessor instance."""
        return DocumentProcessor()

    @pytest.mark.asyncio
    async def test_extract_minimal_ole_doc(self, document_processor: DocumentProcessor):
        """Minimal OLE doc should be processed (may not extract text)."""
        ole_bytes = get_minimal_ole_doc()

        # Minimal OLE docs may not have extractable text,
        # but should not raise unhandled exceptions
        try:
            result = await document_processor.extract_text(
                ole_bytes,
                DOC_MIME_TYPE,
                "minimal.doc",
            )
            # Success - result should be a string (possibly empty)
            assert isinstance(result, str)
        except TikaCorruptedFileError:
            # This is also acceptable - minimal OLE is not a real .doc
            pass

    @pytest.mark.asyncio
    async def test_extract_corrupted_doc_handles_error(
        self, document_processor: DocumentProcessor
    ):
        """Corrupted .doc should raise TikaCorruptedFileError or return error."""
        corrupted_bytes = get_corrupted_doc()

        with pytest.raises(TikaCorruptedFileError):
            await document_processor.extract_text(
                corrupted_bytes,
                DOC_MIME_TYPE,
                "corrupted.doc",
            )

    @pytest.mark.asyncio
    async def test_extract_empty_file_handles_gracefully(
        self, document_processor: DocumentProcessor
    ):
        """Empty file should be handled gracefully."""
        empty_bytes = get_empty_file()

        # Empty files may result in error or empty string
        try:
            result = await document_processor.extract_text(
                empty_bytes,
                DOC_MIME_TYPE,
                "empty.doc",
            )
            assert isinstance(result, str)
        except TikaCorruptedFileError:
            # This is also acceptable
            pass

    @pytest.mark.asyncio
    async def test_mime_mismatch_handled(self, document_processor: DocumentProcessor):
        """Plain text claiming to be .doc should still process."""
        text_bytes = get_text_file_claiming_doc_mime()

        # Tika should still process this - it's the MIME type validator's
        # job to catch mismatches, not Tika's
        try:
            result = await document_processor.extract_text(
                text_bytes,
                DOC_MIME_TYPE,
                "fake.doc",
            )
            # If successful, result should be the text content
            assert isinstance(result, str)
        except TikaCorruptedFileError:
            # Also acceptable - Tika may reject non-OLE files
            pass


class TestDocExtractionTimeout:
    """Integration tests for timeout handling."""

    @pytest.fixture
    def short_timeout_client(self) -> TikaClient:
        """Create a TikaClient with very short timeout."""
        # Note: We need to modify the client after creation since
        # timeout is set in __init__
        client = TikaClient()
        client._timeout = 0.001  # 1ms - will definitely timeout
        return client

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_extraction_timeout_returns_error(
        self, short_timeout_client: TikaClient
    ):
        """Very short timeout should result in timeout error."""
        ole_bytes = get_minimal_ole_doc()

        response = await short_timeout_client.extract_text(
            content=ole_bytes,
            mime_type=DOC_MIME_TYPE,
            filename="test.doc",
        )

        # Should get an error response (either timeout or other)
        assert response.result == ExtractionResult.ERROR
        # Message should indicate timeout
        assert "timed out" in response.message.lower()


class TestDocUploadFlow:
    """Integration tests for .doc upload and processing flow."""

    def test_doc_file_accepted_for_upload(self):
        """application/msword files should be accepted."""
        assert DocumentProcessor.is_supported(DOC_MIME_TYPE)

    def test_doc_returns_correct_file_type(self):
        """application/msword should map to 'doc' file type."""
        assert DocumentProcessor.get_file_type(DOC_MIME_TYPE) == "doc"

    @pytest.mark.asyncio
    async def test_doc_extraction_in_processor_flow(self):
        """Full processor flow should work for .doc files with mock."""
        # Create processor with mock TikaClient for this test
        mock_tika = MagicMock()
        mock_tika.extract_text = AsyncMock(
            return_value=ExtractionResponse(
                result=ExtractionResult.SUCCESS,
                text="Document content extracted successfully",
            )
        )
        processor = DocumentProcessor(tika_client=mock_tika)

        result = await processor.extract_text(
            b"test content",
            DOC_MIME_TYPE,
            "test.doc",
        )

        assert result == "Document content extracted successfully"
        mock_tika.extract_text.assert_called_once()


class TestTikaClientConfiguration:
    """Tests for TikaClient configuration."""

    def test_tika_enabled_when_configured(self):
        """TikaClient.is_enabled should be True when configured."""
        client = TikaClient()
        settings = get_settings()
        assert client.is_enabled == settings.tika_enabled

    def test_tika_uses_configured_url(self):
        """TikaClient should use the configured URL."""
        client = TikaClient()
        settings = get_settings()
        assert client._base_url == settings.tika_url

    def test_tika_uses_configured_timeout(self):
        """TikaClient should use the configured timeout."""
        client = TikaClient()
        settings = get_settings()
        assert client._timeout == float(settings.tika_timeout)
