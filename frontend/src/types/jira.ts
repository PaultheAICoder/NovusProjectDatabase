/**
 * Jira integration types.
 */

/** Link type for Jira issues */
export type JiraLinkType = "epic" | "story" | "related";

/** Jira link stored in database */
export interface JiraLink {
  id: string;
  project_id: string;
  issue_key: string; // e.g., "PROJ-123"
  project_key: string; // e.g., "PROJ"
  url: string; // Full Jira URL
  link_type: JiraLinkType;
  cached_status: string | null;
  cached_summary: string | null;
  cached_at: string | null; // ISO datetime
  created_at: string;
}

/** Request to create a Jira link */
export interface JiraLinkCreate {
  url: string;
  link_type?: JiraLinkType;
}

/** Response from refresh operation */
export interface JiraRefreshResponse {
  total: number;
  refreshed: number;
  failed: number;
  errors: string[];
  timestamp: string;
}

/** Jira status category for color mapping */
export type JiraStatusCategory = "new" | "indeterminate" | "done";

/** Map Jira status names to categories */
export const JIRA_STATUS_CATEGORIES: Record<string, JiraStatusCategory> = {
  // To Do statuses
  "To Do": "new",
  Open: "new",
  Backlog: "new",
  New: "new",
  // In Progress statuses
  "In Progress": "indeterminate",
  "In Review": "indeterminate",
  "In Development": "indeterminate",
  Testing: "indeterminate",
  // Done statuses
  Done: "done",
  Closed: "done",
  Resolved: "done",
  Complete: "done",
};
