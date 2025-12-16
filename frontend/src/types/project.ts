/**
 * Project types.
 */

import type { Contact } from "./contact";
import type { Organization } from "./organization";
import type { Tag } from "./tag";
import type { User } from "./index";

export type ProjectStatus =
  | "approved"
  | "active"
  | "on_hold"
  | "completed"
  | "cancelled";

export type ProjectLocation =
  | "headquarters"
  | "test_house"
  | "remote"
  | "client_site"
  | "other";

export interface ProjectSummary {
  id: string;
  name: string;
  organization_name: string;
  status: ProjectStatus;
  start_date: string;
}

export interface Project {
  id: string;
  name: string;
  organization: Organization;
  owner: User;
  description: string;
  status: ProjectStatus;
  start_date: string;
  end_date: string | null;
  location: ProjectLocation;
  location_other: string | null;
  tags: Tag[];
  created_at: string;
  updated_at: string;
}

export interface ProjectContact extends Contact {
  is_primary: boolean;
  role: string | null;
}

export interface ProjectDetail extends Project {
  contacts: ProjectContact[];
  billing_amount: number | null;
  invoice_count: number | null;
  billing_recipient: string | null;
  billing_notes: string | null;
  pm_notes: string | null;
  monday_url: string | null;
  jira_url: string | null;
  gitlab_url: string | null;
  created_by: User;
  updated_by: User;
}

export interface ProjectCreate {
  name: string;
  organization_id: string;
  description: string;
  status: ProjectStatus;
  start_date: string;
  end_date?: string;
  location: ProjectLocation;
  location_other?: string;
  contact_ids?: string[];
  primary_contact_id?: string;
  tag_ids?: string[];
  billing_amount?: number;
  invoice_count?: number;
  billing_recipient?: string;
  billing_notes?: string;
  pm_notes?: string;
  monday_url?: string;
  jira_url?: string;
  gitlab_url?: string;
}

export interface ProjectUpdate {
  name?: string;
  organization_id?: string;
  description?: string;
  status?: ProjectStatus;
  start_date?: string;
  end_date?: string;
  location?: ProjectLocation;
  location_other?: string;
  contact_ids?: string[];
  primary_contact_id?: string;
  tag_ids?: string[];
  billing_amount?: number;
  invoice_count?: number;
  billing_recipient?: string;
  billing_notes?: string;
  pm_notes?: string;
  monday_url?: string;
  jira_url?: string;
  gitlab_url?: string;
}
