"""Integration tests for SharePoint storage against real SharePoint environment.

These tests require a configured SharePoint dev environment.
Set environment variables before running:
  - SHAREPOINT_ENABLED=true
  - SHAREPOINT_SITE_URL
  - SHAREPOINT_DRIVE_ID
  - SHAREPOINT_CLIENT_ID (or AZURE_AD_CLIENT_ID)
  - SHAREPOINT_CLIENT_SECRET (or AZURE_AD_CLIENT_SECRET)

Run: pytest tests/integration/test_sharepoint_integration.py -v
Skip: pytest tests/ -m "not integration"
"""

import asyncio
import io
from uuid import uuid4

import pytest

from app.config import get_settings
from app.core.sharepoint import (
    SharePointError,
    SharePointNotFoundError,
    SharePointStorageAdapter,
)

# Skip all tests if SharePoint not configured
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not get_settings().is_sharepoint_configured,
        reason="SharePoint not configured - set SHAREPOINT_ENABLED and credentials",
    ),
]


class TestUploadCycle:
    """Integration tests for SharePoint upload operations."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for class-scoped async fixtures."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="class")
    async def adapter(self, event_loop):  # noqa: ARG002
        """Create SharePoint adapter for tests."""
        settings = get_settings()
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests",
        )
        yield adapter
        await adapter.close()

    @pytest.fixture
    def test_project_id(self):
        """Generate unique project ID for test isolation."""
        return uuid4()

    @pytest.mark.asyncio
    async def test_upload_small_file(self, adapter, test_project_id):
        """Test upload of file < 4MB."""
        content = b"Integration test content - small file"
        filename = f"test_small_{uuid4().hex[:8]}.txt"

        item_id = await adapter.save(
            file=io.BytesIO(content),
            filename=filename,
            project_id=test_project_id,
        )

        assert item_id is not None
        assert len(item_id) > 0

        # Verify exists
        exists = await adapter.exists(item_id)
        assert exists is True

        # Cleanup
        await adapter.delete(item_id)

    @pytest.mark.asyncio
    async def test_upload_returns_valid_item_id(self, adapter, test_project_id):
        """Test that upload returns a valid SharePoint item ID."""
        content = b"Item ID validation test"
        filename = f"test_itemid_{uuid4().hex[:8]}.txt"

        item_id = await adapter.save(
            file=io.BytesIO(content),
            filename=filename,
            project_id=test_project_id,
        )

        # SharePoint item IDs are alphanumeric without slashes
        assert item_id is not None
        assert "/" not in item_id
        assert len(item_id) > 0

        # Cleanup
        await adapter.delete(item_id)

    @pytest.mark.asyncio
    async def test_upload_creates_project_folder(self, adapter):
        """Test that upload creates project folder if not exists."""
        # Use a new unique project ID to ensure folder doesn't exist
        unique_project_id = uuid4()
        content = b"Folder creation test content"
        filename = f"test_folder_{uuid4().hex[:8]}.txt"

        item_id = await adapter.save(
            file=io.BytesIO(content),
            filename=filename,
            project_id=unique_project_id,
        )

        assert item_id is not None

        # Verify file exists (implies folder was created)
        exists = await adapter.exists(item_id)
        assert exists is True

        # Cleanup
        await adapter.delete(item_id)


class TestDownloadCycle:
    """Integration tests for SharePoint download operations."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for class-scoped async fixtures."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="class")
    async def adapter(self, event_loop):  # noqa: ARG002
        """Create SharePoint adapter for tests."""
        settings = get_settings()
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests",
        )
        yield adapter
        await adapter.close()

    @pytest.mark.asyncio
    async def test_download_returns_original_content(self, adapter):
        """Test download returns exact content that was uploaded."""
        original_content = b"Download test content with special chars: \x00\xff\n\t"
        project_id = uuid4()
        filename = f"download_test_{uuid4().hex[:8]}.bin"

        # Upload
        item_id = await adapter.save(
            file=io.BytesIO(original_content),
            filename=filename,
            project_id=project_id,
        )

        try:
            # Download
            downloaded = await adapter.read(item_id)

            # Verify content matches
            assert downloaded == original_content
        finally:
            await adapter.delete(item_id)

    @pytest.mark.asyncio
    async def test_download_text_file_preserves_encoding(self, adapter):
        """Test download preserves text content and encoding."""
        original_content = "Hello World! Unicode: \u00e9\u00e8\u00ea".encode()
        project_id = uuid4()
        filename = f"text_test_{uuid4().hex[:8]}.txt"

        # Upload
        item_id = await adapter.save(
            file=io.BytesIO(original_content),
            filename=filename,
            project_id=project_id,
        )

        try:
            # Download
            downloaded = await adapter.read(item_id)

            # Verify content matches
            assert downloaded == original_content
            # Verify it decodes correctly
            assert (
                downloaded.decode("utf-8") == "Hello World! Unicode: \u00e9\u00e8\u00ea"
            )
        finally:
            await adapter.delete(item_id)

    @pytest.mark.asyncio
    async def test_download_nonexistent_raises_error(self, adapter):
        """Test downloading non-existent file raises FileNotFoundError."""
        fake_item_id = "nonexistent-item-id-12345"

        with pytest.raises(FileNotFoundError):
            await adapter.read(fake_item_id)


