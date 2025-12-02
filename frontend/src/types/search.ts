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

export interface SearchResultItem extends Project {}

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
