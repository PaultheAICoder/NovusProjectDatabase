/**
 * Tests for ErrorBoundary components.
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ErrorBoundary } from "react-error-boundary";
import {
  PageErrorFallback,
  InlineErrorFallback,
  logError,
} from "../components/ErrorBoundary";

// Component that throws an error
function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error("Test error message");
  }
  return <div>No error</div>;
}

describe("PageErrorFallback", () => {
  const mockReset = vi.fn();
  const testError = new Error("An error occurred in the component");

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders error message and default title", () => {
    render(
      <PageErrorFallback error={testError} resetErrorBoundary={mockReset} />
    );
    // Title (default)
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    // Error message
    expect(
      screen.getByText("An error occurred in the component")
    ).toBeInTheDocument();
  });

  it("renders custom title when provided", () => {
    render(
      <PageErrorFallback
        error={testError}
        resetErrorBoundary={mockReset}
        title="Custom Error Title"
      />
    );
    expect(screen.getByText("Custom Error Title")).toBeInTheDocument();
  });

  it("calls resetErrorBoundary when Try Again is clicked", () => {
    render(
      <PageErrorFallback error={testError} resetErrorBoundary={mockReset} />
    );

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(mockReset).toHaveBeenCalledTimes(1);
  });

  it("renders Home button by default", () => {
    render(
      <PageErrorFallback error={testError} resetErrorBoundary={mockReset} />
    );
    expect(
      screen.getByRole("button", { name: /go home/i })
    ).toBeInTheDocument();
  });

  it("hides Home button when showHomeButton is false", () => {
    render(
      <PageErrorFallback
        error={testError}
        resetErrorBoundary={mockReset}
        showHomeButton={false}
      />
    );
    expect(
      screen.queryByRole("button", { name: /go home/i })
    ).not.toBeInTheDocument();
  });
});

describe("InlineErrorFallback", () => {
  const mockReset = vi.fn();
  const testError = new Error("Component failed");

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders compact error message", () => {
    render(
      <InlineErrorFallback error={testError} resetErrorBoundary={mockReset} />
    );
    expect(screen.getByText("Failed to load component")).toBeInTheDocument();
    expect(screen.getByText("Component failed")).toBeInTheDocument();
  });

  it("calls resetErrorBoundary when Retry is clicked", () => {
    render(
      <InlineErrorFallback error={testError} resetErrorBoundary={mockReset} />
    );

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(mockReset).toHaveBeenCalledTimes(1);
  });
});

describe("logError", () => {
  it("logs error to console in development", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const testError = new Error("Log test");
    const componentStack = "at Component (file.tsx:10)";

    logError(testError, { componentStack });

    expect(consoleSpy).toHaveBeenCalledWith(
      "[ErrorBoundary] Caught error:",
      testError
    );
    expect(consoleSpy).toHaveBeenCalledWith(
      "[ErrorBoundary] Component stack:",
      componentStack
    );

    consoleSpy.mockRestore();
  });
});

describe("ErrorBoundary integration", () => {
  beforeEach(() => {
    // Suppress console.error from React's error boundary
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary FallbackComponent={PageErrorFallback}>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText("No error")).toBeInTheDocument();
  });

  it("renders fallback when error occurs", () => {
    render(
      <ErrorBoundary FallbackComponent={PageErrorFallback}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText("Test error message")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
