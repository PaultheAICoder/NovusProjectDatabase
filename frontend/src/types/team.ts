/**
 * Team types for ACL-based access control.
 */

/** Team response from backend. */
export interface Team {
  id: string;
  name: string;
  azure_ad_group_id: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

/** Team member from backend. */
export interface TeamMember {
  id: string;
  team_id: string;
  user_id: string;
  synced_at: string;
}

/** Detailed team with members. */
export interface TeamDetail extends Team {
  members: TeamMember[];
}

/** Paginated team list response. */
export interface TeamListResponse {
  items: Team[];
  total: number;
  page: number;
  page_size: number;
}

/** Create team request. */
export interface TeamCreate {
  name: string;
  azure_ad_group_id: string;
  description?: string;
}

/** Update team request. */
export interface TeamUpdate {
  name?: string;
  description?: string;
}

/** Team sync response. */
export interface TeamSyncResponse {
  status: "success" | "partial";
  team_id: string;
  team_name: string;
  members_added: number;
  members_removed: number;
  members_unchanged: number;
  errors: string[];
  synced_at: string;
}
