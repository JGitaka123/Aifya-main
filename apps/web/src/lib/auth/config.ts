/**
 * Shared auth configuration for the Next.js BFF route handlers.
 *
 * Aifya can sign users in two ways, selected by AUTH_PROVIDER:
 *
 *   internal  the BFF proxies the email and password to the Aifya API and
 *             stores the self-issued tokens it returns in httpOnly cookies.
 *   keycloak  the browser is sent to Keycloak (OpenID Connect authorization
 *             code flow with PKCE) and the tokens Keycloak returns are stored
 *             in the same cookies. The Aifya API validates them against
 *             Keycloak's published JWKS, so it stays the authority on who the
 *             caller is.
 *
 * Either way the tokens live in httpOnly cookies and the browser never sees
 * them.
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

/**
 * Whether this deployment signs users in through Keycloak.
 *
 * Read on the server from AUTH_PROVIDER - the same switch the API reads - so
 * the web app and the API can never disagree about which flow is in force.
 * NEXT_PUBLIC_AUTH_PROVIDER is the fallback for the browser bundle, which
 * cannot see the server-only variable.
 *
 * @returns True when the Keycloak OIDC flow should be used
 */
export function isKeycloakAuthEnabled(): boolean {
  const provider = (
    process.env.AUTH_PROVIDER ??
    process.env.NEXT_PUBLIC_AUTH_PROVIDER ??
    "internal"
  )
    .trim()
    .toLowerCase();
  return provider === "keycloak";
}

/**
 * Keycloak realm base URL, e.g. http://localhost:8080/realms/aifya.
 *
 * @returns Issuer URL without a trailing slash
 */
export function getKeycloakIssuer(): string {
  const url = (process.env.KEYCLOAK_URL ?? "http://localhost:8080").replace(
    /\/+$/,
    "",
  );
  const realm = process.env.KEYCLOAK_REALM ?? "aifya";
  return `${url}/realms/${realm}`;
}

/**
 * Public Keycloak client the browser signs in with.
 *
 * This is the browser-facing client (aifya-web), not the bearer-only resource
 * client the API validates an audience against.
 *
 * @returns Keycloak client id
 */
export function getKeycloakClientId(): string {
  return process.env.KEYCLOAK_CLIENT_ID ?? "aifya-web";
}

/**
 * Confidential-client secret used for the back-channel code exchange.
 *
 * Empty when the client is public, in which case only PKCE protects the code.
 *
 * @returns Client secret, or an empty string
 */
export function getKeycloakClientSecret(): string {
  return process.env.KEYCLOAK_CLIENT_SECRET ?? "";
}

/**
 * Public base URL of this web app, used to build the OIDC redirect URI.
 *
 * @returns Origin without a trailing slash
 */
export function getAppBaseUrl(): string {
  return (process.env.NEXTAUTH_URL ?? "http://localhost:3000").replace(
    /\/+$/,
    "",
  );
}

/**
 * The redirect URI Keycloak sends the browser back to.
 *
 * Must match a valid redirect URI on the Keycloak client exactly, so this
 * value is derived in one place rather than spelled out at each call site.
 *
 * @returns Absolute callback URL
 */
export function getOidcRedirectUri(): string {
  return `${getAppBaseUrl()}/api/auth/keycloak/callback`;
}
