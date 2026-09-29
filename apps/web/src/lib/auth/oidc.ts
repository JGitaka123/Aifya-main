/**
 * Keycloak OpenID Connect helpers for the BFF route handlers.
 *
 * Implements the authorization code flow with PKCE (RFC 7636). The browser is
 * redirected to Keycloak, comes back with a one-time code, and this module
 * exchanges that code for tokens over a back channel. The tokens are then
 * stored in httpOnly cookies by the calling route handler.
 *
 * WHAT PROTECTS THE EXCHANGE
 * ``state`` is a random value stashed in an httpOnly cookie before the
 * redirect and compared on return, so an attacker cannot feed us a code from
 * a login they started (CSRF). ``code_verifier`` is never sent to the browser
 * until the back-channel call, so an intercepted code is useless on its own
 * (interception/replay).
 *
 * The ID token is deliberately not inspected here. Aifya does not use it for
 * authorization: the API validates the *access* token against Keycloak's JWKS
 * (signature, issuer and audience) on every request, so it - not this module -
 * is the authority on identity. Verifying the ID token twice would add code
 * without adding a security decision.
 */

import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

/** Cookie holding the anti-CSRF state for an in-flight login. */
export const OIDC_STATE_COOKIE = "oidc_state";
/** Cookie holding the PKCE code verifier for an in-flight login. */
export const OIDC_VERIFIER_COOKIE = "oidc_verifier";
/** Cookie holding where to send the user once the login completes. */
export const OIDC_RETURN_TO_COOKIE = "oidc_return_to";
/** How long a half-finished login stays valid, in seconds. */
export const OIDC_TRANSACTION_MAX_AGE_SECONDS = 600;

/** Token endpoint response, narrowed to the fields the BFF stores. */
export interface OidcTokens {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  refresh_expires_in?: number;
  token_type?: string;
}

/** A PKCE verifier and the challenge derived from it. */
export interface PkcePair {
  verifier: string;
  challenge: string;
}

/**
 * Generate a PKCE code verifier and its S256 challenge.
 *
 * @returns The verifier to keep secret and the challenge to publish
 */
export function createPkcePair(): PkcePair {
  const verifier = randomBytes(32).toString("base64url");
  return { verifier, challenge: createCodeChallenge(verifier) };
}

/**
 * Derive the S256 PKCE challenge for a verifier.
 *
 * @param verifier - PKCE code verifier
 * @returns Base64url-encoded SHA-256 digest of the verifier
 */
export function createCodeChallenge(verifier: string): string {
  return createHash("sha256").update(verifier).digest("base64url");
}

/**
 * Generate an unguessable anti-CSRF state value.
 *
 * @returns Base64url-encoded random string
 */
export function createState(): string {
  return randomBytes(32).toString("base64url");
}

/**
 * Compare two values without leaking their contents through timing.
 *
 * @param left - First value, e.g. the state from the query string
 * @param right - Second value, e.g. the state from the cookie
 * @returns True only when both are present and byte-identical
 */
export function safeEquals(left: string | undefined, right: string | undefined): boolean {
  if (!left || !right) {
    return false;
  }
  const leftBytes = Buffer.from(left, "utf8");
  const rightBytes = Buffer.from(right, "utf8");
  if (leftBytes.length !== rightBytes.length) {
    return false;
  }
  return timingSafeEqual(leftBytes, rightBytes);
}

/**
 * Build the Keycloak authorization endpoint URL to redirect the browser to.
 *
 * @param params - Issuer, client, redirect URI, state and PKCE challenge
 * @returns Absolute authorization URL
 */
export function buildAuthorizeUrl(params: {
  issuer: string;
  clientId: string;
  redirectUri: string;
  state: string;
  codeChallenge: string;
}): string {
  const url = new URL(`${params.issuer}/protocol/openid-connect/auth`);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", params.clientId);
  url.searchParams.set("redirect_uri", params.redirectUri);
  url.searchParams.set("scope", "openid profile email");
  url.searchParams.set("state", params.state);
  url.searchParams.set("code_challenge", params.codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  return url.toString();
}

/**
 * Trade an authorization code for tokens at Keycloak's token endpoint.
 *
 * @param params - Issuer, client credentials, redirect URI, code and verifier
 * @returns Tokens, or null when Keycloak rejected the exchange
 */
export async function exchangeCodeForTokens(params: {
  issuer: string;
  clientId: string;
  clientSecret: string;
  redirectUri: string;
  code: string;
  codeVerifier: string;
}): Promise<OidcTokens | null> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code: params.code,
    redirect_uri: params.redirectUri,
    client_id: params.clientId,
    code_verifier: params.codeVerifier,
  });
  if (params.clientSecret) {
    body.set("client_secret", params.clientSecret);
  }
  return postToTokenEndpoint(params.issuer, body);
}

/**
 * Renew an access token with a Keycloak refresh token.
 *
 * @param params - Issuer, client credentials and the refresh token
 * @returns Fresh tokens, or null when the refresh token is spent or revoked
 */
export async function refreshWithKeycloak(params: {
  issuer: string;
  clientId: string;
  clientSecret: string;
  refreshToken: string;
}): Promise<OidcTokens | null> {
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: params.refreshToken,
    client_id: params.clientId,
  });
  if (params.clientSecret) {
    body.set("client_secret", params.clientSecret);
  }
  return postToTokenEndpoint(params.issuer, body);
}

/**
 * POST a form-encoded grant to the realm token endpoint.
 *
 * @param issuer - Realm issuer URL
 * @param body - Grant parameters
 * @returns Tokens, or null on any non-2xx response
 */
async function postToTokenEndpoint(
  issuer: string,
  body: URLSearchParams,
): Promise<OidcTokens | null> {
  try {
    const response = await fetch(`${issuer}/protocol/openid-connect/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    const data = (await response.json()) as OidcTokens;
    return data.access_token ? data : null;
  } catch {
    return null;
  }
}

/**
 * Build the Keycloak end-session URL that also clears the SSO session.
 *
 * Without this the Keycloak session cookie survives, so the next sign-in
 * silently re-authenticates the same user.
 *
 * @param params - Issuer, client id and where Keycloak should return to
 * @returns Absolute logout URL
 */
export function buildEndSessionUrl(params: {
  issuer: string;
  clientId: string;
  postLogoutRedirectUri: string;
}): string {
  const url = new URL(`${params.issuer}/protocol/openid-connect/logout`);
  url.searchParams.set("client_id", params.clientId);
  url.searchParams.set("post_logout_redirect_uri", params.postLogoutRedirectUri);
  return url.toString();
}
