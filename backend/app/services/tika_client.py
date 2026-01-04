"""Apache Tika client for text extraction from legacy document formats."""

from dataclasses import dataclass
from enum import Enum

import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExtractionResult(Enum):
    """Result of text extraction."""

    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class ExtractionResponse:
    """Response from text extraction."""

    result: ExtractionResult
    text: str | None = None
    message: str | None = None


class TikaClient:
    """Async client for Apache Tika text extraction.

    Uses HTTP REST API to communicate with Tika server for
    extracting text from various document formats, particularly
    legacy .doc files (Word 97-2003).
    """

    def __init__(self) -> None:
        """Initialize the Tika client."""
        self.settings = get_settings()
        self._base_url = self.settings.tika_url
        self._timeout = float(self.settings.tika_timeout)

    @property
    def is_enabled(self) -> bool:
        """Check if Tika extraction is enabled."""
        return self.settings.tika_enabled

    async def extract_text(
        self,
        content: bytes,
        mime_type: str,
        filename: str = "unknown",
    ) -> ExtractionResponse:
        """
        Extract text from binary content via Tika.

        Args:
            content: File content bytes
            mime_type: MIME type of the content (e.g., 'application/msword')
            filename: Original filename for logging

        Returns:
            ExtractionResponse with extracted text or error details
        """
        if not self.is_enabled:
            logger.debug(
                "tika_extraction_skipped",
                reason="disabled",
                filename=filename,
            )
            return ExtractionResponse(
                result=ExtractionResult.SKIPPED,
                message="Tika extraction is disabled",
            )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.put(
                    f"{self._base_url}/tika",
                    content=content,
                    headers={
                        "Content-Type": mime_type,
                        "Accept": "text/plain; charset=utf-8",
                    },
                )
                response.raise_for_status()

                extracted_text = response.text

                logger.info(
                    "tika_extraction_success",
                    filename=filename,
                    mime_type=mime_type,
                    text_length=len(extracted_text),
                )

                return ExtractionResponse(
                    result=ExtractionResult.SUCCESS,
                    text=extracted_text,
                )

        except httpx.TimeoutException:
            logger.warning(
                "tika_extraction_timeout",
                filename=filename,
                mime_type=mime_type,
                timeout=self._timeout,
            )
            return ExtractionResponse(
                result=ExtractionResult.ERROR,
                message=f"Extraction timed out after {self._timeout}s",
            )

        except httpx.ConnectError as e:
            logger.warning(
                "tika_connection_error",
                filename=filename,
                url=self._base_url,
                error=str(e),
            )
            return ExtractionResponse(
                result=ExtractionResult.ERROR,
                message=f"Cannot connect to Tika: {e!s}",
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "tika_http_error",
                filename=filename,
                status_code=e.response.status_code,
                error=str(e),
            )
            return ExtractionResponse(
                result=ExtractionResult.ERROR,
                message=f"Tika returned error: {e.response.status_code}",
            )

        except Exception as e:
            logger.exception(
                "tika_extraction_error",
                filename=filename,
                error=str(e),
            )
            return ExtractionResponse(
                result=ExtractionResult.ERROR,
                message=f"Extraction failed: {e!s}",
            )

    async def health_check(self) -> bool:
        """
        Check if Tika server is available.

        Returns:
            True if Tika responds, False otherwise
        """
        if not self.is_enabled:
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/tika")
                is_healthy = response.status_code == 200

                if is_healthy:
                    logger.debug("tika_health_check_success")
                else:
                    logger.warning(
                        "tika_health_check_failed",
                        status_code=response.status_code,
                    )

                return is_healthy

        except Exception as e:
            logger.warning(
                "tika_health_check_error",
                error=str(e),
            )
            return False
