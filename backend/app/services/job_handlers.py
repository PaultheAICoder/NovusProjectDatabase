"""Job handler implementations for different job types.

This module contains the actual implementations for each job type.
Handlers are registered using the @register_job_handler decorator.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.job import Job, JobType
from app.services.job_service import register_job_handler

logger = get_logger(__name__)


@register_job_handler(JobType.JIRA_REFRESH)
async def handle_jira_refresh(job: Job, db: AsyncSession) -> dict | None:
    """Refresh Jira status for linked issues.

    This handler wraps the existing Jira refresh functionality
    to be executed as a background job.

    Args:
        job: The job being processed
        db: Database session

    Returns:
        Dict with refresh results
    """
    from app.services.jira_service import refresh_all_jira_statuses

    logger.info(
        "jira_refresh_job_started",
        job_id=str(job.id),
    )

    result = await refresh_all_jira_statuses()

    logger.info(
        "jira_refresh_job_completed",
        job_id=str(job.id),
        refreshed=result.get("refreshed", 0),
        failed=result.get("failed", 0),
    )

    return result


@register_job_handler(JobType.EMBEDDING_GENERATION)
async def handle_embedding_generation(job: Job, db: AsyncSession) -> dict | None:
    """Generate embeddings for a batch of documents.

    This handler processes embedding generation for documents
    that have been uploaded but not yet embedded.

    Payload options:
        - document_ids: List of document IDs to process (optional)
        - If no document_ids provided, processes all pending documents

    Args:
        job: The job being processed
        db: Database session

    Returns:
        Dict with generation results
    """
    from uuid import UUID

    from sqlalchemy import select

    from app.models.document import Document, DocumentChunk
    from app.services.embedding_service import EmbeddingService

    logger.info(
        "embedding_generation_job_started",
        job_id=str(job.id),
        entity_id=str(job.entity_id) if job.entity_id else None,
    )

    payload = job.payload or {}
    document_ids = payload.get("document_ids", [])

    embedding_service = EmbeddingService()
    processed = 0
    failed = 0
    chunks_created = 0
    errors = []

    # Build query for documents to process
    if document_ids:
        # Process specific documents
        doc_uuids = [UUID(d) if isinstance(d, str) else d for d in document_ids]
        stmt = select(Document).where(Document.id.in_(doc_uuids))
    else:
        # Process documents that have extracted text but no chunks
        stmt = (
            select(Document)
            .outerjoin(DocumentChunk)
            .where(
                Document.extracted_text.isnot(None),
                Document.extracted_text != "",
                DocumentChunk.id.is_(None),
            )
            .limit(50)  # Batch size
        )

    result = await db.execute(stmt)
    documents = list(result.scalars().all())

    for doc in documents:
        try:
            if not doc.extracted_text:
                continue

            # Create chunks and embeddings
            chunks = embedding_service.chunk_text(doc.extracted_text)

            for i, chunk_content in enumerate(chunks):
                embedding = await embedding_service.generate_embedding(chunk_content)
                chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk_content,
                    embedding=embedding,
                )
                db.add(chunk)
                chunks_created += 1

            processed += 1
        except Exception as e:
            failed += 1
            errors.append(f"Document {doc.id}: {str(e)[:100]}")
            logger.warning(
                "embedding_generation_document_failed",
                document_id=str(doc.id),
                error=str(e),
            )

    await db.flush()

    logger.info(
        "embedding_generation_job_completed",
        job_id=str(job.id),
        processed=processed,
        failed=failed,
        chunks_created=chunks_created,
    )

    return {
        "processed": processed,
        "failed": failed,
        "chunks_created": chunks_created,
        "errors": errors[:10],  # Limit error list
    }


@register_job_handler(JobType.BULK_IMPORT)
async def handle_bulk_import(job: Job, db: AsyncSession) -> dict | None:
    """Process bulk import operation.

    This handler processes bulk import operations that are
    too large to handle synchronously.

    Payload must contain:
        - rows: List of ImportRowUpdate dicts
        - user_id: UUID of user who initiated import
        - skip_invalid: bool (default True)

    Args:
        job: The job being processed
        db: Database session

    Returns:
        Dict with import results
    """
    from datetime import date
    from uuid import UUID

    from app.schemas.import_ import ImportRowUpdate
    from app.services.import_service import ImportService

    logger.info(
        "bulk_import_job_started",
        job_id=str(job.id),
    )

    payload = job.payload or {}

    if "rows" not in payload:
        raise ValueError("Payload must contain 'rows' list")
    if "user_id" not in payload:
        raise ValueError("Payload must contain 'user_id'")

    rows_data = payload["rows"]
    user_id = (
        UUID(payload["user_id"])
        if isinstance(payload["user_id"], str)
        else payload["user_id"]
    )
    skip_invalid = payload.get("skip_invalid", True)

    # Convert row dicts to ImportRowUpdate objects
    rows = []
    for row_data in rows_data:
        # Handle date conversion
        if row_data.get("start_date") and isinstance(row_data["start_date"], str):
            row_data["start_date"] = date.fromisoformat(row_data["start_date"])
        if row_data.get("end_date") and isinstance(row_data["end_date"], str):
            row_data["end_date"] = date.fromisoformat(row_data["end_date"])
        rows.append(ImportRowUpdate(**row_data))

    import_service = ImportService(db)
    results = await import_service.commit_import(
        rows=rows,
        user_id=user_id,
        skip_invalid=skip_invalid,
    )

    succeeded = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    errors = [r.error for r in results if r.error]

    logger.info(
        "bulk_import_job_completed",
        job_id=str(job.id),
        total=len(results),
        succeeded=succeeded,
        failed=failed,
    )

    return {
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "errors": errors[:10],
        "results": [
            {
                "row_number": r.row_number,
                "success": r.success,
                "project_id": str(r.project_id) if r.project_id else None,
                "error": r.error,
            }
            for r in results
        ],
    }


@register_job_handler(JobType.AUDIT_CLEANUP)
async def handle_audit_cleanup(job: Job, db: AsyncSession) -> dict | None:
    """Clean up old audit log entries.

    This handler removes audit log entries older than the
    configured retention period.

    Args:
        job: The job being processed (payload may contain retention_days)
        db: Database session

    Returns:
        Dict with cleanup results
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete

    from app.models.audit import AuditLog

    logger.info(
        "audit_cleanup_job_started",
        job_id=str(job.id),
    )

    # Get retention days from payload or use default (90 days)
    payload = job.payload or {}
    retention_days = payload.get("retention_days", 90)

    cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)

    # Delete old audit entries
    result = await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff_date))
    deleted_count = result.rowcount

    logger.info(
        "audit_cleanup_job_completed",
        job_id=str(job.id),
        deleted_count=deleted_count,
        retention_days=retention_days,
    )

    return {
        "deleted_count": deleted_count,
        "retention_days": retention_days,
        "cutoff_date": cutoff_date.isoformat(),
    }


