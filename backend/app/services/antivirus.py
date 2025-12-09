"""Antivirus scanning service using ClamAV."""

import asyncio
from dataclasses import dataclass
from enum import Enum

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ScanResult(Enum):
    """Result of antivirus scan."""

    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class ScanResponse:
    """Response from antivirus scan."""

    result: ScanResult
    threat_name: str | None = None
    message: str | None = None


class AntivirusService:
    """Service for scanning files with ClamAV antivirus."""

    # ClamAV protocol constants
    INSTREAM_CMD = b"zINSTREAM\x00"
    CHUNK_SIZE = 8192
    MAX_STREAM_SIZE = 26214400  # 25MB - ClamAV default limit

    def __init__(self) -> None:
        """Initialize the antivirus service."""
        self.settings = get_settings()
        self._host = self.settings.clamav_host
        self._port = self.settings.clamav_port
        self._timeout = self.settings.clamav_timeout

    @property
    def is_enabled(self) -> bool:
        """Check if antivirus scanning is enabled."""
        return self.settings.clamav_enabled and self.settings.clamav_scan_on_upload

    @property
    def fail_open(self) -> bool:
        """Check if uploads should proceed when scanning fails."""
        return self.settings.clamav_fail_open

    async def scan_bytes(
        self, content: bytes, filename: str = "unknown"
    ) -> ScanResponse:
        """
        Scan file content for malware using ClamAV.

        Args:
            content: File content bytes to scan
            filename: Original filename for logging

        Returns:
            ScanResponse with result and details
        """
        if not self.is_enabled:
            logger.debug(
                "antivirus_scan_skipped",
                reason="disabled",
                filename=filename,
            )
            return ScanResponse(
                result=ScanResult.SKIPPED,
                message="Antivirus scanning is disabled",
            )

        if len(content) > self.MAX_STREAM_SIZE:
            logger.warning(
                "antivirus_file_too_large",
                filename=filename,
                size=len(content),
                max_size=self.MAX_STREAM_SIZE,
            )
            return ScanResponse(
                result=ScanResult.ERROR,
                message=f"File too large for scanning (max {self.MAX_STREAM_SIZE} bytes)",
            )

        try:
            return await self._scan_with_clamd(content, filename)
        except Exception as e:
            logger.exception(
                "antivirus_scan_error",
                filename=filename,
                error=str(e),
            )
            return ScanResponse(
                result=ScanResult.ERROR,
                message=f"Scan error: {str(e)}",
            )

    async def _scan_with_clamd(self, content: bytes, filename: str) -> ScanResponse:
        """
        Perform actual scan using ClamAV daemon protocol.

        Uses INSTREAM command for memory-efficient scanning.
        """
        try:
            # Connect to ClamAV daemon
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout,
            )
        except TimeoutError:
            logger.warning(
                "clamav_connection_timeout",
                host=self._host,
                port=self._port,
            )
            return ScanResponse(
                result=ScanResult.ERROR,
                message="Connection to ClamAV timed out",
            )
        except (ConnectionRefusedError, OSError) as e:
            logger.warning(
                "clamav_connection_failed",
                host=self._host,
                port=self._port,
                error=str(e),
            )
            return ScanResponse(
                result=ScanResult.ERROR,
                message=f"Cannot connect to ClamAV: {str(e)}",
            )

        try:
            # Send INSTREAM command
            writer.write(self.INSTREAM_CMD)
            await writer.drain()

            # Send file content in chunks
            # Format: [4-byte chunk size][chunk data]
            offset = 0
            while offset < len(content):
                chunk = content[offset : offset + self.CHUNK_SIZE]
                chunk_size = len(chunk).to_bytes(4, byteorder="big")
                writer.write(chunk_size + chunk)
                offset += self.CHUNK_SIZE

            # Send zero-length chunk to signal end
            writer.write((0).to_bytes(4, byteorder="big"))
            await writer.drain()

            # Read response
            response = await asyncio.wait_for(
                reader.read(4096),
                timeout=self._timeout,
            )
            response_str = response.decode("utf-8").strip()

            logger.debug(
                "clamav_scan_response",
                filename=filename,
                response=response_str,
            )

            # Parse response
            return self._parse_scan_response(response_str, filename)

        finally:
            writer.close()
            await writer.wait_closed()

    def _parse_scan_response(self, response: str, filename: str) -> ScanResponse:
        """
        Parse ClamAV scan response.

        Response format:
        - Clean: "stream: OK"
        - Infected: "stream: <virus_name> FOUND"
        - Error: "stream: <error_message> ERROR"
        """
        response = response.strip("\x00")  # Remove null terminators

        if response.endswith("OK"):
            logger.info(
                "antivirus_scan_clean",
                filename=filename,
            )
            return ScanResponse(result=ScanResult.CLEAN)

        if "FOUND" in response:
            # Extract threat name: "stream: Win.Test.EICAR_HDB-1 FOUND"
            parts = response.split(":")
            if len(parts) >= 2:
                threat_info = parts[1].strip()
                threat_name = threat_info.replace(" FOUND", "").strip()
            else:
                threat_name = "Unknown threat"

            logger.warning(
                "antivirus_threat_detected",
                filename=filename,
                threat_name=threat_name,
            )
            return ScanResponse(
                result=ScanResult.INFECTED,
                threat_name=threat_name,
                message=f"Malware detected: {threat_name}",
            )

        if "ERROR" in response:
            logger.error(
                "antivirus_scan_error_response",
                filename=filename,
                response=response,
            )
            return ScanResponse(
                result=ScanResult.ERROR,
                message=response,
            )

        # Unknown response format
        logger.warning(
            "antivirus_unknown_response",
            filename=filename,
            response=response,
        )
        return ScanResponse(
            result=ScanResult.ERROR,
            message=f"Unknown response: {response}",
        )

    async def ping(self) -> bool:
        """
        Check if ClamAV daemon is available.

        Returns:
            True if ClamAV responds, False otherwise
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=5,
            )
            try:
                writer.write(b"zPING\x00")
                await writer.drain()
                response = await asyncio.wait_for(reader.read(32), timeout=5)
                return b"PONG" in response
            finally:
                writer.close()
                await writer.wait_closed()
        except Exception:
            return False