class TestDeleteCycle:
    """Integration tests for SharePoint delete operations."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for class-scoped async fixtures."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="class")
    async def adapter(self, event_loop):  # noqa: ARG002
        """Create SharePoint adapter for tests."""
        settings = get_settings()
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests",
        )
        yield adapter
        await adapter.close()

    @pytest.mark.asyncio
    async def test_delete_removes_file(self, adapter):
        """Test that delete removes file from SharePoint."""
        content = b"File to be deleted"
        project_id = uuid4()
        filename = f"delete_test_{uuid4().hex[:8]}.txt"

        # Upload
        item_id = await adapter.save(
            file=io.BytesIO(content),
            filename=filename,
            project_id=project_id,
        )

        # Verify exists
        assert await adapter.exists(item_id) is True

        # Delete
        await adapter.delete(item_id)

        # Verify no longer exists
        assert await adapter.exists(item_id) is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_does_not_raise(self, adapter):
        """Test deleting non-existent file does not raise error."""
        fake_item_id = "nonexistent-item-id-67890"

        # Should not raise
        await adapter.delete(fake_item_id)


class TestLargeFileHandling:
    """Integration tests for large file operations (chunked upload)."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for class-scoped async fixtures."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="class")
    async def adapter(self, event_loop):  # noqa: ARG002
        """Create SharePoint adapter for tests."""
        settings = get_settings()
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests",
        )
        yield adapter
        await adapter.close()

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_upload_download_10mb_file(self, adapter):
        """Test upload and download of 10MB file (uses chunked upload)."""
        # Generate 10MB of content
        content = b"x" * (10 * 1024 * 1024)
        project_id = uuid4()
        filename = f"large_10mb_{uuid4().hex[:8]}.bin"

        # Upload
        item_id = await adapter.save(
            file=io.BytesIO(content),
            filename=filename,
            project_id=project_id,
        )

        try:
            assert item_id is not None

            # Download
            downloaded = await adapter.read(item_id)

            # Verify size and content
            assert len(downloaded) == len(content)
            assert downloaded == content
        finally:
            await adapter.delete(item_id)

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_upload_download_50mb_file(self, adapter):
        """Test upload and download of 50MB file (near limit)."""
        # Generate 50MB of content
        content = b"y" * (50 * 1024 * 1024)
        project_id = uuid4()
        filename = f"large_50mb_{uuid4().hex[:8]}.bin"

        # Upload (may take 30-60 seconds)
        item_id = await adapter.save(
            file=io.BytesIO(content),
            filename=filename,
            project_id=project_id,
        )

        try:
            assert item_id is not None

            # Download
            downloaded = await adapter.read(item_id)

            # Verify size (full content comparison expensive)
            assert len(downloaded) == len(content)

            # Spot check: first and last 1MB should match
            assert downloaded[: 1024 * 1024] == content[: 1024 * 1024]
            assert downloaded[-1024 * 1024 :] == content[-1024 * 1024 :]
        finally:
            await adapter.delete(item_id)

    @pytest.mark.asyncio
    async def test_upload_medium_file_5mb(self, adapter):
        """Test upload of 5MB file (just above simple upload limit)."""
        # 5MB - just above the 4MB simple upload limit
        content = b"z" * (5 * 1024 * 1024)
        project_id = uuid4()
        filename = f"medium_5mb_{uuid4().hex[:8]}.bin"

        item_id = await adapter.save(
            file=io.BytesIO(content),
            filename=filename,
            project_id=project_id,
        )

        try:
            assert item_id is not None

            # Download and verify
            downloaded = await adapter.read(item_id)
            assert len(downloaded) == len(content)
        finally:
            await adapter.delete(item_id)


