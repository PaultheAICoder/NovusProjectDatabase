/**
 * Project hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PaginatedResponse } from "@/types";
import type {
  Project,
  ProjectCreate,
  ProjectDetail,
  ProjectStatus,
  ProjectUpdate,
} from "@/types/project";

interface UseProjectsParams {
  page?: number;
  pageSize?: number;
  status?: ProjectStatus[];
  organizationId?: string;
  ownerId?: string;
  sortBy?: "name" | "start_date" | "updated_at";
  sortOrder?: "asc" | "desc";
}

export function useProjects({
  page = 1,
  pageSize = 20,
  status,
  organizationId,
  ownerId,
  sortBy = "updated_at",
  sortOrder = "desc",
}: UseProjectsParams = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  if (status?.length) {
    status.forEach((s) => params.append("status", s));
  }
  if (organizationId) params.append("organization_id", organizationId);
  if (ownerId) params.append("owner_id", ownerId);

  return useQuery({
    queryKey: [
      "projects",
      { page, pageSize, status, organizationId, ownerId, sortBy, sortOrder },
    ],
    queryFn: () =>
      api.get<PaginatedResponse<Project>>(`/projects?${params.toString()}`),
  });
}

export function useProject(id: string | undefined) {
  return useQuery({
    queryKey: ["projects", id],
    queryFn: () => api.get<ProjectDetail>(`/projects/${id}`),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProjectCreate) => api.post<Project>("/projects", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ProjectUpdate }) =>
      api.put<Project>(`/projects/${id}`, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["projects", id] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/projects/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
