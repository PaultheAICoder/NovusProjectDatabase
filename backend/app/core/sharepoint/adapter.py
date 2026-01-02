"""SharePoint storage adapter implementing StorageBackend interface.

Provides a high-level storage abstraction for SharePoint Online using
the GraphClient for low-level operations.
"""

from typing import BinaryIO
from uuid import UUID

from app.core.logging import get_logger
from app.core.sharepoint.auth import get_sharepoint_auth
from app.core.sharepoint.client import GraphClient
from app.core.sharepoint.exceptions import (
    SharePointError,
    SharePointNotFoundError,
)
from app.core.storage import StorageBackend

logger = get_logger(__name__)


class SharePointStorageAdapter(StorageBackend):
    """StorageBackend implementation for SharePoint Online.

    Provides file storage operations via Microsoft Graph API:
    - save: Upload files with automatic chunking for large files
    - read: Download file content by item ID
    - delete: Soft-delete files to SharePoint recycle bin
    - exists: Check if file exists by item ID

    The adapter uses SharePoint item IDs as storage references, which are
    returned by save() and used by other methods.

    Attributes:
        _drive_id: SharePoint drive ID for file storage
        _base_folder: Base folder path for project files
        _client: GraphClient instance for API calls
    """

    def __init__(
        self,
        drive_id: str,
        base_folder: str = "/NPD/projects",
    ) -> None:
        """Initialize SharePoint storage adapter.

        Args:
            drive_id: SharePoint drive ID (from drive discovery)
            base_folder: Base folder path for project files
                (default: /NPD/projects)
        """
        self._drive_id = drive_id
        self._base_folder = base_folder.rstrip("/")
        self._client: GraphClient | None = None

        logger.info(
            "sharepoint_adapter_init",
            drive_id=drive_id,
            base_folder=base_folder,
        )

    async def _get_client(self) -> GraphClient:
        """Get or create Graph client.

        Returns:
            GraphClient instance with authentication
        """
        if self._client is None:
            auth = get_sharepoint_auth()
            self._client = GraphClient(auth)
            logger.debug("sharepoint_adapter_client_created")
        return self._client

    async def close(self) -> None:
        """Close the Graph client and release resources."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.debug("sharepoint_adapter_closed")

    def _get_project_folder(self, project_id: UUID) -> str:
        """Construct folder path for a project.

        Args:
            project_id: UUID of the project

        Returns:
            Full folder path (e.g., NPD/projects/uuid-string)
        """
        return f"{self._base_folder.lstrip('/')}/{project_id}"

    async def save(
        self,
        file: BinaryIO,
        filename: str,
        project_id: UUID,
    ) -> str:
        """Upload file to SharePoint, return item ID as storage reference.

        Automatically uses chunked upload for files > 4MB.
        Creates project folder if it doesn't exist.

        Args:
            file: File-like object positioned at start
            filename: Original filename for the file
            project_id: UUID of the project this file belongs to

        Returns:
            SharePoint item ID as storage reference

        Raises:
            SharePointUploadError: If upload fails
            SharePointError: For other Graph API errors
        """
        client = await self._get_client()
        folder_path = self._get_project_folder(project_id)

        # Read file content
        content = file.read()
        file_size = len(content)

        logger.info(
            "sharepoint_adapter_save_start",
            filename=filename,
            project_id=str(project_id),
            size=file_size,
        )

        # Ensure folder exists
        await client.ensure_folder(self._drive_id, folder_path)

        # Choose upload method based on file size
        if file_size <= GraphClient.SIMPLE_UPLOAD_LIMIT:
            result = await client.upload_small(
                drive_id=self._drive_id,
                folder_path=folder_path,
                filename=filename,
                content=content,
            )
        else:
            result = await client.upload_large(
                drive_id=self._drive_id,
                folder_path=folder_path,
                filename=filename,
                content=content,
            )

        item_id = result.get("id")
        if not item_id:
            raise SharePointError("Upload succeeded but no item ID returned")

        logger.info(
            "sharepoint_adapter_save_success",
            filename=filename,
            project_id=str(project_id),
            item_id=item_id,
        )

        return item_id

    async def read(self, path: str) -> bytes:
        """Download file by item ID.

        Args:
            path: SharePoint item ID (returned by save())

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file does not exist
            SharePointError: For other Graph API errors
        """
        client = await self._get_client()

        logger.info(
            "sharepoint_adapter_read_start",
            item_id=path,
        )

        try:
            content = await client.download(self._drive_id, path)
            logger.info(
                "sharepoint_adapter_read_success",
                item_id=path,
                size=len(content),
            )
            return content
        except SharePointNotFoundError as e:
            logger.warning(
                "sharepoint_adapter_read_not_found",
                item_id=path,
            )
            raise FileNotFoundError(f"File not found: {path}") from e

    async def delete(self, path: str) -> None:
        """Delete file by item ID (soft-delete to recycle bin).

        Does not raise an error if file doesn't exist.

        Args:
            path: SharePoint item ID (returned by save())

        Raises:
            SharePointError: For Graph API errors (except 404)
        """
        client = await self._get_client()

        logger.info(
            "sharepoint_adapter_delete_start",
            item_id=path,
        )

        try:
            await client.delete(self._drive_id, path)
            logger.info(
                "sharepoint_adapter_delete_success",
                item_id=path,
            )
        except SharePointNotFoundError:
            # File already deleted, not an error
            logger.info(
                "sharepoint_adapter_delete_not_found",
                item_id=path,
            )

    async def exists(self, path: str) -> bool:
        """Check if file exists by item ID.

        Args:
            path: SharePoint item ID (returned by save())

        Returns:
            True if file exists, False otherwise

        Raises:
            SharePointError: For Graph API errors (except 404)
        """
        client = await self._get_client()

        logger.debug(
            "sharepoint_adapter_exists_check",
            item_id=path,
        )

        item = await client.get_item(self._drive_id, path)

        if item is not None:
            logger.debug(
                "sharepoint_adapter_exists_true",
                item_id=path,
            )
            return True
        else:
            logger.debug(
                "sharepoint_adapter_exists_false",
                item_id=path,
            )
            return False

    @property
    def drive_id(self) -> str:
        """Get the SharePoint drive ID."""
        return self._drive_id

    @property
    def base_folder(self) -> str:
        """Get the base folder path."""
        return self._base_folder
