/**
 * Debounce hook for delaying value updates.
 *
 * Useful for preventing excessive API calls when values change rapidly,
 * such as during filter changes or typing.
 */

import { useState, useEffect } from "react";

/**
 * Returns a debounced version of the input value.
 * The returned value only updates after the specified delay has passed
 * without the input value changing.
 *
 * @param value - The value to debounce
 * @param delay - The delay in milliseconds before updating
 * @returns The debounced value
 *
 * @example
 * ```tsx
 * const [searchTerm, setSearchTerm] = useState("");
 * const debouncedSearchTerm = useDebounce(searchTerm, 300);
 *
 * // Use debouncedSearchTerm for API calls
 * useEffect(() => {
 *   if (debouncedSearchTerm) {
 *     searchApi(debouncedSearchTerm);
 *   }
 * }, [debouncedSearchTerm]);
 * ```
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    // Set up a timer to update the debounced value after the delay
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    // Clean up the timer if value changes before delay completes
    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}
