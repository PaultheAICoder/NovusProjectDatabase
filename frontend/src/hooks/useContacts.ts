/**
 * Contact hooks with TanStack Query.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PaginatedResponse } from "@/types";
import type {
  Contact,
  ContactCreate,
  ContactUpdate,
  ContactWithOrganization,
} from "@/types/contact";

interface UseContactsParams {
  page?: number;
  pageSize?: number;
  organizationId?: string;
  search?: string;
}

export function useContacts({
  page = 1,
  pageSize = 20,
  organizationId,
  search,
}: UseContactsParams = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (organizationId) params.append("organization_id", organizationId);
  if (search) params.append("search", search);

  return useQuery({
    queryKey: ["contacts", { page, pageSize, organizationId, search }],
    queryFn: () =>
      api.get<PaginatedResponse<ContactWithOrganization>>(
        `/contacts?${params.toString()}`,
      ),
  });
}

export function useContact(id: string | undefined) {
  return useQuery({
    queryKey: ["contacts", id],
    queryFn: () => api.get<ContactWithOrganization>(`/contacts/${id}`),
    enabled: !!id,
  });
}

export function useCreateContact() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ContactCreate) =>
      api.post<Contact>("/contacts", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
    },
  });
}

export function useUpdateContact() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ContactUpdate }) =>
      api.put<Contact>(`/contacts/${id}`, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      queryClient.invalidateQueries({ queryKey: ["contacts", id] });
    },
  });
}
