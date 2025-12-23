/**
 * Search types.
 */

import type { Project, ProjectStatus } from "./project";

export interface SearchParams {
  q?: string;
  status?: ProjectStatus[];
  organizationId?: string;
  tagIds?: string[];
  ownerId?: string;
  sortBy?: "relevance" | "name" | "start_date" | "updated_at";
  sortOrder?: "asc" | "desc";
  page?: number;
  pageSize?: number;
}

export type SearchResultItem = Project;

export interface SearchResponse {
  items: SearchResultItem[];
  total: number;
  page: number;
  page_size: number;
  query: string;
}

export interface SearchSuggestion {
  text: string;
  type: string;
}

export interface SearchSuggestionsResponse {
  suggestions: SearchSuggestion[];
}

// Saved Searches

export interface SavedSearchFilters {
  status?: string[];
  organization_id?: string;
  tag_ids?: string[];
  owner_id?: string;
  sort_by?: string;
  sort_order?: string;
}

export interface SavedSearch {
  id: string;
  name: string;
  description?: string;
  query?: string;
  filters: SavedSearchFilters;
  is_global: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface SavedSearchCreate {
  name: string;
  description?: string;
  query?: string;
  filters: SavedSearchFilters;
}

export interface SavedSearchUpdate {
  name?: string;
  description?: string;
  query?: string;
  filters?: SavedSearchFilters;
}

export interface SavedSearchListResponse {
  my_searches: SavedSearch[];
  global_searches: SavedSearch[];
}

// Semantic Search Types

export interface DateRange {
  start_date: string | null;
  end_date: string | null;
  original_expression: string | null;
}

export interface ParsedQueryIntent {
  search_text: string;
  date_range: DateRange | null;
  organization_name: string | null;
  organization_id: string | null;
  technology_keywords: string[];
  tag_ids: string[];
  status: string[];
  confidence: number;
}

export interface ParsedQueryMetadata {
  parsed_intent: ParsedQueryIntent;
  fallback_used: boolean;
  parse_explanation: string | null;
}

export interface SemanticSearchFilters {
  status?: string[];
  organization_id?: string;
  tag_ids?: string[];
  owner_id?: string;
}

export interface SemanticSearchRequest {
  query: string;
  filters?: SemanticSearchFilters;
  page?: number;
  page_size?: number;
}

export interface SemanticSearchResponse {
  items: SearchResultItem[];
  total: number;
  page: number;
  page_size: number;
  query: string;
  parsed_query: ParsedQueryMetadata;
}

// Summarization Types

export interface SummarizationRequest {
  query: string;
  project_ids?: string[];
  max_chunks?: number;
  stream?: boolean;
}

export interface SummarizationResponse {
  summary: string;
  query: string;
  context_used: number;
  truncated: boolean;
}
