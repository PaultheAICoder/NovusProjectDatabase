/**
 * TokenCreateDialog - Dialog for creating a new API token.
 */

import { useState } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EXPIRATION_OPTIONS } from "@/types/token";
import type { APITokenCreateRequest } from "@/types/token";

interface TokenCreateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (data: APITokenCreateRequest) => void;
  isCreating: boolean;
}

export function TokenCreateDialog({
  isOpen,
  onClose,
  onCreate,
  isCreating,
}: TokenCreateDialogProps) {
  const [name, setName] = useState("");
  const [expiration, setExpiration] = useState<string>("90"); // Default 90 days

  const handleSubmit = () => {
    if (!name.trim()) return;

    let expires_at: string | undefined;
    if (expiration && expiration !== "never") {
      const days = parseInt(expiration, 10);
      const date = new Date();
      date.setDate(date.getDate() + days);
      expires_at = date.toISOString();
    }

    onCreate({
      name: name.trim(),
      expires_at,
    });
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setName("");
      setExpiration("90");
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create API Token</DialogTitle>
          <DialogDescription>
            Create a new personal access token for API authentication. The token will
            only be shown once after creation.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="token-name">Token Name</Label>
            <Input
              id="token-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., CI/CD Pipeline, Local Development"
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              Choose a descriptive name to identify this token.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="expiration">Expiration</Label>
            <Select value={expiration} onValueChange={setExpiration}>
              <SelectTrigger id="expiration">
                <SelectValue placeholder="Select expiration" />
              </SelectTrigger>
              <SelectContent>
                {EXPIRATION_OPTIONS.map((option) => (
                  <SelectItem
                    key={option.value ?? "never"}
                    value={option.value ?? "never"}
                  >
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isCreating}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!name.trim() || isCreating}>
            {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create Token
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
