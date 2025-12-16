/**
 * Organization types.
 */

export interface BillingContactSummary {
  id: string;
  name: string;
  email: string;
  role_title: string | null;
}

export interface Organization {
  id: string;
  name: string;
  aliases: string[] | null;
  billing_contact_id: string | null;
  address_street: string | null;
  address_city: string | null;
  address_state: string | null;
  address_zip: string | null;
  address_country: string | null;
  inventory_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  monday_id: string | null;
  monday_last_synced: string | null;
}

export interface OrganizationCreate {
  name: string;
  aliases?: string[];
  billing_contact_id?: string;
  address_street?: string;
  address_city?: string;
  address_state?: string;
  address_zip?: string;
  address_country?: string;
  inventory_url?: string;
  notes?: string;
}

export interface OrganizationUpdate {
  name?: string;
  aliases?: string[];
  billing_contact_id?: string | null;
  address_street?: string | null;
  address_city?: string | null;
  address_state?: string | null;
  address_zip?: string | null;
  address_country?: string | null;
  inventory_url?: string | null;
  notes?: string | null;
}

export interface ProjectSummaryForOrg {
  id: string;
  name: string;
  status: string;
  start_date: string;
  end_date: string | null;
}

export interface ContactSummaryForOrg {
  id: string;
  name: string;
  email: string;
  role_title: string | null;
}

export interface OrganizationDetail extends Organization {
  project_count: number;
  projects: ProjectSummaryForOrg[];
  contacts: ContactSummaryForOrg[];
  billing_contact: BillingContactSummary | null;
}
