/**
 * Tests for AuditTimeline component.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuditTimeline } from "../components/audit/AuditTimeline";
import type { AuditLogEntry, AuditLogResponse } from "../types/audit";

// Mock the useAuditHistory hooks
const mockUseProjectAuditHistory = vi.fn();
const mockUseContactAuditHistory = vi.fn();

vi.mock("../hooks/useAuditHistory", () => ({
  useProjectAuditHistory: () => mockUseProjectAuditHistory(),
  useContactAuditHistory: () => mockUseContactAuditHistory(),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return function TestWrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
};

const mockEntries: AuditLogEntry[] = [
  {
    id: "entry-1",
    entity_type: "project",
    entity_id: "proj-123",
    action: "create",
    user: { id: "user-1", display_name: "John Doe" },
    changed_fields: null,
    created_at: "2024-01-15T10:30:00Z",
  },
  {
    id: "entry-2",
    entity_type: "project",
    entity_id: "proj-123",
    action: "update",
    user: { id: "user-2", display_name: "Jane Smith" },
    changed_fields: { name: { old: "Old Name", new: "New Name" } },
    created_at: "2024-01-16T14:00:00Z",
  },
];

const mockResponse: AuditLogResponse = {
  items: mockEntries,
  total: 2,
  page: 1,
  page_size: 10,
  pages: 1,
};

describe("AuditTimeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProjectAuditHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });
    mockUseContactAuditHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  it("renders header with Change History title", () => {
    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText("Change History")).toBeInTheDocument();
  });

  it("shows loading state while fetching data", () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText("Loading history...")).toBeInTheDocument();
  });

  it("shows error state on fetch failure", () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("Network error"),
    });

    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText(/Failed to load audit history/)).toBeInTheDocument();
  });

  it("shows empty state when no entries exist", () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: { ...mockResponse, items: [] },
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText("No changes recorded yet.")).toBeInTheDocument();
  });

  it("renders audit entries correctly", async () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
      expect(screen.getByText("Jane Smith")).toBeInTheDocument();
      expect(screen.getByText("Created")).toBeInTheDocument();
      expect(screen.getByText("Updated")).toBeInTheDocument();
    });
  });

  it("shows date range filters when showFilters is true", () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(
      <AuditTimeline entityType="project" entityId="proj-123" showFilters={true} />,
      { wrapper: createWrapper() }
    );
    expect(screen.getByLabelText("From:")).toBeInTheDocument();
    expect(screen.getByLabelText("To:")).toBeInTheDocument();
  });

  it("hides date range filters when showFilters is false", () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(
      <AuditTimeline entityType="project" entityId="proj-123" showFilters={false} />,
      { wrapper: createWrapper() }
    );
    expect(screen.queryByLabelText("From:")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("To:")).not.toBeInTheDocument();
  });

  it("filters entries by date range", async () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });

    // Set from date to filter out first entry
    const fromInput = screen.getByLabelText("From:");
    fireEvent.change(fromInput, { target: { value: "2024-01-16" } });

    await waitFor(() => {
      // John Doe's entry (Jan 15) should be filtered out
      expect(screen.queryByText("John Doe")).not.toBeInTheDocument();
      // Jane Smith's entry (Jan 16) should still be visible
      expect(screen.getByText("Jane Smith")).toBeInTheDocument();
    });
  });

  it("shows clear filters button when filters are applied", async () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });

    // Apply a filter
    const fromInput = screen.getByLabelText("From:");
    fireEvent.change(fromInput, { target: { value: "2024-01-16" } });

    await waitFor(() => {
      expect(screen.getByText("Clear filters")).toBeInTheDocument();
    });
  });

  it("clears filters when clear button is clicked", async () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });

    // Apply a filter
    const fromInput = screen.getByLabelText("From:");
    fireEvent.change(fromInput, { target: { value: "2024-01-16" } });

    // Clear filters
    await waitFor(() => {
      expect(screen.getByText("Clear filters")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Clear filters"));

    await waitFor(() => {
      // Both entries should be visible again
      expect(screen.getByText("John Doe")).toBeInTheDocument();
      expect(screen.getByText("Jane Smith")).toBeInTheDocument();
    });
  });

  it("uses contact audit hook when entityType is contact", () => {
    mockUseContactAuditHistory.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<AuditTimeline entityType="contact" entityId="contact-123" />, {
      wrapper: createWrapper(),
    });

    // Verify that the contact hook was called
    expect(mockUseContactAuditHistory).toHaveBeenCalled();
    expect(screen.getByText("John Doe")).toBeInTheDocument();
  });

  it("shows pagination controls when multiple pages exist", () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: { ...mockResponse, pages: 3, total: 25 },
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Previous/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Next/i })).not.toBeDisabled();
  });

  it("hides pagination when only one page exists", () => {
    mockUseProjectAuditHistory.mockReturnValue({
      data: mockResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<AuditTimeline entityType="project" entityId="proj-123" />, {
      wrapper: createWrapper(),
    });

    expect(screen.queryByText(/Page \d of \d/)).not.toBeInTheDocument();
  });
});
