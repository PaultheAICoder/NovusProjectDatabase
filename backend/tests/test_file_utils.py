"""Tests for file handling utilities."""

import io
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from app.core.file_utils import read_file_with_size_limit, read_file_with_spooling


class TestReadFileWithSizeLimit:
    """Tests for streaming file size validation.

    These tests verify the fix for the memory exhaustion DoS vulnerability
    (GitHub Issue #77) where large file uploads could exhaust server memory
    before size validation occurred.
    """

    @pytest.mark.asyncio
    async def test_small_file_reads_successfully(self):
        """Files under the limit should read successfully."""
        content = b"small file content"
        file = self._create_mock_upload(content, size=len(content))

        result = await read_file_with_size_limit(file, max_size_bytes=1024)

        assert result == content

    @pytest.mark.asyncio
    async def test_rejects_file_exceeding_content_length(self):
        """Files with Content-Length exceeding limit should be rejected immediately."""
        # Create a file that claims to be 100MB via Content-Length
        file = self._create_mock_upload(b"", size=100 * 1024 * 1024)

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_size_limit(file, max_size_bytes=50 * 1024 * 1024)

        assert exc_info.value.status_code == 413
        assert "File too large" in exc_info.value.detail
        assert "50MB" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejects_file_exceeding_limit_during_streaming(self):
        """Files that exceed limit during read should be rejected mid-stream."""
        # Simulate file with no Content-Length that exceeds limit
        large_content = b"x" * (2 * 1024 * 1024)  # 2MB
        file = self._create_mock_upload(large_content, size=None)

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_size_limit(
                file, max_size_bytes=1 * 1024 * 1024
            )  # 1MB limit

        assert exc_info.value.status_code == 413
        assert "File too large" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_empty_file_returns_empty_bytes(self):
        """Empty files should return empty bytes."""
        file = self._create_mock_upload(b"", size=0)

        result = await read_file_with_size_limit(file, max_size_bytes=1024)

        assert result == b""

    @pytest.mark.asyncio
    async def test_exact_limit_file_accepted(self):
        """Files exactly at the limit should be accepted."""
        content = b"x" * 1024  # Exactly 1KB
        file = self._create_mock_upload(content, size=len(content))

        result = await read_file_with_size_limit(file, max_size_bytes=1024)

        assert result == content

    @pytest.mark.asyncio
    async def test_file_one_byte_over_limit_rejected(self):
        """Files one byte over the limit should be rejected."""
        content = b"x" * 1025  # 1 byte over 1KB
        file = self._create_mock_upload(content, size=len(content))

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_size_limit(file, max_size_bytes=1024)

        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_file_without_content_length_validates_during_read(self):
        """Files without Content-Length header should still be size-validated during read."""
        # This is the key regression test - if Content-Length is spoofed or missing,
        # the streaming validation must still catch oversized files
        content = b"x" * 2048  # 2KB
        file = self._create_mock_upload(content, size=None)  # No Content-Length

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_size_limit(file, max_size_bytes=1024)

        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_custom_chunk_size_works(self):
        """Custom chunk sizes should work correctly."""
        content = b"hello world" * 100  # 1100 bytes
        file = self._create_mock_upload(content, size=len(content))

        # Use small chunk size to test multiple reads
        result = await read_file_with_size_limit(
            file, max_size_bytes=2000, chunk_size=100
        )

        assert result == content

    @pytest.mark.asyncio
    async def test_error_message_shows_limit_in_mb(self):
        """Error messages should show the limit in MB, not bytes."""
        file = self._create_mock_upload(b"", size=100 * 1024 * 1024)  # 100MB

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_size_limit(
                file, max_size_bytes=10 * 1024 * 1024
            )  # 10MB limit

        assert exc_info.value.status_code == 413
        assert "10MB" in exc_info.value.detail
        assert "bytes" not in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_spoofed_content_length_caught_during_streaming(self):
        """Files with spoofed Content-Length (claims small, actually large) are caught."""
        # File claims to be 500 bytes but is actually 2KB
        large_content = b"x" * 2048
        file = self._create_mock_upload(large_content, size=500)  # Spoofed size

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_size_limit(file, max_size_bytes=1024)

        assert exc_info.value.status_code == 413

    def _create_mock_upload(self, content: bytes, size: int | None) -> UploadFile:
        """Create a mock UploadFile for testing.

        Args:
            content: The actual file content
            size: The Content-Length value (can be None to simulate missing header)

        Returns:
            A mock UploadFile that behaves like a real upload
        """
        file = MagicMock(spec=UploadFile)
        file.size = size

        # Mock read() to return content in chunks then empty
        buffer = io.BytesIO(content)

        async def mock_read(chunk_size: int | None = None) -> bytes:
            if chunk_size:
                return buffer.read(chunk_size)
            return buffer.read()

        file.read = mock_read
        return file


