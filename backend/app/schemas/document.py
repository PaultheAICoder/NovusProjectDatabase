"""Document Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.tag import TagResponse
from app.schemas.user import UserResponse


class DocumentBase(BaseModel):
    """Base document schema."""

    display_name: str = Field(max_length=255)


class DocumentResponse(DocumentBase):
    """Document response schema."""

    id: UUID
    project_id: UUID
    file_path: str
    mime_type: str
    file_size: int
    uploaded_by: UUID
    uploaded_at: datetime
    processing_status: str
    processing_error: str | None = None
    suggested_tag_ids: list[UUID] | None = None
    dismissed_tag_ids: list[UUID] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentResponse):
    """Document detail with uploader info."""

    uploader: UserResponse
    extracted_text: str | None = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Response for document list with pagination."""

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DocumentStatusResponse(BaseModel):
    """Lightweight status response for polling."""

    id: UUID
    processing_status: str
    processing_error: str | None = None

    model_config = {"from_attributes": True}


class DocumentTagSuggestionsResponse(BaseModel):
    """Tag suggestions for a document."""

    document_id: UUID
    suggested_tags: list[TagResponse] = []
    has_suggestions: bool = False


class DismissTagSuggestionRequest(BaseModel):
    """Request to dismiss a tag suggestion."""

    tag_id: UUID


class DocumentQueueProcessResult(BaseModel):
    """Result from processing the document queue."""

    status: str = Field(..., description="Overall status: success, partial, error")
    items_processed: int
    items_succeeded: int
    items_failed: int
    items_requeued: int = Field(default=0, description="Items requeued for retry")
    items_max_retries: int = Field(
        default=0, description="Items that hit max retry limit"
    )
    items_recovered: int = Field(
        default=0, description="Items recovered from stuck state"
    )
    errors: list[str] = Field(default_factory=list)
    timestamp: str
