"""Antivirus scanning service using ClamAV."""

import asyncio
import time
from asyncio import Queue, QueueEmpty
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

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


class PooledConnection(NamedTuple):
    """A pooled TCP connection with metadata."""

    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    created_at: float


class ClamAVConnectionPool:
    """
    Async connection pool for ClamAV daemon connections.

    Uses asyncio.Queue to manage a pool of reusable TCP connections,
    reducing connection overhead and preventing socket exhaustion.
    """

    def __init__(
        self,
        host: str,
        port: int,
        pool_size: int = 5,
        connection_timeout: float = 10.0,
        max_connection_age: float = 300.0,
    ) -> None:
        self._host = host
        self._port = port
        self._pool_size = pool_size
        self._connection_timeout = connection_timeout
        self._max_connection_age = max_connection_age
        self._pool: Queue[PooledConnection] = Queue(maxsize=pool_size)
        self._created_count = 0
        self._active_count = 0
        self._closed = False
        self._lock = asyncio.Lock()

    async def acquire(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Acquire a connection from the pool.

        Returns an existing connection if available, or creates a new one.
        Stale connections (exceeding max_connection_age) are discarded.

        Raises:
            TimeoutError: If unable to acquire connection within timeout
            ConnectionRefusedError: If ClamAV is unavailable
        """
        if self._closed:
            raise RuntimeError("Pool is closed")

        # Try to get an existing connection
        try:
            while True:
                conn = self._pool.get_nowait()
                # Check if connection is too old
                if time.monotonic() - conn.created_at > self._max_connection_age:
                    await self._close_connection(conn)
                    continue
                # Check if connection is still valid
                if conn.writer.is_closing():
                    await self._close_connection(conn)
                    continue
                self._active_count += 1
                return conn.reader, conn.writer
        except QueueEmpty:
            pass

        # Create new connection if pool not full
        async with self._lock:
            if self._created_count < self._pool_size:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port),
                    timeout=self._connection_timeout,
                )
                self._created_count += 1
                self._active_count += 1
                return reader, writer

        # Pool full - wait for a connection to be released
        try:
            conn = await asyncio.wait_for(
                self._pool.get(),
                timeout=self._connection_timeout,
            )
            if (
                time.monotonic() - conn.created_at > self._max_connection_age
                or conn.writer.is_closing()
            ):
                await self._close_connection(conn)
                # Recursively try again
                return await self.acquire()
            self._active_count += 1
            return conn.reader, conn.writer
        except TimeoutError:
            raise TimeoutError("Timed out waiting for connection from pool")

    async def release(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        discard: bool = False,
    ) -> None:
        """
        Return a connection to the pool.

        Args:
            reader: The stream reader
            writer: The stream writer
            discard: If True, close connection instead of returning to pool
        """
        self._active_count = max(0, self._active_count - 1)

        if discard or self._closed or writer.is_closing():
            await self._close_connection_raw(writer)
            async with self._lock:
                self._created_count = max(0, self._created_count - 1)
            return

        # Return to pool (create new PooledConnection to reset age tracking)
        conn = PooledConnection(
            reader=reader,
            writer=writer,
            created_at=time.monotonic(),
        )
        try:
            self._pool.put_nowait(conn)
        except asyncio.QueueFull:
            await self._close_connection(conn)
            async with self._lock:
                self._created_count = max(0, self._created_count - 1)

    async def _close_connection(self, conn: PooledConnection) -> None:
        """Close a pooled connection."""
        await self._close_connection_raw(conn.writer)

    async def _close_connection_raw(self, writer: asyncio.StreamWriter) -> None:
        """Close a raw writer."""
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass  # Ignore errors during close

    async def close(self) -> None:
        """Close all connections in the pool."""
        self._closed = True
        while True:
            try:
                conn = self._pool.get_nowait()
                await self._close_connection(conn)
            except QueueEmpty:
                break
        self._created_count = 0
        self._active_count = 0

    @property
    def stats(self) -> dict:
        """Return pool statistics."""
        return {
            "pool_size": self._pool_size,
            "created_count": self._created_count,
            "active_count": self._active_count,
            "available_count": self._pool.qsize(),
            "closed": self._closed,
        }


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
        Uses connection pool when available for better performance.
        """
        pool = get_clamav_pool()
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None
        discard_connection = False

        try:
            # Acquire connection (from pool or direct)
            if pool is not None:
                try:
                    reader, writer = await pool.acquire()
                except TimeoutError:
                    logger.warning(
                        "clamav_pool_timeout",
                        filename=filename,
                        pool_stats=pool.stats,
                    )
                    return ScanResponse(
                        result=ScanResult.ERROR,
                        message="Connection pool timeout",
                    )
            else:
                # Fallback to direct connection (pool not initialized)
                try:
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

        except Exception:
            # On error, discard the connection (may be in bad state)
            discard_connection = True
            raise
        finally:
            if writer is not None:
                if pool is not None:
                    await pool.release(reader, writer, discard=discard_connection)
                else:
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
        pool = get_clamav_pool()
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None
        discard_connection = False

        try:
            # Acquire connection
            if pool is not None:
                try:
                    reader, writer = await pool.acquire()
                except Exception:
                    return False
            else:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port),
                    timeout=5,
                )

            try:
                writer.write(b"zPING\x00")
                await writer.drain()
                response = await asyncio.wait_for(reader.read(32), timeout=5)
                return b"PONG" in response
            except Exception:
                discard_connection = True
                return False
        except Exception:
            return False
        finally:
            if writer is not None:
                if pool is not None:
                    await pool.release(reader, writer, discard=discard_connection)
                else:
                    writer.close()
                    await writer.wait_closed()


# Global connection pool instance (lazy initialization)
_clamav_pool: ClamAVConnectionPool | None = None


def get_clamav_pool() -> ClamAVConnectionPool | None:
    """Get the global ClamAV connection pool (if initialized)."""
    return _clamav_pool


async def init_clamav_pool() -> ClamAVConnectionPool | None:
    """
    Initialize the global ClamAV connection pool.

    Should be called during application startup.
    Returns None if ClamAV is disabled.
    """
    global _clamav_pool

    settings = get_settings()
    if not settings.clamav_enabled:
        logger.info("clamav_pool_init_skipped", reason="disabled")
        return None

    _clamav_pool = ClamAVConnectionPool(
        host=settings.clamav_host,
        port=settings.clamav_port,
        pool_size=settings.clamav_pool_size,
        connection_timeout=float(settings.clamav_pool_timeout),
        max_connection_age=float(settings.clamav_connection_max_age),
    )
    logger.info(
        "clamav_pool_initialized",
        host=settings.clamav_host,
        port=settings.clamav_port,
        pool_size=settings.clamav_pool_size,
    )
    return _clamav_pool


async def close_clamav_pool() -> None:
    """
    Close the global ClamAV connection pool.

    Should be called during application shutdown.
    """
    global _clamav_pool

    if _clamav_pool is not None:
        stats = _clamav_pool.stats
        await _clamav_pool.close()
        _clamav_pool = None
        logger.info("clamav_pool_closed", final_stats=stats)
