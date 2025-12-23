"""Document API endpoints."""

import os
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.config import get_settings
from app.core.file_utils import read_file_with_spooling
from app.core.logging import get_logger
from app.core.rate_limit import crud_limit, limiter, upload_limit
from app.core.storage import StorageService
from app.models.document import Document
from app.models.document_queue import DocumentQueueOperation
from app.models.project import Project
from app.models.tag import Tag
from app.models.user import User
from app.schemas.document import (
    DismissTagSuggestionRequest,
    DocumentDetail,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentTagSuggestionsResponse,
)
from app.schemas.tag import TagResponse
from app.services.antivirus import AntivirusService, ScanResult
from app.services.audit_service import AuditService
from app.services.document_processor import DocumentProcessor
from app.services.document_queue_service import DocumentQueueService
from app.services.file_validation import FileValidationService
from app.services.search_cache import invalidate_search_cache

logger = get_logger(__name__)

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])

settings = get_settings()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/plain",
    "text/csv",
}


async def get_project(
    project_id: UUID,
    db: AsyncSession,
) -> Project:
    """Get project or raise 404."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(upload_limit)
async def upload_document(
    request: Request,
    project_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """
    Upload a document to a project.

    Supports PDF, DOCX, XLSX, XLS, TXT, and CSV files.
    Maximum file size is configured by MAX_FILE_SIZE_MB.
    """
    # Verify project exists
    await get_project(project_id, db)

    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. "
            f"Allowed types: PDF, DOCX, XLSX, XLS, TXT, CSV",
        )

    # Read file with size validation and automatic disk spillover for large files
    spooled_file = await read_file_with_spooling(
        file=file,
        max_size_bytes=settings.max_file_size_bytes,
        spool_threshold=5 * 1024 * 1024,  # 5MB threshold
    )

    try:
        # Get file size for later
        spooled_file.seek(0, 2)
        file_size = spooled_file.tell()
        spooled_file.seek(0)

        # Validate file content matches claimed type (magic number check)
        validator = FileValidationService()

        # First, check for dangerous file types
        if not validator.is_safe_file_type_from_file(spooled_file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File type not allowed for security reasons",
            )

        # Then verify content matches claimed MIME type
        is_valid, detected_mime = validator.validate_content_type_from_file(
            spooled_file, file.content_type or "application/octet-stream"
        )
        if not is_valid:
            logger.warning(
                "file_type_spoofing_attempt",
                claimed_type=file.content_type,
                detected_type=detected_mime,
                filename=file.filename,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match the declared file type",
            )

        # Antivirus scan (if enabled)
        antivirus = AntivirusService()
        if antivirus.is_enabled:
            scan_result = await antivirus.scan_file(
                spooled_file, file.filename or "document"
            )

            if scan_result.result == ScanResult.INFECTED:
                logger.warning(
                    "upload_blocked_malware",
                    filename=file.filename,
                    threat_name=scan_result.threat_name,
                    user_id=str(current_user.id),
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File rejected: malware detected ({scan_result.threat_name})",
                )

            if scan_result.result == ScanResult.ERROR:
                if not antivirus.fail_open:
                    logger.warning(
                        "upload_blocked_scan_error",
                        filename=file.filename,
                        error=scan_result.message,
                        user_id=str(current_user.id),
                    )
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Antivirus scanning unavailable. Upload rejected.",
                    )
                else:
                    logger.warning(
                        "upload_allowed_scan_error",
                        filename=file.filename,
                        error=scan_result.message,
                        user_id=str(current_user.id),
                    )

            if scan_result.result == ScanResult.CLEAN:
                logger.info(
                    "antivirus_scan_passed",
                    filename=file.filename,
                )

        # Store file (reset position before saving)
        spooled_file.seek(0)
        storage = StorageService()
        file_path = await storage.save_file(
            spooled_file,
            filename=file.filename or "document",
            project_id=str(project_id),
        )
    finally:
        # Always close the spooled file
        spooled_file.close()

    # Create document record with pending status
    document = Document(
        project_id=project_id,
        file_path=file_path,
        display_name=file.filename or "document",
        mime_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        uploaded_by=current_user.id,
        processing_status="pending",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_create(
        entity_type="document",
        entity_id=document.id,
        entity_data={
            "id": str(document.id),
            "project_id": str(document.project_id),
            "display_name": document.display_name,
            "mime_type": document.mime_type,
            "file_size": document.file_size,
        },
        user_id=current_user.id,
    )

    # Queue document for processing (durable queue survives restarts)
    processor = DocumentProcessor()
    if processor.is_supported(document.mime_type):
        queue_service = DocumentQueueService(db)
        await queue_service.enqueue(
            document_id=document.id,
            operation=DocumentQueueOperation.PROCESS,
        )
        await db.commit()
        logger.info(
            "document_processing_queued",
            document_id=str(document.id),
            project_id=str(project_id),
            filename=document.display_name,
        )
    else:
        # Mark unsupported documents as skipped immediately
        document.processing_status = "skipped"
        await db.commit()
        await db.refresh(document)
        logger.info(
            "document_processing_skipped",
            document_id=str(document.id),
            mime_type=document.mime_type,
            reason="Unsupported MIME type",
        )

    # Invalidate search cache (new document may affect search results)
    await invalidate_search_cache()

    return DocumentResponse.model_validate(document)


@router.get("", response_model=DocumentListResponse)
@limiter.limit(crud_limit)
async def list_documents(
    request: Request,
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    """List documents for a project with pagination."""
    await get_project(project_id, db)

    # Build base query
    query = select(Document).where(Document.project_id == project_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.order_by(Document.uploaded_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.get("/{document_id}", response_model=DocumentDetail)
@limiter.limit(crud_limit)
async def get_document(
    request: Request,
    project_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentDetail:
    """Get a document's details."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.uploader))
        .where(Document.id == document_id, Document.project_id == project_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentDetail.model_validate(document)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
@limiter.limit(crud_limit)
async def get_document_status(
    request: Request,
    project_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentStatusResponse:
    """
    Get document processing status (lightweight for polling).

    Returns only the document ID, processing status, and any error message.
    Optimized for frequent polling during document processing.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.project_id == project_id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentStatusResponse.model_validate(document)


@router.get("/{document_id}/download")
@limiter.limit(crud_limit)
async def download_document(
    request: Request,
    project_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a document file."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.project_id == project_id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Get file from storage
    storage = StorageService()
    file_path = storage.get_path(document.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on storage",
        )

    return FileResponse(
        path=file_path,
        filename=document.display_name,
        media_type=document.mime_type,
    )


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
@limiter.limit(upload_limit)
async def reprocess_document(
    request: Request,
    project_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """
    Retry processing a failed document.

    Only documents with status "failed" can be reprocessed.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.project_id == project_id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.processing_status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document cannot be reprocessed. Current status: {document.processing_status}. "
            "Only failed documents can be reprocessed.",
        )

    # Reset status and clear error
    document.processing_status = "pending"
    document.processing_error = None
    await db.commit()
    await db.refresh(document)

    # Queue document for reprocessing (durable queue survives restarts)
    queue_service = DocumentQueueService(db)
    await queue_service.enqueue(
        document_id=document.id,
        operation=DocumentQueueOperation.REPROCESS,
    )
    await db.commit()
    logger.info(
        "document_reprocessing_queued",
        document_id=str(document.id),
        project_id=str(project_id),
        filename=document.display_name,
    )

    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(crud_limit)
async def delete_document(
    request: Request,
    project_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a document."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.project_id == project_id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Capture data for audit before deletion
    document_data = {
        "id": str(document.id),
        "project_id": str(document.project_id),
        "display_name": document.display_name,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
    }

    # Delete file from storage
    storage = StorageService()
    try:
        await storage.delete(document.file_path)
    except Exception as e:
        logger.debug(
            "document_file_deletion_skipped",
            document_id=str(document_id),
            file_path=document.file_path,
            reason="File may already be deleted",
            error=str(e),
        )

    # Delete from database (cascade will delete chunks)
    await db.delete(document)
    await db.commit()

    # Audit logging
    audit_service = AuditService(db)
    await audit_service.log_delete(
        entity_type="document",
        entity_id=document_id,
        entity_data=document_data,
        user_id=current_user.id,
    )

    # Invalidate search cache
    await invalidate_search_cache()


@router.get(
    "/{document_id}/tag-suggestions", response_model=DocumentTagSuggestionsResponse
)
@limiter.limit(crud_limit)
async def get_document_tag_suggestions(
    request: Request,
    project_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentTagSuggestionsResponse:
    """
    Get tag suggestions based on document content.

    Returns tags that were suggested by document content analysis,
    excluding any tags that have been dismissed by the user.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.project_id == project_id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Filter out dismissed tags
    suggested_ids = document.suggested_tag_ids or []
    dismissed_ids = set(document.dismissed_tag_ids or [])
    active_ids = [tid for tid in suggested_ids if tid not in dismissed_ids]

    if not active_ids:
        return DocumentTagSuggestionsResponse(
            document_id=document_id,
            suggested_tags=[],
            has_suggestions=False,
        )

    # Fetch tag details
    tag_result = await db.execute(select(Tag).where(Tag.id.in_(active_ids)))
    tags = tag_result.scalars().all()

    return DocumentTagSuggestionsResponse(
        document_id=document_id,
        suggested_tags=[TagResponse.model_validate(t) for t in tags],
        has_suggestions=len(tags) > 0,
    )


@router.post("/{document_id}/dismiss-tag", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(crud_limit)
async def dismiss_tag_suggestion(
    request: Request,
    project_id: UUID,
    document_id: UUID,
    data: DismissTagSuggestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Dismiss a tag suggestion for a document.

    The dismissed tag will no longer appear in suggestions for this document.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.project_id == project_id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    dismissed = document.dismissed_tag_ids or []
    if data.tag_id not in dismissed:
        document.dismissed_tag_ids = dismissed + [data.tag_id]
        await db.commit()
