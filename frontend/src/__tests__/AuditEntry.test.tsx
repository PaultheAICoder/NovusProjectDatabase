/**
 * Tests for AuditEntry component.
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AuditEntry } from "../components/audit/AuditEntry";
import type { AuditLogEntry } from "../types/audit";

const baseEntry: AuditLogEntry = {
  id: "entry-1",
  entity_type: "project",
  entity_id: "proj-123",
  action: "create",
  user: {
    id: "user-1",
    display_name: "John Doe",
  },
  changed_fields: null,
  created_at: "2024-01-15T10:30:00Z",
};

describe("AuditEntry", () => {
  it("renders create action with success badge", () => {
    render(<AuditEntry entry={baseEntry} />);
    expect(screen.getByText("Created")).toBeInTheDocument();
  });

  it("renders update action with default badge", () => {
    const updateEntry: AuditLogEntry = {
      ...baseEntry,
      action: "update",
      changed_fields: { name: { old: "Old Name", new: "New Name" } },
    };
    render(<AuditEntry entry={updateEntry} />);
    expect(screen.getByText("Updated")).toBeInTheDocument();
  });

  it("renders delete action with destructive badge", () => {
    const deleteEntry: AuditLogEntry = {
      ...baseEntry,
      action: "delete",
    };
    render(<AuditEntry entry={deleteEntry} />);
    expect(screen.getByText("Deleted")).toBeInTheDocument();
  });

  it("renders archive action with secondary badge", () => {
    const archiveEntry: AuditLogEntry = {
      ...baseEntry,
      action: "archive",
    };
    render(<AuditEntry entry={archiveEntry} />);
    expect(screen.getByText("Archived")).toBeInTheDocument();
  });

  it("displays user name", () => {
    render(<AuditEntry entry={baseEntry} />);
    expect(screen.getByText("John Doe")).toBeInTheDocument();
  });

  it("displays System when user is null", () => {
    const systemEntry: AuditLogEntry = {
      ...baseEntry,
      user: null,
    };
    render(<AuditEntry entry={systemEntry} />);
    expect(screen.getByText("System")).toBeInTheDocument();
  });

  it("formats timestamp correctly", () => {
    render(<AuditEntry entry={baseEntry} />);
    // Using regex to match the date format as it depends on timezone
    expect(screen.getByText(/Jan 15, 2024 at/)).toBeInTheDocument();
  });

  it("shows expand button for update entries with field changes", () => {
    const updateEntry: AuditLogEntry = {
      ...baseEntry,
      action: "update",
      changed_fields: { name: { old: "Old Name", new: "New Name" } },
    };
    render(<AuditEntry entry={updateEntry} />);
    expect(screen.getByRole("button", { name: /expand changes/i })).toBeInTheDocument();
    expect(screen.getByText("1 field(s)")).toBeInTheDocument();
  });

  it("does not show expand button for create entries", () => {
    render(<AuditEntry entry={baseEntry} />);
    expect(screen.queryByRole("button", { name: /expand/i })).not.toBeInTheDocument();
  });

  it("does not show expand button for delete entries", () => {
    const deleteEntry: AuditLogEntry = {
      ...baseEntry,
      action: "delete",
    };
    render(<AuditEntry entry={deleteEntry} />);
    expect(screen.queryByRole("button", { name: /expand/i })).not.toBeInTheDocument();
  });

  it("toggles field changes visibility when expand button is clicked", () => {
    const updateEntry: AuditLogEntry = {
      ...baseEntry,
      action: "update",
      changed_fields: {
        name: { old: "Old Name", new: "New Name" },
        status: { old: "active", new: "completed" },
      },
    };
    render(<AuditEntry entry={updateEntry} />);

    // Initially field changes should not be visible
    expect(screen.queryByText("Previous")).not.toBeInTheDocument();
    expect(screen.queryByText("New")).not.toBeInTheDocument();

    // Click expand button
    const expandButton = screen.getByRole("button", { name: /expand changes/i });
    fireEvent.click(expandButton);

    // Field changes should now be visible
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("respects controlled expanded state", () => {
    const updateEntry: AuditLogEntry = {
      ...baseEntry,
      action: "update",
      changed_fields: { name: { old: "Old Name", new: "New Name" } },
    };

    const { rerender } = render(
      <AuditEntry entry={updateEntry} isExpanded={true} onToggleExpand={vi.fn()} />
    );
    expect(screen.getByText("Name")).toBeInTheDocument();

    rerender(
      <AuditEntry entry={updateEntry} isExpanded={false} onToggleExpand={vi.fn()} />
    );
    expect(screen.queryByText("Previous")).not.toBeInTheDocument();
  });

  it("calls onToggleExpand when expand button is clicked in controlled mode", () => {
    const updateEntry: AuditLogEntry = {
      ...baseEntry,
      action: "update",
      changed_fields: { name: { old: "Old Name", new: "New Name" } },
    };

    const onToggleExpand = vi.fn();
    render(
      <AuditEntry entry={updateEntry} isExpanded={false} onToggleExpand={onToggleExpand} />
    );

    fireEvent.click(screen.getByRole("button", { name: /expand changes/i }));
    expect(onToggleExpand).toHaveBeenCalledTimes(1);
  });
});
