"""Migration service for moving documents from local storage to SharePoint."""

import io
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.sharepoint import SharePointStorageAdapter
from app.core.storage import LocalStorageBackend
from app.models.document import Document

logger = get_logger(__name__)


@dataclass
class MigrationProgress:
    """Progress tracking for migration."""

    total: int = 0
    processed: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class MigrationResult:
    """Result of a single file migration."""

    document_id: UUID
    success: bool
    old_path: str
    new_path: str | None = None
    error: str | None = None


class MigrationService:
    """Service for migrating documents from local storage to SharePoint.

    This service handles batch migration of documents from local filesystem
    storage to SharePoint Online, with support for:
    - Dry-run mode for previewing changes
    - Progress tracking and callbacks
    - Error handling with continuation
    - Resume capability (skips already-migrated files)
    """

    def __init__(
        self,
        db: AsyncSession,
        local_storage: LocalStorageBackend,
        sharepoint_storage: SharePointStorageAdapter,
    ) -> None:
        """Initialize migration service.

        Args:
            db: Async database session
            local_storage: Local filesystem storage backend
            sharepoint_storage: SharePoint storage adapter
        """
        self.db = db
        self.local = local_storage
        self.sharepoint = sharepoint_storage

    def _is_sharepoint_path(self, path: str) -> bool:
        """Check if path is a SharePoint item ID (already migrated).

        Local paths contain slashes (e.g., project-uuid/file-uuid.ext).
        SharePoint item IDs are alphanumeric without slashes.

        Args:
            path: File path or item ID to check

        Returns:
            True if path appears to be a SharePoint item ID
        """
        # Local paths: {project_uuid}/{file_uuid}.ext (contain slashes)
        # SharePoint item IDs: alphanumeric, no slashes
        return "/" not in path

    async def get_migratable_documents(
        self,
        limit: int | None = None,
    ) -> list[Document]:
        """Get documents stored locally (not yet migrated).

        Documents with file_path containing slashes are local files.
        Documents with SharePoint item IDs (no slashes) are already migrated.

        Args:
            limit: Optional limit on number of documents to return

        Returns:
            List of documents that need migration
        """
        # Local paths are like: {project_uuid}/{file_uuid}.ext
        # SharePoint paths are item IDs (no slashes)
        stmt = (
            select(Document)
            .where(Document.file_path.contains("/"))  # Local paths have slashes
            .order_by(Document.created_at)
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def migrate_document(
        self,
        document: Document,
        dry_run: bool = False,
    ) -> MigrationResult:
        """Migrate a single document from local to SharePoint.

        Args:
            document: Document model instance to migrate
            dry_run: If True, preview without making changes

        Returns:
            MigrationResult with success/failure details
        """
        try:
            # Read from local storage
            content = await self.local.read(document.file_path)

            if dry_run:
                logger.info(
                    "migration_dry_run",
                    document_id=str(document.id),
                    file_path=document.file_path,
                    size=len(content),
                )
                return MigrationResult(
                    document_id=document.id,
                    success=True,
                    old_path=document.file_path,
                    new_path="[DRY_RUN]",
                )

            # Upload to SharePoint
            file_obj = io.BytesIO(content)
            new_path = await self.sharepoint.save(
                file=file_obj,
                filename=document.display_name,
                project_id=document.project_id,
            )

            # Update database reference
            old_path = document.file_path
            document.file_path = new_path
            await self.db.flush()

            logger.info(
                "migration_success",
                document_id=str(document.id),
                old_path=old_path,
                new_path=new_path,
            )

            return MigrationResult(
                document_id=document.id,
                success=True,
                old_path=old_path,
                new_path=new_path,
            )

        except FileNotFoundError as e:
            logger.error(
                "migration_file_not_found",
                document_id=str(document.id),
                file_path=document.file_path,
                error=str(e),
            )
            return MigrationResult(
                document_id=document.id,
                success=False,
                old_path=document.file_path,
                error=f"File not found: {document.file_path}",
            )
        except Exception as e:
            logger.error(
                "migration_error",
                document_id=str(document.id),
                file_path=document.file_path,
                error=str(e),
            )
            return MigrationResult(
                document_id=document.id,
                success=False,
                old_path=document.file_path,
                error=str(e),
            )

    async def migrate_batch(
        self,
        batch_size: int = 10,
        dry_run: bool = False,
        progress_callback: Callable[[MigrationProgress], None] | None = None,
    ) -> MigrationProgress:
        """Migrate documents in batches.

        Args:
            batch_size: Number of documents to commit per batch
            dry_run: If True, preview without making changes
            progress_callback: Optional callback for progress updates

        Returns:
            MigrationProgress with summary statistics
        """
        documents = await self.get_migratable_documents()
        progress = MigrationProgress(total=len(documents))

        logger.info(
            "migration_started",
            total_documents=progress.total,
            batch_size=batch_size,
            dry_run=dry_run,
        )

        for doc in documents:
            result = await self.migrate_document(doc, dry_run=dry_run)
            progress.processed += 1

            if result.success:
                progress.success += 1
            else:
                progress.failed += 1
                progress.errors.append(
                    {
                        "document_id": str(result.document_id),
                        "file_path": result.old_path,
                        "error": result.error,
                    }
                )

            if progress_callback:
                progress_callback(progress)

            # Commit in batches
            if not dry_run and progress.processed % batch_size == 0:
                await self.db.commit()

        # Final commit
        if not dry_run:
            await self.db.commit()

        logger.info(
            "migration_completed",
            total=progress.total,
            success=progress.success,
            failed=progress.failed,
            skipped=progress.skipped,
        )

        return progress
