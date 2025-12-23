/**
 * AuditEntry component for displaying individual audit log entries.
 * Shows action, user, timestamp, and expandable field changes.
 */

import { useState } from "react";
import { format } from "date-fns";
import { ChevronDown, ChevronRight, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldDiff } from "./FieldDiff";
import type { AuditLogEntry, AuditAction } from "@/types/audit";

interface AuditEntryProps {
  entry: AuditLogEntry;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

/**
 * Get badge variant for each action type.
 */
function getActionVariant(
  action: AuditAction
): "default" | "secondary" | "success" | "destructive" {
  switch (action) {
    case "create":
      return "success";
    case "update":
      return "default";
    case "delete":
      return "destructive";
    case "archive":
      return "secondary";
    default:
      return "default";
  }
}

/**
 * Get human-readable label for action type.
 */
function getActionLabel(action: AuditAction): string {
  switch (action) {
    case "create":
      return "Created";
    case "update":
      return "Updated";
    case "delete":
      return "Deleted";
    case "archive":
      return "Archived";
    default:
      return action;
  }
}

export function AuditEntry({
  entry,
  isExpanded: controlledExpanded,
  onToggleExpand,
}: AuditEntryProps) {
  const [internalExpanded, setInternalExpanded] = useState(false);

  // Use controlled state if provided, otherwise internal state
  const isExpanded = controlledExpanded ?? internalExpanded;
  const handleToggle = onToggleExpand ?? (() => setInternalExpanded(!internalExpanded));

  const hasFieldChanges =
    entry.changed_fields && Object.keys(entry.changed_fields).length > 0;
  const canExpand = hasFieldChanges && entry.action !== "create" && entry.action !== "delete";

  const userName = entry.user?.display_name ?? "System";
  const formattedDate = format(new Date(entry.created_at), "MMM d, yyyy 'at' h:mm a");

  return (
    <div className="border-l-2 border-gray-200 pl-4 pb-4">
      {/* Timeline dot */}
      <div className="relative">
        <div className="absolute -left-[21px] top-1 h-3 w-3 rounded-full border-2 border-gray-300 bg-white" />
      </div>

      {/* Entry header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={getActionVariant(entry.action)}>
              {getActionLabel(entry.action)}
            </Badge>
            <span className="flex items-center gap-1 text-sm text-muted-foreground">
              <User className="h-3 w-3" />
              {userName}
            </span>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {formattedDate}
          </div>
        </div>

        {/* Expand button */}
        {canExpand && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleToggle}
            aria-expanded={isExpanded}
            aria-label={isExpanded ? "Collapse changes" : "Expand changes"}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            <span className="ml-1 text-xs">
              {Object.keys(entry.changed_fields || {}).length} field(s)
            </span>
          </Button>
        )}
      </div>

      {/* Expanded field changes */}
      {isExpanded && hasFieldChanges && (
        <div className="mt-3 space-y-2">
          {Object.entries(entry.changed_fields!).map(([fieldName, change]) => (
            <FieldDiff
              key={fieldName}
              fieldName={fieldName}
              oldValue={change.old}
              newValue={change.new}
            />
          ))}
        </div>
      )}
    </div>
  );
}
