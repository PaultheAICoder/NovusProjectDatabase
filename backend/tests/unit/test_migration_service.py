"""Tests for migration service."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.document import Document
from app.services.migration_service import (
    MigrationProgress,
    MigrationResult,
    MigrationService,
)


class TestMigrationServiceInit:
    """Tests for MigrationService initialization."""

    def test_init_stores_dependencies(self):
        """Initialization stores all dependencies."""
        mock_db = AsyncMock()
        mock_local = MagicMock()
        mock_sharepoint = MagicMock()

        service = MigrationService(
            db=mock_db,
            local_storage=mock_local,
            sharepoint_storage=mock_sharepoint,
        )

        assert service.db is mock_db
        assert service.local is mock_local
        assert service.sharepoint is mock_sharepoint


class TestIsSharePointPath:
    """Tests for _is_sharepoint_path method."""

    def test_local_path_with_slash_returns_false(self):
        """Local paths with slashes return False."""
        mock_db = AsyncMock()
        mock_local = MagicMock()
        mock_sharepoint = MagicMock()

        service = MigrationService(
            db=mock_db,
            local_storage=mock_local,
            sharepoint_storage=mock_sharepoint,
        )

        assert service._is_sharepoint_path("project-uuid/file-uuid.pdf") is False

    def test_sharepoint_id_without_slash_returns_true(self):
        """SharePoint item IDs without slashes return True."""
        mock_db = AsyncMock()
        mock_local = MagicMock()
        mock_sharepoint = MagicMock()

        service = MigrationService(
            db=mock_db,
            local_storage=mock_local,
            sharepoint_storage=mock_sharepoint,
        )

        assert service._is_sharepoint_path("01ABCDEFGHIJKLMNO") is True


class TestGetMigratableDocuments:
    """Tests for get_migratable_documents method."""

    @pytest.fixture
    def mock_service(self):
        """Create service with mocked dependencies."""
        mock_db = AsyncMock()
        mock_local = MagicMock()
        mock_sharepoint = MagicMock()
        return MigrationService(
            db=mock_db,
            local_storage=mock_local,
            sharepoint_storage=mock_sharepoint,
        )

    @pytest.mark.asyncio
    async def test_returns_local_documents(self, mock_service):
        """Returns documents with local paths (containing slashes)."""
        doc1 = MagicMock(spec=Document)
        doc1.file_path = "project-uuid/file-uuid.pdf"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [doc1]
        mock_service.db.execute.return_value = mock_result

        docs = await mock_service.get_migratable_documents()

        assert len(docs) == 1
        mock_service.db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_respects_limit(self, mock_service):
        """Respects limit parameter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_service.db.execute.return_value = mock_result

        await mock_service.get_migratable_documents(limit=5)

        # Verify query was executed
        mock_service.db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_documents(self, mock_service):
        """Returns empty list when no documents match."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_service.db.execute.return_value = mock_result

        docs = await mock_service.get_migratable_documents()

        assert docs == []


class TestMigrateDocument:
    """Tests for migrate_document method."""

    @pytest.fixture
    def mock_service(self):
        """Create service with mocked dependencies."""
        mock_db = AsyncMock()
        mock_local = AsyncMock()
        mock_sharepoint = AsyncMock()
        return MigrationService(
            db=mock_db,
            local_storage=mock_local,
            sharepoint_storage=mock_sharepoint,
        )

    @pytest.fixture
    def sample_document(self):
        """Create sample document."""
        doc = MagicMock(spec=Document)
        doc.id = uuid4()
        doc.project_id = uuid4()
        doc.file_path = "project-uuid/file-uuid.pdf"
        doc.display_name = "test.pdf"
        return doc

    @pytest.mark.asyncio
    async def test_migrate_success(self, mock_service, sample_document):
        """Successful migration updates file_path."""
        mock_service.local.read.return_value = b"file content"
        mock_service.sharepoint.save.return_value = "sharepoint_item_id"

        result = await mock_service.migrate_document(sample_document)

        assert result.success is True
        assert result.new_path == "sharepoint_item_id"
        assert sample_document.file_path == "sharepoint_item_id"
        mock_service.db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_dry_run_does_not_modify(self, mock_service, sample_document):
        """Dry run does not modify database."""
        mock_service.local.read.return_value = b"file content"
        original_path = sample_document.file_path

        result = await mock_service.migrate_document(sample_document, dry_run=True)

        assert result.success is True
        assert result.new_path == "[DRY_RUN]"
        assert sample_document.file_path == original_path
        mock_service.sharepoint.save.assert_not_called()
        mock_service.db.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_file_not_found(self, mock_service, sample_document):
        """Handles missing local file gracefully."""
        mock_service.local.read.side_effect = FileNotFoundError("File not found")

        result = await mock_service.migrate_document(sample_document)

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handles_sharepoint_error(self, mock_service, sample_document):
        """Handles SharePoint upload error gracefully."""
        mock_service.local.read.return_value = b"file content"
        mock_service.sharepoint.save.side_effect = Exception("SharePoint error")

        result = await mock_service.migrate_document(sample_document)

        assert result.success is False
        assert "SharePoint error" in result.error

    @pytest.mark.asyncio
    async def test_result_contains_old_path(self, mock_service, sample_document):
        """Migration result contains the original path."""
        mock_service.local.read.return_value = b"file content"
        mock_service.sharepoint.save.return_value = "new_item_id"

        result = await mock_service.migrate_document(sample_document)

        assert result.old_path == "project-uuid/file-uuid.pdf"


class TestMigrateBatch:
    """Tests for migrate_batch method."""

    @pytest.fixture
    def mock_service(self):
        """Create service with mocked dependencies."""
        mock_db = AsyncMock()
        mock_local = AsyncMock()
        mock_sharepoint = AsyncMock()
        return MigrationService(
            db=mock_db,
            local_storage=mock_local,
            sharepoint_storage=mock_sharepoint,
        )

    @pytest.mark.asyncio
    async def test_batch_processes_all_documents(self, mock_service):
        """Batch processes all documents."""
        docs = [MagicMock(spec=Document) for _ in range(3)]
        for i, doc in enumerate(docs):
            doc.id = uuid4()
            doc.project_id = uuid4()
            doc.file_path = f"project/file{i}.pdf"
            doc.display_name = f"file{i}.pdf"

        with (
            patch.object(mock_service, "get_migratable_documents", return_value=docs),
            patch.object(
                mock_service,
                "migrate_document",
                return_value=MigrationResult(
                    document_id=uuid4(),
                    success=True,
                    old_path="old",
                    new_path="new",
                ),
            ) as mock_migrate,
        ):
            progress = await mock_service.migrate_batch(batch_size=2)

        assert progress.total == 3
        assert progress.success == 3
        assert mock_migrate.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_commits_periodically(self, mock_service):
        """Batch commits after batch_size documents."""
        docs = [MagicMock(spec=Document) for _ in range(5)]
        for i, doc in enumerate(docs):
            doc.id = uuid4()
            doc.project_id = uuid4()
            doc.file_path = f"project/file{i}.pdf"
            doc.display_name = f"file{i}.pdf"

        with (
            patch.object(mock_service, "get_migratable_documents", return_value=docs),
            patch.object(
                mock_service,
                "migrate_document",
                return_value=MigrationResult(
                    document_id=uuid4(),
                    success=True,
                    old_path="old",
                    new_path="new",
                ),
            ),
        ):
            await mock_service.migrate_batch(batch_size=2)

        # Should commit after every 2 docs + final commit
        # 5 docs with batch_size=2: commit at 2, 4, and final = 3 commits
        assert mock_service.db.commit.call_count >= 2

    @pytest.mark.asyncio
    async def test_batch_tracks_failures(self, mock_service):
        """Batch tracks failed migrations."""
        docs = [MagicMock(spec=Document) for _ in range(3)]
        for i, doc in enumerate(docs):
            doc.id = uuid4()
            doc.project_id = uuid4()
            doc.file_path = f"project/file{i}.pdf"
            doc.display_name = f"file{i}.pdf"

        results = [
            MigrationResult(
                document_id=docs[0].id, success=True, old_path="a", new_path="b"
            ),
            MigrationResult(
                document_id=docs[1].id, success=False, old_path="c", error="Failed"
            ),
            MigrationResult(
                document_id=docs[2].id, success=True, old_path="d", new_path="e"
            ),
        ]

        with (
            patch.object(mock_service, "get_migratable_documents", return_value=docs),
            patch.object(mock_service, "migrate_document", side_effect=results),
        ):
            progress = await mock_service.migrate_batch()

        assert progress.total == 3
        assert progress.success == 2
        assert progress.failed == 1
        assert len(progress.errors) == 1

    @pytest.mark.asyncio
    async def test_progress_callback_called(self, mock_service):
        """Progress callback is called for each document."""
        docs = [MagicMock(spec=Document) for _ in range(3)]
        for i, doc in enumerate(docs):
            doc.id = uuid4()
            doc.project_id = uuid4()
            doc.file_path = f"project/file{i}.pdf"
            doc.display_name = f"file{i}.pdf"

        callback = MagicMock()

        with (
            patch.object(mock_service, "get_migratable_documents", return_value=docs),
            patch.object(
                mock_service,
                "migrate_document",
                return_value=MigrationResult(
                    document_id=uuid4(),
                    success=True,
                    old_path="old",
                    new_path="new",
                ),
            ),
        ):
            await mock_service.migrate_batch(progress_callback=callback)

        assert callback.call_count == 3

    @pytest.mark.asyncio
    async def test_dry_run_does_not_commit(self, mock_service):
        """Dry run mode does not commit to database."""
        docs = [MagicMock(spec=Document) for _ in range(3)]
        for i, doc in enumerate(docs):
            doc.id = uuid4()
            doc.project_id = uuid4()
            doc.file_path = f"project/file{i}.pdf"
            doc.display_name = f"file{i}.pdf"

        with (
            patch.object(mock_service, "get_migratable_documents", return_value=docs),
            patch.object(
                mock_service,
                "migrate_document",
                return_value=MigrationResult(
                    document_id=uuid4(),
                    success=True,
                    old_path="old",
                    new_path="[DRY_RUN]",
                ),
            ),
        ):
            await mock_service.migrate_batch(dry_run=True)

        mock_service.db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_document_list(self, mock_service):
        """Handles empty document list gracefully."""
        with patch.object(mock_service, "get_migratable_documents", return_value=[]):
            progress = await mock_service.migrate_batch()

        assert progress.total == 0
        assert progress.processed == 0
        assert progress.success == 0


class TestMigrationProgress:
    """Tests for MigrationProgress dataclass."""

    def test_default_values(self):
        """Progress has sensible defaults."""
        progress = MigrationProgress()

        assert progress.total == 0
        assert progress.processed == 0
        assert progress.success == 0
        assert progress.failed == 0
        assert progress.skipped == 0
        assert progress.errors == []

    def test_errors_list_is_independent(self):
        """Each instance has its own errors list."""
        progress1 = MigrationProgress()
        progress2 = MigrationProgress()

        progress1.errors.append({"error": "test"})

        assert len(progress1.errors) == 1
        assert len(progress2.errors) == 0


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_success_result(self):
        """Success result has expected fields."""
        doc_id = uuid4()
        result = MigrationResult(
            document_id=doc_id,
            success=True,
            old_path="/local/path",
            new_path="sharepoint_id",
        )

        assert result.document_id == doc_id
        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        """Failure result has error field."""
        doc_id = uuid4()
        result = MigrationResult(
            document_id=doc_id,
            success=False,
            old_path="/local/path",
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.new_path is None

    def test_old_path_required(self):
        """old_path is a required field."""
        doc_id = uuid4()
        result = MigrationResult(
            document_id=doc_id,
            success=True,
            old_path="path/to/file.pdf",
        )

        assert result.old_path == "path/to/file.pdf"
