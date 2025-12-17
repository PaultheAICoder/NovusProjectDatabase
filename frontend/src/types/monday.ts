/**
 * Monday.com sync types.
 */

export type MondaySyncStatus = "pending" | "in_progress" | "completed" | "failed";
export type MondaySyncType = "organizations" | "contacts";

/** Sync status for individual records (contacts, organizations). */
export type RecordSyncStatus = "synced" | "pending" | "conflict" | "disabled";

/** Sync direction for records. */
export type SyncDirection = "bidirectional" | "npd_to_monday" | "monday_to_npd" | "none";

export interface MondaySyncLog {
  id: string;
  sync_type: MondaySyncType;
  status: MondaySyncStatus;
  board_id: string;
  started_at: string;
  completed_at: string | null;
  items_processed: number;
  items_created: number;
  items_updated: number;
  items_skipped: number;
  error_message: string | null;
}

export interface MondaySyncStatusResponse {
  is_configured: boolean;
  last_org_sync: MondaySyncLog | null;
  last_contact_sync: MondaySyncLog | null;
  recent_logs: MondaySyncLog[];
}

export interface MondayConfigResponse {
  is_configured: boolean;
  organizations_board_id: string | null;
  contacts_board_id: string | null;
}

export interface MondayBoardColumn {
  id: string;
  title: string;
  type: string;
}

export interface MondayBoardInfo {
  id: string;
  name: string;
  columns: MondayBoardColumn[];
}

export interface MondayBoardsResponse {
  boards: MondayBoardInfo[];
}

export interface MondaySyncTriggerRequest {
  sync_type: MondaySyncType;
  board_id?: string;
}

// ============== Conflict Resolution Types ==============

/** Resolution type for sync conflicts. */
export type ConflictResolutionType = "keep_npd" | "keep_monday" | "merge";

/** Sync conflict details from backend. */
export interface SyncConflict {
  id: string;
  entity_type: "contact" | "organization";
  entity_id: string;
  monday_item_id: string;
  npd_data: Record<string, unknown>;
  monday_data: Record<string, unknown>;
  conflict_fields: string[];
  detected_at: string;
  resolved_at: string | null;
  resolution_type: string | null;
  resolved_by_id: string | null;
}

/** Paginated list of conflicts response. */
export interface ConflictListResponse {
  items: SyncConflict[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** Request to resolve a sync conflict. */
export interface ConflictResolveRequest {
  resolution_type: ConflictResolutionType;
  merge_selections?: Record<string, "npd" | "monday">;
}

/** Conflict statistics. */
export interface ConflictStats {
  unresolved: number;
  resolved: number;
  total: number;
}

// ============== Sync Queue Types ==============

/** Status for sync queue items. */
export type SyncQueueStatus = "pending" | "in_progress" | "completed" | "failed";

/** Direction for sync queue operations. */
export type SyncQueueDirection = "to_monday" | "to_npd";

/** Operation type for sync queue items. */
export type SyncQueueOperation = "create" | "update" | "delete";

/** Sync queue item from backend. */
export interface SyncQueueItem {
  id: string;
  entity_type: "contact" | "organization";
  entity_id: string;
  direction: SyncQueueDirection;
  operation: SyncQueueOperation;
  status: SyncQueueStatus;
  attempts: number;
  max_attempts: number;
  last_attempt: string | null;
  next_retry: string | null;
  error_message: string | null;
  created_at: string;
}

/** Paginated list of sync queue items response. */
export interface SyncQueueListResponse {
  items: SyncQueueItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** Sync queue statistics. */
export interface SyncQueueStats {
  pending: number;
  in_progress: number;
  completed: number;
  failed: number;
}
