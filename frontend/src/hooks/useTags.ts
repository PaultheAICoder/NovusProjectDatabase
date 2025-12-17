/**
 * Tag hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PaginatedResponse } from "@/types";
import type {
  CooccurrenceTagsResponse,
  PopularTag,
  StructuredTagCreate,
  Tag,
  TagCreate,
  TagListResponse,
  TagMergeRequest,
  TagMergeResponse,
  TagSuggestionsResponse,
  TagType,
  TagUpdate,
} from "@/types/tag";

interface UseTagsParams {
  type?: TagType;
  search?: string;
}

export function useTags({ type, search }: UseTagsParams = {}) {
  const params = new URLSearchParams();
  if (type) params.append("type", type);
  if (search) params.append("search", search);

  const queryString = params.toString();
  const endpoint = queryString ? `/tags?${queryString}` : "/tags";

  return useQuery({
    queryKey: ["tags", { type, search }],
    queryFn: () => api.get<TagListResponse>(endpoint),
  });
}

interface UseTagSuggestionsParams {
  query: string;
  type?: TagType;
  includeFuzzy?: boolean;
  limit?: number;
}

export function useTagSuggestions({
  query,
  type,
  includeFuzzy = true,
  limit = 10,
}: UseTagSuggestionsParams) {
  const params = new URLSearchParams();
  params.append("query", query);
  if (type) params.append("type", type);
  params.append("include_fuzzy", String(includeFuzzy));
  params.append("limit", String(limit));

  return useQuery({
    queryKey: ["tags", "suggest", { query, type, includeFuzzy, limit }],
    queryFn: () =>
      api.get<TagSuggestionsResponse>(`/tags/suggest?${params.toString()}`),
    enabled: query.length >= 2,
  });
}

export function usePopularTags(type?: TagType, limit = 10) {
  const params = new URLSearchParams();
  if (type) params.append("type", type);
  params.append("limit", String(limit));

  return useQuery({
    queryKey: ["tags", "popular", { type, limit }],
    queryFn: () => api.get<PopularTag[]>(`/tags/popular?${params.toString()}`),
  });
}

/**
 * Get tag suggestions based on co-occurrence with selected tags.
 * Returns tags that frequently appear together with the selected tags.
 */
export function useCooccurrenceSuggestions(selectedTagIds: string[], limit = 5) {
  const tagIdsParam = selectedTagIds.join(",");

  return useQuery({
    queryKey: ["tags", "cooccurrence", { tagIds: selectedTagIds, limit }],
    queryFn: () =>
      api.get<CooccurrenceTagsResponse>(
        `/tags/cooccurrence?tag_ids=${encodeURIComponent(tagIdsParam)}&limit=${limit}`
      ),
    enabled: selectedTagIds.length > 0, // Only fetch when tags are selected
    staleTime: 1000 * 60, // 1 minute - co-occurrence data doesn't change frequently
  });
}

export function useCreateTag() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TagCreate) => api.post<Tag>("/tags", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

// Admin hooks

export function useCreateStructuredTag() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: StructuredTagCreate) => api.post<Tag>("/admin/tags", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

export function useUpdateTag() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TagUpdate }) =>
      api.patch<Tag>(`/admin/tags/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

export function useDeleteTag() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/admin/tags/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

export function useTagUsage(tagId: string | null) {
  return useQuery({
    queryKey: ["tags", "usage", tagId],
    queryFn: () =>
      api.get<{ tag_id: string; usage_count: number }>(
        `/admin/tags/${tagId}/usage`
      ),
    enabled: !!tagId,
  });
}

export function useMergeTags() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TagMergeRequest) =>
      api.post<TagMergeResponse>("/admin/tags/merge", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

/**
 * Get all tags as a flat array, sorted alphabetically by name.
 */
export function useAllTags() {
  const { data, ...rest } = useTags();

  const allTags = data
    ? [
        ...data.technology,
        ...data.domain,
        ...data.test_type,
        ...data.freeform,
      ].sort((a, b) => a.name.localeCompare(b.name))
    : [];

  return { data: allTags, ...rest };
}

interface UseTagSearchParams {
  search: string;
  type?: TagType;
  pageSize?: number;
}

export function useTagSearch({
  search,
  type,
  pageSize = 30,
}: UseTagSearchParams) {
  const params = new URLSearchParams({
    page: "1",
    page_size: String(pageSize),
  });
  if (search) params.append("search", search);
  if (type) params.append("type", type);

  return useQuery({
    queryKey: ["tags", "search", { search, type, pageSize }],
    queryFn: () =>
      api.get<PaginatedResponse<Tag>>(`/tags/list?${params.toString()}`),
    enabled: search.length >= 1,
    staleTime: 1000 * 60, // 1 minute cache
  });
}
