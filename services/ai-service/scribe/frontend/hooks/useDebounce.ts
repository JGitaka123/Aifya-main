import { useState, useEffect } from "react";

/**
 * Debounce a value by a specified delay.
 * Returns the debounced value that only updates after the delay has passed
 * since the last change to the input value.
 */
export function useDebounce<T>(value: T, delayMs: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debouncedValue;
}
