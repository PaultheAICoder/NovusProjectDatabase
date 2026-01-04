/**
 * DeletePermissionDialog - Confirmation dialog for removing a permission.
 */

import { AlertTriangle, Loader2, User, Users } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useRemovePermission } from "@/hooks/usePermissions";
import type { ProjectPermission } from "@/types/permission";
import { PERMISSION_LEVEL_LABELS } from "@/types/permission";

interface DeletePermissionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  permission: ProjectPermission | null;
}

export function DeletePermissionDialog({
  isOpen,
  onClose,
  projectId,
  permission,
}: DeletePermissionDialogProps) {
  const removePermission = useRemovePermission();

  const handleConfirm = async () => {
    if (!permission) return;

    try {
      await removePermission.mutateAsync({
        projectId,
        permissionId: permission.id,
      });
      onClose();
    } catch {
      // Error handled by mutation
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Remove Permission
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to remove this permission?
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <p className="text-sm text-muted-foreground">
            This will revoke access for the following grantee. They will no
            longer be able to access this project unless they have other
            permissions.
          </p>
          {permission && (
            <div className="mt-4 rounded-md border bg-muted/50 p-3">
              <div className="flex items-center gap-2 text-sm">
                {permission.user_id ? (
                  <>
                    <User className="h-4 w-4 text-muted-foreground" />
                    <span>User:</span>
                    <code className="rounded bg-muted px-1 text-xs">
                      {permission.user_id}
                    </code>
                  </>
                ) : (
                  <>
                    <Users className="h-4 w-4 text-muted-foreground" />
                    <span>Team:</span>
                    <code className="rounded bg-muted px-1 text-xs">
                      {permission.team_id}
                    </code>
                  </>
                )}
              </div>
              <div className="mt-1 text-sm text-muted-foreground">
                Level: {PERMISSION_LEVEL_LABELS[permission.permission_level]}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={removePermission.isPending}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={removePermission.isPending}
          >
            {removePermission.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Remove Permission
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
