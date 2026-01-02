"""Migration script to move documents from local storage to SharePoint.

This script migrates documents from local filesystem storage to SharePoint
Online. It supports dry-run mode, batch processing, and resume capability.

Usage:
    python -m app.scripts.migrate_to_sharepoint --dry-run
    python -m app.scripts.migrate_to_sharepoint --batch-size 50
    python -m app.scripts.migrate_to_sharepoint --resume

Examples:
    # Preview migration without making changes
    python -m app.scripts.migrate_to_sharepoint --dry-run

    # Migrate with larger batch size for better performance
    python -m app.scripts.migrate_to_sharepoint --batch-size 50

    # Default run (resumes from where it left off)
    python -m app.scripts.migrate_to_sharepoint
"""

import argparse
import asyncio
import sys

from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.sharepoint import SharePointStorageAdapter
from app.core.storage import LocalStorageBackend
from app.database import async_session_maker
from app.services.migration_service import MigrationProgress, MigrationService

logger = get_logger(__name__)


def print_progress(progress: MigrationProgress) -> None:
    """Print progress update to console.

    Args:
        progress: Current migration progress
    """
    percent = (progress.processed / progress.total * 100) if progress.total > 0 else 0
    print(
        f"\rProgress: {progress.processed}/{progress.total} ({percent:.1f}%) "
        f"- Success: {progress.success}, Failed: {progress.failed}, "
        f"Skipped: {progress.skipped}",
        end="",
        flush=True,
    )


async def run_migration(
    dry_run: bool = False,
    batch_size: int = 10,
) -> int:
    """Run the migration process.

    Args:
        dry_run: If True, preview without making changes
        batch_size: Number of documents to commit per batch

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    settings = get_settings()

    # Verify SharePoint is configured
    if not settings.is_sharepoint_configured:
        logger.error(
            "sharepoint_not_configured",
            message="SharePoint is not configured. "
            "Set SHAREPOINT_ENABLED=true and configure credentials.",
        )
        print(
            "ERROR: SharePoint is not configured.\n"
            "Set SHAREPOINT_ENABLED=true and configure the following:\n"
            "  - SHAREPOINT_SITE_URL\n"
            "  - SHAREPOINT_DRIVE_ID\n"
            "  - SHAREPOINT_CLIENT_ID (or reuse AZURE_AD_CLIENT_ID)\n"
            "  - SHAREPOINT_CLIENT_SECRET (or reuse AZURE_AD_CLIENT_SECRET)"
        )
        return 1

    # Initialize storage backends
    local_storage = LocalStorageBackend()
    sharepoint_storage = SharePointStorageAdapter(
        drive_id=settings.sharepoint_drive_id,
        base_folder=settings.sharepoint_base_folder,
    )

    try:
        async with async_session_maker() as db:
            service = MigrationService(
                db=db,
                local_storage=local_storage,
                sharepoint_storage=sharepoint_storage,
            )

            # Get count first
            docs = await service.get_migratable_documents()
            print(f"Found {len(docs)} documents to migrate")

            if dry_run:
                print("DRY RUN MODE - No changes will be made")

            if len(docs) == 0:
                print(
                    "No documents to migrate. "
                    "All documents may already be on SharePoint."
                )
                return 0

            # Run migration
            progress = await service.migrate_batch(
                batch_size=batch_size,
                dry_run=dry_run,
                progress_callback=print_progress,
            )

            print()  # Newline after progress

            # Print summary
            print("\n=== Migration Summary ===")
            print(f"Total documents: {progress.total}")
            print(f"Successfully migrated: {progress.success}")
            print(f"Failed: {progress.failed}")
            print(f"Skipped: {progress.skipped}")

            if progress.errors:
                print("\n=== Errors ===")
                for error in progress.errors[:10]:  # Show first 10 errors
                    print(f"  - Document {error['document_id']}: {error['error']}")
                if len(progress.errors) > 10:
                    print(f"  ... and {len(progress.errors) - 10} more errors")

            return 0 if progress.failed == 0 else 1

    finally:
        await sharepoint_storage.close()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate documents from local storage to SharePoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview migration without making changes
  python -m app.scripts.migrate_to_sharepoint --dry-run

  # Migrate with larger batch size
  python -m app.scripts.migrate_to_sharepoint --batch-size 50

  # Normal migration (resumes automatically)
  python -m app.scripts.migrate_to_sharepoint
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without making changes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of documents to commit per batch (default: 10)",
    )

    args = parser.parse_args()

    # Configure logging
    configure_logging()

    # Run migration
    exit_code = asyncio.run(
        run_migration(
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        )
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
