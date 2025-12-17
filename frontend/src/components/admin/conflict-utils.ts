/**
 * Utility functions for conflict resolution components.
 */

/**
 * Convert snake_case or camelCase field names to Title Case labels.
 */
export function formatFieldLabel(fieldName: string): string {
  return fieldName
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
