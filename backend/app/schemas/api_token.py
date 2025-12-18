"""API Token Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class APITokenBase(BaseModel):
    """Base API token schema."""

    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] | None = Field(None, max_length=10)
    expires_at: datetime | None = None


class APITokenCreate(APITokenBase):
    """Schema for creating an API token."""

    pass  # Inherits all fields from base


class APITokenResponse(BaseModel):
    """API token response schema (metadata only, no secrets)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    token_prefix: str  # First 8 chars for identification
    scopes: list[str] | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    is_active: bool
    created_at: datetime


class APITokenCreateResponse(BaseModel):
    """Response after token creation (includes plaintext token ONCE)."""

    token: str = Field(..., description="Plaintext token - shown only once")
    token_info: APITokenResponse
