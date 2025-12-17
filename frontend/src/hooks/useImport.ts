/**
 * Import hooks with TanStack Query.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AutofillRequest,
  AutofillResponse,
  ImportCommitRequest,
  ImportCommitResponse,
  ImportPreviewResponse,
  ImportRowsValidateRequest,
  ImportRowsValidateResponse,
} from "@/types/import";

export function useImportPreview() {
  return useMutation({
    mutationFn: async ({
      file,
      includeSuggestions = true,
    }: {
      file: File;
      includeSuggestions?: boolean;
    }) => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `/api/v1/admin/import/preview?include_suggestions=${includeSuggestions}`,
        {
          method: "POST",
          body: formData,
          credentials: "include",
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to preview import");
      }

      return response.json() as Promise<ImportPreviewResponse>;
    },
  });
}

export function useImportCommit() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ImportCommitRequest) =>
      api.post<ImportCommitResponse>("/admin/import/commit", data),
    onSuccess: () => {
      // Invalidate projects list after import
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useValidateRows() {
  return useMutation({
    mutationFn: (data: ImportRowsValidateRequest) =>
      api.post<ImportRowsValidateResponse>("/admin/import/validate-rows", data),
  });
}

export function useAutofill() {
  return useMutation({
    mutationFn: (data: AutofillRequest) =>
      api.post<AutofillResponse>("/projects/autofill", data),
  });
}
