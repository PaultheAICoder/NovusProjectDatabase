/**
 * Audit history hooks with TanStack Query.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AuditLogResponse, AuditQueryParams } from "@/types/audit";

/**
 * Query audit logs with optional filters.
 */
export function useAuditLogs(params: AuditQueryParams = {}) {
  return useQuery({
    queryKey: ["audit", params],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      if (params.entity_type) searchParams.set("entity_type", params.entity_type);
      if (params.entity_id) searchParams.set("entity_id", params.entity_id);
      if (params.user_id) searchParams.set("user_id", params.user_id);
      if (params.action) searchParams.set("action", params.action);
      if (params.from_date) searchParams.set("from_date", params.from_date);
      if (params.to_date) searchParams.set("to_date", params.to_date);
      if (params.page) searchParams.set("page", String(params.page));
      if (params.page_size) searchParams.set("page_size", String(params.page_size));

      const queryString = searchParams.toString();
      return api.get<AuditLogResponse>(
        `/audit${queryString ? `?${queryString}` : ""}`
      );
    },
  });
}

/**
 * Query audit history for a specific project.
 */
export function useProjectAuditHistory(
  projectId: string | undefined,
  params: { page?: number; page_size?: number } = {}
) {
  return useQuery({
    queryKey: ["audit", "project", projectId, params],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      if (params.page) searchParams.set("page", String(params.page));
      if (params.page_size) searchParams.set("page_size", String(params.page_size));

      const queryString = searchParams.toString();
      return api.get<AuditLogResponse>(
        `/projects/${projectId}/audit${queryString ? `?${queryString}` : ""}`
      );
    },
    enabled: !!projectId,
  });
}

/**
 * Query audit history for a specific contact.
 */
export function useContactAuditHistory(
  contactId: string | undefined,
  params: { page?: number; page_size?: number } = {}
) {
  return useQuery({
    queryKey: ["audit", "contact", contactId, params],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      if (params.page) searchParams.set("page", String(params.page));
      if (params.page_size) searchParams.set("page_size", String(params.page_size));

      const queryString = searchParams.toString();
      return api.get<AuditLogResponse>(
        `/contacts/${contactId}/audit${queryString ? `?${queryString}` : ""}`
      );
    },
    enabled: !!contactId,
  });
}
