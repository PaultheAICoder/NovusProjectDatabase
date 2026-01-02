"""Tests for SharePoint storage adapter."""

import io
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.core.sharepoint.adapter import SharePointStorageAdapter
from app.core.sharepoint.client import GraphClient
from app.core.sharepoint.exceptions import (
    SharePointError,
    SharePointNotFoundError,
)


class TestSharePointStorageAdapterInit:
    """Tests for SharePointStorageAdapter initialization."""

    def test_init_stores_drive_id(self):
        """Initialization stores drive_id."""
        adapter = SharePointStorageAdapter(drive_id="drv123")

        assert adapter._drive_id == "drv123"
        assert adapter.drive_id == "drv123"

    def test_init_stores_base_folder(self):
        """Initialization stores base_folder."""
        adapter = SharePointStorageAdapter(
            drive_id="drv123",
            base_folder="/Custom/Path",
        )

        assert adapter._base_folder == "/Custom/Path"
        assert adapter.base_folder == "/Custom/Path"

    def test_init_default_base_folder(self):
        """Initialization uses default base_folder."""
        adapter = SharePointStorageAdapter(drive_id="drv123")

        assert adapter._base_folder == "/NPD/projects"

    def test_init_strips_trailing_slash(self):
        """Initialization strips trailing slash from base_folder."""
        adapter = SharePointStorageAdapter(
            drive_id="drv123",
            base_folder="/Custom/Path/",
        )

        assert adapter._base_folder == "/Custom/Path"


class TestSharePointStorageAdapterGetClient:
    """Tests for _get_client method."""

    @pytest.mark.asyncio
    async def test_get_client_creates_graph_client(self):
        """_get_client creates GraphClient with auth."""
        adapter = SharePointStorageAdapter(drive_id="drv123")

        with patch("app.core.sharepoint.adapter.get_sharepoint_auth") as mock_get_auth:
            mock_auth = MagicMock()
            mock_get_auth.return_value = mock_auth

            client = await adapter._get_client()

            assert isinstance(client, GraphClient)
            mock_get_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_reuses_existing_client(self):
        """_get_client reuses existing client."""
        adapter = SharePointStorageAdapter(drive_id="drv123")

        with patch("app.core.sharepoint.adapter.get_sharepoint_auth") as mock_get_auth:
            mock_auth = MagicMock()
            mock_get_auth.return_value = mock_auth

            client1 = await adapter._get_client()
            client2 = await adapter._get_client()

            assert client1 is client2
            # Should only create auth once
            assert mock_get_auth.call_count == 1


class TestSharePointStorageAdapterClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        """close() properly closes GraphClient."""
        adapter = SharePointStorageAdapter(drive_id="drv123")

        mock_client = AsyncMock()
        adapter._client = mock_client

        await adapter.close()

        mock_client.close.assert_called_once()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_close_handles_no_client(self):
        """close() handles case when client doesn't exist."""
        adapter = SharePointStorageAdapter(drive_id="drv123")

        # Should not raise
        await adapter.close()


