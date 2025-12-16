"""Import Pydantic schemas for bulk import functionality."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.project import ProjectLocation, ProjectStatus


class ImportRowBase(BaseModel):
    """Base import row representing a project to import."""

    row_number: int = Field(..., description="Row number in the source CSV")
    name: str | None = None
    organization_name: str | None = None
    description: str | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    owner_email: str | None = None
    tags: list[str] | None = None
    billing_amount: str | None = None
    billing_recipient: str | None = None
    billing_notes: str | None = None
    pm_notes: str | None = None
    monday_url: str | None = None
    jira_url: str | None = None
    gitlab_url: str | None = None


class ImportRowValidation(BaseModel):
    """Validation result for a single import row."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ImportRowSuggestion(BaseModel):
    """AI-generated suggestions for an import row."""

    suggested_description: str | None = None
    suggested_tags: list[str] | None = None
    suggested_organization_id: UUID | None = None
    suggested_owner_id: UUID | None = None
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score for suggestions"
    )


class ImportRowPreview(ImportRowBase):
    """Import row with validation and suggestions for preview."""

    validation: ImportRowValidation
    suggestions: ImportRowSuggestion | None = None

    # Resolved IDs (when found)
    resolved_organization_id: UUID | None = None
    resolved_owner_id: UUID | None = None
    resolved_tag_ids: list[UUID] | None = None


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
    name: str | None = None
    organization_id: UUID | None = None
    owner_id: UUID | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    location: ProjectLocation | None = None
    location_other: str | None = None
    tag_ids: list[UUID] | None = None
    billing_amount: Decimal | None = None
    billing_recipient: str | None = None
    billing_notes: str | None = None
    pm_notes: str | None = None
    monday_url: str | None = None
    jira_url: str | None = None
    gitlab_url: str | None = None


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
    project_id: UUID | None = None
    error: str | None = None


class ImportCommitResponse(BaseModel):
    """Response from import commit."""

    total: int
    successful: int
    failed: int
    results: list[ImportCommitResult]


class AutofillRequest(BaseModel):
    """Request for AI-assisted field autofill."""

    name: str = Field(..., min_length=1, description="Project name to use for context")
    existing_description: str | None = None
    organization_id: UUID | None = None


class AutofillResponse(BaseModel):
    """Response with AI-suggested field values."""

    suggested_description: str | None = None
    suggested_tags: list[str] = Field(default_factory=list)
    suggested_tag_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall confidence score"
    )
