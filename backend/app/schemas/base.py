"""Base schemas for common response patterns."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response schema."""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    message: str


class ValidationErrorDetail(BaseModel):
    """Validation error detail schema."""

    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    """Validation error response schema."""

    error: str = "validation_error"
    message: str
    details: list[ValidationErrorDetail]


class MessageResponse(BaseModel):
    """Simple message response schema."""

    message: str
