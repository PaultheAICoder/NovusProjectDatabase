/**
 * Tests for useAuditHistory hooks.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  useAuditLogs,
  useProjectAuditHistory,
  useContactAuditHistory,
} from "../hooks/useAuditHistory";
import type { AuditLogResponse } from "../types/audit";

// Mock the api module
const mockGet = vi.fn();
vi.mock("../lib/api", () => ({
  api: {
    get: (endpoint: string) => mockGet(endpoint),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
};

const mockResponse: AuditLogResponse = {
  items: [
    {
      id: "entry-1",
      entity_type: "project",
      entity_id: "proj-123",
      action: "create",
      user: { id: "user-1", display_name: "John Doe" },
      changed_fields: null,
      created_at: "2024-01-15T10:30:00Z",
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
  pages: 1,
};

describe("useAuditLogs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches audit logs without params", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useAuditLogs(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith("/audit");
    expect(result.current.data).toEqual(mockResponse);
  });

  it("builds query string with entity_type param", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useAuditLogs({ entity_type: "project" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith("/audit?entity_type=project");
  });

  it("builds query string with pagination params", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useAuditLogs({ page: 2, page_size: 10 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith("/audit?page=2&page_size=10");
  });

  it("builds query string with date filters", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(
      () =>
        useAuditLogs({
          from_date: "2024-01-01",
          to_date: "2024-12-31",
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith(
      "/audit?from_date=2024-01-01&to_date=2024-12-31"
    );
  });

  it("builds query string with action filter", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useAuditLogs({ action: "update" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith("/audit?action=update");
  });

  it("builds query string with multiple params", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(
      () =>
        useAuditLogs({
          entity_type: "project",
          action: "create",
          page: 1,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith(
      "/audit?entity_type=project&action=create&page=1"
    );
  });
});

describe("useProjectAuditHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is disabled when projectId is undefined", () => {
    const { result } = renderHook(() => useProjectAuditHistory(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("fetches project audit history when projectId is provided", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useProjectAuditHistory("proj-123"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith("/projects/proj-123/audit");
  });

  it("includes pagination params in query", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(
      () => useProjectAuditHistory("proj-123", { page: 2, page_size: 5 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith(
      "/projects/proj-123/audit?page=2&page_size=5"
    );
  });

  it("has correct query key for cache invalidation", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderHook(() => useProjectAuditHistory("proj-123", { page: 1 }), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    await waitFor(() => {
      const cache = queryClient.getQueryCache().getAll();
      const auditQuery = cache.find(
        (q) =>
          Array.isArray(q.queryKey) &&
          q.queryKey[0] === "audit" &&
          q.queryKey[1] === "project"
      );
      expect(auditQuery).toBeDefined();
    });
  });
});

describe("useContactAuditHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is disabled when contactId is undefined", () => {
    const { result } = renderHook(() => useContactAuditHistory(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("fetches contact audit history when contactId is provided", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useContactAuditHistory("contact-123"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith("/contacts/contact-123/audit");
  });

  it("includes pagination params in query", async () => {
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(
      () => useContactAuditHistory("contact-123", { page: 3, page_size: 15 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledWith(
      "/contacts/contact-123/audit?page=3&page_size=15"
    );
  });
});