@register_job_handler(JobType.MONDAY_SYNC)
async def handle_monday_sync(job: Job, db: AsyncSession) -> dict | None:
    """Sync data with Monday.com.

    This handler processes Monday.com sync operations
    for contacts and organizations.

    Payload must contain:
        - sync_type: "contacts" or "organizations"
        - board_id: Monday.com board ID
        - field_mapping: Dict mapping columns to fields
        - triggered_by: UUID of user who triggered sync

    Args:
        job: The job being processed
        db: Database session

    Returns:
        Dict with sync results
    """
    from uuid import UUID

    from app.services.monday_service import MondayService

    logger.info(
        "monday_sync_job_started",
        job_id=str(job.id),
        entity_type=job.entity_type,
        entity_id=str(job.entity_id) if job.entity_id else None,
    )

    payload = job.payload or {}

    if "sync_type" not in payload:
        raise ValueError("Payload must contain 'sync_type' (contacts or organizations)")
    if "board_id" not in payload:
        raise ValueError("Payload must contain 'board_id'")
    if "triggered_by" not in payload:
        raise ValueError("Payload must contain 'triggered_by' user ID")

    sync_type = payload["sync_type"]
    board_id = payload["board_id"]
    field_mapping = payload.get("field_mapping", {})
    triggered_by = (
        UUID(payload["triggered_by"])
        if isinstance(payload["triggered_by"], str)
        else payload["triggered_by"]
    )

    monday_service = MondayService(db)

    try:
        if sync_type == "contacts":
            sync_log = await monday_service.sync_contacts(
                board_id=board_id,
                field_mapping=field_mapping,
                triggered_by=triggered_by,
            )
        elif sync_type == "organizations":
            sync_log = await monday_service.sync_organizations(
                board_id=board_id,
                field_mapping=field_mapping,
                triggered_by=triggered_by,
            )
        else:
            raise ValueError(f"Unknown sync_type: {sync_type}")

        result = {
            "sync_type": sync_type,
            "status": sync_log.status.value,
            "items_processed": sync_log.items_processed,
            "items_created": sync_log.items_created,
            "items_updated": sync_log.items_updated,
            "items_skipped": sync_log.items_skipped,
            "error_message": sync_log.error_message,
        }

        logger.info(
            "monday_sync_job_completed",
            job_id=str(job.id),
            sync_type=sync_type,
            items_processed=sync_log.items_processed,
        )

        return result

    finally:
        await monday_service.close()


@register_job_handler(JobType.DOCUMENT_PROCESSING)
async def handle_document_processing(job: Job, db: AsyncSession) -> dict | None:
    """Process a document for text extraction and embedding.

    This handler wraps existing document processing functionality
    to be executed as a background job.

    entity_id should be set to the document UUID.

    Args:
        job: The job being processed (entity_id = document_id)
        db: Database session

    Returns:
        Dict with processing results
    """
    from sqlalchemy import select

    from app.core.storage import StorageService
    from app.models.document import Document
    from app.services.document_processing_task import _process_document_content

    logger.info(
        "document_processing_job_started",
        job_id=str(job.id),
        document_id=str(job.entity_id) if job.entity_id else None,
    )

    if not job.entity_id:
        raise ValueError("Job must have entity_id set to document UUID")

    # Fetch document
    result = await db.execute(select(Document).where(Document.id == job.entity_id))
    document = result.scalar_one_or_none()

    if not document:
        raise ValueError(f"Document {job.entity_id} not found")

    # Read file content
    storage = StorageService()
    try:
        file_content = await storage.read(document.file_path)
    except FileNotFoundError:
        raise ValueError(f"File not found in storage: {document.file_path}")

    # Process document content
    await _process_document_content(db, document, file_content)

    logger.info(
        "document_processing_job_completed",
        job_id=str(job.id),
        document_id=str(job.entity_id),
        status=document.processing_status,
    )

    return {
        "document_id": str(job.entity_id),
        "status": document.processing_status,
        "text_length": len(document.extracted_text) if document.extracted_text else 0,
    }
