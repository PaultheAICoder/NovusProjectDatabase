/**
 * Monday.com sync types.
 */

export type MondaySyncStatus = "pending" | "in_progress" | "completed" | "failed";
export type MondaySyncType = "organizations" | "contacts";

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
