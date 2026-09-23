/**
 * Secure API fetch wrapper.
 * Uses httpOnly cookies for authentication — tokens never touch JS.
 * All requests include credentials so the browser sends the access_token cookie.
 *
 * @param path - API path (e.g., "/api/v1/patients")
 * @param options - Standard fetch options
 * @returns Parsed JSON response
 * @throws Error with status code and message on failure
 */
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const configuredBase =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  // Some deployments configure the base with /api/v1 already included.
  const API_BASE = configuredBase.replace(/\/+$/, "").replace(/\/api\/v1$/i, "");

  // If path starts with /api/v1, prepend the backend base URL
  // Otherwise assume it's a relative path to the current origin (Next.js API routes)
  const url = path.startsWith("/api/v1") ? `${API_BASE}${path}` : path;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include", // Send httpOnly cookies to backend
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: response.statusText,
    }));
    const message = error.detail ?? "Request failed";
    throw new Error(`${response.status}: ${message}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
