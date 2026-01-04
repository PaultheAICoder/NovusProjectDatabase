/**
 * EditPermissionDialog - Dialog for editing a permission level.
 */

import { useState, useEffect } from "react";
import { Loader2, User, Users } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useUpdatePermission } from "@/hooks/usePermissions";
import type { PermissionLevel, ProjectPermission } from "@/types/permission";
import {
  PERMISSION_LEVEL_LABELS,
  PERMISSION_LEVEL_DESCRIPTIONS,
} from "@/types/permission";

interface EditPermissionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  permission: ProjectPermission | null;
}

const PERMISSION_LEVELS: PermissionLevel[] = ["viewer", "editor", "owner"];

export function EditPermissionDialog({
  isOpen,
  onClose,
  projectId,
  permission,
}: EditPermissionDialogProps) {
  const [permissionLevel, setPermissionLevel] =
    useState<PermissionLevel>("viewer");
  const updatePermission = useUpdatePermission();

  // Reset to current permission level when dialog opens
  useEffect(() => {
    if (permission) {
      setPermissionLevel(permission.permission_level);
    }
  }, [permission]);

  const handleSubmit = async () => {
    if (!permission) return;

    try {
      await updatePermission.mutateAsync({
        projectId,
        permissionId: permission.id,
        data: { permission_level: permissionLevel },
      });
      onClose();
    } catch {
      // Error handled by mutation
    }
  };

  const handleClose = () => {
    onClose();
  };

  const isChanged = permission?.permission_level !== permissionLevel;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Permission</DialogTitle>
          <DialogDescription>
            Change the permission level for this grant.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          {/* Display grantee info (read-only) */}
          <div className="space-y-2">
            <Label>Grantee</Label>
            <div className="flex items-center gap-2 rounded-md border bg-muted/50 p-3">
              {permission?.user_id ? (
                <>
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">User</span>
                  <code className="ml-auto rounded bg-muted px-2 py-1 text-xs">
                    {permission.user_id}
                  </code>
                </>
              ) : (
                <>
                  <Users className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">Team</span>
                  <code className="ml-auto rounded bg-muted px-2 py-1 text-xs">
                    {permission?.team_id}
                  </code>
                </>
              )}
            </div>
          </div>

          {/* Permission Level */}
          <div className="space-y-2">
            <Label htmlFor="permission-level">Permission Level</Label>
            <Select
              value={permissionLevel}
              onValueChange={(v) => setPermissionLevel(v as PermissionLevel)}
            >
              <SelectTrigger id="permission-level">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERMISSION_LEVELS.map((level) => (
                  <SelectItem key={level} value={level}>
                    <div className="flex flex-col">
                      <span>{PERMISSION_LEVEL_LABELS[level]}</span>
                      <span className="text-xs text-muted-foreground">
                        {PERMISSION_LEVEL_DESCRIPTIONS[level]}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={updatePermission.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isChanged || updatePermission.isPending}
          >
            {updatePermission.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
