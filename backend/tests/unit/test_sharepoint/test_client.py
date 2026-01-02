"""Tests for SharePoint Graph API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.sharepoint.client import GraphClient
from app.core.sharepoint.exceptions import (
    SharePointAuthenticationError,
    SharePointError,
    SharePointNotFoundError,
    SharePointPermissionError,
    SharePointRateLimitError,
    SharePointUploadError,
)


class TestGraphClientInit:
    """Tests for GraphClient initialization."""

    def test_init_stores_auth_service(self):
        """GraphClient stores auth service reference."""
        mock_auth = MagicMock()
        client = GraphClient(mock_auth)

        assert client._auth is mock_auth
        assert client._client is None

    def test_init_sets_constants(self):
        """GraphClient has correct constants."""
        mock_auth = MagicMock()
        client = GraphClient(mock_auth)

        assert client.GRAPH_BASE_URL == "https://graph.microsoft.com/v1.0"
        assert client.CHUNK_SIZE == 5 * 1024 * 1024  # 5MB
        assert client.SIMPLE_UPLOAD_LIMIT == 4 * 1024 * 1024  # 4MB


class TestGraphClientGetClient:
    """Tests for _get_client method."""

    @pytest.mark.asyncio
    async def test_get_client_creates_httpx_client(self):
        """_get_client creates httpx.AsyncClient with auth token."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token_123")

        client = GraphClient(mock_auth)

        with patch("httpx.AsyncClient") as mock_async_client:
            await client._get_client()

            mock_async_client.assert_called_once()
            call_kwargs = mock_async_client.call_args[1]
            assert call_kwargs["base_url"] == "https://graph.microsoft.com/v1.0"
            assert call_kwargs["headers"]["Authorization"] == "Bearer test_token_123"

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing_client(self):
        """_get_client reuses existing client instance."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token_123")

        client = GraphClient(mock_auth)

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = MagicMock()
            client1 = await client._get_client()
            client2 = await client._get_client()

            # Should only create once
            mock_async_client.assert_called_once()
            assert client1 is client2


class TestGraphClientClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        """close() properly closes httpx client."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token")

        client = GraphClient(mock_auth)

        mock_httpx_client = AsyncMock()
        client._client = mock_httpx_client

        await client.close()

        mock_httpx_client.aclose.assert_called_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_handles_no_client(self):
        """close() handles case when client doesn't exist."""
        mock_auth = MagicMock()
        client = GraphClient(mock_auth)

        # Should not raise
        await client.close()


