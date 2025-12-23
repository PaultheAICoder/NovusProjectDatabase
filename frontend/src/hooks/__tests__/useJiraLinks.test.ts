/**
 * Tests for Jira links hooks.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import {
  useJiraLinks,
  useCreateJiraLink,
  useDeleteJiraLink,
  useRefreshJiraLinks,
} from "../useJiraLinks";
import type { JiraLink, JiraRefreshResponse } from "@/types/jira";

// Mock the api module
const mockApiGet = vi.fn();
const mockApiPost = vi.fn();
const mockApiDelete = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
    post: (...args: unknown[]) => mockApiPost(...args),
    delete: (...args: unknown[]) => mockApiDelete(...args),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return function TestWrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
};

const mockJiraLinks: JiraLink[] = [
  {
    id: "link-1",
    project_id: "proj-123",
    issue_key: "PROJ-101",
    project_key: "PROJ",
    url: "https://test.atlassian.net/browse/PROJ-101",
    link_type: "epic",
    cached_status: "In Progress",
    cached_summary: "Test epic issue",
    cached_at: "2025-12-23T00:00:00Z",
    created_at: "2025-12-20T00:00:00Z",
  },
  {
    id: "link-2",
    project_id: "proj-123",
    issue_key: "PROJ-102",
    project_key: "PROJ",
    url: "https://test.atlassian.net/browse/PROJ-102",
    link_type: "story",
    cached_status: "To Do",
    cached_summary: "Test story issue",
    cached_at: "2025-12-23T00:00:00Z",
    created_at: "2025-12-21T00:00:00Z",
  },
];

const mockRefreshResponse: JiraRefreshResponse = {
  total: 2,
  refreshed: 2,
  failed: 0,
  errors: [],
  timestamp: "2025-12-23T01:00:00Z",
};

describe("useJiraLinks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiGet.mockResolvedValue(mockJiraLinks);
  });

  it("fetches links when projectId is provided", async () => {
    const { result } = renderHook(() => useJiraLinks("proj-123"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockApiGet).toHaveBeenCalledWith("/projects/proj-123/jira-links");
    expect(result.current.data).toEqual(mockJiraLinks);
  });

  it("is disabled when projectId is undefined", async () => {
    const { result } = renderHook(() => useJiraLinks(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.data).toBeUndefined();
    expect(result.current.isFetching).toBe(false);
    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it("handles API error", async () => {
    mockApiGet.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useJiraLinks("proj-123"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });
});

describe("useCreateJiraLink", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiPost.mockResolvedValue(mockJiraLinks[0]);
  });

  it("calls POST with URL data", async () => {
    const { result } = renderHook(() => useCreateJiraLink("proj-123"), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync({
      url: "https://test.atlassian.net/browse/PROJ-101",
    });

    expect(mockApiPost).toHaveBeenCalledWith("/projects/proj-123/jira-links", {
      url: "https://test.atlassian.net/browse/PROJ-101",
    });
  });

  it("returns created link on success", async () => {
    const { result } = renderHook(() => useCreateJiraLink("proj-123"), {
      wrapper: createWrapper(),
    });

    const response = await result.current.mutateAsync({
      url: "https://test.atlassian.net/browse/PROJ-101",
    });

    expect(response).toEqual(mockJiraLinks[0]);
  });

  it("handles API error", async () => {
    mockApiPost.mockRejectedValue(new Error("Failed to create"));

    const { result } = renderHook(() => useCreateJiraLink("proj-123"), {
      wrapper: createWrapper(),
    });

    await expect(
      result.current.mutateAsync({
        url: "https://test.atlassian.net/browse/PROJ-101",
      })
    ).rejects.toThrow("Failed to create");
  });
});

describe("useDeleteJiraLink", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiDelete.mockResolvedValue(undefined);
  });

  it("calls DELETE with link ID", async () => {
    const { result } = renderHook(() => useDeleteJiraLink("proj-123"), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("link-1");

    expect(mockApiDelete).toHaveBeenCalledWith(
      "/projects/proj-123/jira-links/link-1"
    );
  });

  it("handles API error", async () => {
    mockApiDelete.mockRejectedValue(new Error("Delete failed"));

    const { result } = renderHook(() => useDeleteJiraLink("proj-123"), {
      wrapper: createWrapper(),
    });

    await expect(result.current.mutateAsync("link-1")).rejects.toThrow(
      "Delete failed"
    );
  });
});

describe("useRefreshJiraLinks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiPost.mockResolvedValue(mockRefreshResponse);
  });

  it("calls POST to refresh endpoint", async () => {
    const { result } = renderHook(() => useRefreshJiraLinks("proj-123"), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync();

    expect(mockApiPost).toHaveBeenCalledWith("/projects/proj-123/jira/refresh");
  });

  it("returns refresh response on success", async () => {
    const { result } = renderHook(() => useRefreshJiraLinks("proj-123"), {
      wrapper: createWrapper(),
    });

    const response = await result.current.mutateAsync();

    expect(response).toEqual(mockRefreshResponse);
  });

  it("handles API error", async () => {
    mockApiPost.mockRejectedValue(new Error("Refresh failed"));

    const { result } = renderHook(() => useRefreshJiraLinks("proj-123"), {
      wrapper: createWrapper(),
    });

    await expect(result.current.mutateAsync()).rejects.toThrow("Refresh failed");
  });
});