class TestReadFileWithSpooling:
    """Tests for spooled file reading with disk spillover."""

    @pytest.mark.asyncio
    async def test_small_file_stays_in_memory(self):
        """Files under spool threshold should remain in memory."""
        content = b"small file content"
        file = self._create_mock_upload(content, size=len(content))

        result = await read_file_with_spooling(
            file, max_size_bytes=1024, spool_threshold=1024
        )

        try:
            # SpooledTemporaryFile._rolled indicates if it spilled to disk
            assert not result._rolled
            assert result.read() == content
        finally:
            result.close()

    @pytest.mark.asyncio
    async def test_large_file_spills_to_disk(self):
        """Files over spool threshold should spill to disk."""
        content = b"x" * (2 * 1024 * 1024)  # 2MB
        file = self._create_mock_upload(content, size=len(content))

        result = await read_file_with_spooling(
            file,
            max_size_bytes=10 * 1024 * 1024,
            spool_threshold=1024 * 1024,  # 1MB threshold
        )

        try:
            assert result._rolled  # Should have spilled to disk
            assert result.read() == content
        finally:
            result.close()

    @pytest.mark.asyncio
    async def test_rejects_oversized_file_via_content_length(self):
        """Files exceeding max size should be rejected early via Content-Length."""
        file = self._create_mock_upload(b"", size=100 * 1024 * 1024)

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_spooling(file, max_size_bytes=50 * 1024 * 1024)

        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_rejects_oversized_file_during_streaming(self):
        """Files that exceed limit during read should be rejected."""
        content = b"x" * (2 * 1024 * 1024)  # 2MB
        file = self._create_mock_upload(content, size=None)  # No Content-Length

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_spooling(file, max_size_bytes=1 * 1024 * 1024)

        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_file_position_at_start_after_read(self):
        """Returned file should be positioned at start."""
        content = b"test content"
        file = self._create_mock_upload(content, size=len(content))

        result = await read_file_with_spooling(file, max_size_bytes=1024)

        try:
            assert result.tell() == 0
        finally:
            result.close()

    @pytest.mark.asyncio
    async def test_empty_file_returns_empty_spooled_file(self):
        """Empty files should return empty spooled file."""
        file = self._create_mock_upload(b"", size=0)

        result = await read_file_with_spooling(file, max_size_bytes=1024)

        try:
            assert result.read() == b""
        finally:
            result.close()

    @pytest.mark.asyncio
    async def test_exact_limit_file_accepted(self):
        """Files exactly at the limit should be accepted."""
        content = b"x" * 1024  # Exactly 1KB
        file = self._create_mock_upload(content, size=len(content))

        result = await read_file_with_spooling(file, max_size_bytes=1024)

        try:
            assert result.read() == content
        finally:
            result.close()

    @pytest.mark.asyncio
    async def test_file_one_byte_over_limit_rejected(self):
        """Files one byte over the limit should be rejected."""
        content = b"x" * 1025  # 1 byte over 1KB
        file = self._create_mock_upload(content, size=len(content))

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_spooling(file, max_size_bytes=1024)

        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_custom_chunk_size_works(self):
        """Custom chunk sizes should work correctly."""
        content = b"hello world" * 100  # 1100 bytes
        file = self._create_mock_upload(content, size=len(content))

        # Use small chunk size to test multiple reads
        result = await read_file_with_spooling(
            file, max_size_bytes=2000, chunk_size=100
        )

        try:
            assert result.read() == content
        finally:
            result.close()

    @pytest.mark.asyncio
    async def test_spoofed_content_length_caught_during_streaming(self):
        """Files with spoofed Content-Length (claims small, actually large) are caught."""
        # File claims to be 500 bytes but is actually 2KB
        large_content = b"x" * 2048
        file = self._create_mock_upload(large_content, size=500)  # Spoofed size

        with pytest.raises(HTTPException) as exc_info:
            await read_file_with_spooling(file, max_size_bytes=1024)

        assert exc_info.value.status_code == 413

    def _create_mock_upload(self, content: bytes, size: int | None) -> UploadFile:
        """Create a mock UploadFile for testing.

        Args:
            content: The actual file content
            size: The Content-Length value (can be None to simulate missing header)

        Returns:
            A mock UploadFile that behaves like a real upload
        """
        file = MagicMock(spec=UploadFile)
        file.size = size

        # Mock read() to return content in chunks then empty
        buffer = io.BytesIO(content)

        async def mock_read(chunk_size: int | None = None) -> bytes:
            if chunk_size:
                return buffer.read(chunk_size)
            return buffer.read()

        file.read = mock_read
        return file
