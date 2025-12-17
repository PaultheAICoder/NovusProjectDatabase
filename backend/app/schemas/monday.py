"""Monday.com sync Pydantic schemas."""

from datetime import datetime
from typing import Any
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
    "MondayItemMutationResponse",
    "MondayCreateItemRequest",
    "MondayUpdateItemRequest",
    # Webhook schemas
    "MondayWebhookChallenge",
    "MondayWebhookChallengeResponse",
    "MondayWebhookEventValue",
    "MondayWebhookEvent",
    "MondayWebhookPayload",
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


class MondayItemMutationResponse(BaseModel):
    """Response from Monday.com item mutation (create/update/delete)."""

    id: str = Field(..., description="Monday.com item ID")
    name: str | None = Field(None, description="Item name (not returned by delete)")


class MondayCreateItemRequest(BaseModel):
    """Request to create a new item in Monday.com."""

    board_id: str = Field(..., description="Target board ID")
    item_name: str = Field(..., description="Name for the new item")
    column_values: dict[str, Any] | None = Field(
        None, description="Column values (column_id -> value)"
    )
    group_id: str | None = Field(None, description="Target group ID")


class MondayUpdateItemRequest(BaseModel):
    """Request to update an existing Monday.com item."""

    board_id: str = Field(..., description="Board containing the item")
    item_id: str = Field(..., description="Item ID to update")
    column_values: dict[str, Any] = Field(..., description="Column values to update")


# Webhook-related schemas


class MondayWebhookChallenge(BaseModel):
    """Monday.com webhook challenge verification request."""

    challenge: str = Field(..., description="Challenge token to echo back")


class MondayWebhookChallengeResponse(BaseModel):
    """Response to Monday.com challenge verification."""

    challenge: str = Field(..., description="Echo of the challenge token")


class MondayWebhookEventValue(BaseModel):
    """Value object within a webhook event."""

    value: Any | None = None
    name: str | None = None
    # Other potential fields from Monday.com

    model_config = ConfigDict(extra="allow")


class MondayWebhookEvent(BaseModel):
    """Event payload from Monday.com webhook."""

    type: str = Field(
        ..., description="Event type: create_item, change_column_value, item_deleted"
    )
    pulseId: str | None = Field(
        None, description="Item ID (called pulse in Monday.com)"
    )
    pulseName: str | None = Field(None, description="Item name")
    boardId: str | None = Field(None, description="Board ID where event occurred")
    groupId: str | None = Field(None, description="Group ID within the board")
    groupName: str | None = Field(None, description="Group name")
    columnId: str | None = Field(None, description="Column ID for column value changes")
    columnType: str | None = Field(None, description="Column type")
    columnTitle: str | None = Field(None, description="Column title")
    value: MondayWebhookEventValue | None = Field(None, description="New value")
    previousValue: MondayWebhookEventValue | None = Field(
        None, description="Previous value"
    )
    triggerTime: str | None = Field(None, description="When the event was triggered")
    subscriptionId: str | None = Field(None, description="Webhook subscription ID")
    triggerUuid: str | None = Field(None, description="Unique event identifier")

    model_config = ConfigDict(extra="allow")


class MondayWebhookPayload(BaseModel):
    """Full Monday.com webhook payload."""

    event: MondayWebhookEvent = Field(..., description="The event data")

    model_config = ConfigDict(extra="allow")
