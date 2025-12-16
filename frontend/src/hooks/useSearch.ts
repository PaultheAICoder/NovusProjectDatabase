/**
 * Search hooks with TanStack Query.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  SearchParams,
  SearchResponse,
  SearchSuggestionsResponse,
} from "@/types/search";

export function useSearch({
  q = "",
  status,
  organizationId,
  tagIds,
  ownerId,
  sortBy = "relevance",
  sortOrder = "desc",
  page = 1,
  pageSize = 20,
}: SearchParams = {}) {
  const params = new URLSearchParams();

  if (q) params.append("q", q);
  if (status?.length) {
    status.forEach((s) => params.append("status", s));
  }
  if (organizationId) params.append("organization_id", organizationId);
  if (tagIds?.length) {
    tagIds.forEach((id) => params.append("tag_ids", id));
  }
  if (ownerId) params.append("owner_id", ownerId);
  params.append("sort_by", sortBy);
  params.append("sort_order", sortOrder);
  params.append("page", String(page));
  params.append("page_size", String(pageSize));

  return useQuery({
    queryKey: [
      "search",
      { q, status, organizationId, tagIds, ownerId, sortBy, sortOrder, page, pageSize },
    ],
    queryFn: () => api.get<SearchResponse>(`/search?${params.toString()}`),
    enabled: true,
    // Cache search results for 2 minutes - search results don't change frequently
    // and this reduces redundant API calls when navigating or changing pagination
    staleTime: 1000 * 60 * 2,
  });
}

export function useSearchSuggestions(query: string) {
  return useQuery({
    queryKey: ["search", "suggestions", query],
    queryFn: () =>
      api.get<SearchSuggestionsResponse>(
        `/search/suggest?q=${encodeURIComponent(query)}`,
      ),
    enabled: query.length >= 2,
  });
}
