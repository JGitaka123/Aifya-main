import { apiFetch } from "@/lib/api";
import { generateId } from "@/lib/utils";

/**
 * Execute a state-changing API request with an idempotency key.
 *
 * @param path - Absolute API path
 * @param options - Fetch options for the request
 * @returns Parsed API response
 */
export function idempotentApiFetch<T>(
  path: string,
  options: RequestInit,
): Promise<T> {
  return apiFetch<T>(path, {
    ...options,
    headers: {
      ...(options.headers as Record<string, string> | undefined),
      "X-Idempotency-Key": generateId(),
    },
  });
}
