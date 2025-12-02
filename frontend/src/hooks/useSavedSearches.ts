/**
 * Saved searches hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  SavedSearch,
  SavedSearchCreate,
  SavedSearchListResponse,
  SavedSearchUpdate,
} from "@/types/search";

export function useSavedSearches() {
  return useQuery({
    queryKey: ["savedSearches"],
    queryFn: () => api.get<SavedSearchListResponse>("/search/saved"),
  });
}

export function useSavedSearch(id: string) {
  return useQuery({
    queryKey: ["savedSearches", id],
    queryFn: () => api.get<SavedSearch>(`/search/saved/${id}`),
    enabled: !!id,
  });
}

export function useCreateSavedSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SavedSearchCreate) =>
      api.post<SavedSearch>("/search/saved", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["savedSearches"] });
    },
  });
}

export function useUpdateSavedSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SavedSearchUpdate }) =>
      api.patch<SavedSearch>(`/search/saved/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["savedSearches"] });
    },
  });
}

export function useDeleteSavedSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/search/saved/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["savedSearches"] });
    },
  });
}

export function useToggleSavedSearchGlobal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      api.patch<SavedSearch>(`/admin/saved-searches/${id}/toggle-global`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["savedSearches"] });
    },
  });
}
