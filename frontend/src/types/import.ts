/**
 * Import types for bulk import functionality.
 */

import type { ProjectStatus } from "./project";

export interface ImportRowValidation {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface ImportRowSuggestion {
  suggested_description?: string;
  suggested_tags?: string[];
  suggested_organization_id?: string;
  suggested_owner_id?: string;
  confidence: number;
}

export interface ImportRowPreview {
  row_number: number;
  name?: string;
  organization_name?: string;
  description?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
  location?: string;
  owner_email?: string;
  tags?: string[];
  billing_amount?: string;
  billing_recipient?: string;
  billing_notes?: string;
  pm_notes?: string;
  monday_url?: string;
  jira_url?: string;
  gitlab_url?: string;
  validation: ImportRowValidation;
  suggestions?: ImportRowSuggestion;
  resolved_organization_id?: string;
  resolved_owner_id?: string;
  resolved_tag_ids?: string[];
}

export interface ImportPreviewResponse {
  filename: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  rows: ImportRowPreview[];
  column_mapping: Record<string, string>;
}

export interface ImportRowUpdate {
  row_number: number;
  name?: string;
  organization_id?: string;
  owner_id?: string;
  description?: string;
  status?: ProjectStatus;
  start_date?: string;
  end_date?: string;
  location?: string;
  tag_ids?: string[];
  billing_amount?: number;
  billing_recipient?: string;
  billing_notes?: string;
  pm_notes?: string;
  monday_url?: string;
  jira_url?: string;
  gitlab_url?: string;
}

export interface ImportCommitRequest {
  rows: ImportRowUpdate[];
  skip_invalid: boolean;
}

export interface ImportCommitResult {
  row_number: number;
  success: boolean;
  project_id?: string;
  error?: string;
}

export interface ImportCommitResponse {
  total: number;
  successful: number;
  failed: number;
  results: ImportCommitResult[];
}

export interface AutofillRequest {
  name: string;
  existing_description?: string;
  organization_id?: string;
}

export interface AutofillResponse {
  suggested_description?: string;
  suggested_tags: string[];
  suggested_tag_ids: string[];
  confidence: number;
}
