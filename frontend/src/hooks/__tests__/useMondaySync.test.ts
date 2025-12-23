/**
 * Tests for Monday sync hooks.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import {
  useMondayContactSearch,
  usePushContactToMonday,
} from "../useMondaySync";
import type { MondayContactSearchResponse, ContactSyncResponse } from "@/types/monday";

// Mock the api module
const mockApiGet = vi.fn();
const mockApiPost = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
    post: (...args: unknown[]) => mockApiPost(...args),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return function TestWrapper({ children }: { children: ReactNode }) {
    // Use createElement instead of JSX to avoid TypeScript issues in .ts file
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
};

const mockSearchResponse: MondayContactSearchResponse = {
  matches: [
    {
      monday_id: "1001",
      name: "John Doe",
      email: "john@example.com",
      phone: "+1-555-1234",
      role_title: "Project Manager",
      organization: "Acme Corp",
      board_id: "board123",
    },
  ],
  total_matches: 1,
  query: "john",
  board_id: "board123",
  has_more: false,
  cursor: null,
};

const mockSyncResponse: ContactSyncResponse = {
  contact_id: "contact-123",
  sync_triggered: true,
  message: "Contact synced successfully",
  monday_id: "monday-1001",
};

describe("useMondayContactSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiGet.mockResolvedValue(mockSearchResponse);
  });

  it("does not fetch when query is less than 2 characters", async () => {
    const { result } = renderHook(() => useMondayContactSearch("j"), {
      wrapper: createWrapper(),
    });

    // The query should be disabled
    expect(result.current.data).toBeUndefined();
    expect(result.current.isFetching).toBe(false);
    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it("does not fetch when query is empty", async () => {
    const { result } = renderHook(() => useMondayContactSearch(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.data).toBeUndefined();
    expect(result.current.isFetching).toBe(false);
    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it("fetches when query has 2+ characters", async () => {
    const { result } = renderHook(() => useMondayContactSearch("jo"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockApiGet).toHaveBeenCalledWith(
      "/admin/monday/contacts/search?q=jo"
    );
    expect(result.current.data).toEqual(mockSearchResponse);
  });

  it("includes board_id in query when provided", async () => {
    const { result } = renderHook(
      () => useMondayContactSearch("john", "board456"),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockApiGet).toHaveBeenCalledWith(
      "/admin/monday/contacts/search?q=john&board_id=board456"
    );
  });

  it("handles API error", async () => {
    mockApiGet.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useMondayContactSearch("test"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });
});

describe("usePushContactToMonday", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiPost.mockResolvedValue(mockSyncResponse);
  });

  it("calls the sync API with contact ID", async () => {
    const { result } = renderHook(() => usePushContactToMonday(), {
      wrapper: createWrapper(),
    });

    await result.current.mutateAsync("contact-123");

    expect(mockApiPost).toHaveBeenCalledWith(
      "/contacts/contact-123/sync-to-monday"
    );
  });

  it("returns sync response on success", async () => {
    const { result } = renderHook(() => usePushContactToMonday(), {
      wrapper: createWrapper(),
    });

    const response = await result.current.mutateAsync("contact-123");

    expect(response).toEqual(mockSyncResponse);
  });

  it("handles API error", async () => {
    mockApiPost.mockRejectedValue(new Error("Sync failed"));

    const { result } = renderHook(() => usePushContactToMonday(), {
      wrapper: createWrapper(),
    });

    await expect(result.current.mutateAsync("contact-123")).rejects.toThrow(
      "Sync failed"
    );
  });
});
