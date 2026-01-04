/**
 * Project permission hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  PermissionCreate,
  PermissionListResponse,
  PermissionUpdate,
  ProjectPermission,
  VisibilityUpdate,
} from "@/types/permission";

/** List permissions for a project (requires owner access). */
export function useProjectPermissions(projectId: string | undefined) {
  return useQuery({
    queryKey: ["permissions", projectId],
    queryFn: () =>
      api.get<PermissionListResponse>(`/projects/${projectId}/permissions`),
    enabled: !!projectId,
  });
}

/** Add a permission to a project. */
export function useAddPermission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      data,
    }: {
      projectId: string;
      data: PermissionCreate;
    }) =>
      api.post<ProjectPermission>(
        `/projects/${projectId}/permissions`,
        data,
      ),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ["permissions", projectId] });
    },
  });
}

/** Update a permission level. */
export function useUpdatePermission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      permissionId,
      data,
    }: {
      projectId: string;
      permissionId: string;
      data: PermissionUpdate;
    }) =>
      api.put<ProjectPermission>(
        `/projects/${projectId}/permissions/${permissionId}`,
        data,
      ),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ["permissions", projectId] });
    },
  });
}

/** Remove a permission. */
export function useRemovePermission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      permissionId,
    }: {
      projectId: string;
      permissionId: string;
    }) => api.delete(`/projects/${projectId}/permissions/${permissionId}`),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ["permissions", projectId] });
    },
  });
}

/** Update project visibility. */
export function useUpdateVisibility() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      data,
    }: {
      projectId: string;
      data: VisibilityUpdate;
    }) =>
      api.put<{ visibility: string }>(
        `/projects/${projectId}/visibility`,
        data,
      ),
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
      queryClient.invalidateQueries({ queryKey: ["permissions", projectId] });
    },
  });
}
