/**
 * Team management hooks with TanStack Query (Admin only).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  Team,
  TeamCreate,
  TeamDetail,
  TeamListResponse,
  TeamSyncResponse,
  TeamUpdate,
} from "@/types/team";

interface UseTeamsParams {
  page?: number;
  pageSize?: number;
}

/** List all teams (admin only). */
export function useTeams({ page = 1, pageSize = 20 }: UseTeamsParams = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  return useQuery({
    queryKey: ["teams", { page, pageSize }],
    queryFn: () => api.get<TeamListResponse>(`/teams?${params.toString()}`),
  });
}

/** Get team details with members (admin only). */
export function useTeam(teamId: string | null) {
  return useQuery({
    queryKey: ["teams", teamId],
    queryFn: () => api.get<TeamDetail>(`/teams/${teamId}`),
    enabled: !!teamId,
  });
}

/** Create a new team (admin only). */
export function useCreateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TeamCreate) => api.post<Team>("/teams", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
    },
  });
}

/** Update a team (admin only). */
export function useUpdateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ teamId, data }: { teamId: string; data: TeamUpdate }) =>
      api.put<Team>(`/teams/${teamId}`, data),
    onSuccess: (_, { teamId }) => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      queryClient.invalidateQueries({ queryKey: ["teams", teamId] });
    },
  });
}

/** Delete a team (admin only). */
export function useDeleteTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (teamId: string) => api.delete(`/teams/${teamId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
    },
  });
}

/** Trigger team sync from Azure AD (admin only). */
export function useSyncTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (teamId: string) =>
      api.post<TeamSyncResponse>(`/teams/${teamId}/sync`),
    onSuccess: (_, teamId) => {
      queryClient.invalidateQueries({ queryKey: ["teams", teamId] });
    },
  });
}
