/**
 * Permission types for ACL-based access control.
 */

/** Permission levels matching backend enum. */
export type PermissionLevel = "viewer" | "editor" | "owner";

/** Project visibility options. */
export type ProjectVisibility = "public" | "restricted";

/** Project permission response. */
export interface ProjectPermission {
  id: string;
  project_id: string;
  user_id: string | null;
  team_id: string | null;
  permission_level: PermissionLevel;
  granted_by: string | null;
  granted_at: string;
}

/** Permission list response. */
export interface PermissionListResponse {
  items: ProjectPermission[];
  total: number;
}

/** Create permission request. */
export interface PermissionCreate {
  user_id?: string;
  team_id?: string;
  permission_level: PermissionLevel;
}

/** Update permission request. */
export interface PermissionUpdate {
  permission_level: PermissionLevel;
}

/** Visibility update request. */
export interface VisibilityUpdate {
  visibility: ProjectVisibility;
}

/** Permission level labels for UI. */
export const PERMISSION_LEVEL_LABELS: Record<PermissionLevel, string> = {
  viewer: "Viewer",
  editor: "Editor",
  owner: "Owner",
};

/** Permission level descriptions. */
export const PERMISSION_LEVEL_DESCRIPTIONS: Record<PermissionLevel, string> = {
  viewer: "Can view project details and documents",
  editor: "Can view and edit project details, upload documents",
  owner: "Full control including permission management",
};