class TestSharePointStorageAdapterSave:
    """Tests for save method."""

    @pytest.fixture
    def mock_adapter(self):
        """Create adapter with mocked GraphClient."""
        adapter = SharePointStorageAdapter(drive_id="drv123")
        mock_client = AsyncMock(spec=GraphClient)
        mock_client.SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024
        adapter._client = mock_client
        return adapter, mock_client

    @pytest.mark.asyncio
    async def test_save_small_file_uses_simple_upload(self, mock_adapter):
        """save() uses simple upload for small files."""
        adapter, mock_client = mock_adapter
        project_id = UUID("12345678-1234-5678-1234-567812345678")

        # Small file (< 4MB)
        content = b"small file content"
        file_obj = io.BytesIO(content)

        mock_client.ensure_folder = AsyncMock()
        mock_client.upload_small = AsyncMock(return_value={"id": "item123"})

        result = await adapter.save(file_obj, "test.txt", project_id)

        assert result == "item123"
        mock_client.ensure_folder.assert_called_once()
        mock_client.upload_small.assert_called_once()
        mock_client.upload_large.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_large_file_uses_chunked_upload(self, mock_adapter):
        """save() uses chunked upload for large files."""
        adapter, mock_client = mock_adapter
        project_id = UUID("12345678-1234-5678-1234-567812345678")

        # Large file (> 4MB)
        content = b"x" * (5 * 1024 * 1024)
        file_obj = io.BytesIO(content)

        mock_client.ensure_folder = AsyncMock()
        mock_client.upload_large = AsyncMock(return_value={"id": "item456"})

        result = await adapter.save(file_obj, "large.bin", project_id)

        assert result == "item456"
        mock_client.ensure_folder.assert_called_once()
        mock_client.upload_large.assert_called_once()
        mock_client.upload_small.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_returns_item_id(self, mock_adapter):
        """save() returns SharePoint item ID."""
        adapter, mock_client = mock_adapter
        project_id = UUID("12345678-1234-5678-1234-567812345678")

        file_obj = io.BytesIO(b"content")
        mock_client.ensure_folder = AsyncMock()
        mock_client.upload_small = AsyncMock(
            return_value={"id": "unique_item_id_123", "name": "test.txt"}
        )

        result = await adapter.save(file_obj, "test.txt", project_id)

        assert result == "unique_item_id_123"

    @pytest.mark.asyncio
    async def test_save_creates_project_folder(self, mock_adapter):
        """save() creates project folder before upload."""
        adapter, mock_client = mock_adapter
        project_id = UUID("12345678-1234-5678-1234-567812345678")

        file_obj = io.BytesIO(b"content")
        mock_client.ensure_folder = AsyncMock()
        mock_client.upload_small = AsyncMock(return_value={"id": "item123"})

        await adapter.save(file_obj, "test.txt", project_id)

        # Verify folder path includes project ID
        folder_arg = mock_client.ensure_folder.call_args[0][1]
        assert str(project_id) in folder_arg

    @pytest.mark.asyncio
    async def test_save_raises_on_missing_item_id(self, mock_adapter):
        """save() raises error if upload returns no item ID."""
        adapter, mock_client = mock_adapter
        project_id = UUID("12345678-1234-5678-1234-567812345678")

        file_obj = io.BytesIO(b"content")
        mock_client.ensure_folder = AsyncMock()
        mock_client.upload_small = AsyncMock(return_value={})  # No id

        with pytest.raises(SharePointError) as exc_info:
            await adapter.save(file_obj, "test.txt", project_id)

        assert "no item ID" in str(exc_info.value)


