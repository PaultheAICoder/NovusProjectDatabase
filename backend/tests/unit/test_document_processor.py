"""Tests for document processor service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document_processor import DocumentProcessor
from app.services.tika_client import (
    ExtractionResponse,
    ExtractionResult,
    TikaClient,
    TikaCorruptedFileError,
    TikaExtractionError,
    TikaPasswordProtectedError,
    TikaTimeoutError,
    TikaUnavailableError,
)


class TestDocumentProcessorMimeTypes:
    """Tests for DocumentProcessor MIME type handling."""

    def test_is_supported_doc_mime_type(self):
        """application/msword should be a supported MIME type."""
        assert DocumentProcessor.is_supported("application/msword") is True

    def test_is_supported_pdf_mime_type(self):
        """application/pdf should be a supported MIME type."""
        assert DocumentProcessor.is_supported("application/pdf") is True

    def test_is_supported_docx_mime_type(self):
        """DOCX MIME type should be supported."""
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert DocumentProcessor.is_supported(mime) is True

    def test_is_supported_unsupported_mime_type(self):
        """Unknown MIME types should not be supported."""
        assert DocumentProcessor.is_supported("application/unknown") is False

    def test_get_file_type_returns_doc(self):
        """application/msword should return 'doc' file type."""
        assert DocumentProcessor.get_file_type("application/msword") == "doc"

    def test_get_file_type_returns_pdf(self):
        """application/pdf should return 'pdf' file type."""
        assert DocumentProcessor.get_file_type("application/pdf") == "pdf"

    def test_get_file_type_returns_docx(self):
        """DOCX MIME type should return 'docx' file type."""
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert DocumentProcessor.get_file_type(mime) == "docx"

    def test_get_file_type_returns_none_for_unsupported(self):
        """Unknown MIME types should return None."""
        assert DocumentProcessor.get_file_type("application/unknown") is None


class TestDocumentProcessorExtractDoc:
    """Tests for DocumentProcessor._extract_doc method."""

    @pytest.fixture
    def mock_tika_client(self) -> MagicMock:
        """Create a mock TikaClient."""
        mock = MagicMock(spec=TikaClient)
        mock.extract_text = AsyncMock()
        return mock

    @pytest.fixture
    def processor(self, mock_tika_client: MagicMock) -> DocumentProcessor:
        """Create a DocumentProcessor with mocked TikaClient."""
        return DocumentProcessor(tika_client=mock_tika_client)

    @pytest.mark.asyncio
    async def test_extract_doc_success(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Successful .doc extraction should return extracted text."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.SUCCESS,
            text="Extracted document text content",
        )

        result = await processor._extract_doc(b"test content", "test.doc")

        assert result == "Extracted document text content"
        mock_tika_client.extract_text.assert_called_once_with(
            content=b"test content",
            mime_type="application/msword",
            filename="test.doc",
        )

    @pytest.mark.asyncio
    async def test_extract_doc_success_empty_text(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Successful extraction with empty text should return empty string."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.SUCCESS,
            text=None,
        )

        result = await processor._extract_doc(b"test content", "test.doc")

        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_doc_tika_disabled(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """When Tika is disabled, should raise TikaUnavailableError."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.SKIPPED,
            message="Tika extraction is disabled",
        )

        with pytest.raises(TikaUnavailableError) as exc_info:
            await processor._extract_doc(b"test content", "test.doc")

        assert "disabled" in exc_info.value.message.lower()
        assert exc_info.value.filename == "test.doc"

    @pytest.mark.asyncio
    async def test_extract_doc_timeout(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Timeout during extraction should raise TikaTimeoutError."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.ERROR,
            message="Extraction timed out after 30s",
        )

        with pytest.raises(TikaTimeoutError) as exc_info:
            await processor._extract_doc(b"test content", "test.doc")

        assert "timed out" in exc_info.value.message.lower()
        assert exc_info.value.filename == "test.doc"

    @pytest.mark.asyncio
    async def test_extract_doc_connection_error(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Connection error should raise TikaUnavailableError."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.ERROR,
            message="Cannot connect to Tika after 3 attempts",
        )

        with pytest.raises(TikaUnavailableError) as exc_info:
            await processor._extract_doc(b"test content", "test.doc")

        assert "cannot connect" in exc_info.value.message.lower()
        assert exc_info.value.filename == "test.doc"

    @pytest.mark.asyncio
    async def test_extract_doc_password_protected(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Password-protected documents should raise TikaPasswordProtectedError."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.ERROR,
            message="Document is password protected or encrypted",
        )

        with pytest.raises(TikaPasswordProtectedError) as exc_info:
            await processor._extract_doc(b"test content", "secret.doc")

        assert "password" in exc_info.value.message.lower()
        assert exc_info.value.filename == "secret.doc"

    @pytest.mark.asyncio
    async def test_extract_doc_encrypted(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Encrypted documents should also raise TikaPasswordProtectedError."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.ERROR,
            message="File is encrypted and cannot be read",
        )

        with pytest.raises(TikaPasswordProtectedError) as exc_info:
            await processor._extract_doc(b"test content", "encrypted.doc")

        assert exc_info.value.filename == "encrypted.doc"

    @pytest.mark.asyncio
    async def test_extract_doc_corrupted_422(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """HTTP 422 error should raise TikaCorruptedFileError."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.ERROR,
            message="Tika returned error: 422",
        )

        with pytest.raises(TikaCorruptedFileError) as exc_info:
            await processor._extract_doc(b"corrupted content", "corrupted.doc")

        assert "corrupted" in exc_info.value.message.lower()
        assert exc_info.value.filename == "corrupted.doc"

    @pytest.mark.asyncio
    async def test_extract_doc_corrupted_unprocessable(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Unprocessable entity error should raise TikaCorruptedFileError."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.ERROR,
            message="Document is unprocessable",
        )

        with pytest.raises(TikaCorruptedFileError) as exc_info:
            await processor._extract_doc(b"bad content", "bad.doc")

        assert "corrupted" in exc_info.value.message.lower()
        assert exc_info.value.filename == "bad.doc"

    @pytest.mark.asyncio
    async def test_extract_doc_generic_error(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Unknown errors should raise TikaExtractionError."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.ERROR,
            message="Some unexpected error occurred",
        )

        with pytest.raises(TikaExtractionError) as exc_info:
            await processor._extract_doc(b"test content", "test.doc")

        assert "Some unexpected error occurred" in exc_info.value.message
        assert exc_info.value.filename == "test.doc"


class TestDocumentProcessorExtractText:
    """Tests for DocumentProcessor.extract_text routing."""

    @pytest.fixture
    def mock_tika_client(self) -> MagicMock:
        """Create a mock TikaClient."""
        mock = MagicMock(spec=TikaClient)
        mock.extract_text = AsyncMock()
        return mock

    @pytest.fixture
    def processor(self, mock_tika_client: MagicMock) -> DocumentProcessor:
        """Create a DocumentProcessor with mocked TikaClient."""
        return DocumentProcessor(tika_client=mock_tika_client)

    @pytest.mark.asyncio
    async def test_extract_text_routes_doc_to_extract_doc(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """application/msword files should route to _extract_doc."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.SUCCESS,
            text="Doc content",
        )

        result = await processor.extract_text(
            b"test content",
            "application/msword",
            "test.doc",
        )

        assert result == "Doc content"
        mock_tika_client.extract_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_text_unsupported_mime_raises(
        self, processor: DocumentProcessor
    ):
        """Unsupported MIME types should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await processor.extract_text(
                b"test content",
                "application/unknown",
                "test.xyz",
            )

        assert "Unsupported MIME type" in str(exc_info.value)


class TestDocumentProcessorTikaClientLazy:
    """Tests for DocumentProcessor TikaClient lazy initialization."""

    def test_tika_client_property_lazy_init(self):
        """TikaClient should be lazily initialized when accessed."""
        processor = DocumentProcessor()

        # Private attribute should be None initially
        assert processor._tika_client is None

        # Accessing property should create client
        with patch("app.services.document_processor.TikaClient") as mock_cls:
            mock_cls.return_value = MagicMock(spec=TikaClient)
            _ = processor.tika_client
            mock_cls.assert_called_once()

    def test_tika_client_property_returns_injected(self):
        """Injected TikaClient should be used without creating new one."""
        mock_client = MagicMock(spec=TikaClient)
        processor = DocumentProcessor(tika_client=mock_client)

        # Should return the injected client
        assert processor.tika_client is mock_client


class TestDocumentProcessorErrorPropagation:
    """Tests for error propagation in DocumentProcessor."""

    @pytest.fixture
    def mock_tika_client(self) -> MagicMock:
        """Create a mock TikaClient."""
        mock = MagicMock(spec=TikaClient)
        mock.extract_text = AsyncMock()
        return mock

    @pytest.fixture
    def processor(self, mock_tika_client: MagicMock) -> DocumentProcessor:
        """Create a DocumentProcessor with mocked TikaClient."""
        return DocumentProcessor(tika_client=mock_tika_client)

    @pytest.mark.asyncio
    async def test_extract_text_propagates_tika_unavailable_error(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """TikaUnavailableError should propagate through extract_text."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.SKIPPED,
            message="Tika extraction is disabled",
        )

        with pytest.raises(TikaUnavailableError) as exc_info:
            await processor.extract_text(
                b"test content",
                "application/msword",
                "test.doc",
            )

        assert "disabled" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_extract_text_propagates_tika_timeout_error(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """TikaTimeoutError should propagate through extract_text."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.ERROR,
            message="Extraction timed out after 60s",
        )

        with pytest.raises(TikaTimeoutError) as exc_info:
            await processor.extract_text(
                b"test content",
                "application/msword",
                "test.doc",
            )

        assert "timed out" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_extract_text_propagates_corrupted_file_error(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """TikaCorruptedFileError should propagate through extract_text."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.ERROR,
            message="Tika returned error: 422",
        )

        with pytest.raises(TikaCorruptedFileError) as exc_info:
            await processor.extract_text(
                b"corrupted content",
                "application/msword",
                "corrupted.doc",
            )

        assert "corrupted" in exc_info.value.message.lower()


