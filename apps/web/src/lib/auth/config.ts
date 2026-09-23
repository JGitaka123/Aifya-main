/**
 * Shared auth configuration for the Next.js BFF route handlers.
 *
 * Aifya authenticates against its own API (self-issued tokens). The BFF
 * simply proxies credentials to the API and stores the returned tokens in
 * httpOnly cookies - the browser never sees the tokens.
 */

/**
 * Server-side base URL for the Aifya API (used by the BFF route handlers,
 * never exposed to the browser).
 *
 * @returns API v1 base URL without a trailing slash
 */
export function getBackendApiBase(): string {
  const raw =
    process.env.API_REWRITE_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000/api/v1";
  const trimmed = raw.replace(/\/+$/, "");
  return trimmed || "http://localhost:8000/api/v1";
}

/**
 * URL of the branded login page (default English locale).
 *
 * @returns The internal login page URL
 */
export function getLoginPageUrl(): string {
  return "/en/login";
}