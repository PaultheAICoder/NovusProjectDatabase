/**
 * Contact types.
 */

import type { Organization } from "./organization";

export interface Contact {
  id: string;
  name: string;
  email: string;
  organization_id: string;
  role_title: string | null;
  phone: string | null;
  notes: string | null;
  monday_url: string | null;
  created_at: string;
  updated_at: string;
  monday_id: string | null;
  monday_last_synced: string | null;
}

export interface ContactWithOrganization extends Contact {
  organization: Organization;
}

export interface ContactCreate {
  name: string;
  email: string;
  organization_id: string;
  role_title?: string;
  phone?: string;
  notes?: string;
  monday_url?: string;
}

export interface ContactUpdate {
  name?: string;
  email?: string;
  role_title?: string;
  phone?: string;
  notes?: string;
  monday_url?: string;
}

export interface ProjectSummaryForContact {
  id: string;
  name: string;
  organization_name: string;
  status: string;
  start_date: string;
  end_date: string | null;
  is_primary: boolean;
}

export interface ContactDetail extends ContactWithOrganization {
  project_count: number;
  projects: ProjectSummaryForContact[];
}
