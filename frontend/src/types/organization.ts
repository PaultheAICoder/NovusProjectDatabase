/**
 * Organization types.
 */

export interface Organization {
  id: string;
  name: string;
  aliases: string[] | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrganizationCreate {
  name: string;
  aliases?: string[];
  notes?: string;
}

export interface OrganizationUpdate {
  name?: string;
  aliases?: string[];
  notes?: string;
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
}
