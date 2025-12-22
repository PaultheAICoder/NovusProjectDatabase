/**
 * Unit tests for TokenList component.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@/test-utils";
import userEvent from "@testing-library/user-event";
import { TokenList } from "./TokenList";
import type { APIToken } from "@/types/token";

// Mock date-fns to avoid timezone issues in tests
vi.mock("date-fns", () => ({
  formatDistanceToNow: vi.fn(() => "2 days ago"),
}));

const mockToken: APIToken = {
  id: "token-123",
  name: "Test Token",
  token_prefix: "npd_test",
  scopes: null,
  expires_at: null,
  last_used_at: "2025-12-20T10:00:00Z",
  is_active: true,
  created_at: "2025-12-18T10:00:00Z",
};

const mockInactiveToken: APIToken = {
  ...mockToken,
  id: "token-456",
  name: "Revoked Token",
  is_active: false,
  last_used_at: null,
};

describe("TokenList", () => {
  const defaultProps = {
    tokens: [mockToken],
    total: 1,
    page: 1,
    pageSize: 20,
    isLoading: false,
    onPageChange: vi.fn(),
    onRename: vi.fn(),
    onToggleActive: vi.fn(),
    onDelete: vi.fn(),
  };

  it("renders loading state", () => {
    render(<TokenList {...defaultProps} isLoading={true} tokens={[]} />);

    // Should show loading spinner (Loader2 icon has animate-spin class)
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("renders empty state when no tokens", () => {
    render(<TokenList {...defaultProps} tokens={[]} total={0} />);

    expect(screen.getByText("No API tokens found")).toBeInTheDocument();
    expect(
      screen.getByText("Create a token to get started with API access.")
    ).toBeInTheDocument();
  });

  it("renders token list with correct data", () => {
    render(<TokenList {...defaultProps} />);

    // Token name
    expect(screen.getByText("Test Token")).toBeInTheDocument();

    // Token prefix
    expect(screen.getByText("npd_test...")).toBeInTheDocument();

    // Active badge
    expect(screen.getByText("Active")).toBeInTheDocument();

    // Results count
    expect(screen.getByText("Showing 1-1 of 1")).toBeInTheDocument();
  });

  it("renders revoked token with correct badge", () => {
    render(<TokenList {...defaultProps} tokens={[mockInactiveToken]} />);

    expect(screen.getByText("Revoked")).toBeInTheDocument();
    expect(screen.getByText("Never")).toBeInTheDocument(); // last_used_at is null
  });

  it("calls onRename when rename action clicked", async () => {
    const onRename = vi.fn();
    const user = userEvent.setup();

    render(<TokenList {...defaultProps} onRename={onRename} />);

    // Open dropdown menu - look for the button with MoreHorizontal icon
    const menuButtons = screen.getAllByRole("button");
    const menuButton = menuButtons.find(
      (btn) => btn.querySelector("svg.lucide-more-horizontal") !== null
    );
    expect(menuButton).toBeDefined();
    await user.click(menuButton!);

    // Click rename option
    const renameOption = screen.getByText("Rename");
    await user.click(renameOption);

    expect(onRename).toHaveBeenCalledWith(mockToken);
  });

  it("calls onDelete when delete action clicked", async () => {
    const onDelete = vi.fn();
    const user = userEvent.setup();

    render(<TokenList {...defaultProps} onDelete={onDelete} />);

    // Open dropdown menu
    const menuButtons = screen.getAllByRole("button");
    const menuButton = menuButtons.find(
      (btn) => btn.querySelector("svg.lucide-more-horizontal") !== null
    );
    expect(menuButton).toBeDefined();
    await user.click(menuButton!);

    // Click delete option
    const deleteOption = screen.getByText("Delete");
    await user.click(deleteOption);

    expect(onDelete).toHaveBeenCalledWith(mockToken);
  });

  it("shows pagination when total exceeds pageSize", () => {
    render(
      <TokenList
        {...defaultProps}
        tokens={[mockToken]}
        total={25}
        page={1}
        pageSize={20}
      />
    );

    expect(screen.getByText("Previous")).toBeInTheDocument();
    expect(screen.getByText("Next")).toBeInTheDocument();
  });

  it("does not show pagination when total is within pageSize", () => {
    render(<TokenList {...defaultProps} total={10} pageSize={20} />);

    expect(screen.queryByText("Previous")).not.toBeInTheDocument();
    expect(screen.queryByText("Next")).not.toBeInTheDocument();
  });

  it("disables previous button on first page", () => {
    render(
      <TokenList {...defaultProps} total={25} page={1} pageSize={20} />
    );

    const prevButton = screen.getByText("Previous").closest("button");
    expect(prevButton).toBeDisabled();
  });

  it("calls onPageChange with correct page number", async () => {
    const onPageChange = vi.fn();
    const user = userEvent.setup();

    render(
      <TokenList
        {...defaultProps}
        tokens={[mockToken]}
        total={25}
        page={1}
        pageSize={20}
        onPageChange={onPageChange}
      />
    );

    const nextButton = screen.getByText("Next").closest("button")!;
    await user.click(nextButton);

    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("shows user column when showUserColumn is true", () => {
    render(<TokenList {...defaultProps} showUserColumn={true} />);

    expect(screen.getByText("User")).toBeInTheDocument();
  });
});
