/**
 * Document types.
 */

import type { User } from "./index";

export type ProcessingStatus = "pending" | "completed" | "failed" | "skipped";

export interface Document {
  id: string;
  project_id: string;
  file_path: string;
  display_name: string;
  mime_type: string;
  file_size: number;
  uploaded_by: string;
  uploaded_at: string;
  processing_status: ProcessingStatus;
  processing_error: string | null;
  created_at: string;
}

export interface DocumentDetail extends Document {
  uploader: User;
  extracted_text: string | null;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
}
