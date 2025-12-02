/**
 * Organization types.
 */

export interface Organization {
  id: string;
  name: string;
  aliases: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface OrganizationCreate {
  name: string;
  aliases?: string[];
}

export interface OrganizationUpdate {
  name?: string;
  aliases?: string[];
}

export interface OrganizationDetail extends Organization {
  project_count: number;
}
