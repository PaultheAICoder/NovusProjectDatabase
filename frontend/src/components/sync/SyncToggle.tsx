/**
 * SyncToggle component for enabling/disabling Monday.com sync.
 */

import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

interface SyncToggleProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  disabled?: boolean;
  label?: string;
}

export function SyncToggle({
  enabled,
  onToggle,
  disabled = false,
  label = "Monday.com Sync",
}: SyncToggleProps) {
  const id = "sync-toggle";

  return (
    <div className="flex items-center gap-2">
      <Switch
        id={id}
        checked={enabled}
        onCheckedChange={onToggle}
        disabled={disabled}
        aria-label={label}
      />
      <Label
        htmlFor={id}
        className={disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}
      >
        {label}
      </Label>
    </div>
  );
}
