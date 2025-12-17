"""Monday.com sync Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.monday_sync import (
    MondaySyncStatus,
    MondaySyncType,
    RecordSyncStatus,
    SyncDirection,
)

# Re-export enums for external use
__all__ = [
    "MondaySyncStatus",
    "MondaySyncType",
    "RecordSyncStatus",
    "SyncDirection",
    "MondayFieldMapping",
    "MondayBoardConfig",
    "MondaySyncTriggerRequest",
    "MondaySyncLogResponse",
    "MondaySyncStatusResponse",
    "MondayConfigResponse",
    "MondayBoardColumn",
    "MondayBoardInfo",
    "MondayBoardsResponse",
    "SyncConflictResponse",
]


class MondayFieldMapping(BaseModel):
    """Field mapping from Monday column to NPD field."""

    monday_column_id: str = Field(..., description="Monday.com column ID")
    npd_field: str = Field(..., description="NPD field name (e.g., 'name', 'email')")


class MondayBoardConfig(BaseModel):
    """Configuration for a Monday.com board sync."""

    board_id: str = Field(..., description="Monday.com board ID")
    sync_type: MondaySyncType
    field_mappings: list[MondayFieldMapping] = Field(
        default_factory=list, description="Mapping of Monday columns to NPD fields"
    )


class MondaySyncTriggerRequest(BaseModel):
    """Request to trigger a Monday sync."""

    sync_type: MondaySyncType
    board_id: str | None = Field(
        None, description="Override board ID (uses config default if not provided)"
    )


class MondaySyncLogResponse(BaseModel):
    """Response with sync log details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sync_type: MondaySyncType
    status: MondaySyncStatus
    board_id: str
    started_at: datetime
    completed_at: datetime | None
    items_processed: int
    items_created: int
    items_updated: int
    items_skipped: int
    error_message: str | None


class MondaySyncStatusResponse(BaseModel):
    """Response with sync status and recent logs."""

    is_configured: bool = Field(..., description="Whether Monday API key is set")
    last_org_sync: MondaySyncLogResponse | None = None
    last_contact_sync: MondaySyncLogResponse | None = None
    recent_logs: list[MondaySyncLogResponse] = Field(default_factory=list)


class MondayConfigResponse(BaseModel):
    """Response with Monday configuration status."""

    is_configured: bool
    organizations_board_id: str | None
    contacts_board_id: str | None


class MondayBoardColumn(BaseModel):
    """Column information from a Monday board."""

    id: str
    title: str
    type: str


class MondayBoardInfo(BaseModel):
    """Information about a Monday board."""

    id: str
    name: str
    columns: list[MondayBoardColumn]


class MondayBoardsResponse(BaseModel):
    """Response with available Monday boards."""

    boards: list[MondayBoardInfo]


class SyncConflictResponse(BaseModel):
    """Response with sync conflict details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    entity_id: UUID
    monday_item_id: str
    npd_data: dict
    monday_data: dict
    conflict_fields: list[str]
    detected_at: datetime
    resolved_at: datetime | None
    resolution_type: str | None
