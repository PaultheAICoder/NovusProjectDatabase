/**
 * Audit types for change history tracking.
 */

/** Audit action type - matches backend AuditAction enum */
export type AuditAction = "create" | "update" | "delete" | "archive";

/** Minimal user info for audit log display */
export interface UserSummary {
  id: string;
  display_name: string;
}

/** Individual field change - before and after values */
export interface FieldChange {
  old: unknown;
  new: unknown;
}

/** Audit log entry with user information */
export interface AuditLogEntry {
  id: string;
  entity_type: string;
  entity_id: string;
  action: AuditAction;
  user: UserSummary | null;
  changed_fields: Record<string, FieldChange> | null;
  created_at: string;
}

/** Paginated audit log response - matches backend PaginatedResponse */
export interface AuditLogResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/** Parameters for querying audit logs */
export interface AuditQueryParams {
  entity_type?: string;
  entity_id?: string;
  user_id?: string;
  action?: AuditAction;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
}
