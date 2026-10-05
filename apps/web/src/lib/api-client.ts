import { BETA_PUBLIC_ACCESS_ENABLED } from "@/lib/auth/beta";

/**
 * Normalize the API base URL so callers can pass module paths.
 *
 * @param baseUrl - Root API URL from environment
 * @returns API v1 base URL without a trailing slash
 */
function normalizeApiBaseUrl(baseUrl: string): string {
  const trimmed = baseUrl.replace(/\/+$/, "");
  return trimmed.endsWith("/api/v1") ? trimmed : `${trimmed}/api/v1`;
}

export const API_BASE_URL = normalizeApiBaseUrl(
  process.env.NEXT_PUBLIC_API_URL ?? "/api/v1",
);

interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
  /**
   * Public endpoints (the corridor display board) are called without a staff
   * session, so a 401 means "wrong display token", not "sign in again". Skip
   * the refresh-and-redirect dance and let the caller render its own error.
   */
  skipAuthRedirect?: boolean;
}

/**
 * API client for communicating with the FastAPI backend.
 * Handles auth headers, JSON serialization, and idempotency keys.
 */
class ApiClient {
  private baseUrl: string;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  /**
   * Refresh the session via /api/auth/refresh, deduplicating concurrent
   * refresh attempts so parallel 401s trigger a single token exchange.
   * @returns Whether the session was refreshed
   */
  private async refreshSession(): Promise<boolean> {
    this.refreshPromise ??= fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        this.refreshPromise = null;
      });
    return this.refreshPromise;
  }

  /**
   * Make an authenticated API request.
   * Uses httpOnly cookies for authentication — tokens never touch JS.
   * On 401 the client refreshes the session once and retries; if the
   * refresh fails the user is sent back through login.
   * @param path - API path (e.g., "/patients")
   * @param options - Fetch options with optional params
   * @returns Parsed JSON response
   */
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { params, skipAuthRedirect, ...fetchOptions } = options;

    let url = `${this.baseUrl}${path}`;
    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(fetchOptions.headers as Record<string, string>),
    };

    const doFetch = (): Promise<Response> =>
      fetch(url, {
        ...fetchOptions,
        headers,
        credentials: "include", // Send httpOnly cookies
      });

    let response = await doFetch();

    if (
      response.status === 401 &&
      !skipAuthRedirect &&
      typeof window !== "undefined" &&
      !BETA_PUBLIC_ACCESS_ENABLED
    ) {
      const refreshed = await this.refreshSession();
      if (refreshed) {
        response = await doFetch();
      } else {
        window.location.assign(
          `/api/auth/login?returnTo=${encodeURIComponent(
            window.location.pathname + window.location.search
          )}`
        );
        throw new ApiError(401, "Session expired");
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      const detail = error.detail ?? "Request failed";
      throw new ApiError(response.status, formatErrorDetail(detail), detail);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  }

  /**
   * GET request.
   * @param path - API path
   * @param params - Query parameters
   * @returns Parsed response
   */
  async get<T>(
    path: string,
    params?: Record<string, string>,
    options: RequestOptions = {},
  ): Promise<T> {
    return this.request<T>(path, { ...options, method: "GET", params });
  }

  /**
   * POST request with idempotency key.
   * @param path - API path
   * @param body - Request body
   * @param idempotencyKey - Idempotency key for safe retries
   * @returns Parsed response
   */
  async post<T>(
    path: string,
    body: unknown,
    idempotencyKey?: string
  ): Promise<T> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["X-Idempotency-Key"] = idempotencyKey;
    }
    return this.request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
      headers,
    });
  }

  /**
   * PATCH request with idempotency key.
   * @param path - API path
   * @param body - Request body
   * @param idempotencyKey - Idempotency key for safe retries
   * @returns Parsed response
   */
  async patch<T>(
    path: string,
    body: unknown,
    idempotencyKey?: string
  ): Promise<T> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["X-Idempotency-Key"] = idempotencyKey;
    }
    return this.request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
      headers,
    });
  }

  /**
   * PUT request with idempotency key.
   * @param path - API path
   * @param body - Request body
   * @param idempotencyKey - Idempotency key for safe retries
   * @returns Parsed response
   */
  async put<T>(
    path: string,
    body: unknown,
    idempotencyKey?: string
  ): Promise<T> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["X-Idempotency-Key"] = idempotencyKey;
    }
    return this.request<T>(path, {
      method: "PUT",
      body: JSON.stringify(body),
      headers,
    });
  }

  /**
   * DELETE request.
   * @param path - API path
   * @returns Parsed response
   */
  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }

}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Whether a failed request means the Aifya server could not be reached.
 *
 * The web app proxies /api/v1 to the API gateway, so a gateway that is not
 * running arrives as a 5xx from the proxy rather than as a connection error.
 * Both mean the same thing to the person on screen: the list is not empty and
 * the data is not wrong - nobody answered. Saying so out loud is the
 * difference between a support ticket about a broken queue and a restart of
 * the service.
 *
 * @param error - Error thrown by an apiClient call
 * @returns True when the server could not be reached or answered with a 5xx
 */
export function isServerUnavailable(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status >= 500;
  }
  // A failed fetch (server down, DNS, offline) rejects with a TypeError.
  return error instanceof TypeError;
}

/** One field error from a FastAPI validation failure. */
interface ValidationErrorItem {
  loc?: unknown[];
  msg?: string;
}

/**
 * Fold an API error payload into a readable sentence.
 *
 * FastAPI answers a rejected body with a list of field errors; each becomes
 * "field: reason" so the caller can tell which input to fix instead of getting
 * a bare "Request failed".
 *
 * @param detail - The `detail` value from the API error body
 * @returns Human-readable message
 */
function formatErrorDetail(detail: unknown): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const parts = (detail as ValidationErrorItem[]).map((item) => {
      const field = Array.isArray(item.loc)
        ? item.loc.filter((part) => typeof part === "string" && part !== "body").join(".")
        : "";
      const reason = typeof item.msg === "string" ? item.msg : "Invalid value";
      return field ? `${field}: ${reason}` : reason;
    });
    if (parts.length > 0) return parts.join("; ");
  }
  return "Request failed";
}

export const apiClient = new ApiClient(API_BASE_URL);
