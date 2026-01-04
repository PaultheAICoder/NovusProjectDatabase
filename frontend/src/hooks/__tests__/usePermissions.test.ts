/**
 * Tests for usePermissions hooks.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import {
  useProjectPermissions,
  useAddPermission,
  useUpdatePermission,
  useRemovePermission,
  useUpdateVisibility,
} from "../usePermissions";
import { api } from "@/lib/api";
import type { PermissionListResponse, ProjectPermission } from "@/types/permission";

// Mock the api module
vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockPermission: ProjectPermission = {
  id: "perm-1",
  project_id: "proj-123",
  user_id: "user-456",
  team_id: null,
  permission_level: "editor",
  granted_by: "user-789",
  granted_at: "2024-01-15T10:30:00Z",
};

const mockPermissionListResponse: PermissionListResponse = {
  items: [mockPermission],
  total: 1,
};

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

function createWrapper() {
  const queryClient = createTestQueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe("useProjectPermissions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches permissions for a project", async () => {
    vi.mocked(api.get).mockResolvedValueOnce(mockPermissionListResponse);

    const { result } = renderHook(() => useProjectPermissions("proj-123"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.get).toHaveBeenCalledWith("/projects/proj-123/permissions");
    expect(result.current.data).toEqual(mockPermissionListResponse);
  });

  it("does not fetch when projectId is undefined", async () => {
    const { result } = renderHook(() => useProjectPermissions(undefined), {
      wrapper: createWrapper(),
    });

    // Query should not run
    expect(result.current.isLoading).toBe(false);
    expect(api.get).not.toHaveBeenCalled();
  });
});

describe("useAddPermission", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("posts a new permission", async () => {
    vi.mocked(api.post).mockResolvedValueOnce(mockPermission);

    const { result } = renderHook(() => useAddPermission(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      projectId: "proj-123",
      data: {
        user_id: "user-456",
        permission_level: "editor",
      },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.post).toHaveBeenCalledWith("/projects/proj-123/permissions", {
      user_id: "user-456",
      permission_level: "editor",
    });
  });
});

describe("useUpdatePermission", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updates a permission level", async () => {
    vi.mocked(api.put).mockResolvedValueOnce({
      ...mockPermission,
      permission_level: "owner",
    });

    const { result } = renderHook(() => useUpdatePermission(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      projectId: "proj-123",
      permissionId: "perm-1",
      data: { permission_level: "owner" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.put).toHaveBeenCalledWith(
      "/projects/proj-123/permissions/perm-1",
      { permission_level: "owner" },
    );
  });
});

describe("useRemovePermission", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("deletes a permission", async () => {
    vi.mocked(api.delete).mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useRemovePermission(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      projectId: "proj-123",
      permissionId: "perm-1",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.delete).toHaveBeenCalledWith(
      "/projects/proj-123/permissions/perm-1",
    );
  });
});

describe("useUpdateVisibility", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updates project visibility", async () => {
    vi.mocked(api.put).mockResolvedValueOnce({ visibility: "restricted" });

    const { result } = renderHook(() => useUpdateVisibility(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      projectId: "proj-123",
      data: { visibility: "restricted" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.put).toHaveBeenCalledWith("/projects/proj-123/visibility", {
      visibility: "restricted",
    });
  });
});
