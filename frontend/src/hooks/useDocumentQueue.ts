/**
 * Document processing queue hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  DocumentQueueItem,
  DocumentQueueListResponse,
  DocumentQueueStats,
  DocumentQueueStatus,
} from "@/types/document-queue";

interface DocumentQueueParams {
  page?: number;
  pageSize?: number;
  status?: DocumentQueueStatus | null;
}

export function useDocumentQueue(params: DocumentQueueParams = {}) {
  return useQuery({
    queryKey: ["document-queue", params],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      if (params.page) searchParams.set("page", String(params.page));
      if (params.pageSize) searchParams.set("page_size", String(params.pageSize));
      if (params.status) searchParams.set("status", params.status);
      const queryString = searchParams.toString();
      return api.get<DocumentQueueListResponse>(
        `/admin/document-queue${queryString ? `?${queryString}` : ""}`
      );
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useDocumentQueueStats() {
  return useQuery({
    queryKey: ["document-queue", "stats"],
    queryFn: () => api.get<DocumentQueueStats>("/admin/document-queue/stats"),
    refetchInterval: 30000,
  });
}

export function useRetryDocumentQueueItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      queueId,
      resetAttempts = false,
    }: {
      queueId: string;
      resetAttempts?: boolean;
    }) =>
      api.post<DocumentQueueItem>(
        `/admin/document-queue/${queueId}/retry?reset_attempts=${resetAttempts}`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document-queue"] });
    },
  });
}

export function useCancelDocumentQueueItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (queueId: string) =>
      api.delete(`/admin/document-queue/${queueId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document-queue"] });
    },
  });
}
