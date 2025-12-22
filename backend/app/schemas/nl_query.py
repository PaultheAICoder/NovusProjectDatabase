"""Natural Language Query Parser schemas."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.project import ProjectStatus


class DateRange(BaseModel):
    """Parsed date range from temporal expressions."""

    start_date: date | None = None
    end_date: date | None = None
    original_expression: str | None = Field(
        default=None,
        description="Original temporal expression, e.g., 'last 2 years'",
    )


class ParsedQueryIntent(BaseModel):
    """Structured intent extracted from natural language query."""

    # Search text (keywords that don't map to filters)
    search_text: str = Field(
        default="",
        description="Remaining search keywords after extracting structured filters",
    )

    # Temporal filters
    date_range: DateRange | None = Field(
        default=None,
        description="Parsed date range for filtering by start_date",
    )

    # Entity filters
    organization_name: str | None = Field(
        default=None,
        description="Extracted organization/client name",
    )
    organization_id: UUID | None = Field(
        default=None,
        description="Resolved organization UUID (after DB lookup)",
    )

    # Technology/domain filters
    technology_keywords: list[str] = Field(
        default_factory=list,
        description="Technology-related keywords (IoT, Bluetooth, etc.)",
    )
    tag_ids: list[UUID] = Field(
        default_factory=list,
        description="Resolved tag UUIDs for technology keywords",
    )

    # Status filters
    status: list[ProjectStatus] = Field(
        default_factory=list,
        description="Extracted status filters",
    )

    # Confidence score
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Parser confidence in the interpretation",
    )


class NLQueryParseRequest(BaseModel):
    """Request to parse a natural language query."""

    query: str = Field(..., min_length=1, description="Natural language search query")


class NLQueryParseResponse(BaseModel):
    """Response from natural language query parsing."""

    original_query: str
    parsed_intent: ParsedQueryIntent
    fallback_used: bool = Field(
        default=False,
        description="True if parsing failed and fallback was used",
    )
    parse_explanation: str | None = Field(
        default=None,
        description="Human-readable explanation of how query was interpreted",
    )
