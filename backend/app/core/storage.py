"""File storage abstraction layer.

This module provides an abstract interface for file storage that can be
implemented with different backends (local filesystem, SharePoint, S3, etc.).
"""

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from app.config import get_settings

settings = get_settings()


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save(
        self,
        file: BinaryIO,
        filename: str,
        project_id: UUID,
    ) -> str:
        """Save a file and return its storage path."""
        pass

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read a file's contents."""
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete a file."""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a file exists."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.upload_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_project_dir(self, project_id: UUID) -> Path:
        """Get the directory for a project's files."""
        project_dir = self.base_dir / str(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    async def save(
        self,
        file: BinaryIO,
        filename: str,
        project_id: UUID,
    ) -> str:
        """Save a file to the local filesystem."""
        project_dir = self._get_project_dir(project_id)

        # Generate unique filename to avoid collisions
        file_ext = Path(filename).suffix
        unique_name = f"{uuid4()}{file_ext}"
        file_path = project_dir / unique_name

        # Write file
        with open(file_path, "wb") as dest:
            shutil.copyfileobj(file, dest)

        # Return relative path from base_dir
        return str(file_path.relative_to(self.base_dir))

    async def read(self, path: str) -> bytes:
        """Read a file from the local filesystem."""
        file_path = self.base_dir / path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return file_path.read_bytes()

    async def delete(self, path: str) -> None:
        """Delete a file from the local filesystem."""
        file_path = self.base_dir / path
        if file_path.exists():
            file_path.unlink()

    async def exists(self, path: str) -> bool:
        """Check if a file exists in the local filesystem."""
        file_path = self.base_dir / path
        return file_path.exists()

    def get_absolute_path(self, path: str) -> Path:
        """Get absolute path for a stored file."""
        return self.base_dir / path


# Default storage instance
_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Get the configured storage backend."""
    global _storage
    if _storage is None:
        _storage = LocalStorageBackend()
    return _storage


class StorageService:
    """High-level storage service for document management."""

    def __init__(self) -> None:
        self._backend = get_storage()

    async def save(
        self,
        content: bytes,
        filename: str,
        project_id: str,
    ) -> str:
        """Save file content and return storage path."""
        import io
        file_obj = io.BytesIO(content)
        return await self._backend.save(file_obj, filename, UUID(project_id))

    async def read(self, path: str) -> bytes:
        """Read file contents."""
        return await self._backend.read(path)

    async def delete(self, path: str) -> None:
        """Delete a file."""
        await self._backend.delete(path)

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        return await self._backend.exists(path)

    def get_path(self, relative_path: str) -> str:
        """Get absolute path for a stored file."""
        if isinstance(self._backend, LocalStorageBackend):
            return str(self._backend.get_absolute_path(relative_path))
        return relative_path
