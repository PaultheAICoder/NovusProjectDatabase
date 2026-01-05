"""Microsoft Graph API client wrapper for SharePoint file operations.

Provides low-level HTTP operations for SharePoint via Graph API with:
- Automatic retry with exponential backoff for transient errors
- Rate limit handling (HTTP 429) with Retry-After header support
- Chunked upload for large files (> 4MB)
- Proper error mapping to SharePoint exception classes
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.logging import get_logger
from app.core.sharepoint.auth import SharePointAuthService
from app.core.sharepoint.exceptions import (
    SharePointAuthenticationError,
    SharePointError,
    SharePointNotFoundError,
    SharePointPermissionError,
    SharePointRateLimitError,
    SharePointUploadError,
)

logger = get_logger(__name__)


class GraphClient:
    """Low-level Microsoft Graph API client with retry and throttling.

    Provides direct access to Graph API endpoints for SharePoint file
    operations including upload, download, delete, and folder management.

    Attributes:
        GRAPH_BASE_URL: Base URL for Microsoft Graph API v1.0
        CHUNK_SIZE: Size of chunks for large file uploads (5MB)
        SIMPLE_UPLOAD_LIMIT: Maximum size for simple PUT upload (4MB)
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks for upload
    SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024  # 4MB limit for simple PUT

    def __init__(self, auth_service: SharePointAuthService) -> None:
        """Initialize Graph client with authentication service.

        Args:
            auth_service: SharePointAuthService for token acquisition
        """
        self._auth = auth_service
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with current auth token.

        Returns:
            Configured httpx.AsyncClient with authorization header
        """
        if self._client is None:
            token = await self._auth.get_app_token()
            self._client = httpx.AsyncClient(
                base_url=self.GRAPH_BASE_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def _refresh_token(self) -> None:
        """Refresh the auth token and recreate the client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        # Next call to _get_client will create a new client with fresh token

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("graph_client_closed")

    async def _request(
        self,
        method: str,
        path: str,
        retry_count: int = 3,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make HTTP request with retry and error handling.

        Implements retry logic for:
        - HTTP 429 (rate limit): Uses Retry-After header
        - HTTP 5xx (server errors): Exponential backoff (1s, 2s, 4s)
        - Connection errors: Exponential backoff

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., /drives/{drive-id}/items/{item-id})
            retry_count: Maximum number of retries (default: 3)
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response on success

        Raises:
            SharePointAuthenticationError: On HTTP 401
            SharePointPermissionError: On HTTP 403
            SharePointNotFoundError: On HTTP 404
            SharePointRateLimitError: On HTTP 429 after retries exhausted
            SharePointError: On other errors after retries exhausted
        """
        client = await self._get_client()
        last_exception: Exception | None = None

        for attempt in range(retry_count + 1):
            try:
                logger.debug(
                    "graph_request_attempt",
                    method=method,
                    path=path,
                    attempt=attempt + 1,
                    max_attempts=retry_count + 1,
                )

                response = await client.request(method, path, **kwargs)

                # Handle specific status codes
                if response.status_code == 401:
                    # Try to refresh token once
                    if attempt == 0:
                        logger.warning(
                            "graph_token_expired_refreshing",
                            path=path,
                        )
                        await self._refresh_token()
                        client = await self._get_client()
                        continue
                    logger.error(
                        "graph_authentication_error",
                        path=path,
                        status_code=response.status_code,
                    )
                    raise SharePointAuthenticationError(
                        f"Authentication failed: {response.text}"
                    )

                if response.status_code == 403:
                    logger.error(
                        "graph_permission_error",
                        path=path,
                        status_code=response.status_code,
                    )
                    raise SharePointPermissionError(
                        f"Permission denied: {response.text}"
                    )

                if response.status_code == 404:
                    logger.warning(
                        "graph_not_found",
                        path=path,
                        status_code=response.status_code,
                    )
                    raise SharePointNotFoundError(f"Resource not found: {path}")

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    if attempt < retry_count:
                        logger.warning(
                            "graph_rate_limit_retrying",
                            path=path,
                            retry_after=retry_after,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    logger.error(
                        "graph_rate_limit_exhausted",
                        path=path,
                        retry_after=retry_after,
                    )
                    raise SharePointRateLimitError(
                        "Rate limit exceeded",
                        retry_after_seconds=retry_after,
                    )

                if response.status_code >= 500:
                    if attempt < retry_count:
                        delay = 2**attempt  # Exponential backoff: 1, 2, 4 seconds
                        logger.warning(
                            "graph_server_error_retrying",
                            path=path,
                            status_code=response.status_code,
                            delay=delay,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error(
                        "graph_server_error_exhausted",
                        path=path,
                        status_code=response.status_code,
                    )
                    raise SharePointError(
                        f"Server error {response.status_code}: {response.text}"
                    )

                # Check for other error status codes
                if response.status_code >= 400:
                    logger.error(
                        "graph_client_error",
                        path=path,
                        status_code=response.status_code,
                        response=response.text[:500],
                    )
                    raise SharePointError(
                        f"Graph API error {response.status_code}: {response.text}"
                    )

                logger.debug(
                    "graph_request_success",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                )
                return response

            except httpx.RequestError as e:
                last_exception = e
                if attempt < retry_count:
                    delay = 2**attempt  # Exponential backoff
                    logger.warning(
                        "graph_connection_error_retrying",
                        path=path,
                        error=str(e),
                        delay=delay,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(
                    "graph_connection_error_exhausted",
                    path=path,
                    error=str(e),
                )
                raise SharePointError(
                    f"Connection error after {retry_count + 1} attempts: {e}"
                ) from e

        # Should not reach here, but handle edge case
        raise SharePointError(
            f"Request failed after {retry_count + 1} attempts"
        ) from last_exception

    async def upload_small(
        self,
        drive_id: str,
        folder_path: str,
        filename: str,
        content: bytes,
    ) -> dict[str, Any]:
        """Upload file <= 4MB using simple PUT.

        Args:
            drive_id: SharePoint drive ID
            folder_path: Path to folder (e.g., /NPD/projects/uuid)
            filename: Name for the uploaded file
            content: File content as bytes

        Returns:
            Graph API response with item metadata including id

        Raises:
            SharePointUploadError: If upload fails
            SharePointError: For other Graph API errors
        """
        if len(content) > self.SIMPLE_UPLOAD_LIMIT:
            raise SharePointUploadError(
                f"File size {len(content)} exceeds simple upload limit of {self.SIMPLE_UPLOAD_LIMIT}",
                filename=filename,
            )

        # Ensure folder path is properly formatted
        folder_path = folder_path.strip("/")
        path = f"/drives/{drive_id}/root:/{folder_path}/{filename}:/content"

        logger.info(
            "graph_upload_small_start",
            drive_id=drive_id,
            folder_path=folder_path,
            filename=filename,
            size=len(content),
        )

        try:
            # Ensure client is ready before getting token for headers
            await self._get_client()
            token = await self._auth.get_app_token()

            response = await self._request(
                "PUT",
                path,
                content=content,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/octet-stream",
                },
            )

            result = response.json()
            logger.info(
                "graph_upload_small_success",
                drive_id=drive_id,
                filename=filename,
                item_id=result.get("id"),
            )
            return result

        except (
            SharePointError,
            SharePointAuthenticationError,
            SharePointPermissionError,
        ):
            raise
        except httpx.RequestError as e:
            # Network/connection errors during upload
            logger.error(
                "graph_upload_small_error",
                drive_id=drive_id,
                filename=filename,
                error=str(e),
            )
            raise SharePointUploadError(
                f"Failed to upload {filename}: {e}",
                filename=filename,
            ) from e
        except Exception as e:
            # Unexpected errors - wrap in SharePointUploadError with context
            logger.error(
                "graph_upload_small_unexpected_error",
                drive_id=drive_id,
                filename=filename,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise SharePointUploadError(
                f"Unexpected error uploading {filename}: {e}",
                filename=filename,
            ) from e

    async def create_upload_session(
        self,
        drive_id: str,
        folder_path: str,
        filename: str,
    ) -> str:
        """Create upload session for large file (> 4MB).

        Args:
            drive_id: SharePoint drive ID
            folder_path: Path to folder (e.g., /NPD/projects/uuid)
            filename: Name for the uploaded file

        Returns:
            Upload URL for chunked upload

        Raises:
            SharePointUploadError: If session creation fails
        """
        folder_path = folder_path.strip("/")
        path = f"/drives/{drive_id}/root:/{folder_path}/{filename}:/createUploadSession"

        logger.info(
            "graph_upload_session_create",
            drive_id=drive_id,
            folder_path=folder_path,
            filename=filename,
        )

        try:
            response = await self._request(
                "POST",
                path,
                json={
                    "item": {
                        "@microsoft.graph.conflictBehavior": "replace",
                        "name": filename,
                    }
                },
            )

            result = response.json()
            upload_url = result.get("uploadUrl")

            if not upload_url:
                raise SharePointUploadError(
                    "Upload session response missing uploadUrl",
                    filename=filename,
                )

            logger.info(
                "graph_upload_session_created",
                drive_id=drive_id,
                filename=filename,
            )
            return upload_url

        except (SharePointError, SharePointUploadError):
            raise
        except httpx.RequestError as e:
            # Network/connection errors during session creation
            logger.error(
                "graph_upload_session_error",
                drive_id=drive_id,
                filename=filename,
                error=str(e),
            )
            raise SharePointUploadError(
                f"Failed to create upload session for {filename}: {e}",
                filename=filename,
            ) from e
        except Exception as e:
            # Unexpected errors - wrap in SharePointUploadError with context
            logger.error(
                "graph_upload_session_unexpected_error",
                drive_id=drive_id,
                filename=filename,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise SharePointUploadError(
                f"Unexpected error creating upload session for {filename}: {e}",
                filename=filename,
            ) from e

    async def upload_chunk(
        self,
        upload_url: str,
        content: bytes,
        start_byte: int,
        total_size: int,
    ) -> dict[str, Any]:
        """Upload a chunk to an existing upload session.

        Args:
            upload_url: URL from create_upload_session
            content: Chunk content as bytes
            start_byte: Starting byte position in file
            total_size: Total file size

        Returns:
            Graph API response (final chunk includes item metadata)

        Raises:
            SharePointUploadError: If chunk upload fails
        """
        end_byte = start_byte + len(content) - 1
        content_range = f"bytes {start_byte}-{end_byte}/{total_size}"

        logger.debug(
            "graph_upload_chunk",
            start_byte=start_byte,
            end_byte=end_byte,
            total_size=total_size,
            chunk_size=len(content),
        )

        try:
            # Upload session uses its own URL, not base URL
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.put(
                    upload_url,
                    content=content,
                    headers={
                        "Content-Length": str(len(content)),
                        "Content-Range": content_range,
                    },
                )

                if response.status_code == 202:
                    # More chunks expected
                    return response.json()
                elif response.status_code in (200, 201):
                    # Upload complete
                    result = response.json()
                    logger.info(
                        "graph_upload_chunk_complete",
                        item_id=result.get("id"),
                    )
                    return result
                else:
                    raise SharePointUploadError(
                        f"Chunk upload failed with status {response.status_code}: {response.text}",
                        bytes_uploaded=start_byte,
                    )

        except httpx.RequestError as e:
            logger.error(
                "graph_upload_chunk_error",
                start_byte=start_byte,
                error=str(e),
            )
            raise SharePointUploadError(
                f"Failed to upload chunk: {e}",
                bytes_uploaded=start_byte,
            ) from e

    async def upload_large(
        self,
        drive_id: str,
        folder_path: str,
        filename: str,
        content: bytes,
    ) -> dict[str, Any]:
        """Upload large file using chunked upload session.

        Args:
            drive_id: SharePoint drive ID
            folder_path: Path to folder
            filename: Name for the uploaded file
            content: File content as bytes

        Returns:
            Graph API response with item metadata including id

        Raises:
            SharePointUploadError: If upload fails
        """
        total_size = len(content)
        logger.info(
            "graph_upload_large_start",
            drive_id=drive_id,
            folder_path=folder_path,
            filename=filename,
            size=total_size,
        )

        # Create upload session
        upload_url = await self.create_upload_session(drive_id, folder_path, filename)

        # Upload chunks
        uploaded = 0
        result: dict[str, Any] = {}

        while uploaded < total_size:
            chunk_end = min(uploaded + self.CHUNK_SIZE, total_size)
            chunk = content[uploaded:chunk_end]

            result = await self.upload_chunk(upload_url, chunk, uploaded, total_size)
            uploaded = chunk_end

            logger.debug(
                "graph_upload_large_progress",
                uploaded=uploaded,
                total=total_size,
                percent=round(uploaded / total_size * 100, 1),
            )

        logger.info(
            "graph_upload_large_success",
            drive_id=drive_id,
            filename=filename,
            item_id=result.get("id"),
        )
        return result

    async def download(
        self,
        drive_id: str,
        item_id: str,
    ) -> bytes:
        """Download file content by item ID.

        Args:
            drive_id: SharePoint drive ID
            item_id: SharePoint item ID

        Returns:
            File content as bytes

        Raises:
            SharePointNotFoundError: If file does not exist
            SharePointError: For other errors
        """
        path = f"/drives/{drive_id}/items/{item_id}/content"

        logger.info(
            "graph_download_start",
            drive_id=drive_id,
            item_id=item_id,
        )

        response = await self._request("GET", path)

        logger.info(
            "graph_download_success",
            drive_id=drive_id,
            item_id=item_id,
            size=len(response.content),
        )
        return response.content

    async def download_stream(
        self,
        drive_id: str,
        item_id: str,
        chunk_size: int = 1024 * 1024,  # 1MB chunks
    ) -> AsyncIterator[bytes]:
        """Stream download for large files.

        Args:
            drive_id: SharePoint drive ID
            item_id: SharePoint item ID
            chunk_size: Size of chunks to yield (default 1MB)

        Yields:
            File content in chunks

        Raises:
            SharePointNotFoundError: If file does not exist
            SharePointError: For other errors
        """
        path = f"/drives/{drive_id}/items/{item_id}/content"

        logger.info(
            "graph_download_stream_start",
            drive_id=drive_id,
            item_id=item_id,
        )

        client = await self._get_client()
        token = await self._auth.get_app_token()

        async with client.stream(
            "GET",
            path,
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            if response.status_code == 404:
                raise SharePointNotFoundError(f"Item not found: {item_id}")
            if response.status_code >= 400:
                raise SharePointError(
                    f"Download failed with status {response.status_code}"
                )

            async for chunk in response.aiter_bytes(chunk_size):
                yield chunk

        logger.info(
            "graph_download_stream_complete",
            drive_id=drive_id,
            item_id=item_id,
        )

    async def delete(
        self,
        drive_id: str,
        item_id: str,
    ) -> bool:
        """Delete file (soft-delete to recycle bin).

        Args:
            drive_id: SharePoint drive ID
            item_id: SharePoint item ID

        Returns:
            True if deletion successful

        Raises:
            SharePointNotFoundError: If file does not exist
            SharePointPermissionError: If not authorized to delete
            SharePointError: For other errors
        """
        path = f"/drives/{drive_id}/items/{item_id}"

        logger.info(
            "graph_delete_start",
            drive_id=drive_id,
            item_id=item_id,
        )

        response = await self._request("DELETE", path)

        # 204 No Content is success for DELETE
        if response.status_code in (204, 200):
            logger.info(
                "graph_delete_success",
                drive_id=drive_id,
                item_id=item_id,
            )
            return True

        return False

    async def get_item(
        self,
        drive_id: str,
        item_id: str,
    ) -> dict[str, Any] | None:
        """Get item metadata by ID.

        Args:
            drive_id: SharePoint drive ID
            item_id: SharePoint item ID

        Returns:
            Item metadata dict, or None if not found

        Raises:
            SharePointError: For errors other than 404
        """
        path = f"/drives/{drive_id}/items/{item_id}"

        logger.debug(
            "graph_get_item",
            drive_id=drive_id,
            item_id=item_id,
        )

        try:
            response = await self._request("GET", path)
            return response.json()
        except SharePointNotFoundError:
            return None

    async def ensure_folder(
        self,
        drive_id: str,
        folder_path: str,
    ) -> str:
        """Ensure folder exists, create if needed.

        Creates nested folders as needed (e.g., /NPD/projects/uuid).

        Args:
            drive_id: SharePoint drive ID
            folder_path: Path to ensure exists (e.g., NPD/projects/uuid)

        Returns:
            Folder item ID

        Raises:
            SharePointError: If folder creation fails
        """
        folder_path = folder_path.strip("/")
        parts = folder_path.split("/")

        logger.info(
            "graph_ensure_folder",
            drive_id=drive_id,
            folder_path=folder_path,
        )

        current_path = ""
        folder_id = "root"

        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part

            # Check if folder exists
            check_path = f"/drives/{drive_id}/root:/{current_path}"
            try:
                response = await self._request("GET", check_path)
                result = response.json()
                folder_id = result.get("id", folder_id)
                logger.debug(
                    "graph_folder_exists",
                    path=current_path,
                    folder_id=folder_id,
                )
            except SharePointNotFoundError:
                # Create folder
                create_path = f"/drives/{drive_id}/items/{folder_id}/children"
                response = await self._request(
                    "POST",
                    create_path,
                    json={
                        "name": part,
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "fail",
                    },
                )
                result = response.json()
                folder_id = result.get("id", folder_id)
                logger.info(
                    "graph_folder_created",
                    path=current_path,
                    folder_id=folder_id,
                )

        return folder_id
