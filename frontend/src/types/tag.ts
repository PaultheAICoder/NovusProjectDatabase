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

export interface TagListResponse {
  technology: Tag[];
  domain: Tag[];
  test_type: Tag[];
  freeform: Tag[];
}
