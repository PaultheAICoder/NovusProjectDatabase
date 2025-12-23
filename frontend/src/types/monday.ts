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

/** Result for a single conflict in bulk resolution. */
export interface BulkResolveResult {
  conflict_id: string;
  success: boolean;
  error: string | null;
}

/** Request to bulk resolve multiple conflicts. */
export interface BulkConflictResolveRequest {
  conflict_ids: string[];
  resolution_type: "keep_npd" | "keep_monday"; // merge not allowed for bulk
}

/** Response from bulk conflict resolution. */
export interface BulkConflictResolveResponse {
  total: number;
  succeeded: number;
  failed: number;
  results: BulkResolveResult[];
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

// ============== Auto-Resolution Rule Types ==============

/** Preferred source for auto-resolution. */
export type PreferredSource = "npd" | "monday";

/** Auto-resolution rule from backend. */
export interface AutoResolutionRule {
  id: string;
  name: string;
  entity_type: "contact" | "organization" | "*";
  field_name: string | null;
  preferred_source: PreferredSource;
  is_enabled: boolean;
  priority: number;
  created_at: string;
  created_by_id: string | null;
}

/** Request to create an auto-resolution rule. */
export interface AutoResolutionRuleCreate {
  name: string;
  entity_type: "contact" | "organization" | "*";
  field_name?: string | null;
  preferred_source: PreferredSource;
  is_enabled?: boolean;
  priority?: number;
}

/** Request to update an auto-resolution rule. */
export interface AutoResolutionRuleUpdate {
  name?: string;
  entity_type?: "contact" | "organization" | "*";
  field_name?: string | null;
  preferred_source?: PreferredSource;
  is_enabled?: boolean;
  priority?: number;
}

/** List of auto-resolution rules response. */
export interface AutoResolutionRuleListResponse {
  rules: AutoResolutionRule[];
  total: number;
}

/** Request to reorder rule priorities. */
export interface AutoResolutionRuleReorderRequest {
  rule_ids: string[];
}

// ============== Monday Contact Search Types ==============

/** A matching contact from Monday.com search. */
export interface MondayContactMatch {
  monday_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  role_title: string | null;
  organization: string | null;
  board_id: string;
}

/** Response from Monday.com contact search. */
export interface MondayContactSearchResponse {
  matches: MondayContactMatch[];
  total_matches: number;
  query: string;
  board_id: string;
  has_more: boolean;
  cursor: string | null;
}

/** Response from push contact to Monday. */
export interface ContactSyncResponse {
  contact_id: string;
  sync_triggered: boolean;
  message: string;
  monday_id: string | null;
}