class TestGraphClientRequest:
    """Tests for _request method."""

    @pytest.fixture
    def mock_client_setup(self):
        """Setup mock auth and httpx client."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token")

        mock_httpx_client = AsyncMock()

        def setup_response(status_code, json_data=None, text="", headers=None):
            response = MagicMock()
            response.status_code = status_code
            response.json.return_value = json_data or {}
            response.text = text
            response.content = b""
            response.headers = headers or {}
            mock_httpx_client.request = AsyncMock(return_value=response)
            return response

        client = GraphClient(mock_auth)
        client._client = mock_httpx_client

        return client, mock_httpx_client, setup_response

    @pytest.mark.asyncio
    async def test_request_success_returns_response(self, mock_client_setup):
        """Successful request returns httpx response."""
        client, mock_httpx, setup_response = mock_client_setup
        response = setup_response(200, {"id": "item123"})

        result = await client._request("GET", "/drives/drv123/items/item123")

        assert result is response
        mock_httpx.request.assert_called_once_with(
            "GET", "/drives/drv123/items/item123"
        )

    @pytest.mark.asyncio
    async def test_request_401_raises_auth_error(self, mock_client_setup):
        """HTTP 401 raises SharePointAuthenticationError after retry."""
        client, mock_httpx, setup_response = mock_client_setup
        setup_response(401, text="Unauthorized")

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            await client._request("GET", "/test/path", retry_count=1)

        assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_403_raises_permission_error(self, mock_client_setup):
        """HTTP 403 raises SharePointPermissionError."""
        client, mock_httpx, setup_response = mock_client_setup
        setup_response(403, text="Forbidden")

        with pytest.raises(SharePointPermissionError) as exc_info:
            await client._request("GET", "/test/path")

        assert "Permission denied" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_404_raises_not_found_error(self, mock_client_setup):
        """HTTP 404 raises SharePointNotFoundError."""
        client, mock_httpx, setup_response = mock_client_setup
        setup_response(404, text="Not Found")

        with pytest.raises(SharePointNotFoundError) as exc_info:
            await client._request("GET", "/drives/drv/items/notfound")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_request_429_retries_then_raises_rate_limit(self, mock_client_setup):
        """HTTP 429 retries with Retry-After header, then raises."""
        client, mock_httpx, _ = mock_client_setup

        # Always return 429
        response = MagicMock()
        response.status_code = 429
        response.text = "Rate limit"
        response.headers = {"Retry-After": "1"}
        mock_httpx.request = AsyncMock(return_value=response)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            pytest.raises(SharePointRateLimitError) as exc_info,
        ):
            await client._request("GET", "/test", retry_count=2)

        # Should have retried twice (sleep called twice before failing)
        assert mock_sleep.call_count == 2
        assert exc_info.value.retry_after_seconds == 1

    @pytest.mark.asyncio
    async def test_request_5xx_retries_with_backoff(self, mock_client_setup):
        """HTTP 5xx errors retry with exponential backoff."""
        client, mock_httpx, _ = mock_client_setup

        # Always return 500
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        mock_httpx.request = AsyncMock(return_value=response)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            pytest.raises(SharePointError) as exc_info,
        ):
            await client._request("GET", "/test", retry_count=3)

        # Should have retried 3 times with exponential backoff
        assert mock_sleep.call_count == 3
        # Verify backoff: 1s, 2s, 4s
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)
        assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_connection_error_retries(self, mock_client_setup):
        """Connection errors retry with exponential backoff."""
        client, mock_httpx, _ = mock_client_setup

        mock_httpx.request = AsyncMock(
            side_effect=httpx.RequestError("Connection failed")
        )

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            pytest.raises(SharePointError) as exc_info,
        ):
            await client._request("GET", "/test", retry_count=2)

        assert mock_sleep.call_count == 2
        assert "Connection error" in str(exc_info.value)


class TestGraphClientUpload:
    """Tests for upload methods."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create GraphClient with mocked dependencies."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token")
        client = GraphClient(mock_auth)
        return client

    @pytest.mark.asyncio
    async def test_upload_small_success(self, mock_graph_client):
        """Small file upload uses simple PUT."""
        client = mock_graph_client
        content = b"test file content"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "item123", "name": "test.txt"}

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.upload_small(
                drive_id="drv123",
                folder_path="NPD/projects",
                filename="test.txt",
                content=content,
            )

            assert result["id"] == "item123"
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "PUT"
            assert "NPD/projects/test.txt" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_upload_small_rejects_large_file(self, mock_graph_client):
        """upload_small raises error for files > 4MB."""
        client = mock_graph_client
        large_content = b"x" * (5 * 1024 * 1024)  # 5MB

        with pytest.raises(SharePointUploadError) as exc_info:
            await client.upload_small(
                drive_id="drv123",
                folder_path="NPD/projects",
                filename="large.txt",
                content=large_content,
            )

        assert "exceeds simple upload limit" in str(exc_info.value)
        assert exc_info.value.filename == "large.txt"

    @pytest.mark.asyncio
    async def test_create_upload_session_returns_url(self, mock_graph_client):
        """create_upload_session returns upload URL."""
        client = mock_graph_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "uploadUrl": "https://upload.sharepoint.com/session123"
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            url = await client.create_upload_session(
                drive_id="drv123",
                folder_path="NPD/projects",
                filename="large.txt",
            )

            assert url == "https://upload.sharepoint.com/session123"

    @pytest.mark.asyncio
    async def test_create_upload_session_missing_url_raises(self, mock_graph_client):
        """create_upload_session raises if uploadUrl missing."""
        client = mock_graph_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No uploadUrl

        with (
            patch.object(client, "_request", new_callable=AsyncMock) as mock_request,
            pytest.raises(SharePointUploadError) as exc_info,
        ):
            mock_request.return_value = mock_response
            await client.create_upload_session("drv123", "folder", "file.txt")

        assert "missing uploadUrl" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_chunk_success(self, mock_graph_client):
        """upload_chunk successfully uploads chunk."""
        client = mock_graph_client
        chunk = b"chunk content"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_response.json.return_value = {"nextExpectedRanges": ["13-"]}
            mock_client.put = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await client.upload_chunk(
                upload_url="https://upload.sharepoint.com/session",
                content=chunk,
                start_byte=0,
                total_size=100,
            )

            assert "nextExpectedRanges" in result
            mock_client.put.assert_called_once()
            call_kwargs = mock_client.put.call_args[1]
            assert "Content-Range" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Content-Range"] == "bytes 0-12/100"

    @pytest.mark.asyncio
    async def test_upload_chunk_final_returns_item(self, mock_graph_client):
        """Final chunk returns item metadata."""
        client = mock_graph_client
        chunk = b"final chunk"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 201  # Complete
            mock_response.json.return_value = {"id": "item123", "name": "file.txt"}
            mock_client.put = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await client.upload_chunk(
                upload_url="https://upload.sharepoint.com/session",
                content=chunk,
                start_byte=90,
                total_size=100,
            )

            assert result["id"] == "item123"


