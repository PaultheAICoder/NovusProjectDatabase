/**
 * Export hooks for CSV download functionality.
 */

import { useState } from "react";
import { api } from "@/lib/api";
import type { ProjectStatus } from "@/types/project";

interface ProjectExportParams {
  status?: ProjectStatus[];
  organizationId?: string;
  ownerId?: string;
  tagIds?: string[];
}

interface SearchExportParams {
  q?: string;
  status?: ProjectStatus[];
  organizationId?: string;
  tagIds?: string[];
  ownerId?: string;
  sortBy?: string;
  sortOrder?: string;
}

/**
 * Build query string from params.
 */
function buildQueryString(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((v) => {
        if (v !== undefined && v !== null && v !== "") {
          searchParams.append(key, String(v));
        }
      });
    } else if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

/**
 * Hook for exporting projects to CSV.
 */
export function useExportProjects() {
  const [isExporting, setIsExporting] = useState(false);

  const exportProjects = async (params: ProjectExportParams = {}) => {
    setIsExporting(true);
    try {
      const queryString = buildQueryString({
        status: params.status,
        organization_id: params.organizationId,
        owner_id: params.ownerId,
        tag_ids: params.tagIds,
      });

      await api.download(
        `/projects/export/csv${queryString}`,
        "projects_export.csv"
      );
    } finally {
      setIsExporting(false);
    }
  };

  return { exportProjects, isExporting };
}

/**
 * Hook for exporting search results to CSV.
 */
export function useExportSearchResults() {
  const [isExporting, setIsExporting] = useState(false);

  const exportSearchResults = async (params: SearchExportParams = {}) => {
    setIsExporting(true);
    try {
      const queryString = buildQueryString({
        q: params.q,
        status: params.status,
        organization_id: params.organizationId,
        tag_ids: params.tagIds,
        owner_id: params.ownerId,
        sort_by: params.sortBy,
        sort_order: params.sortOrder,
      });

      await api.download(
        `/search/export/csv${queryString}`,
        "search_results_export.csv"
      );
    } finally {
      setIsExporting(false);
    }
  };

  return { exportSearchResults, isExporting };
}