class TestSharePointStorageAdapterRead:
    """Tests for read method."""

    @pytest.fixture
    def mock_adapter(self):
        """Create adapter with mocked GraphClient."""
        adapter = SharePointStorageAdapter(drive_id="drv123")
        mock_client = AsyncMock(spec=GraphClient)
        adapter._client = mock_client
        return adapter, mock_client

    @pytest.mark.asyncio
    async def test_read_returns_bytes(self, mock_adapter):
        """read() returns file content as bytes."""
        adapter, mock_client = mock_adapter

        expected_content = b"file content here"
        mock_client.download = AsyncMock(return_value=expected_content)

        result = await adapter.read("item123")

        assert result == expected_content
        mock_client.download.assert_called_once_with("drv123", "item123")

    @pytest.mark.asyncio
    async def test_read_not_found_raises_file_not_found(self, mock_adapter):
        """read() raises FileNotFoundError for missing file."""
        adapter, mock_client = mock_adapter

        mock_client.download = AsyncMock(
            side_effect=SharePointNotFoundError("Not found")
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            await adapter.read("nonexistent")

        assert "nonexistent" in str(exc_info.value)


class TestSharePointStorageAdapterDelete:
    """Tests for delete method."""

    @pytest.fixture
    def mock_adapter(self):
        """Create adapter with mocked GraphClient."""
        adapter = SharePointStorageAdapter(drive_id="drv123")
        mock_client = AsyncMock(spec=GraphClient)
        adapter._client = mock_client
        return adapter, mock_client

    @pytest.mark.asyncio
    async def test_delete_calls_graph_delete(self, mock_adapter):
        """delete() calls GraphClient.delete."""
        adapter, mock_client = mock_adapter

        mock_client.delete = AsyncMock(return_value=True)

        await adapter.delete("item123")

        mock_client.delete.assert_called_once_with("drv123", "item123")

    @pytest.mark.asyncio
    async def test_delete_not_found_raises_no_error(self, mock_adapter):
        """delete() does not raise error for non-existent file."""
        adapter, mock_client = mock_adapter

        mock_client.delete = AsyncMock(side_effect=SharePointNotFoundError("Not found"))

        # Should not raise
        await adapter.delete("nonexistent")


class TestSharePointStorageAdapterExists:
    """Tests for exists method."""

    @pytest.fixture
    def mock_adapter(self):
        """Create adapter with mocked GraphClient."""
        adapter = SharePointStorageAdapter(drive_id="drv123")
        mock_client = AsyncMock(spec=GraphClient)
        adapter._client = mock_client
        return adapter, mock_client

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing(self, mock_adapter):
        """exists() returns True for existing file."""
        adapter, mock_client = mock_adapter

        mock_client.get_item = AsyncMock(
            return_value={"id": "item123", "name": "test.txt"}
        )

        result = await adapter.exists("item123")

        assert result is True
        mock_client.get_item.assert_called_once_with("drv123", "item123")

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_missing(self, mock_adapter):
        """exists() returns False for non-existent file."""
        adapter, mock_client = mock_adapter

        mock_client.get_item = AsyncMock(return_value=None)

        result = await adapter.exists("nonexistent")

        assert result is False


class TestSharePointStorageAdapterProjectFolder:
    """Tests for project folder path construction."""

    def test_get_project_folder_constructs_path(self):
        """_get_project_folder constructs correct path."""
        adapter = SharePointStorageAdapter(
            drive_id="drv123",
            base_folder="/NPD/projects",
        )
        project_id = UUID("12345678-1234-5678-1234-567812345678")

        result = adapter._get_project_folder(project_id)

        assert result == "NPD/projects/12345678-1234-5678-1234-567812345678"

    def test_get_project_folder_strips_leading_slash(self):
        """_get_project_folder strips leading slash for Graph API compatibility."""
        adapter = SharePointStorageAdapter(
            drive_id="drv123",
            base_folder="/Custom/Base",
        )
        project_id = UUID("abcdef12-3456-7890-abcd-ef1234567890")

        result = adapter._get_project_folder(project_id)

        # Should not start with /
        assert not result.startswith("/")
        assert result == "Custom/Base/abcdef12-3456-7890-abcd-ef1234567890"


class TestSharePointStorageAdapterInterface:
    """Tests to verify StorageBackend interface compliance."""

    def test_implements_storage_backend(self):
        """SharePointStorageAdapter implements StorageBackend."""
        from app.core.storage import StorageBackend

        adapter = SharePointStorageAdapter(drive_id="drv123")

        # Verify all required methods exist
        assert hasattr(adapter, "save")
        assert hasattr(adapter, "read")
        assert hasattr(adapter, "delete")
        assert hasattr(adapter, "exists")

        # Verify it's a subclass
        assert isinstance(adapter, StorageBackend)

    @pytest.mark.asyncio
    async def test_save_signature_matches_interface(self):
        """save() signature matches StorageBackend interface."""
        from inspect import signature

        from app.core.storage import StorageBackend

        adapter = SharePointStorageAdapter(drive_id="drv123")

        # Get signatures
        interface_sig = signature(StorageBackend.save)
        adapter_sig = signature(adapter.save)

        # Parameters should match (excluding self from interface)
        interface_params = [p for p in interface_sig.parameters if p != "self"]
        adapter_params = list(adapter_sig.parameters)

        assert interface_params == adapter_params
