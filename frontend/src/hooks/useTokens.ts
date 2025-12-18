/**
 * Token management hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  APIToken,
  APITokenCreateRequest,
  APITokenCreateResponse,
  APITokenListResponse,
  APITokenUpdateRequest,
} from "@/types/token";

// ============== User Token Hooks ==============

interface UseUserTokensParams {
  page?: number;
  pageSize?: number;
}

/**
 * List current user's tokens.
 */
export function useUserTokens(params: UseUserTokensParams = {}) {
  const { page = 1, pageSize = 20 } = params;

  return useQuery({
    queryKey: ["tokens", "user", { page, pageSize }],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      searchParams.set("page", String(page));
      searchParams.set("page_size", String(pageSize));
      return api.get<APITokenListResponse>(`/tokens?${searchParams.toString()}`);
    },
  });
}

/**
 * Get a single token by ID.
 */
export function useToken(tokenId: string | null) {
  return useQuery({
    queryKey: ["tokens", "user", tokenId],
    queryFn: () => api.get<APIToken>(`/tokens/${tokenId}`),
    enabled: !!tokenId,
  });
}

/**
 * Create a new token.
 */
export function useCreateToken() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: APITokenCreateRequest) =>
      api.post<APITokenCreateResponse>("/tokens", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tokens"] });
    },
  });
}

/**
 * Update a token (rename or change is_active).
 */
export function useUpdateToken() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ tokenId, data }: { tokenId: string; data: APITokenUpdateRequest }) =>
      api.patch<APIToken>(`/tokens/${tokenId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tokens"] });
    },
  });
}

/**
 * Delete a token permanently.
 */
export function useDeleteToken() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (tokenId: string) => api.delete(`/tokens/${tokenId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tokens"] });
    },
  });
}

// ============== Admin Token Hooks ==============

interface UseAdminTokensParams {
  page?: number;
  pageSize?: number;
  userId?: string | null;
  isActive?: boolean | null;
}

/**
 * List all tokens (admin only).
 */
export function useAdminTokens(params: UseAdminTokensParams = {}) {
  const { page = 1, pageSize = 20, userId, isActive } = params;

  return useQuery({
    queryKey: ["tokens", "admin", { page, pageSize, userId, isActive }],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      searchParams.set("page", String(page));
      searchParams.set("page_size", String(pageSize));
      if (userId) searchParams.set("user_id", userId);
      if (isActive !== null && isActive !== undefined) {
        searchParams.set("is_active", String(isActive));
      }
      return api.get<APITokenListResponse>(`/admin/tokens?${searchParams.toString()}`);
    },
  });
}

/**
 * Delete any token (admin only).
 */
export function useAdminDeleteToken() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (tokenId: string) => api.delete(`/admin/tokens/${tokenId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tokens"] });
    },
  });
}
