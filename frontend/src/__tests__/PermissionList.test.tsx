/**
 * Tests for PermissionList component.
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PermissionList } from "../components/permissions/PermissionList";
import type { ProjectPermission } from "../types/permission";

const mockPermissions: ProjectPermission[] = [
  {
    id: "perm-1",
    project_id: "proj-123",
    user_id: "user-456",
    team_id: null,
    permission_level: "editor",
    granted_by: "user-789",
    granted_at: "2024-01-15T10:30:00Z",
  },
  {
    id: "perm-2",
    project_id: "proj-123",
    user_id: null,
    team_id: "team-abc",
    permission_level: "viewer",
    granted_by: "user-789",
    granted_at: "2024-01-10T08:00:00Z",
  },
  {
    id: "perm-3",
    project_id: "proj-123",
    user_id: "user-owner",
    team_id: null,
    permission_level: "owner",
    granted_by: null,
    granted_at: "2024-01-01T00:00:00Z",
  },
];

describe("PermissionList", () => {
  it("renders list of permissions", () => {
    render(<PermissionList permissions={mockPermissions} />);

    expect(screen.getByText("user-456")).toBeInTheDocument();
    expect(screen.getByText("team-abc")).toBeInTheDocument();
    expect(screen.getByText("user-owner")).toBeInTheDocument();
  });

  it("shows empty message when no permissions", () => {
    render(<PermissionList permissions={[]} />);
    expect(
      screen.getByText("No permissions assigned yet."),
    ).toBeInTheDocument();
  });

  it("shows loading spinner when loading", () => {
    render(<PermissionList permissions={[]} isLoading={true} />);
    expect(screen.getByText("Loading permissions...")).toBeInTheDocument();
  });

  it("displays correct permission level badges", () => {
    render(<PermissionList permissions={mockPermissions} />);

    expect(screen.getByText("Editor")).toBeInTheDocument();
    expect(screen.getByText("Viewer")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
  });

  it("displays User type for user permissions", () => {
    render(<PermissionList permissions={mockPermissions} />);

    // Find all User type cells
    const userTypes = screen.getAllByText("User");
    expect(userTypes.length).toBe(2); // Two user permissions
  });

  it("displays Team type for team permissions", () => {
    render(<PermissionList permissions={mockPermissions} />);

    expect(screen.getByText("Team")).toBeInTheDocument();
  });

  it("calls onEdit when edit button clicked", () => {
    const onEdit = vi.fn();
    render(<PermissionList permissions={mockPermissions} onEdit={onEdit} />);

    // Get all edit buttons and click the first one
    const editButtons = screen.getAllByRole("button");
    expect(editButtons.length).toBeGreaterThan(0);
    fireEvent.click(editButtons[0]!);

    expect(onEdit).toHaveBeenCalledWith(mockPermissions[0]);
  });

  it("calls onDelete when delete button clicked", () => {
    const onDelete = vi.fn();
    render(
      <PermissionList permissions={mockPermissions} onDelete={onDelete} />,
    );

    // Get all delete buttons (buttons with trash icon) and click the first one
    const deleteButtons = screen.getAllByRole("button");
    expect(deleteButtons.length).toBeGreaterThan(0);
    fireEvent.click(deleteButtons[0]!);

    expect(onDelete).toHaveBeenCalledWith(mockPermissions[0]);
  });

  it("disables buttons when isUpdating is true", () => {
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    render(
      <PermissionList
        permissions={mockPermissions}
        onEdit={onEdit}
        onDelete={onDelete}
        isUpdating={true}
      />,
    );

    const buttons = screen.getAllByRole("button");
    buttons.forEach((button) => {
      expect(button).toBeDisabled();
    });
  });

  it("formats date correctly", () => {
    render(<PermissionList permissions={mockPermissions} />);

    expect(screen.getByText("Jan 15, 2024")).toBeInTheDocument();
    expect(screen.getByText("Jan 10, 2024")).toBeInTheDocument();
    expect(screen.getByText("Jan 1, 2024")).toBeInTheDocument();
  });
});
