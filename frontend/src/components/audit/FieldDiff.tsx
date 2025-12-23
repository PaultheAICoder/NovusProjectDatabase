/**
 * FieldDiff component for displaying before/after field value comparisons.
 * Shows old and new values with visual distinction.
 */

import { cn } from "@/lib/utils";

interface FieldDiffProps {
  fieldName: string;
  oldValue: unknown;
  newValue: unknown;
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
 * Check if value should be displayed in a code/pre block.
 */
function isComplexValue(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    JSON.stringify(value).length > 50
  );
}

export function FieldDiff({ fieldName, oldValue, newValue }: FieldDiffProps) {
  const formattedOld = formatValue(oldValue);
  const formattedNew = formatValue(newValue);
  const usePreFormat = isComplexValue(oldValue) || isComplexValue(newValue);

  return (
    <div className="rounded-md border border-gray-200 p-3">
      <div className="mb-2 text-sm font-medium text-gray-700">
        {formatFieldLabel(fieldName)}
      </div>
      <div className="grid grid-cols-2 gap-4">
        {/* Old Value */}
        <div>
          <div className="mb-1 text-xs font-medium text-red-600">Previous</div>
          <div
            className={cn(
              "rounded border border-red-200 bg-red-50 p-2 text-sm",
              usePreFormat && "overflow-x-auto"
            )}
          >
            {usePreFormat ? (
              <pre className="whitespace-pre-wrap font-mono text-xs">
                {formattedOld}
              </pre>
            ) : (
              <span>{formattedOld}</span>
            )}
          </div>
        </div>
        {/* New Value */}
        <div>
          <div className="mb-1 text-xs font-medium text-green-600">New</div>
          <div
            className={cn(
              "rounded border border-green-200 bg-green-50 p-2 text-sm",
              usePreFormat && "overflow-x-auto"
            )}
          >
            {usePreFormat ? (
              <pre className="whitespace-pre-wrap font-mono text-xs">
                {formattedNew}
              </pre>
            ) : (
              <span>{formattedNew}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
