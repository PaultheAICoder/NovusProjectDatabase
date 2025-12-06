/**
 * Organization hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PaginatedResponse } from "@/types";
import type {
  Organization,
  OrganizationCreate,
  OrganizationDetail,
  OrganizationUpdate,
} from "@/types/organization";

interface UseOrganizationsParams {
  page?: number;
  pageSize?: number;
  search?: string;
}

export function useOrganizations({
  page = 1,
  pageSize = 20,
  search,
}: UseOrganizationsParams = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (search) params.append("search", search);

  return useQuery({
    queryKey: ["organizations", { page, pageSize, search }],
    queryFn: () =>
      api.get<PaginatedResponse<Organization>>(
        `/organizations?${params.toString()}`,
      ),
  });
}

export function useOrganization(id: string | undefined) {
  return useQuery({
    queryKey: ["organizations", id],
    queryFn: () => api.get<OrganizationDetail>(`/organizations/${id}`),
    enabled: !!id,
  });
}

export function useCreateOrganization() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: OrganizationCreate) =>
      api.post<Organization>("/organizations", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
  });
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: OrganizationUpdate }) =>
      api.put<Organization>(`/organizations/${id}`, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
      queryClient.invalidateQueries({ queryKey: ["organizations", id] });
    },
  });
}

export function useDeleteOrganization() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/organizations/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
  });
}
