/**
 * Jira links hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { JiraLink, JiraLinkCreate, JiraRefreshResponse } from "@/types/jira";

/**
 * Fetch all Jira links for a project.
 */
export function useJiraLinks(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "jira-links"],
    queryFn: () => api.get<JiraLink[]>(`/projects/${projectId}/jira-links`),
    enabled: !!projectId,
    staleTime: 60000, // 1 minute
  });
}

/**
 * Create a new Jira link for a project.
 */
export function useCreateJiraLink(projectId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: JiraLinkCreate) =>
      api.post<JiraLink>(`/projects/${projectId}/jira-links`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "jira-links"],
      });
    },
  });
}

/**
 * Delete a Jira link from a project.
 */
export function useDeleteJiraLink(projectId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (linkId: string) =>
      api.delete(`/projects/${projectId}/jira-links/${linkId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "jira-links"],
      });
    },
  });
}

/**
 * Refresh all Jira link statuses for a project.
 */
export function useRefreshJiraLinks(projectId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      api.post<JiraRefreshResponse>(`/projects/${projectId}/jira/refresh`),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "jira-links"],
      });
    },
  });
}
