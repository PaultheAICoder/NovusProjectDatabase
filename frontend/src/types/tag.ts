/**
 * Tag types.
 */

export type TagType = "technology" | "domain" | "test_type" | "freeform";

export interface Tag {
  id: string;
  name: string;
  type: TagType;
}

export interface TagWithUsage extends Tag {
  usage_count: number;
}

export interface TagCreate {
  name: string;
}

export interface StructuredTagCreate {
  name: string;
  type: TagType;
}

export interface TagUpdate {
  name?: string;
  type?: TagType;
}

export interface TagListResponse {
  technology: Tag[];
  domain: Tag[];
  test_type: Tag[];
  freeform: Tag[];
}

export interface TagSuggestion {
  tag: Tag;
  score: number;
  suggestion: string | null;
}

export interface TagSuggestionsResponse {
  suggestions: TagSuggestion[];
}

export interface PopularTag {
  tag: Tag;
  usage_count: number;
}

export interface CooccurrenceTagSuggestion {
  tag: Tag;
  co_occurrence_count: number;
}

export interface CooccurrenceTagsResponse {
  suggestions: CooccurrenceTagSuggestion[];
  selected_tag_ids: string[];
}

export interface TagMergeRequest {
  source_tag_id: string;
  target_tag_id: string;
}

export interface TagMergeResponse {
  merged_count: number;
  target_tag: Tag;
}
