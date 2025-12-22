/**
 * Unit tests for useDebounce hook.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "./useDebounce";

describe("useDebounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns initial value immediately", () => {
    const { result } = renderHook(() => useDebounce("initial", 500));
    expect(result.current).toBe("initial");
  });

  it("does not update value before delay", () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "initial", delay: 500 } }
    );

    // Change value
    rerender({ value: "updated", delay: 500 });

    // Advance time but not past delay
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Should still be initial value
    expect(result.current).toBe("initial");
  });

  it("updates value after delay", () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "initial", delay: 500 } }
    );

    // Change value
    rerender({ value: "updated", delay: 500 });

    // Advance time past delay
    act(() => {
      vi.advanceTimersByTime(500);
    });

    // Should now be updated
    expect(result.current).toBe("updated");
  });

  it("resets timer on rapid value changes", () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "initial", delay: 500 } }
    );

    // First change
    rerender({ value: "change1", delay: 500 });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Second change before delay completes
    rerender({ value: "change2", delay: 500 });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Still should be initial (timer reset)
    expect(result.current).toBe("initial");

    // Complete the delay
    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Now should be the latest value
    expect(result.current).toBe("change2");
  });

  it("works with different types", () => {
    // Number type
    const { result: numberResult } = renderHook(() => useDebounce(42, 100));
    expect(numberResult.current).toBe(42);

    // Object type
    const obj = { foo: "bar" };
    const { result: objResult } = renderHook(() => useDebounce(obj, 100));
    expect(objResult.current).toBe(obj);

    // Null type
    const { result: nullResult } = renderHook(() => useDebounce(null, 100));
    expect(nullResult.current).toBeNull();
  });
});