class TestConcurrentOperations:
    """Integration tests for concurrent SharePoint operations."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for class-scoped async fixtures."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="class")
    async def adapter(self, event_loop):  # noqa: ARG002
        """Create SharePoint adapter for tests."""
        settings = get_settings()
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests",
        )
        yield adapter
        await adapter.close()

    @pytest.mark.asyncio
    async def test_concurrent_uploads(self, adapter):
        """Test multiple concurrent file uploads."""
        project_id = uuid4()
        num_files = 5
        uploaded_ids = []

        async def upload_file(index):
            content = f"Concurrent upload test file {index}".encode()
            filename = f"concurrent_{index}_{uuid4().hex[:8]}.txt"
            item_id = await adapter.save(
                file=io.BytesIO(content),
                filename=filename,
                project_id=project_id,
            )
            return item_id

        try:
            # Upload concurrently
            tasks = [upload_file(i) for i in range(num_files)]
            uploaded_ids = await asyncio.gather(*tasks)

            # Verify all succeeded
            assert len(uploaded_ids) == num_files
            assert all(item_id is not None for item_id in uploaded_ids)

            # Verify all exist
            exist_checks = await asyncio.gather(
                *[adapter.exists(item_id) for item_id in uploaded_ids]
            )
            assert all(exist_checks)
        finally:
            # Cleanup all files
            await asyncio.gather(*[adapter.delete(item_id) for item_id in uploaded_ids])

    @pytest.mark.asyncio
    async def test_concurrent_downloads(self, adapter):
        """Test multiple concurrent file downloads."""
        project_id = uuid4()
        num_files = 5
        uploaded_ids = []
        contents = []

        # Upload files first
        for i in range(num_files):
            content = f"Concurrent download test file {i} - {uuid4().hex}".encode()
            contents.append(content)
            filename = f"download_{i}_{uuid4().hex[:8]}.txt"
            item_id = await adapter.save(
                file=io.BytesIO(content),
                filename=filename,
                project_id=project_id,
            )
            uploaded_ids.append(item_id)

        try:
            # Download concurrently
            downloaded = await asyncio.gather(
                *[adapter.read(item_id) for item_id in uploaded_ids]
            )

            # Verify all content matches
            assert len(downloaded) == num_files
            for i, (original, dl) in enumerate(zip(contents, downloaded, strict=True)):
                assert dl == original, f"File {i} content mismatch"
        finally:
            # Cleanup
            await asyncio.gather(*[adapter.delete(item_id) for item_id in uploaded_ids])

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, adapter):
        """Test mixed concurrent operations (upload, download, delete)."""
        project_id = uuid4()

        # First, upload some files
        uploaded_ids = []
        for i in range(3):
            content = f"Mixed ops test {i}".encode()
            filename = f"mixed_{i}_{uuid4().hex[:8]}.txt"
            item_id = await adapter.save(
                file=io.BytesIO(content),
                filename=filename,
                project_id=project_id,
            )
            uploaded_ids.append(item_id)

        try:
            # Perform mixed operations concurrently:
            # - Upload a new file
            # - Download first existing file
            # - Check existence of second file
            async def upload_new():
                return await adapter.save(
                    file=io.BytesIO(b"New concurrent file"),
                    filename=f"new_concurrent_{uuid4().hex[:8]}.txt",
                    project_id=project_id,
                )

            async def download_first():
                return await adapter.read(uploaded_ids[0])

            async def check_exists():
                return await adapter.exists(uploaded_ids[1])

            new_id, downloaded, exists = await asyncio.gather(
                upload_new(), download_first(), check_exists()
            )

            assert new_id is not None
            assert downloaded == b"Mixed ops test 0"
            assert exists is True

            uploaded_ids.append(new_id)
        finally:
            # Cleanup all
            await asyncio.gather(*[adapter.delete(item_id) for item_id in uploaded_ids])


class TestMigrationIntegration:
    """Integration tests for local-to-SharePoint migration."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for class-scoped async fixtures."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture
    def mock_document(self):
        """Create mock document for migration test."""
        from unittest.mock import MagicMock

        from app.models.document import Document

        # Create mock document
        doc = MagicMock(spec=Document)
        doc.id = uuid4()
        doc.project_id = uuid4()
        doc.file_path = f"{doc.project_id}/test-file.txt"
        doc.display_name = "test_migration.txt"

        return doc

    @pytest.fixture
    def local_storage_with_file(self, tmp_path, mock_document):
        """Create local storage with a test file."""
        from app.core.storage import LocalStorageBackend

        storage = LocalStorageBackend(base_dir=str(tmp_path))

        # Create project directory and test file
        project_dir = tmp_path / str(mock_document.project_id)
        project_dir.mkdir(exist_ok=True)
        test_file = project_dir / "test-file.txt"
        test_file.write_bytes(b"Migration test content")

        return storage

    @pytest.mark.asyncio
    async def test_migration_uploads_to_sharepoint(
        self, mock_document, local_storage_with_file
    ):
        """Test that migration service uploads files to SharePoint."""
        from unittest.mock import AsyncMock

        from app.services.migration_service import MigrationService

        settings = get_settings()
        sharepoint_storage = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests/migration",
        )

        # Mock DB session
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        try:
            service = MigrationService(
                db=mock_db,
                local_storage=local_storage_with_file,
                sharepoint_storage=sharepoint_storage,
            )

            result = await service.migrate_document(mock_document, dry_run=False)

            # Verify success
            assert result.success is True
            assert result.new_path is not None
            assert result.new_path != "[DRY_RUN]"

            # Verify file exists in SharePoint
            exists = await sharepoint_storage.exists(result.new_path)
            assert exists is True

            # Cleanup
            await sharepoint_storage.delete(result.new_path)
        finally:
            await sharepoint_storage.close()

    @pytest.mark.asyncio
    async def test_migration_dry_run_does_not_upload(
        self, mock_document, local_storage_with_file
    ):
        """Test that dry run does not actually upload files."""
        from unittest.mock import AsyncMock

        from app.services.migration_service import MigrationService

        settings = get_settings()
        sharepoint_storage = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests/migration",
        )

        # Mock DB session
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        try:
            service = MigrationService(
                db=mock_db,
                local_storage=local_storage_with_file,
                sharepoint_storage=sharepoint_storage,
            )

            result = await service.migrate_document(mock_document, dry_run=True)

            # Verify dry run result
            assert result.success is True
            assert result.new_path == "[DRY_RUN]"

            # DB should not be called for flush in dry run
            mock_db.flush.assert_not_called()
        finally:
            await sharepoint_storage.close()


