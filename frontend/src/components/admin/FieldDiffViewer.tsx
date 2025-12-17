/**
 * FieldDiffViewer component for displaying field value comparisons.
 * Shows NPD and Monday.com values side by side with visual highlighting.
 */

import { cn } from "@/lib/utils";

interface FieldDiffViewerProps {
  fieldName: string;
  npdValue: unknown;
  mondayValue: unknown;
  isDifferent: boolean;
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

/**
 * Convert snake_case or camelCase field names to Title Case labels.
 */
function formatFieldLabel(fieldName: string): string {
  return fieldName
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function FieldDiffViewer({
  fieldName,
  npdValue,
  mondayValue,
  isDifferent,
}: FieldDiffViewerProps) {
  const formattedNpd = formatValue(npdValue);
  const formattedMonday = formatValue(mondayValue);

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
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="mb-1 text-xs font-medium text-blue-600">NPD</div>
          <div
            className={cn(
              "rounded border p-2 text-sm",
              isDifferent
                ? "border-blue-200 bg-blue-50"
                : "border-gray-200 bg-white"
            )}
          >
            <pre className="whitespace-pre-wrap font-sans">{formattedNpd}</pre>
          </div>
        </div>
        <div>
          <div className="mb-1 text-xs font-medium text-purple-600">Monday.com</div>
          <div
            className={cn(
              "rounded border p-2 text-sm",
              isDifferent
                ? "border-purple-200 bg-purple-50"
                : "border-gray-200 bg-white"
            )}
          >
            <pre className="whitespace-pre-wrap font-sans">{formattedMonday}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}
