/**
 * Tag types.
 */

export type TagType = "technology" | "domain" | "test_type" | "freeform";

export interface Tag {
  id: string;
  name: string;
  type: TagType;
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

export interface TagMergeRequest {
  source_tag_id: string;
  target_tag_id: string;
}

export interface TagMergeResponse {
  merged_count: number;
  target_tag: Tag;
}
