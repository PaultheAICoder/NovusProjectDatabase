"""Document API endpoints."""

import os
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import crud_limit, limiter, upload_limit
from app.core.storage import StorageService
from app.models.document import Document, DocumentChunk
from app.models.project import Project
from app.models.user import User
from app.schemas.document import (
    DocumentDetail,
    DocumentListResponse,
    DocumentResponse,
)
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService

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

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_file_size_mb}MB",
        )

    # Store file
    storage = StorageService()
    file_path = await storage.save(
        content,
        filename=file.filename or "document",
        project_id=str(project_id),
    )

    # Create document record
    document = Document(
        project_id=project_id,
        file_path=file_path,
        display_name=file.filename or "document",
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        uploaded_by=current_user.id,
        processing_status="pending",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Process document asynchronously (for now, inline for simplicity)
    # In production, this should be a background task
    try:
        processor = DocumentProcessor()
        if processor.is_supported(document.mime_type):
            extracted_text = await processor.extract_text(
                content,
                document.mime_type,
                document.display_name,
            )
            document.extracted_text = extracted_text
            document.processing_status = "completed"

            # Create chunks and embeddings
            embedding_service = EmbeddingService()
            chunks = embedding_service.chunk_text(extracted_text)

            for i, chunk_content in enumerate(chunks):
                embedding = await embedding_service.generate_embedding(chunk_content)
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=i,
                    content=chunk_content,
                    embedding=embedding,
                )
                db.add(chunk)
        else:
            document.processing_status = "skipped"

        await db.commit()
        await db.refresh(document)

    except Exception as e:
        logger.exception(
            "document_processing_failed",
            document_id=str(document.id),
            project_id=str(project_id),
            filename=document.display_name,
            error=str(e),
        )
        document.processing_status = "failed"
        document.processing_error = str(e)
        await db.commit()

    return DocumentResponse.model_validate(document)


@router.get("", response_model=DocumentListResponse)
@limiter.limit(crud_limit)
async def list_documents(
    request: Request,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    """List all documents for a project."""
    await get_project(project_id, db)

    # Get documents
    result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.uploaded_at.desc())
    )
    documents = result.scalars().all()

    # Get count
    count_result = await db.execute(
        select(func.count())
        .select_from(Document)
        .where(Document.project_id == project_id)
    )
    total = count_result.scalar() or 0

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
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
