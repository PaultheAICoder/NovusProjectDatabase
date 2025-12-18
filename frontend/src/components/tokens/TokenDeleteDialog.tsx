/**
 * TokenDeleteDialog - Confirmation dialog for deleting a token.
 */

import { AlertTriangle, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { APIToken } from "@/types/token";

interface TokenDeleteDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  token: APIToken | null;
  isDeleting: boolean;
}

export function TokenDeleteDialog({
  isOpen,
  onClose,
  onConfirm,
  token,
  isDeleting,
}: TokenDeleteDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Delete Token
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to delete the token &quot;{token?.name}&quot;?
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <p className="text-sm text-muted-foreground">
            This action cannot be undone. The token will immediately stop working for
            API authentication.
          </p>
          {token && (
            <div className="mt-4 rounded-md border bg-muted/50 p-3">
              <div className="text-sm">
                <strong>Token:</strong>{" "}
                <code className="rounded bg-muted px-1 text-xs">
                  {token.token_prefix}...
                </code>
              </div>
              {token.last_used_at && (
                <div className="mt-1 text-sm text-muted-foreground">
                  Last used: {new Date(token.last_used_at).toLocaleDateString()}
                </div>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isDeleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Delete Token
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
