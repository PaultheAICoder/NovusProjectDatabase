"""Tests for OCR service."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.ocr_service import (
    OCRConfig,
    OCRQuality,
    OCRResult,
    OCRService,
)


class TestOCRConfig:
    """Tests for OCRConfig dataclass."""

    def test_default_values(self):
        """Default config should have sensible defaults."""
        config = OCRConfig()
        assert config.enabled is False
        assert config.language == "eng"
        assert config.dpi == 300
        assert config.timeout_seconds == 60
        assert config.max_pages == 200
        assert config.confidence_threshold == 0.3
        assert config.preprocess_enabled is True

    def test_custom_values(self):
        """Config should accept custom values."""
        config = OCRConfig(
            enabled=True,
            language="deu",
            dpi=200,
            timeout_seconds=120,
            max_pages=50,
            confidence_threshold=0.5,
            preprocess_enabled=False,
        )
        assert config.enabled is True
        assert config.language == "deu"
        assert config.dpi == 200
        assert config.timeout_seconds == 120
        assert config.max_pages == 50
        assert config.confidence_threshold == 0.5
        assert config.preprocess_enabled is False


class TestOCRResult:
    """Tests for OCRResult dataclass."""

    def test_result_creation(self):
        """OCRResult should store all fields correctly."""
        result = OCRResult(
            text="Sample text",
            confidence=0.85,
            quality=OCRQuality.GOOD,
            page_count=5,
            pages_processed=5,
            processing_time_seconds=2.5,
            warnings=["Minor warning"],
        )
        assert result.text == "Sample text"
        assert result.confidence == 0.85
        assert result.quality == OCRQuality.GOOD
        assert result.page_count == 5
        assert result.pages_processed == 5
        assert result.processing_time_seconds == 2.5
        assert result.warnings == ["Minor warning"]

    def test_result_default_warnings(self):
        """OCRResult warnings should default to empty list."""
        result = OCRResult(
            text="Text",
            confidence=0.7,
            quality=OCRQuality.FAIR,
            page_count=1,
            pages_processed=1,
            processing_time_seconds=1.0,
        )
        assert result.warnings == []


class TestOCRQuality:
    """Tests for OCRQuality enum."""

    def test_quality_values(self):
        """OCRQuality enum should have correct values."""
        assert OCRQuality.GOOD.value == "good"
        assert OCRQuality.FAIR.value == "fair"
        assert OCRQuality.POOR.value == "poor"


class TestOCRService:
    """Tests for OCRService class."""

    @pytest.fixture
    def service(self) -> OCRService:
        """Create an OCRService with default config."""
        config = OCRConfig(enabled=True)
        return OCRService(config=config)

    @pytest.fixture
    def disabled_service(self) -> OCRService:
        """Create a disabled OCRService."""
        config = OCRConfig(enabled=False)
        return OCRService(config=config)

    def test_is_enabled_returns_config_value(self, service: OCRService):
        """is_enabled should return config.enabled."""
        assert service.is_enabled is True

    def test_is_enabled_when_disabled(self, disabled_service: OCRService):
        """is_enabled should return False when disabled."""
        assert disabled_service.is_enabled is False

    def test_classify_quality_good(self, service: OCRService):
        """High confidence should classify as GOOD."""
        assert service.classify_quality(0.85) == OCRQuality.GOOD
        assert service.classify_quality(0.80) == OCRQuality.GOOD
        assert service.classify_quality(1.0) == OCRQuality.GOOD

    def test_classify_quality_fair(self, service: OCRService):
        """Medium confidence should classify as FAIR."""
        assert service.classify_quality(0.75) == OCRQuality.FAIR
        assert service.classify_quality(0.50) == OCRQuality.FAIR
        assert service.classify_quality(0.79) == OCRQuality.FAIR

    def test_classify_quality_poor(self, service: OCRService):
        """Low confidence should classify as POOR."""
        assert service.classify_quality(0.49) == OCRQuality.POOR
        assert service.classify_quality(0.3) == OCRQuality.POOR
        assert service.classify_quality(0.0) == OCRQuality.POOR

    def test_check_tesseract_not_available(self, service: OCRService):
        """Tesseract check should return False when not available."""
        with patch.dict("sys.modules", {"pytesseract": MagicMock()}) as mock_modules:
            mock_pytesseract = mock_modules["pytesseract"]
            mock_pytesseract.get_tesseract_version.side_effect = Exception(
                "Not installed"
            )
            # Reset cached value
            service._tesseract_available = None
            result = service._check_tesseract_available()
            assert result is False
            # Verify caching
            assert service._tesseract_available is False


class TestOCRServiceScannedPdfDetection:
    """Tests for is_scanned_pdf method."""

    @pytest.fixture
    def service(self) -> OCRService:
        """Create an OCRService for testing."""
        config = OCRConfig(enabled=True)
        return OCRService(config=config)

    def test_empty_bytes_returns_false(self, service: OCRService):
        """Empty bytes should return False."""
        assert service.is_scanned_pdf(b"") is False

    def test_invalid_pdf_returns_false(self, service: OCRService):
        """Invalid PDF bytes should return False."""
        assert service.is_scanned_pdf(b"not a pdf") is False

    @patch("app.services.ocr_service.fitz.open")
    def test_empty_pdf_returns_false(self, mock_fitz_open, service: OCRService):
        """PDF with no pages should return False."""
        mock_doc = MagicMock()
        mock_doc.page_count = 0
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz_open.return_value = mock_doc

        result = service.is_scanned_pdf(b"fake pdf bytes")
        assert result is False

    @patch("app.services.ocr_service.fitz.open")
    def test_pdf_with_text_returns_false(self, mock_fitz_open, service: OCRService):
        """PDF with substantial text should return False."""
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_page = MagicMock()
        mock_page.get_text.return_value = "A" * 100  # > MIN_TEXT_CHARS
        mock_doc.load_page.return_value = mock_page

        mock_fitz_open.return_value = mock_doc

        result = service.is_scanned_pdf(b"fake pdf bytes")
        assert result is False

    @patch("app.services.ocr_service.fitz.open")
    def test_pdf_with_large_image_no_text_returns_true(
        self, mock_fitz_open, service: OCRService
    ):
        """PDF with large image and no text should return True."""
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Short"  # < MIN_TEXT_CHARS
        mock_page.get_images.return_value = [
            (1, 0, 800, 600, 8, "DeviceRGB", "", "", "", "")
        ]

        # Mock page rect (standard letter size at 72 dpi)
        mock_rect = MagicMock()
        mock_rect.width = 612
        mock_rect.height = 792
        mock_page.rect = mock_rect

        # Mock image bbox (covers 60% of page)
        mock_img_rect = MagicMock()
        mock_img_rect.width = 550
        mock_img_rect.height = 600
        mock_page.get_image_bbox.return_value = mock_img_rect

        mock_doc.load_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        result = service.is_scanned_pdf(b"fake pdf bytes")
        assert result is True

    @patch("app.services.ocr_service.fitz.open")
    def test_pdf_with_small_image_returns_false(
        self, mock_fitz_open, service: OCRService
    ):
        """PDF with small image (< 50% coverage) should return False."""
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Short"
        mock_page.get_images.return_value = [
            (1, 0, 100, 100, 8, "DeviceRGB", "", "", "", "")
        ]

        mock_rect = MagicMock()
        mock_rect.width = 612
        mock_rect.height = 792
        mock_page.rect = mock_rect

        # Small image - only 10% coverage
        mock_img_rect = MagicMock()
        mock_img_rect.width = 100
        mock_img_rect.height = 100
        mock_page.get_image_bbox.return_value = mock_img_rect

        mock_doc.load_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        result = service.is_scanned_pdf(b"fake pdf bytes")
        assert result is False

    @patch("app.services.ocr_service.fitz.open")
    def test_pdf_with_no_images_returns_false(
        self, mock_fitz_open, service: OCRService
    ):
        """PDF with no text and no images should return False."""
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_page = MagicMock()
        mock_page.get_text.return_value = ""
        mock_page.get_images.return_value = []

        mock_doc.load_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        result = service.is_scanned_pdf(b"fake pdf bytes")
        assert result is False


class TestOCRServiceImageProcessing:
    """Tests for image rendering and preprocessing methods."""

    @pytest.fixture
    def service(self) -> OCRService:
        """Create an OCRService for testing."""
        config = OCRConfig(enabled=True, preprocess_enabled=True)
        return OCRService(config=config)

    @pytest.fixture
    def service_no_preprocess(self) -> OCRService:
        """Create an OCRService with preprocessing disabled."""
        config = OCRConfig(enabled=True, preprocess_enabled=False)
        return OCRService(config=config)

    def test_preprocess_disabled_returns_original(self, service_no_preprocess):
        """When preprocessing disabled, should return original image."""
        from PIL import Image

        original = Image.new("RGB", (100, 100), color="white")
        result = service_no_preprocess._preprocess_image(original)
        # Should be the same object when preprocessing is disabled
        assert result is original

    @patch("app.services.ocr_service.ImageOps")
    def test_preprocess_converts_to_grayscale(self, mock_imageops, service):
        """Preprocessing should convert to grayscale first."""
        from PIL import Image

        original = Image.new("RGB", (100, 100), color="white")
        mock_gray = MagicMock()
        mock_imageops.grayscale.return_value = mock_gray
        mock_imageops.autocontrast.return_value = mock_gray
        mock_gray.filter.return_value = mock_gray

        with patch.object(service, "_deskew_image", return_value=mock_gray):
            service._preprocess_image(original)

        mock_imageops.grayscale.assert_called_once_with(original)

    def test_render_page_to_image_raises_on_error(self, service):
        """_render_page_to_image should raise OCRError on failure."""
        from app.core.exceptions import OCRError

        mock_doc = MagicMock()
        mock_doc.load_page.side_effect = Exception("Page error")

        with pytest.raises(OCRError) as exc_info:
            service._render_page_to_image(mock_doc, 0)

        assert exc_info.value.page_number == 0
        assert "Failed to render page 0" in exc_info.value.message


class TestOCRServiceExtraction:
    """Tests for extract_text_with_ocr method."""

    @pytest.fixture
    def disabled_service(self) -> OCRService:
        """Create a disabled OCRService."""
        config = OCRConfig(enabled=False)
        return OCRService(config=config)

    @pytest.mark.asyncio
    async def test_extraction_raises_when_disabled(self, disabled_service: OCRService):
        """Extraction should raise when OCR is disabled."""
        from app.core.exceptions import OCRUnavailableError

        with pytest.raises(OCRUnavailableError) as exc_info:
            await disabled_service.extract_text_with_ocr(b"fake pdf", "test.pdf")

        assert "disabled" in exc_info.value.message.lower()
        assert exc_info.value.filename == "test.pdf"

    @pytest.mark.asyncio
    async def test_extraction_warns_when_tesseract_unavailable(self):
        """Extraction should add warnings when Tesseract is not available (per-page)."""
        config = OCRConfig(enabled=True, preprocess_enabled=False)
        service = OCRService(config=config)
        service._tesseract_available = False  # Force unavailable

        # Mock fitz to open successfully but fail on OCR
        with patch("app.services.ocr_service.fitz.open") as mock_fitz:
            mock_doc = MagicMock()
            mock_doc.page_count = 1
            mock_doc.__enter__ = MagicMock(return_value=mock_doc)
            mock_doc.__exit__ = MagicMock(return_value=False)

            mock_page = MagicMock()
            mock_doc.load_page.return_value = mock_page

            # Mock pixmap
            mock_pixmap = MagicMock()
            mock_pixmap.width = 100
            mock_pixmap.height = 100
            mock_pixmap.samples = b"\xff" * 30000  # RGB data
            mock_page.get_pixmap.return_value = mock_pixmap

            mock_fitz.return_value = mock_doc

            # Per-page OCRError is caught and added to warnings
            result = await service.extract_text_with_ocr(b"fake pdf", "test.pdf")

            # Should have warning about not available
            assert len(result.warnings) > 0
            assert any("not available" in w.lower() for w in result.warnings)
            assert result.pages_processed == 0
            assert result.text == ""

    @pytest.mark.asyncio
    async def test_extraction_handles_page_timeout(self):
        """Extraction should continue after page timeout and process next pages."""
        from app.core.exceptions import OCRTimeoutError

        config = OCRConfig(enabled=True, preprocess_enabled=False)
        service = OCRService(config=config)
        service._tesseract_available = True

        with patch("app.services.ocr_service.fitz.open") as mock_fitz:
            mock_doc = MagicMock()
            mock_doc.page_count = 2
            mock_doc.__enter__ = MagicMock(return_value=mock_doc)
            mock_doc.__exit__ = MagicMock(return_value=False)

            mock_page = MagicMock()
            mock_pixmap = MagicMock()
            mock_pixmap.width = 100
            mock_pixmap.height = 100
            mock_pixmap.samples = b"\xff" * 30000
            mock_page.get_pixmap.return_value = mock_pixmap
            mock_doc.load_page.return_value = mock_page

            mock_fitz.return_value = mock_doc

            # First page times out, second succeeds
            call_count = [0]

            def mock_ocr_image(img):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise OCRTimeoutError(message="Timeout")
                return ("Page 2 text", 0.9)

            with patch.object(service, "_ocr_image", side_effect=mock_ocr_image):
                result = await service.extract_text_with_ocr(b"fake pdf", "test.pdf")

            # Should have warning about timeout
            assert any("timed out" in w.lower() for w in result.warnings)
            # Only 1 page processed successfully (page 2); page 1 timed out
            assert result.pages_processed == 1
            assert result.page_count == 2  # Total pages in document (limited)
            assert result.text == "Page 2 text"

    @pytest.mark.asyncio
    async def test_extraction_respects_max_pages(self):
        """Extraction should respect max_pages limit."""
        config = OCRConfig(enabled=True, max_pages=2, preprocess_enabled=False)
        service = OCRService(config=config)
        service._tesseract_available = True

        with patch("app.services.ocr_service.fitz.open") as mock_fitz:
            mock_doc = MagicMock()
            mock_doc.page_count = 10  # More than max_pages
            mock_doc.__enter__ = MagicMock(return_value=mock_doc)
            mock_doc.__exit__ = MagicMock(return_value=False)

            mock_page = MagicMock()
            mock_pixmap = MagicMock()
            mock_pixmap.width = 100
            mock_pixmap.height = 100
            mock_pixmap.samples = b"\xff" * 30000
            mock_page.get_pixmap.return_value = mock_pixmap
            mock_doc.load_page.return_value = mock_page

            mock_fitz.return_value = mock_doc

            with patch.object(service, "_ocr_image", return_value=("text", 0.9)):
                result = await service.extract_text_with_ocr(b"fake pdf", "test.pdf")

            assert result.page_count == 2  # Limited to max_pages
            assert any("only processing first 2" in w for w in result.warnings)


class TestOCRServiceOCRImage:
    """Tests for _ocr_image method."""

    @pytest.fixture
    def service(self) -> OCRService:
        """Create an OCRService for testing."""
        config = OCRConfig(enabled=True, language="eng", timeout_seconds=30)
        return OCRService(config=config)

    def test_ocr_image_raises_when_tesseract_unavailable(self, service):
        """_ocr_image should raise OCRUnavailableError when Tesseract not available."""
        from PIL import Image

        from app.core.exceptions import OCRUnavailableError

        service._tesseract_available = False
        image = Image.new("RGB", (100, 100))

        with pytest.raises(OCRUnavailableError) as exc_info:
            service._ocr_image(image)

        assert "not available" in exc_info.value.message.lower()

    def test_ocr_image_returns_text_and_confidence(self, service):
        """_ocr_image should return extracted text and confidence."""
        from PIL import Image

        service._tesseract_available = True
        image = Image.new("RGB", (100, 100))

        mock_pytesseract = MagicMock()
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.return_value = {
            "text": ["Hello", "World", ""],
            "conf": [90, 85, -1],  # -1 for non-text elements
        }

        with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
            text, confidence = service._ocr_image(image)

        assert text == "Hello World"
        # Average of 90 and 85, divided by 100
        assert confidence == pytest.approx(0.875)

    def test_ocr_image_handles_empty_result(self, service):
        """_ocr_image should handle empty OCR result."""
        from PIL import Image

        service._tesseract_available = True
        image = Image.new("RGB", (100, 100))

        mock_pytesseract = MagicMock()
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.return_value = {
            "text": ["", " ", ""],
            "conf": [-1, -1, -1],
        }

        with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
            text, confidence = service._ocr_image(image)

        assert text == ""
        assert confidence == 0.0

    def test_ocr_image_raises_timeout_error(self, service):
        """_ocr_image should raise OCRTimeoutError on timeout."""
        from PIL import Image

        from app.core.exceptions import OCRTimeoutError

        service._tesseract_available = True
        image = Image.new("RGB", (100, 100))

        mock_pytesseract = MagicMock()
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.side_effect = RuntimeError("Tesseract timeout")

        with (
            patch.dict("sys.modules", {"pytesseract": mock_pytesseract}),
            pytest.raises(OCRTimeoutError),
        ):
            service._ocr_image(image)
