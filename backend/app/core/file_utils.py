"""File handling utilities with security best practices."""

import tempfile
from typing import IO

from fastapi import HTTPException, UploadFile, status


async def read_file_with_size_limit(
    file: UploadFile,
    max_size_bytes: int,
    chunk_size: int = 64 * 1024,
) -> bytes:
    """
    Read file content with streaming size validation.

    Prevents memory exhaustion by validating file size before/during read.
    Uses Content-Length header when available, falls back to chunked reading.

    This function addresses a critical security vulnerability where reading
    the entire file into memory before checking size could allow DoS attacks
    via large file uploads.

    Args:
        file: FastAPI UploadFile object
        max_size_bytes: Maximum allowed file size in bytes
        chunk_size: Size of chunks to read (default 64KB)

    Returns:
        File content as bytes

    Raises:
        HTTPException: 413 if file exceeds max_size_bytes
    """
    # Check Content-Length header if available (fast path)
    if file.size is not None and file.size > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_mb:.0f}MB",
        )

    # Read file in chunks to handle cases where Content-Length is missing/untrusted
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break

        total_size += len(chunk)

        if total_size > max_size_bytes:
            # File exceeds limit - reject without reading more
            max_mb = max_size_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {max_mb:.0f}MB",
            )

        chunks.append(chunk)

    return b"".join(chunks)


async def read_file_with_spooling(
    file: UploadFile,
    max_size_bytes: int,
    spool_threshold: int = 5 * 1024 * 1024,  # 5MB default
    chunk_size: int = 64 * 1024,
) -> IO[bytes]:
    """
    Read file content with streaming size validation and disk spooling.

    Files smaller than spool_threshold stay in memory (SpooledTemporaryFile).
    Larger files automatically spill to disk, reducing memory pressure.

    IMPORTANT: Caller is responsible for closing the returned file object.

    Args:
        file: FastAPI UploadFile object
        max_size_bytes: Maximum allowed file size in bytes
        spool_threshold: Size threshold for disk spillover (default 5MB)
        chunk_size: Size of chunks to read (default 64KB)

    Returns:
        SpooledTemporaryFile containing file content

    Raises:
        HTTPException: 413 if file exceeds max_size_bytes
    """
    # Check Content-Length header if available (fast path)
    if file.size is not None and file.size > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_mb:.0f}MB",
        )

    # Intentionally not using context manager - file is returned to caller
    spooled = tempfile.SpooledTemporaryFile(  # noqa: SIM115
        max_size=spool_threshold, mode="w+b"
    )
    total_size = 0

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break

            total_size += len(chunk)

            if total_size > max_size_bytes:
                spooled.close()
                max_mb = max_size_bytes / (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum size is {max_mb:.0f}MB",
                )

            spooled.write(chunk)

        # Reset to beginning for reading
        spooled.seek(0)
        return spooled
    except HTTPException:
        raise
    except Exception:
        spooled.close()
        raise
