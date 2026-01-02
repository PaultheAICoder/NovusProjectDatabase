"""Integration tests for document download with different storage backends."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.storage import reset_storage


class TestDocumentDownloadLocal:
    """Tests for document download with local storage."""

    def setup_method(self):
        """Reset storage singleton before each test."""
        reset_storage()

    def teardown_method(self):
        """Reset storage singleton after each test."""
        reset_storage()

    def test_storage_service_reports_local_storage(self):
        """StorageService correctly identifies local storage backend."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = False
            mock_settings.return_value.upload_dir = "./uploads"

            from app.core.storage import StorageService

            service = StorageService()
            assert service.is_local_storage() is True
            assert service.is_sharepoint_storage() is False


class TestDocumentDownloadSharePoint:
    """Tests for document download with SharePoint storage."""

    def setup_method(self):
        """Reset storage singleton before each test."""
        reset_storage()

    def teardown_method(self):
        """Reset storage singleton after each test."""
        reset_storage()

    @pytest.mark.asyncio
    async def test_storage_service_detects_sharepoint(self):
        """StorageService correctly identifies SharePoint backend."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = True
            mock_settings.return_value.sharepoint_drive_id = "drv123456789"
            mock_settings.return_value.sharepoint_base_folder = "/NPD/projects"

            from app.core.storage import StorageService

            service = StorageService()
            assert service.is_sharepoint_storage() is True
            assert service.is_local_storage() is False

    @pytest.mark.asyncio
    async def test_sharepoint_read_raises_file_not_found(self):
        """SharePoint adapter raises FileNotFoundError when file doesn't exist."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = True
            mock_settings.return_value.sharepoint_drive_id = "drv123456789"
            mock_settings.return_value.sharepoint_base_folder = "/NPD/projects"

            from app.core.sharepoint import SharePointStorageAdapter
            from app.core.sharepoint.exceptions import SharePointNotFoundError
            from app.core.storage import StorageService

            # Mock the SharePoint client to raise not found error
            with patch.object(
                SharePointStorageAdapter, "_get_client"
            ) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.download.side_effect = SharePointNotFoundError(
                    "Item not found"
                )
                mock_get_client.return_value = mock_client

                service = StorageService()

                with pytest.raises(FileNotFoundError):
                    await service.read("non-existent-item-id")


class TestStorageBackendSelection:
    """Tests for storage backend selection logic."""

    def setup_method(self):
        """Reset storage singleton before each test."""
        reset_storage()

    def teardown_method(self):
        """Reset storage singleton after each test."""
        reset_storage()

    def test_local_backend_when_sharepoint_disabled(self):
        """get_storage returns LocalStorageBackend when SharePoint is disabled."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = False
            mock_settings.return_value.upload_dir = "./uploads"

            from app.core.storage import LocalStorageBackend, get_storage

            storage = get_storage()
            assert isinstance(storage, LocalStorageBackend)

    def test_sharepoint_backend_when_configured(self):
        """get_storage returns SharePointStorageAdapter when configured."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = True
            mock_settings.return_value.sharepoint_drive_id = "drv123456789"
            mock_settings.return_value.sharepoint_base_folder = "/NPD/projects"

            from app.core.sharepoint import SharePointStorageAdapter
            from app.core.storage import get_storage

            storage = get_storage()
            assert isinstance(storage, SharePointStorageAdapter)

    def test_singleton_pattern_preserved(self):
        """get_storage returns the same instance on subsequent calls."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = False
            mock_settings.return_value.upload_dir = "./uploads"

            from app.core.storage import get_storage

            storage1 = get_storage()
            storage2 = get_storage()
            assert storage1 is storage2
