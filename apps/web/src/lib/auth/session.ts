/**
 * Session cookie helpers shared by the auth route handlers.
 *
 * Aifya signs users in with its own credentials: the BFF posts the email and
 * password to the Aifya API and stores the tokens the API returns in httpOnly
 * cookies. The browser never sees a token, and there is no third-party
 * identity provider anywhere in the flow.
 */

/**
 * Whether the session cookies must carry the Secure flag.
 *
 * Local development is served over plain http, where browsers drop Secure
 * cookies, so the flag is only set for non-localhost production hosts.
 *
 * @returns True when the cookies must be marked Secure
 */
function shouldUseSecureCookies(): boolean {
  const appUrl = process.env.NEXTAUTH_URL ?? "";
  if (appUrl.startsWith("http://localhost") || appUrl.startsWith("http://127.0.0.1")) {
    return false;
  }
  return process.env.NODE_ENV === "production";
}

/**
 * Parent domain to scope the session cookies to, e.g. ".aifyamed.com".
 * Set COOKIE_DOMAIN when the web app (www.) and the API (api.) live on
 * different hosts under one registrable domain so the httpOnly access_token
 * cookie is sent to both. Unset = host-only cookie (single-host / local).
 *
 * @returns The cookie domain, or undefined for a host-only cookie
 */
export function getSessionCookieDomain(): string | undefined {
  const domain = process.env.COOKIE_DOMAIN?.trim();
  return domain ? domain : undefined;
}

/**
 * Build cookie options for the session (access_token / refresh_token)
 * cookies, applying COOKIE_DOMAIN when configured.
 *
 * @param maxAge - Cookie lifetime in seconds
 * @returns Cookie options for NextResponse.cookies.set
 */
export function sessionCookieOptions(maxAge: number): {
  httpOnly: true;
  secure: boolean;
  sameSite: "lax";
  path: string;
  maxAge: number;
  domain?: string;
} {
  const domain = getSessionCookieDomain();
  return {
    httpOnly: true,
    secure: shouldUseSecureCookies(),
    sameSite: "lax",
    path: "/",
    maxAge,
    ...(domain ? { domain } : {}),
  };
}

/**
 * Validate a `returnTo` value before it is used as a redirect target.
 *
 * @param value - Raw returnTo value from a query parameter or cookie
 * @param fallback - Path used when the value is missing or unsafe
 * @returns A same-origin path beginning with "/"
 */
export function safeReturnTo(value: string | null, fallback = "/"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }
  return value;
}