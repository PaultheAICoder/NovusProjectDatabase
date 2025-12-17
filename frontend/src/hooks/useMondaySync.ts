/**
 * Monday.com sync hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AutoResolutionRule,
  AutoResolutionRuleCreate,
  AutoResolutionRuleListResponse,
  AutoResolutionRuleReorderRequest,
  AutoResolutionRuleUpdate,
  BulkConflictResolveRequest,
  BulkConflictResolveResponse,
  ConflictListResponse,
  ConflictResolveRequest,
  ConflictStats,
  MondayBoardsResponse,
  MondayConfigResponse,
  MondaySyncLog,
  MondaySyncStatusResponse,
  MondaySyncTriggerRequest,
  SyncConflict,
  SyncQueueItem,
  SyncQueueListResponse,
  SyncQueueStats,
  SyncQueueStatus,
  SyncQueueDirection,
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

// ============== Sync Conflict Hooks ==============

interface SyncConflictParams {
  page?: number;
  pageSize?: number;
  entityType?: "contact" | "organization" | null;
}

export function useSyncConflicts(params: SyncConflictParams = {}) {
  return useQuery({
    queryKey: ["sync", "conflicts", params],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      if (params.page) searchParams.set("page", String(params.page));
      if (params.pageSize) searchParams.set("page_size", String(params.pageSize));
      if (params.entityType) searchParams.set("entity_type", params.entityType);
      const queryString = searchParams.toString();
      return api.get<ConflictListResponse>(
        `/admin/sync/conflicts${queryString ? `?${queryString}` : ""}`
      );
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useSyncConflictStats() {
  return useQuery({
    queryKey: ["sync", "conflicts", "stats"],
    queryFn: () => api.get<ConflictStats>("/admin/sync/conflicts/stats"),
    refetchInterval: 30000,
  });
}

export function useSyncConflict(conflictId: string | null) {
  return useQuery({
    queryKey: ["sync", "conflicts", conflictId],
    queryFn: () => api.get<SyncConflict>(`/admin/sync/conflicts/${conflictId}`),
    enabled: !!conflictId,
  });
}

export function useResolveSyncConflict() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      conflictId,
      data,
    }: {
      conflictId: string;
      data: ConflictResolveRequest;
    }) => api.post<SyncConflict>(`/admin/sync/conflicts/${conflictId}/resolve`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync", "conflicts"] });
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
  });
}

export function useBulkResolveSyncConflicts() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BulkConflictResolveRequest) =>
      api.post<BulkConflictResolveResponse>("/admin/sync/conflicts/bulk-resolve", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync", "conflicts"] });
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
  });
}

// ============== Sync Queue Hooks ==============

interface SyncQueueParams {
  page?: number;
  pageSize?: number;
  entityType?: "contact" | "organization" | null;
  direction?: SyncQueueDirection | null;
  status?: SyncQueueStatus | null;
}

export function useSyncQueue(params: SyncQueueParams = {}) {
  return useQuery({
    queryKey: ["sync", "queue", params],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      if (params.page) searchParams.set("page", String(params.page));
      if (params.pageSize) searchParams.set("page_size", String(params.pageSize));
      if (params.entityType) searchParams.set("entity_type", params.entityType);
      if (params.direction) searchParams.set("direction", params.direction);
      if (params.status) searchParams.set("status", params.status);
      const queryString = searchParams.toString();
      return api.get<SyncQueueListResponse>(
        `/admin/sync/queue${queryString ? `?${queryString}` : ""}`
      );
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useSyncQueueStats() {
  return useQuery({
    queryKey: ["sync", "queue", "stats"],
    queryFn: () => api.get<SyncQueueStats>("/admin/sync/queue/stats"),
    refetchInterval: 30000,
  });
}

export function useRetrySyncQueueItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      queueId,
      resetAttempts = false,
    }: {
      queueId: string;
      resetAttempts?: boolean;
    }) =>
      api.post<SyncQueueItem>(
        `/admin/sync/queue/${queueId}/retry?reset_attempts=${resetAttempts}`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync", "queue"] });
    },
  });
}

// ============== Auto-Resolution Rule Hooks ==============

export function useAutoResolutionRules() {
  return useQuery({
    queryKey: ["sync", "auto-resolution"],
    queryFn: () => api.get<AutoResolutionRuleListResponse>("/admin/sync/auto-resolution"),
  });
}

export function useAutoResolutionRule(ruleId: string | null) {
  return useQuery({
    queryKey: ["sync", "auto-resolution", ruleId],
    queryFn: () => api.get<AutoResolutionRule>(`/admin/sync/auto-resolution/${ruleId}`),
    enabled: !!ruleId,
  });
}

export function useCreateAutoResolutionRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AutoResolutionRuleCreate) =>
      api.post<AutoResolutionRule>("/admin/sync/auto-resolution", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync", "auto-resolution"] });
    },
  });
}

export function useUpdateAutoResolutionRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ruleId, data }: { ruleId: string; data: AutoResolutionRuleUpdate }) =>
      api.patch<AutoResolutionRule>(`/admin/sync/auto-resolution/${ruleId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync", "auto-resolution"] });
    },
  });
}

export function useDeleteAutoResolutionRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ruleId: string) =>
      api.delete(`/admin/sync/auto-resolution/${ruleId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync", "auto-resolution"] });
    },
  });
}

export function useReorderAutoResolutionRules() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AutoResolutionRuleReorderRequest) =>
      api.post<AutoResolutionRuleListResponse>("/admin/sync/auto-resolution/reorder", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync", "auto-resolution"] });
    },
  });
}