class TestDocumentProcessorEmptyContent:
    """Tests for empty and edge case content handling."""

    @pytest.fixture
    def mock_tika_client(self) -> MagicMock:
        """Create a mock TikaClient."""
        mock = MagicMock(spec=TikaClient)
        mock.extract_text = AsyncMock()
        return mock

    @pytest.fixture
    def processor(self, mock_tika_client: MagicMock) -> DocumentProcessor:
        """Create a DocumentProcessor with mocked TikaClient."""
        return DocumentProcessor(tika_client=mock_tika_client)

    @pytest.mark.asyncio
    async def test_extract_empty_doc_returns_empty_string(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Empty .doc file should return empty string if extraction succeeds."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.SUCCESS,
            text="",
        )

        result = await processor.extract_text(
            b"",  # Empty content
            "application/msword",
            "empty.doc",
        )

        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_doc_returns_none_as_empty_string(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """None text result should be returned as empty string."""
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.SUCCESS,
            text=None,
        )

        result = await processor.extract_text(
            b"test content",
            "application/msword",
            "test.doc",
        )

        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_very_large_content_succeeds(
        self, processor: DocumentProcessor, mock_tika_client: MagicMock
    ):
        """Very large content should be handled (with mock, no real extraction)."""
        large_text = "x" * 1000000  # 1 million characters
        mock_tika_client.extract_text.return_value = ExtractionResponse(
            result=ExtractionResult.SUCCESS,
            text=large_text,
        )

        result = await processor.extract_text(
            b"large content",
            "application/msword",
            "large.doc",
        )

        assert len(result) == 1000000
        assert result == large_text
