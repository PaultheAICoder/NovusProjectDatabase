"""OCR service for extracting text from scanned PDFs.

Uses Tesseract OCR via pytesseract with PyMuPDF for PDF-to-image conversion.
Follows the same service pattern as TikaClient.
"""

import time
from dataclasses import dataclass, field
from enum import Enum

import fitz  # PyMuPDF
from PIL import Image, ImageFilter, ImageOps

from app.config import get_settings
from app.core.exceptions import OCRError, OCRTimeoutError, OCRUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


class OCRQuality(Enum):
    """OCR quality classification based on confidence score."""

    GOOD = "good"  # >= 0.8 confidence
    FAIR = "fair"  # 0.5 - 0.8 confidence
    POOR = "poor"  # < 0.5 confidence


@dataclass
class OCRConfig:
    """Configuration for OCR processing."""

    enabled: bool = False
    language: str = "eng"
    dpi: int = 300
    timeout_seconds: int = 60
    max_pages: int = 200
    confidence_threshold: float = 0.3
    preprocess_enabled: bool = True


@dataclass
class OCRResult:
    """Result of OCR text extraction."""

    text: str
    confidence: float  # 0.0 to 1.0
    quality: OCRQuality
    page_count: int
    pages_processed: int
    processing_time_seconds: float
    warnings: list[str] = field(default_factory=list)


