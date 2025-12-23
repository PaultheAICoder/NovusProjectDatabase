/**
 * Tests for MondayContactSearch component.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MondayContactSearch } from "../components/monday/MondayContactSearch";
import type { MondayContactMatch, MondayContactSearchResponse } from "../types/monday";

// Mock the useMondaySync hook
const mockUseMondayContactSearch = vi.fn();
vi.mock("../hooks/useMondaySync", () => ({
  useMondayContactSearch: () => mockUseMondayContactSearch(),
}));

// Mock the useDebounce hook to return value immediately for testing
vi.mock("../hooks/useDebounce", () => ({
  useDebounce: <T,>(value: T) => value,
}));

// Mock scrollIntoView which doesn't exist in JSDOM
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

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

const mockContacts: MondayContactMatch[] = [
  {
    monday_id: "1001",
    name: "John Doe",
    email: "john@example.com",
    phone: "+1-555-1234",
    role_title: "Project Manager",
    organization: "Acme Corp",
    board_id: "board123",
  },
  {
    monday_id: "1002",
    name: "Jane Smith",
    email: "jane@example.com",
    phone: null,
    role_title: "Engineer",
    organization: "Tech Inc",
    board_id: "board123",
  },
];

const mockSearchResponse: MondayContactSearchResponse = {
  matches: mockContacts,
  total_matches: 2,
  query: "john",
  board_id: "board123",
  has_more: false,
  cursor: null,
};

describe("MondayContactSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseMondayContactSearch.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  it("renders button with default label", () => {
    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });
    expect(screen.getByText("Search Monday")).toBeInTheDocument();
  });

  it("renders button with custom label", () => {
    render(
      <MondayContactSearch
        onSelect={vi.fn()}
        buttonLabel="Custom Search Label"
      />,
      { wrapper: createWrapper() }
    );
    expect(screen.getByText("Custom Search Label")).toBeInTheDocument();
  });

  it("renders disabled button when disabled prop is true", () => {
    render(<MondayContactSearch onSelect={vi.fn()} disabled />, {
      wrapper: createWrapper(),
    });
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
  });

  it("opens popover when button is clicked", async () => {
    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    const button = screen.getByText("Search Monday");
    fireEvent.click(button);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Search Monday contacts...")
      ).toBeInTheDocument();
    });
  });

  it("shows minimum character hint when less than 2 characters typed", async () => {
    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    await waitFor(() => {
      expect(
        screen.getByText("Type at least 2 characters to search")
      ).toBeInTheDocument();
    });
  });

  it("shows loading state while searching", async () => {
    mockUseMondayContactSearch.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    // Type to trigger search
    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.change(input, { target: { value: "john" } });

    await waitFor(() => {
      expect(screen.getByText("Searching Monday...")).toBeInTheDocument();
    });
  });

  it("displays search results when available", async () => {
    mockUseMondayContactSearch.mockReturnValue({
      data: mockSearchResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.change(input, { target: { value: "john" } });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
      expect(screen.getByText("Jane Smith")).toBeInTheDocument();
    });
  });

  it("shows contact details in results", async () => {
    mockUseMondayContactSearch.mockReturnValue({
      data: mockSearchResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.change(input, { target: { value: "john" } });

    await waitFor(() => {
      expect(screen.getByText("john@example.com - Acme Corp")).toBeInTheDocument();
      expect(screen.getByText("Project Manager")).toBeInTheDocument();
    });
  });

  it("calls onSelect when a contact is clicked", async () => {
    mockUseMondayContactSearch.mockReturnValue({
      data: mockSearchResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    const onSelect = vi.fn();
    render(<MondayContactSearch onSelect={onSelect} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.change(input, { target: { value: "john" } });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("John Doe"));

    expect(onSelect).toHaveBeenCalledWith(mockContacts[0]);
  });

  it("shows no results message when search returns empty", async () => {
    mockUseMondayContactSearch.mockReturnValue({
      data: { ...mockSearchResponse, matches: [], total_matches: 0 },
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.change(input, { target: { value: "unknown" } });

    await waitFor(() => {
      expect(screen.getByText("No matching contacts found")).toBeInTheDocument();
    });
  });

  it("shows error message on search failure", async () => {
    mockUseMondayContactSearch.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("Network error"),
    });

    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.change(input, { target: { value: "test" } });

    await waitFor(() => {
      expect(
        screen.getByText("Failed to search Monday contacts.")
      ).toBeInTheDocument();
    });
  });

  it("shows rate limit error message when rate limited", async () => {
    mockUseMondayContactSearch.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("429 rate limit exceeded"),
    });

    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.change(input, { target: { value: "test" } });

    await waitFor(() => {
      expect(
        screen.getByText("Rate limit exceeded. Please wait and try again.")
      ).toBeInTheDocument();
    });
  });

  it("shows has_more indicator when more results exist", async () => {
    mockUseMondayContactSearch.mockReturnValue({
      data: { ...mockSearchResponse, has_more: true },
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.change(input, { target: { value: "john" } });

    await waitFor(() => {
      expect(
        screen.getByText("More results available - refine your search")
      ).toBeInTheDocument();
    });
  });

  it("handles keyboard navigation with ArrowDown", async () => {
    mockUseMondayContactSearch.mockReturnValue({
      data: mockSearchResponse,
      isLoading: false,
      isError: false,
      error: null,
    });

    const onSelect = vi.fn();
    render(<MondayContactSearch onSelect={onSelect} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.change(input, { target: { value: "john" } });

    await waitFor(() => {
      expect(screen.getByText("John Doe")).toBeInTheDocument();
    });

    // Press ArrowDown to highlight first item
    fireEvent.keyDown(input, { key: "ArrowDown" });

    // Press Enter to select the highlighted item
    fireEvent.keyDown(input, { key: "Enter" });

    // The first contact should be selected
    expect(onSelect).toHaveBeenCalledWith(mockContacts[0]);
  });

  it("handles Escape key to close popover", async () => {
    render(<MondayContactSearch onSelect={vi.fn()} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByText("Search Monday"));

    const input = await screen.findByPlaceholderText("Search Monday contacts...");
    fireEvent.keyDown(input, { key: "Escape" });

    await waitFor(() => {
      expect(
        screen.queryByPlaceholderText("Search Monday contacts...")
      ).not.toBeInTheDocument();
    });
  });
});
