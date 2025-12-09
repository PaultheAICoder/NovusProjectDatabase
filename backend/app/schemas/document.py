"""Document Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

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
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentResponse):
    """Document detail with uploader info."""

    uploader: UserResponse
    extracted_text: str | None = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Response for document list."""

    items: list[DocumentResponse]
    total: int


class DocumentStatusResponse(BaseModel):
    """Lightweight status response for polling."""

    id: UUID
    processing_status: str
    processing_error: str | None = None

    model_config = {"from_attributes": True}
