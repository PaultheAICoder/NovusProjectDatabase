/**
 * FieldDiffViewer component for displaying field value comparisons.
 * Shows NPD and Monday.com values side by side with visual highlighting.
 * Supports selectable mode for field-level merge operations.
 */

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatFieldLabel } from "./conflict-utils";

interface FieldDiffViewerProps {
  fieldName: string;
  npdValue: unknown;
  mondayValue: unknown;
  isDifferent: boolean;
  /** Enable selection UI for merge mode */
  selectable?: boolean;
  /** Currently selected source ("npd" or "monday"), or null if not selected */
  selected?: "npd" | "monday" | null;
  /** Callback when a source is selected */
  onSelect?: (source: "npd" | "monday") => void;
}

/**
 * Format a value for display, handling various types.
 */
function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "(empty)";
  }
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return String(value);
}

export function FieldDiffViewer({
  fieldName,
  npdValue,
  mondayValue,
  isDifferent,
  selectable = false,
  selected = null,
  onSelect,
}: FieldDiffViewerProps) {
  const formattedNpd = formatValue(npdValue);
  const formattedMonday = formatValue(mondayValue);

  // Only allow selection for fields that are actually different
  const isSelectable = selectable && isDifferent;

  const handleNpdClick = () => {
    if (isSelectable && onSelect) {
      onSelect("npd");
    }
  };

  const handleMondayClick = () => {
    if (isSelectable && onSelect) {
      onSelect("monday");
    }
  };

  return (
    <div
      className={cn(
        "rounded-md border p-3",
        isDifferent ? "border-amber-300 bg-amber-50" : "border-gray-200 bg-gray-50"
      )}
    >
      <div className="mb-2 text-sm font-medium text-gray-700">
        {formatFieldLabel(fieldName)}
        {isDifferent && (
          <span className="ml-2 text-xs font-normal text-amber-600">
            (Different)
          </span>
        )}
        {isSelectable && selected && (
          <span className="ml-2 text-xs font-normal text-green-600">
            - Using {selected === "npd" ? "NPD" : "Monday.com"}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-4">
        {/* NPD Value */}
        <div>
          <div className="mb-1 text-xs font-medium text-blue-600">NPD</div>
          <div
            role={isSelectable ? "button" : undefined}
            tabIndex={isSelectable ? 0 : undefined}
            onClick={handleNpdClick}
            onKeyDown={
              isSelectable
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleNpdClick();
                    }
                  }
                : undefined
            }
            className={cn(
              "relative rounded border p-2 text-sm transition-all",
              // Base styling for different/same values
              isDifferent
                ? "border-blue-200 bg-blue-50"
                : "border-gray-200 bg-white",
              // Selectable mode styling
              isSelectable && "cursor-pointer hover:ring-2 hover:ring-blue-300",
              // Selected state styling
              isSelectable &&
                selected === "npd" &&
                "ring-2 ring-blue-500 bg-blue-100 border-blue-400"
            )}
          >
            {/* Selection indicator */}
            {isSelectable && selected === "npd" && (
              <div className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-blue-500">
                <Check className="h-3 w-3 text-white" />
              </div>
            )}
            <pre className="whitespace-pre-wrap font-sans">{formattedNpd}</pre>
          </div>
        </div>
        {/* Monday.com Value */}
        <div>
          <div className="mb-1 text-xs font-medium text-purple-600">Monday.com</div>
          <div
            role={isSelectable ? "button" : undefined}
            tabIndex={isSelectable ? 0 : undefined}
            onClick={handleMondayClick}
            onKeyDown={
              isSelectable
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleMondayClick();
                    }
                  }
                : undefined
            }
            className={cn(
              "relative rounded border p-2 text-sm transition-all",
              // Base styling for different/same values
              isDifferent
                ? "border-purple-200 bg-purple-50"
                : "border-gray-200 bg-white",
              // Selectable mode styling
              isSelectable &&
                "cursor-pointer hover:ring-2 hover:ring-purple-300",
              // Selected state styling
              isSelectable &&
                selected === "monday" &&
                "ring-2 ring-purple-500 bg-purple-100 border-purple-400"
            )}
          >
            {/* Selection indicator */}
            {isSelectable && selected === "monday" && (
              <div className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-purple-500">
                <Check className="h-3 w-3 text-white" />
              </div>
            )}
            <pre className="whitespace-pre-wrap font-sans">{formattedMonday}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}
