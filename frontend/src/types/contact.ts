/**
 * Contact types.
 */

import type { Organization } from "./organization";
import type { RecordSyncStatus, SyncDirection } from "./monday";

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
  sync_status: RecordSyncStatus;
  sync_enabled: boolean;
  sync_direction: SyncDirection;
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
  sync_enabled?: boolean;
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
