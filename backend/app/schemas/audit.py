"""Audit Log Pydantic schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.audit import AuditAction


class AuditLogResponse(BaseModel):
    """Audit log response schema for reading individual entries."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    entity_id: UUID
    action: AuditAction
    user_id: UUID | None = None
    changed_fields: dict[str, dict[str, Any]] | None = Field(
        None,
        description='Format: {"field_name": {"old": value, "new": value}}',
    )
    metadata_: dict[str, Any] | None = Field(
        None,
        alias="metadata",
        description="Additional context: IP address, user agent, etc.",
    )
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""

    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class FieldChange(BaseModel):
    """Individual field change detail."""

    old: Any = None
    new: Any = None


class AuditLogSummary(BaseModel):
    """Minimal audit log info for inline display."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: AuditAction
    user_id: UUID | None = None
    created_at: datetime
