"""Document processing queue Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.document_queue import DocumentQueueOperation, DocumentQueueStatus


class DocumentQueueItemResponse(BaseModel):
    """Response with document queue item details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    document_name: str  # Joined from documents table
    status: DocumentQueueStatus
    operation: DocumentQueueOperation
    attempts: int
    max_attempts: int
    error_message: str | None
    next_retry: datetime | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DocumentQueueListResponse(BaseModel):
    """Paginated list of document queue items."""

    items: list[DocumentQueueItemResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class DocumentQueueStatsResponse(BaseModel):
    """Document queue statistics."""

    pending: int
    in_progress: int
    completed: int
    failed: int
    total: int
