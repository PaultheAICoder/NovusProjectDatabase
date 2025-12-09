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