class TestGraphClientDownload:
    """Tests for download methods."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create GraphClient with mocked dependencies."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token")
        client = GraphClient(mock_auth)
        return client

    @pytest.mark.asyncio
    async def test_download_returns_bytes(self, mock_graph_client):
        """download returns file content as bytes."""
        client = mock_graph_client
        file_content = b"file content here"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = file_content

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.download("drv123", "item123")

            assert result == file_content
            mock_request.assert_called_once_with(
                "GET", "/drives/drv123/items/item123/content"
            )

    @pytest.mark.asyncio
    async def test_download_not_found_raises(self, mock_graph_client):
        """download raises SharePointNotFoundError for missing file."""
        client = mock_graph_client

        with (
            patch.object(
                client, "_request", side_effect=SharePointNotFoundError("Not found")
            ),
            pytest.raises(SharePointNotFoundError),
        ):
            await client.download("drv123", "nonexistent")


class TestGraphClientDelete:
    """Tests for delete method."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create GraphClient with mocked dependencies."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token")
        client = GraphClient(mock_auth)
        return client

    @pytest.mark.asyncio
    async def test_delete_returns_true(self, mock_graph_client):
        """delete returns True on success."""
        client = mock_graph_client

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.delete("drv123", "item123")

            assert result is True
            mock_request.assert_called_once_with(
                "DELETE", "/drives/drv123/items/item123"
            )

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, mock_graph_client):
        """delete raises SharePointNotFoundError for missing file."""
        client = mock_graph_client

        with (
            patch.object(
                client, "_request", side_effect=SharePointNotFoundError("Not found")
            ),
            pytest.raises(SharePointNotFoundError),
        ):
            await client.delete("drv123", "nonexistent")


