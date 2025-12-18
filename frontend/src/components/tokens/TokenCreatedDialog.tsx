/**
 * TokenCreatedDialog - Shows the plaintext token ONCE after creation.
 * User MUST copy it now - it cannot be retrieved later.
 */

import { useState } from "react";
import { AlertTriangle, Check, Copy } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface TokenCreatedDialogProps {
  isOpen: boolean;
  onClose: () => void;
  token: string | null;
  tokenName: string;
}

export function TokenCreatedDialog({
  isOpen,
  onClose,
  token,
  tokenName,
}: TokenCreatedDialogProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!token) return;

    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = token;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleClose = () => {
    setCopied(false);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Token Created Successfully</DialogTitle>
          <DialogDescription>
            Your new API token &quot;{tokenName}&quot; has been created.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <Alert className="border-amber-200 bg-amber-50">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              <strong>Important:</strong> This token will only be shown once. Copy it now
              and store it securely. You will not be able to see it again.
            </AlertDescription>
          </Alert>

          <div className="space-y-2">
            <label className="text-sm font-medium">Your API Token</label>
            <div className="flex gap-2">
              <code className="flex-1 break-all rounded-md border bg-muted p-3 font-mono text-sm">
                {token}
              </code>
              <Button
                variant="outline"
                size="icon"
                onClick={handleCopy}
                className="shrink-0"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-600" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          <p className="text-sm text-muted-foreground">
            Use this token in the Authorization header:
          </p>
          <code className="block rounded-md border bg-muted p-2 text-xs">
            Authorization: Bearer {token?.substring(0, 15)}...
          </code>
        </div>

        <DialogFooter>
          <Button onClick={handleClose}>
            {copied ? "Done" : "I've Copied the Token"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
