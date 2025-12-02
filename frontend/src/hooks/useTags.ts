/**
 * Tag hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Tag, TagCreate, TagListResponse, TagType } from "@/types/tag";

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

export function useTagSuggestions(query: string) {
  return useQuery({
    queryKey: ["tags", "suggest", query],
    queryFn: () => api.get<Tag[]>(`/tags/suggest?query=${encodeURIComponent(query)}`),
    enabled: query.length >= 2,
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

/**
 * Get all tags as a flat array.
 */
export function useAllTags() {
  const { data, ...rest } = useTags();

  const allTags = data
    ? [
        ...data.technology,
        ...data.domain,
        ...data.test_type,
        ...data.freeform,
      ]
    : [];

  return { data: allTags, ...rest };
}
