"""Import Pydantic schemas for bulk import functionality."""

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.project import ProjectStatus


class ImportRowBase(BaseModel):
    """Base import row representing a project to import."""

    row_number: int = Field(..., description="Row number in the source CSV")
    name: Optional[str] = None
    organization_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    owner_email: Optional[str] = None
    tags: Optional[list[str]] = None
    billing_amount: Optional[str] = None
    billing_recipient: Optional[str] = None
    billing_notes: Optional[str] = None
    pm_notes: Optional[str] = None
    monday_url: Optional[str] = None
    jira_url: Optional[str] = None
    gitlab_url: Optional[str] = None


class ImportRowValidation(BaseModel):
    """Validation result for a single import row."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ImportRowSuggestion(BaseModel):
    """AI-generated suggestions for an import row."""

    suggested_description: Optional[str] = None
    suggested_tags: Optional[list[str]] = None
    suggested_organization_id: Optional[UUID] = None
    suggested_owner_id: Optional[UUID] = None
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score for suggestions"
    )


class ImportRowPreview(ImportRowBase):
    """Import row with validation and suggestions for preview."""

    validation: ImportRowValidation
    suggestions: Optional[ImportRowSuggestion] = None

    # Resolved IDs (when found)
    resolved_organization_id: Optional[UUID] = None
    resolved_owner_id: Optional[UUID] = None
    resolved_tag_ids: Optional[list[UUID]] = None


class ImportPreviewRequest(BaseModel):
    """Request to preview an import."""

    include_suggestions: bool = Field(
        default=True, description="Include AI suggestions for missing fields"
    )


class ImportPreviewResponse(BaseModel):
    """Response containing import preview data."""

    filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    rows: list[ImportRowPreview]
    column_mapping: dict[str, str] = Field(
        default_factory=dict, description="Detected column name mappings"
    )


class ImportRowUpdate(BaseModel):
    """Updates to an import row before committing."""

    row_number: int
    name: Optional[str] = None
    organization_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    tag_ids: Optional[list[UUID]] = None
    billing_amount: Optional[Decimal] = None
    billing_recipient: Optional[str] = None
    billing_notes: Optional[str] = None
    pm_notes: Optional[str] = None
    monday_url: Optional[str] = None
    jira_url: Optional[str] = None
    gitlab_url: Optional[str] = None


class ImportCommitRequest(BaseModel):
    """Request to commit an import."""

    rows: list[ImportRowUpdate] = Field(
        ..., description="Rows to import with any user modifications"
    )
    skip_invalid: bool = Field(
        default=True, description="Skip rows that fail validation"
    )


class ImportCommitResult(BaseModel):
    """Result of a single row import."""

    row_number: int
    success: bool
    project_id: Optional[UUID] = None
    error: Optional[str] = None


class ImportCommitResponse(BaseModel):
    """Response from import commit."""

    total: int
    successful: int
    failed: int
    results: list[ImportCommitResult]


class AutofillRequest(BaseModel):
    """Request for AI-assisted field autofill."""

    name: str = Field(..., min_length=1, description="Project name to use for context")
    existing_description: Optional[str] = None
    organization_id: Optional[UUID] = None


class AutofillResponse(BaseModel):
    """Response with AI-suggested field values."""

    suggested_description: Optional[str] = None
    suggested_tags: list[str] = Field(default_factory=list)
    suggested_tag_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall confidence score"
    )
