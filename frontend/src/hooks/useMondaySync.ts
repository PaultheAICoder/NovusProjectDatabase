/**
 * Monday.com sync hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  MondayBoardsResponse,
  MondayConfigResponse,
  MondaySyncLog,
  MondaySyncStatusResponse,
  MondaySyncTriggerRequest,
} from "@/types/monday";

export function useMondaySyncStatus() {
  return useQuery({
    queryKey: ["monday", "status"],
    queryFn: () => api.get<MondaySyncStatusResponse>("/admin/monday/status"),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useMondayConfig() {
  return useQuery({
    queryKey: ["monday", "config"],
    queryFn: () => api.get<MondayConfigResponse>("/admin/monday/config"),
  });
}

export function useMondayBoards() {
  return useQuery({
    queryKey: ["monday", "boards"],
    queryFn: () => api.get<MondayBoardsResponse>("/admin/monday/boards"),
    enabled: false, // Only fetch when explicitly called
  });
}

export function useTriggerMondaySync() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: MondaySyncTriggerRequest) =>
      api.post<MondaySyncLog>("/admin/monday/sync", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monday"] });
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useMondaySyncLogs(limit: number = 20) {
  return useQuery({
    queryKey: ["monday", "logs", limit],
    queryFn: () =>
      api.get<MondaySyncLog[]>(`/admin/monday/logs?limit=${limit}`),
  });
}
