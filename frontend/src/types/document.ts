/**
 * Document types.
 */

import type { Tag } from "./tag";
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
  suggested_tag_ids: string[] | null;
  dismissed_tag_ids: string[] | null;
  created_at: string;
  // OCR metadata
  ocr_processed: boolean;
  ocr_confidence: number | null;
  ocr_processed_at: string | null;
  ocr_error: string | null;
}

export interface DocumentDetail extends Document {
  uploader: User;
  extracted_text: string | null;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface DocumentTagSuggestionsResponse {
  document_id: string;
  suggested_tags: Tag[];
  has_suggestions: boolean;
}
