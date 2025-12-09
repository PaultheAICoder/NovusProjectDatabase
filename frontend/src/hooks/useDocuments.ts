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
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `${import.meta.env.VITE_API_URL || "/api/v1"}/projects/${projectId}/documents`,
        {
          method: "POST",
          body: formData,
          credentials: "include",
        },
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Upload failed");
      }

      return response.json() as Promise<Document>;
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
