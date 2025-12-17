/**
 * Document hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  Document,
  DocumentDetail,
  DocumentListResponse,
} from "@/types/document";
import type { Tag } from "@/types/tag";

export function useDocuments(projectId: string | undefined) {
  return useQuery({
    queryKey: ["documents", projectId],
    queryFn: () =>
      api.get<DocumentListResponse>(`/projects/${projectId}/documents`),
    enabled: !!projectId,
    // Poll every 3 seconds if any document is pending (processing in progress)
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasPending = data?.items.some(
        (doc) => doc.processing_status === "pending"
      );
      return hasPending ? 3000 : false;
    },
  });
}

export function useDocument(projectId: string | undefined, documentId: string | undefined) {
  return useQuery({
    queryKey: ["documents", projectId, documentId],
    queryFn: () =>
      api.get<DocumentDetail>(`/projects/${projectId}/documents/${documentId}`),
    enabled: !!projectId && !!documentId,
  });
}

export function useUploadDocument(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      onProgress,
    }: {
      file: File;
      onProgress?: (progress: number) => void;
    }) => {
      const formData = new FormData();
      formData.append("file", file);

      return api.uploadWithProgress<Document>(
        `/projects/${projectId}/documents`,
        formData,
        onProgress
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
    },
  });
}

export function useDeleteDocument(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) =>
      api.delete(`/projects/${projectId}/documents/${documentId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
    },
  });
}

export function useReprocessDocument(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (documentId: string) =>
      api.post<Document>(`/projects/${projectId}/documents/${documentId}/reprocess`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
    },
  });
}

export function getDocumentDownloadUrl(projectId: string, documentId: string): string {
  const baseUrl = import.meta.env.VITE_API_URL || "/api/v1";
  return `${baseUrl}/projects/${projectId}/documents/${documentId}/download`;
}

export function useProjectTagSuggestions(projectId: string | undefined) {
  return useQuery({
    queryKey: ["projects", projectId, "document-tag-suggestions"],
    queryFn: () =>
      api.get<Tag[]>(`/projects/${projectId}/document-tag-suggestions`),
    enabled: !!projectId,
    staleTime: 1000 * 30, // 30 seconds - suggestions don't change often
  });
}

export function useDismissTagSuggestion(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ documentId, tagId }: { documentId: string; tagId: string }) =>
      api.post(`/projects/${projectId}/documents/${documentId}/dismiss-tag`, {
        tag_id: tagId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "document-tag-suggestions"],
      });
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
    },
  });
}

export function useDismissProjectTagSuggestion(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (tagId: string) =>
      api.post(`/projects/${projectId}/dismiss-tag-suggestion`, {
        tag_id: tagId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "document-tag-suggestions"],
      });
    },
  });
}