class TestGraphClientGetItem:
    """Tests for get_item method."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create GraphClient with mocked dependencies."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token")
        client = GraphClient(mock_auth)
        return client

    @pytest.mark.asyncio
    async def test_get_item_returns_metadata(self, mock_graph_client):
        """get_item returns item metadata."""
        client = mock_graph_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "item123",
            "name": "test.txt",
            "size": 1024,
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.get_item("drv123", "item123")

            assert result["id"] == "item123"
            assert result["name"] == "test.txt"

    @pytest.mark.asyncio
    async def test_get_item_returns_none_for_not_found(self, mock_graph_client):
        """get_item returns None for non-existent item."""
        client = mock_graph_client

        with patch.object(
            client, "_request", side_effect=SharePointNotFoundError("Not found")
        ):
            result = await client.get_item("drv123", "nonexistent")

            assert result is None


class TestGraphClientEnsureFolder:
    """Tests for ensure_folder method."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create GraphClient with mocked dependencies."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token")
        client = GraphClient(mock_auth)
        return client

    @pytest.mark.asyncio
    async def test_ensure_folder_creates_nested_folders(self, mock_graph_client):
        """ensure_folder creates nested folder structure."""
        client = mock_graph_client

        # Track calls to understand folder creation
        call_count = [0]
        created_folders = []

        async def mock_request(method, path, **kwargs):
            call_count[0] += 1
            response = MagicMock()

            if method == "GET":
                # First folder exists, others don't
                if "NPD" in path and "projects" not in path:
                    response.status_code = 200
                    response.json.return_value = {"id": "folder_npd"}
                    return response
                else:
                    raise SharePointNotFoundError("Not found")
            elif method == "POST":
                name = kwargs.get("json", {}).get("name", "")
                created_folders.append(name)
                response.status_code = 201
                response.json.return_value = {"id": f"folder_{name}"}
                return response

            return response

        with patch.object(client, "_request", side_effect=mock_request):
            result = await client.ensure_folder("drv123", "NPD/projects/abc-123")

            # Should have created projects and abc-123 folders
            assert "projects" in created_folders
            assert "abc-123" in created_folders
            assert result == "folder_abc-123"

    @pytest.mark.asyncio
    async def test_ensure_folder_returns_existing_folder_id(self, mock_graph_client):
        """ensure_folder returns ID of existing folder."""
        client = mock_graph_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "existing_folder_123"}

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await client.ensure_folder("drv123", "existing")

            assert result == "existing_folder_123"


class TestGraphClientUploadLarge:
    """Tests for upload_large method (chunked upload)."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create GraphClient with mocked dependencies."""
        mock_auth = MagicMock()
        mock_auth.get_app_token = AsyncMock(return_value="test_token")
        client = GraphClient(mock_auth)
        return client

    @pytest.mark.asyncio
    async def test_upload_large_uses_chunked_upload(self, mock_graph_client):
        """upload_large creates session and uploads chunks."""
        client = mock_graph_client

        # 10MB file - will need 2 chunks
        content = b"x" * (10 * 1024 * 1024)

        with (
            patch.object(
                client,
                "create_upload_session",
                new_callable=AsyncMock,
                return_value="https://upload.sharepoint.com/session",
            ) as mock_session,
            patch.object(
                client,
                "upload_chunk",
                new_callable=AsyncMock,
                return_value={"id": "item123"},
            ) as mock_chunk,
        ):
            result = await client.upload_large("drv123", "folder", "large.bin", content)

            # Should have created session
            mock_session.assert_called_once_with("drv123", "folder", "large.bin")

            # Should have uploaded 2 chunks (5MB each)
            assert mock_chunk.call_count == 2
            assert result["id"] == "item123"

    @pytest.mark.asyncio
    async def test_upload_large_handles_progress(self, mock_graph_client):
        """upload_large tracks progress correctly."""
        client = mock_graph_client

        # 7MB file - will need 2 chunks (5MB + 2MB)
        content = b"x" * (7 * 1024 * 1024)
        chunk_calls = []

        async def track_chunks(url, chunk, start, total):
            chunk_calls.append({"start": start, "size": len(chunk)})
            return {"id": "item123"} if start + len(chunk) >= total else {}

        with (
            patch.object(
                client,
                "create_upload_session",
                new_callable=AsyncMock,
                return_value="https://upload.sharepoint.com/session",
            ),
            patch.object(client, "upload_chunk", side_effect=track_chunks),
        ):
            await client.upload_large("drv123", "folder", "file.bin", content)

            # First chunk: 0-5MB
            assert chunk_calls[0]["start"] == 0
            assert chunk_calls[0]["size"] == 5 * 1024 * 1024

            # Second chunk: 5MB-7MB
            assert chunk_calls[1]["start"] == 5 * 1024 * 1024
            assert chunk_calls[1]["size"] == 2 * 1024 * 1024
