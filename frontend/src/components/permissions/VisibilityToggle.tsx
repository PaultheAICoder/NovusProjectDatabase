/**
 * VisibilityToggle - Toggle project between public and restricted visibility.
 */

import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useUpdateVisibility } from "@/hooks/usePermissions";
import type { ProjectVisibility } from "@/types/permission";

interface VisibilityToggleProps {
  projectId: string;
  visibility: ProjectVisibility;
  disabled?: boolean;
}

export function VisibilityToggle({
  projectId,
  visibility,
  disabled = false,
}: VisibilityToggleProps) {
  const updateVisibility = useUpdateVisibility();

  const isRestricted = visibility === "restricted";
  const isPending = updateVisibility.isPending;

  const handleToggle = () => {
    updateVisibility.mutate({
      projectId,
      data: { visibility: isRestricted ? "public" : "restricted" },
    });
  };

  return (
    <div className="flex items-center gap-3">
      {isPending ? (
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      ) : isRestricted ? (
        <EyeOff className="h-4 w-4 text-muted-foreground" />
      ) : (
        <Eye className="h-4 w-4 text-muted-foreground" />
      )}
      <div className="flex flex-col">
        <Label htmlFor="visibility-toggle" className="text-sm font-medium">
          {isRestricted ? "Restricted" : "Public"}
        </Label>
        <span className="text-xs text-muted-foreground">
          {isRestricted
            ? "Only users with explicit permissions can access"
            : "All authenticated users can view"}
        </span>
      </div>
      <Switch
        id="visibility-toggle"
        checked={isRestricted}
        onCheckedChange={handleToggle}
        disabled={disabled || isPending}
        className="ml-auto"
      />
    </div>
  );
}
