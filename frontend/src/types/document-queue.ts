/**
 * Document processing queue types.
 */

/** Status for document queue items. */
export type DocumentQueueStatus = "pending" | "in_progress" | "completed" | "failed";

/** Operation type for document queue items. */
export type DocumentQueueOperation = "process" | "reprocess";

/** Document queue item from backend. */
export interface DocumentQueueItem {
  id: string;
  document_id: string;
  document_name: string;
  status: DocumentQueueStatus;
  operation: DocumentQueueOperation;
  attempts: number;
  max_attempts: number;
  error_message: string | null;
  next_retry: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/** Paginated list of document queue items response. */
export interface DocumentQueueListResponse {
  items: DocumentQueueItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** Document queue statistics. */
export interface DocumentQueueStats {
  pending: number;
  in_progress: number;
  completed: number;
  failed: number;
  total: number;
}