class OCRService:
    """Service for OCR text extraction from scanned PDFs.

    Uses Tesseract OCR via pytesseract for text recognition and
    PyMuPDF (fitz) for PDF page rendering.

    Example:
        service = OCRService()
        if service.is_scanned_pdf(pdf_bytes):
            result = await service.extract_text_with_ocr(pdf_bytes)
            print(f"Extracted {len(result.text)} chars with {result.confidence:.0%} confidence")
    """

    # Thresholds for quality classification
    QUALITY_GOOD_THRESHOLD = 0.8
    QUALITY_FAIR_THRESHOLD = 0.5

    # Minimum text length to consider a page as having text
    MIN_TEXT_CHARS = 50

    # Minimum image coverage ratio to consider a page as scanned
    MIN_IMAGE_COVERAGE = 0.5

    def __init__(self, config: OCRConfig | None = None) -> None:
        """Initialize the OCR service.

        Args:
            config: Optional OCRConfig. If not provided, uses settings from environment.
        """
        settings = get_settings()

        if config is None:
            self.config = OCRConfig(
                enabled=settings.ocr_enabled,
                language=settings.ocr_language,
                dpi=settings.ocr_dpi,
                timeout_seconds=settings.ocr_timeout_seconds,
                max_pages=settings.ocr_max_pages,
                confidence_threshold=settings.ocr_confidence_threshold,
                preprocess_enabled=settings.ocr_preprocess_enabled,
            )
        else:
            self.config = config

        self._tesseract_available: bool | None = None

    @property
    def is_enabled(self) -> bool:
        """Check if OCR is enabled in configuration."""
        return self.config.enabled

    def _check_tesseract_available(self) -> bool:
        """Check if Tesseract is available on the system."""
        if self._tesseract_available is None:
            try:
                import pytesseract

                pytesseract.get_tesseract_version()
                self._tesseract_available = True
                logger.debug(
                    "tesseract_available",
                    version=str(pytesseract.get_tesseract_version()),
                )
            except Exception as e:
                self._tesseract_available = False
                logger.warning("tesseract_not_available", error=str(e))
        return self._tesseract_available

    def is_scanned_pdf(self, pdf_bytes: bytes) -> bool:
        """Detect if a PDF is scanned (image-based) rather than text-based.

        Uses a two-step detection:
        1. Try text extraction - if substantial text found, it's not scanned
        2. Check for large images covering significant page area

        Args:
            pdf_bytes: Raw PDF file bytes

        Returns:
            True if PDF appears to be scanned (images, no text)
        """
        if not pdf_bytes:
            return False

        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                if doc.page_count == 0:
                    return False

                # Check first few pages (max 3) for scanned content
                pages_to_check = min(3, doc.page_count)

                for page_num in range(pages_to_check):
                    page = doc.load_page(page_num)

                    # Step 1: Check for existing text
                    text = page.get_text().strip()
                    if len(text) > self.MIN_TEXT_CHARS:
                        # Has substantial text - not a scanned page
                        logger.debug(
                            "pdf_has_text",
                            page=page_num,
                            text_length=len(text),
                        )
                        continue

                    # Step 2: Check for large images
                    images = page.get_images(full=True)
                    if not images:
                        continue

                    page_area = page.rect.width * page.rect.height
                    for img_info in images:
                        # img_info: (xref, smask, width, height, bpc, colorspace, alt, name, filter, invoker)
                        try:
                            img_rect = page.get_image_bbox(img_info)
                            img_area = img_rect.width * img_rect.height
                            coverage = img_area / page_area if page_area > 0 else 0

                            if coverage > self.MIN_IMAGE_COVERAGE:
                                logger.info(
                                    "scanned_pdf_detected",
                                    page=page_num,
                                    image_coverage=f"{coverage:.1%}",
                                )
                                return True
                        except Exception:
                            # Skip problematic images
                            continue

                return False

        except Exception as e:
            logger.warning(
                "scanned_pdf_detection_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    def _render_page_to_image(
        self,
        doc: fitz.Document,
        page_num: int,
    ) -> Image.Image:
        """Render a PDF page to a PIL Image for OCR.

        Args:
            doc: PyMuPDF document object
            page_num: Page number (0-indexed)

        Returns:
            PIL Image of the rendered page

        Raises:
            OCRError: If page rendering fails
        """
        try:
            page = doc.load_page(page_num)

            # Calculate zoom factor for target DPI (PDF base is 72 DPI)
            zoom = self.config.dpi / 72
            matrix = fitz.Matrix(zoom, zoom)

            # Render to pixmap (RGB, no alpha)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)

            # Convert to PIL Image
            img = Image.frombytes(
                "RGB",
                [pixmap.width, pixmap.height],
                pixmap.samples,
            )

            logger.debug(
                "page_rendered",
                page=page_num,
                width=pixmap.width,
                height=pixmap.height,
                dpi=self.config.dpi,
            )

            return img

        except Exception as e:
            raise OCRError(
                message=f"Failed to render page {page_num}: {e}",
                page_number=page_num,
            ) from e

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Apply preprocessing to improve OCR accuracy.

        Preprocessing steps:
        1. Convert to grayscale
        2. Deskew (straighten tilted scans)
        3. Enhance contrast
        4. Reduce noise

        Args:
            image: Input PIL Image

        Returns:
            Preprocessed PIL Image
        """
        if not self.config.preprocess_enabled:
            return image

        try:
            # Step 1: Convert to grayscale
            gray = ImageOps.grayscale(image)

            # Step 2: Deskew (straighten)
            deskewed = self._deskew_image(gray)

            # Step 3: Enhance contrast (auto-contrast)
            contrasted = ImageOps.autocontrast(deskewed, cutoff=1)

            # Step 4: Reduce noise with median filter
            denoised = contrasted.filter(ImageFilter.MedianFilter(size=3))

            logger.debug("image_preprocessed")
            return denoised

        except Exception as e:
            logger.warning(
                "preprocessing_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Return original image if preprocessing fails
            return image

    def _deskew_image(self, image: Image.Image, max_angle: float = 10.0) -> Image.Image:
        """Detect and correct skew angle in an image.

        Uses projection profile analysis to find the optimal rotation angle.

        Args:
            image: Grayscale PIL Image
            max_angle: Maximum angle to search (degrees)

        Returns:
            Deskewed image
        """
        try:
            import numpy as np

            # Try rotation angles in range
            best_angle = 0.0
            best_score = 0.0

            # Search angles: -max_angle to +max_angle in 0.5 degree steps
            for angle in np.arange(-max_angle, max_angle + 0.5, 0.5):
                # Rotate image
                rotated = image.rotate(
                    angle, resample=Image.Resampling.BILINEAR, fillcolor=255
                )
                rotated_arr = np.array(rotated)

                # Score by variance of horizontal projection
                projection = np.sum(rotated_arr, axis=1)
                score = np.var(projection)

                if score > best_score:
                    best_score = score
                    best_angle = angle

            # Only rotate if significant skew detected
            if abs(best_angle) > 0.5:
                logger.debug("deskew_applied", angle=best_angle)
                return image.rotate(
                    best_angle,
                    resample=Image.Resampling.BILINEAR,
                    fillcolor=255,
                    expand=False,
                )

            return image

        except ImportError:
            logger.warning("numpy_not_available_for_deskew")
            return image
        except Exception as e:
            logger.warning("deskew_failed", error=str(e))
            return image

    def _ocr_image(self, image: Image.Image) -> tuple[str, float]:
        """Run OCR on a single image.

        Args:
            image: PIL Image to OCR

        Returns:
            Tuple of (extracted_text, confidence_score)
            Confidence is 0.0-1.0

        Raises:
            OCRTimeoutError: If OCR times out
            OCRUnavailableError: If Tesseract not available
        """
        if not self._check_tesseract_available():
            raise OCRUnavailableError(
                message="Tesseract OCR is not available on this system"
            )

        import pytesseract

        try:
            # Use image_to_data to get both text and confidence
            data = pytesseract.image_to_data(
                image,
                lang=self.config.language,
                output_type=pytesseract.Output.DICT,
                timeout=self.config.timeout_seconds,
            )

            # Extract text from words
            words = []
            confidences = []

            for i, text in enumerate(data["text"]):
                conf = data["conf"][i]
                # conf is -1 for non-text elements
                if conf > 0 and text.strip():
                    words.append(text)
                    confidences.append(conf)

            extracted_text = " ".join(words)

            # Calculate average confidence (0-100 from Tesseract, normalize to 0-1)
            if confidences:
                avg_confidence = sum(confidences) / len(confidences) / 100
            else:
                avg_confidence = 0.0

            return extracted_text, avg_confidence

        except RuntimeError as e:
            if "timeout" in str(e).lower():
                raise OCRTimeoutError(
                    message=f"OCR timed out after {self.config.timeout_seconds}s"
                ) from e
            raise OCRError(message=f"OCR failed: {e}") from e

    async def extract_text_with_ocr(
        self,
        pdf_bytes: bytes,
        filename: str = "unknown.pdf",
        max_pages: int | None = None,
    ) -> OCRResult:
        """Extract text from a scanned PDF using OCR.

        Args:
            pdf_bytes: Raw PDF file bytes
            filename: Original filename for logging
            max_pages: Override for max pages to process

        Returns:
            OCRResult with extracted text and metadata

        Raises:
            OCRUnavailableError: If OCR is disabled or Tesseract unavailable
            OCRError: If extraction fails
        """
        if not self.is_enabled:
            raise OCRUnavailableError(
                message="OCR is disabled in configuration",
                filename=filename,
            )

        start_time = time.perf_counter()
        max_pages_limit = max_pages or self.config.max_pages
        warnings: list[str] = []
        all_text_parts: list[str] = []
        all_confidences: list[float] = []
        pages_processed = 0
        total_pages = 0

        logger.info(
            "ocr_extraction_started",
            filename=filename,
            file_size=len(pdf_bytes),
        )

        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                total_pages = min(doc.page_count, max_pages_limit)

                if doc.page_count > max_pages_limit:
                    warnings.append(
                        f"Document has {doc.page_count} pages, "
                        f"only processing first {max_pages_limit}"
                    )

                for page_num in range(total_pages):
                    try:
                        # Render page to image
                        img = self._render_page_to_image(doc, page_num)

                        # Preprocess image
                        processed_img = self._preprocess_image(img)

                        # Run OCR
                        text, confidence = self._ocr_image(processed_img)

                        if text.strip():
                            all_text_parts.append(text)
                            all_confidences.append(confidence)

                        pages_processed += 1

                        logger.debug(
                            "page_ocr_complete",
                            page=page_num,
                            text_length=len(text),
                            confidence=f"{confidence:.1%}",
                        )

                    except OCRTimeoutError:
                        warnings.append(f"Page {page_num} timed out")
                        logger.warning(
                            "page_ocr_timeout",
                            page=page_num,
                            filename=filename,
                        )
                        continue

                    except OCRError as e:
                        warnings.append(f"Page {page_num} failed: {e.message}")
                        logger.warning(
                            "page_ocr_failed",
                            page=page_num,
                            error=str(e),
                            filename=filename,
                        )
                        continue

        except Exception as e:
            raise OCRError(
                message=f"Failed to process PDF: {e}",
                filename=filename,
            ) from e

        # Combine results
        combined_text = "\n\n".join(all_text_parts)

        # Calculate overall confidence
        if all_confidences:
            avg_confidence = sum(all_confidences) / len(all_confidences)
        else:
            avg_confidence = 0.0

        # Determine quality
        if avg_confidence >= self.QUALITY_GOOD_THRESHOLD:
            quality = OCRQuality.GOOD
        elif avg_confidence >= self.QUALITY_FAIR_THRESHOLD:
            quality = OCRQuality.FAIR
        else:
            quality = OCRQuality.POOR

        elapsed = time.perf_counter() - start_time

        logger.info(
            "ocr_extraction_complete",
            filename=filename,
            pages_processed=pages_processed,
            total_pages=total_pages,
            text_length=len(combined_text),
            confidence=f"{avg_confidence:.1%}",
            quality=quality.value,
            elapsed_seconds=round(elapsed, 2),
            warnings_count=len(warnings),
        )

        return OCRResult(
            text=combined_text,
            confidence=avg_confidence,
            quality=quality,
            page_count=total_pages,
            pages_processed=pages_processed,
            processing_time_seconds=elapsed,
            warnings=warnings,
        )

    def classify_quality(self, confidence: float) -> OCRQuality:
        """Classify OCR quality based on confidence score.

        Args:
            confidence: Confidence score (0.0-1.0)

        Returns:
            OCRQuality enum value
        """
        if confidence >= self.QUALITY_GOOD_THRESHOLD:
            return OCRQuality.GOOD
        elif confidence >= self.QUALITY_FAIR_THRESHOLD:
            return OCRQuality.FAIR
        else:
            return OCRQuality.POOR
