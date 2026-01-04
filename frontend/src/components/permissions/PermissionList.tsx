/**
 * PermissionList - Display and manage project permissions.
 */

import { Edit, Loader2, Trash2, User, Users } from "lucide-react";
import { format } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { PermissionLevel, ProjectPermission } from "@/types/permission";
import { PERMISSION_LEVEL_LABELS } from "@/types/permission";

const levelVariants: Record<
  PermissionLevel,
  "default" | "secondary" | "outline"
> = {
  viewer: "outline",
  editor: "secondary",
  owner: "default",
};

interface PermissionListProps {
  permissions: ProjectPermission[];
  isLoading?: boolean;
  onEdit?: (permission: ProjectPermission) => void;
  onDelete?: (permission: ProjectPermission) => void;
  isUpdating?: boolean;
}

export function PermissionList({
  permissions,
  isLoading = false,
  onEdit,
  onDelete,
  isUpdating = false,
}: PermissionListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="text-muted-foreground">Loading permissions...</span>
      </div>
    );
  }

  if (permissions.length === 0) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        No permissions assigned yet.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Type</TableHead>
          <TableHead>ID</TableHead>
          <TableHead>Level</TableHead>
          <TableHead>Granted</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {permissions.map((perm) => (
          <TableRow key={perm.id}>
            <TableCell>
              {perm.user_id ? (
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4" />
                  <span>User</span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  <span>Team</span>
                </div>
              )}
            </TableCell>
            <TableCell className="font-mono text-xs">
              {perm.user_id || perm.team_id}
            </TableCell>
            <TableCell>
              <Badge variant={levelVariants[perm.permission_level]}>
                {PERMISSION_LEVEL_LABELS[perm.permission_level]}
              </Badge>
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {format(new Date(perm.granted_at), "MMM d, yyyy")}
            </TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-1">
                {onEdit && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onEdit(perm)}
                    disabled={isUpdating}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                )}
                {onDelete && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDelete(perm)}
                    disabled={isUpdating}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
