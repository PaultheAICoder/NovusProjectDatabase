"""Tests for storage factory function."""

from unittest.mock import patch

from app.core.storage import (
    LocalStorageBackend,
    StorageService,
    get_storage,
    reset_storage,
)


class TestGetStorage:
    """Tests for get_storage factory function."""

    def setup_method(self):
        """Reset storage singleton before each test."""
        reset_storage()

    def teardown_method(self):
        """Reset storage singleton after each test."""
        reset_storage()

    def test_get_storage_returns_local_when_sharepoint_not_configured(self):
        """Returns LocalStorageBackend when SharePoint is not configured."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = False
            mock_settings.return_value.upload_dir = "./uploads"

            storage = get_storage()

            assert isinstance(storage, LocalStorageBackend)

    def test_get_storage_returns_sharepoint_when_configured(self):
        """Returns SharePointStorageAdapter when SharePoint is configured."""
        with patch("app.core.storage.get_settings") as mock_settings:
            from app.core.sharepoint import SharePointStorageAdapter

            mock_settings.return_value.is_sharepoint_configured = True
            mock_settings.return_value.sharepoint_drive_id = "drv123456789"
            mock_settings.return_value.sharepoint_base_folder = "/NPD/projects"

            storage = get_storage()

            assert isinstance(storage, SharePointStorageAdapter)
            assert storage.drive_id == "drv123456789"

    def test_get_storage_returns_singleton(self):
        """Returns same instance on subsequent calls."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = False
            mock_settings.return_value.upload_dir = "./uploads"

            storage1 = get_storage()
            storage2 = get_storage()

            assert storage1 is storage2

    def test_reset_storage_clears_singleton(self):
        """reset_storage clears the singleton."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = False
            mock_settings.return_value.upload_dir = "./uploads"

            storage1 = get_storage()
            reset_storage()
            storage2 = get_storage()

            assert storage1 is not storage2


class TestStorageService:
    """Tests for StorageService helper methods."""

    def setup_method(self):
        """Reset storage singleton before each test."""
        reset_storage()

    def teardown_method(self):
        """Reset storage singleton after each test."""
        reset_storage()

    def test_is_local_storage_true_for_local(self):
        """is_local_storage returns True for LocalStorageBackend."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = False
            mock_settings.return_value.upload_dir = "./uploads"

            service = StorageService()
            assert service.is_local_storage() is True
            assert service.is_sharepoint_storage() is False

    def test_is_sharepoint_storage_true_for_sharepoint(self):
        """is_sharepoint_storage returns True for SharePointStorageAdapter."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = True
            mock_settings.return_value.sharepoint_drive_id = "drv123456789"
            mock_settings.return_value.sharepoint_base_folder = "/NPD/projects"

            service = StorageService()
            assert service.is_local_storage() is False
            assert service.is_sharepoint_storage() is True

    def test_get_path_returns_absolute_for_local(self, tmp_path):
        """get_path returns absolute filesystem path for local storage."""
        # Create a LocalStorageBackend directly with the tmp_path
        from app.core.storage import LocalStorageBackend

        backend = LocalStorageBackend(base_dir=str(tmp_path))
        result = str(backend.get_absolute_path("some/file.pdf"))

        assert str(tmp_path) in result
        assert "some/file.pdf" in result

    def test_get_path_returns_item_id_for_sharepoint(self):
        """get_path returns the item ID unchanged for SharePoint storage."""
        with patch("app.core.storage.get_settings") as mock_settings:
            mock_settings.return_value.is_sharepoint_configured = True
            mock_settings.return_value.sharepoint_drive_id = "drv123456789"
            mock_settings.return_value.sharepoint_base_folder = "/NPD/projects"

            service = StorageService()
            item_id = "sp-item-123456"
            result = service.get_path(item_id)

            # For SharePoint, the path IS the item ID
            assert result == item_id