class TestErrorScenarios:
    """Integration tests for error handling in SharePoint operations."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for class-scoped async fixtures."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.mark.asyncio
    async def test_invalid_drive_id_raises_error(self):
        """Test that invalid drive ID raises appropriate error."""
        adapter = SharePointStorageAdapter(
            drive_id="invalid-drive-id-that-does-not-exist",
            base_folder="/NPD/integration-tests",
        )

        try:
            with pytest.raises((SharePointError, SharePointNotFoundError, Exception)):
                await adapter.save(
                    file=io.BytesIO(b"test"),
                    filename="test.txt",
                    project_id=uuid4(),
                )
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_upload_to_nonexistent_folder_creates_folder(self):
        """Test that uploading to non-existent folder creates it."""
        settings = get_settings()
        unique_folder = f"/NPD/integration-tests/new-folder-{uuid4().hex[:8]}"
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder=unique_folder,
        )

        try:
            item_id = await adapter.save(
                file=io.BytesIO(b"test content"),
                filename="test.txt",
                project_id=uuid4(),
            )

            assert item_id is not None

            # Cleanup
            await adapter.delete(item_id)
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_read_deleted_file_raises_not_found(self):
        """Test reading a deleted file raises FileNotFoundError."""
        settings = get_settings()
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests",
        )

        try:
            # Upload then delete
            item_id = await adapter.save(
                file=io.BytesIO(b"temporary"),
                filename=f"temp_{uuid4().hex[:8]}.txt",
                project_id=uuid4(),
            )
            await adapter.delete(item_id)

            # Try to read deleted file
            with pytest.raises(FileNotFoundError):
                await adapter.read(item_id)
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_nonexistent(self):
        """Test exists() returns False for non-existent file."""
        settings = get_settings()
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests",
        )

        try:
            exists = await adapter.exists("definitely-nonexistent-id-xyz123")
            assert exists is False
        finally:
            await adapter.close()

    @pytest.mark.asyncio
    async def test_empty_file_upload(self):
        """Test uploading an empty file."""
        settings = get_settings()
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests",
        )

        try:
            item_id = await adapter.save(
                file=io.BytesIO(b""),
                filename=f"empty_{uuid4().hex[:8]}.txt",
                project_id=uuid4(),
            )

            assert item_id is not None

            # Verify content is empty
            content = await adapter.read(item_id)
            assert content == b""

            # Cleanup
            await adapter.delete(item_id)
        finally:
            await adapter.close()


class TestFileTypes:
    """Integration tests for different file types."""

    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for class-scoped async fixtures."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="class")
    async def adapter(self, event_loop):  # noqa: ARG002
        """Create SharePoint adapter for tests."""
        settings = get_settings()
        adapter = SharePointStorageAdapter(
            drive_id=settings.sharepoint_drive_id,
            base_folder="/NPD/integration-tests",
        )
        yield adapter
        await adapter.close()

    @pytest.mark.asyncio
    async def test_upload_pdf_content(self, adapter):
        """Test uploading PDF-like content."""
        # PDF header bytes
        pdf_content = b"%PDF-1.4\n%Test PDF content\n%%EOF"
        project_id = uuid4()
        filename = f"test_{uuid4().hex[:8]}.pdf"

        item_id = await adapter.save(
            file=io.BytesIO(pdf_content),
            filename=filename,
            project_id=project_id,
        )

        try:
            downloaded = await adapter.read(item_id)
            assert downloaded == pdf_content
        finally:
            await adapter.delete(item_id)

    @pytest.mark.asyncio
    async def test_upload_docx_content(self, adapter):
        """Test uploading DOCX-like content (ZIP format)."""
        # DOCX files are ZIP files with specific structure
        # Using ZIP magic bytes for testing
        docx_content = b"PK\x03\x04" + b"\x00" * 100 + b"Test content"
        project_id = uuid4()
        filename = f"test_{uuid4().hex[:8]}.docx"

        item_id = await adapter.save(
            file=io.BytesIO(docx_content),
            filename=filename,
            project_id=project_id,
        )

        try:
            downloaded = await adapter.read(item_id)
            assert downloaded == docx_content
        finally:
            await adapter.delete(item_id)

    @pytest.mark.asyncio
    async def test_upload_special_characters_in_filename(self, adapter):
        """Test uploading file with special characters in name."""
        content = b"Special chars test"
        project_id = uuid4()
        # Use safe special characters (avoid OS-specific problematic chars)
        filename = f"test-file_{uuid4().hex[:8]} (copy).txt"

        item_id = await adapter.save(
            file=io.BytesIO(content),
            filename=filename,
            project_id=project_id,
        )

        try:
            downloaded = await adapter.read(item_id)
            assert downloaded == content
        finally:
            await adapter.delete(item_id)
