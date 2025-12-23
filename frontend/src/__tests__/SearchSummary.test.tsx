/**
 * Tests for SearchSummary component.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { SearchSummary } from "../components/features/SearchSummary";

describe("SearchSummary", () => {
  it("renders nothing when no summary provided", () => {
    const { container } = render(
      <SearchSummary summary={undefined} isLoading={false} error={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders loading skeleton when loading", () => {
    render(<SearchSummary summary={undefined} isLoading={true} error={null} />);
    expect(screen.getByText("AI Summary")).toBeInTheDocument();
    // Skeleton elements should be present
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error alert when error provided", () => {
    const error = new Error("Failed to generate summary");
    render(<SearchSummary summary={undefined} isLoading={false} error={error} />);
    expect(screen.getByText(/Unable to generate summary/)).toBeInTheDocument();
    expect(screen.getByText(/Failed to generate summary/)).toBeInTheDocument();
  });

  it("renders summary content when provided", () => {
    const summary = {
      summary: "This is a test summary.",
      query: "test query",
      context_used: 5,
      truncated: false,
    };
    render(<SearchSummary summary={summary} isLoading={false} error={null} />);
    expect(screen.getByText("AI Summary")).toBeInTheDocument();
    expect(screen.getByText("This is a test summary.")).toBeInTheDocument();
    expect(screen.getByText("Based on 5 source(s)")).toBeInTheDocument();
  });

  it("shows truncation indicator when truncated", () => {
    const summary = {
      summary: "Truncated summary.",
      query: "test query",
      context_used: 20,
      truncated: true,
    };
    render(<SearchSummary summary={summary} isLoading={false} error={null} />);
    expect(screen.getByText(/partial - context truncated/)).toBeInTheDocument();
  });
});
