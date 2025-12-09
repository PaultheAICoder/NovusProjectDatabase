"""Background document processing task.

This module provides background processing for document text extraction
and embedding generation. It creates its own database session since
FastAPI BackgroundTasks run after the response is sent.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.storage import StorageService
from app.database import async_session_maker
from app.models.document import Document, DocumentChunk
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService

logger = get_logger(__name__)


async def process_document_background(document_id: UUID) -> None:
    """
    Process a document in the background.

    This function is designed to be called from FastAPI BackgroundTasks.
    It creates its own database session since the original request session
    is closed when this runs.

    Args:
        document_id: The UUID of the document to process

    Steps:
        1. Create a new database session
        2. Fetch the document by ID
        3. Read file content from storage
        4. Extract text using DocumentProcessor
        5. Create chunks and generate embeddings
        6. Update document status to completed or failed
    """
    logger.info(
        "background_processing_started",
        document_id=str(document_id),
    )

    async with async_session_maker() as db:
        try:
            # Fetch the document
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()

            if not document:
                logger.error(
                    "document_not_found_for_processing",
                    document_id=str(document_id),
                )
                return

            # Read file content from storage
            storage = StorageService()
            try:
                file_content = await storage.read(document.file_path)
            except FileNotFoundError:
                document.processing_status = "failed"
                document.processing_error = "File not found in storage"
                await db.commit()
                logger.error(
                    "file_not_found_in_storage",
                    document_id=str(document_id),
                    file_path=document.file_path,
                )
                return

            # Process the document
            await _process_document_content(db, document, file_content)

            logger.info(
                "background_processing_completed",
                document_id=str(document_id),
                status=document.processing_status,
            )

        except Exception as e:
            await db.rollback()
            logger.exception(
                "background_processing_failed",
                document_id=str(document_id),
                error=str(e),
            )
            # Try to update the document status to failed
            try:
                async with async_session_maker() as error_db:
                    result = await error_db.execute(
                        select(Document).where(Document.id == document_id)
                    )
                    document = result.scalar_one_or_none()
                    if document:
                        document.processing_status = "failed"
                        document.processing_error = str(e)[:500]
                        await error_db.commit()
            except Exception as inner_e:
                logger.exception(
                    "failed_to_update_error_status",
                    document_id=str(document_id),
                    error=str(inner_e),
                )


async def _process_document_content(
    db: AsyncSession,
    document: Document,
    file_content: bytes,
) -> None:
    """
    Process document content: extract text, create chunks, generate embeddings.

    Args:
        db: Database session
        document: Document model instance
        file_content: Raw file bytes
    """
    processor = DocumentProcessor()

    if not processor.is_supported(document.mime_type):
        document.processing_status = "skipped"
        await db.commit()
        logger.info(
            "document_processing_skipped",
            document_id=str(document.id),
            mime_type=document.mime_type,
            reason="Unsupported MIME type",
        )
        return

    try:
        # Extract text
        extracted_text = await processor.extract_text(
            file_content,
            document.mime_type,
            document.display_name,
        )
        document.extracted_text = extracted_text

        # Create chunks and embeddings
        embedding_service = EmbeddingService()
        chunks = embedding_service.chunk_text(extracted_text)

        logger.debug(
            "creating_document_chunks",
            document_id=str(document.id),
            chunk_count=len(chunks),
        )

        for i, chunk_content in enumerate(chunks):
            embedding = await embedding_service.generate_embedding(chunk_content)
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=i,
                content=chunk_content,
                embedding=embedding,
            )
            db.add(chunk)

        document.processing_status = "completed"
        await db.commit()

        logger.info(
            "document_text_extracted",
            document_id=str(document.id),
            text_length=len(extracted_text),
            chunk_count=len(chunks),
        )

    except Exception as e:
        document.processing_status = "failed"
        document.processing_error = str(e)[:500]
        await db.commit()

        logger.exception(
            "document_content_processing_failed",
            document_id=str(document.id),
            filename=document.display_name,
            error=str(e),
        )
