import { NextRequest, NextResponse } from "next/server";

import {
  getBackendApiBase,
  getKeycloakClientId,
  getKeycloakClientSecret,
  getKeycloakIssuer,
  isKeycloakAuthEnabled,
} from "@/lib/auth/config";
import { refreshWithKeycloak, type OidcTokens } from "@/lib/auth/oidc";
import {
  getSessionCookieDomain,
  sessionCookieOptions,
} from "@/lib/auth/session";

/** Lifetime of the access_token cookie when the issuer omits expires_in. */
const ACCESS_TOKEN_FALLBACK_SECONDS = 300;
/** Lifetime of the refresh_token cookie. */
const REFRESH_TOKEN_SECONDS = 30 * 24 * 60 * 60;

/**
 * Exchange the httpOnly refresh_token cookie for a new access token.
 * Called by the API client when a request returns 401 - sessions would
 * otherwise silently die when the short-lived access token expires.
 *
 * The refresh is routed to whichever issuer minted the token: Keycloak's token
 * endpoint in keycloak mode, the Aifya API in internal mode. Both return the
 * same fields, so the cookie handling below is shared.
 *
 * @param request - Incoming request carrying the refresh_token cookie
 * @returns 204 with refreshed cookies, or 401 when re-login is required
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const refreshToken = request.cookies.get("refresh_token")?.value;
  if (!refreshToken) {
    return new NextResponse(null, { status: 401 });
  }

  const cookieDomain = getSessionCookieDomain();

  try {
    const tokens = isKeycloakAuthEnabled()
      ? await refreshWithKeycloak({
          issuer: getKeycloakIssuer(),
          clientId: getKeycloakClientId(),
          clientSecret: getKeycloakClientSecret(),
          refreshToken,
        })
      : await refreshWithAifyaApi(refreshToken);

    if (!tokens?.access_token) {
      // The token is spent or revoked: clear it so the client stops retrying.
      const failed = new NextResponse(null, { status: 401 });
      failed.cookies.set("access_token", "", { path: "/", maxAge: 0, domain: cookieDomain });
      failed.cookies.set("refresh_token", "", { path: "/", maxAge: 0, domain: cookieDomain });
      return failed;
    }

    const ok = new NextResponse(null, { status: 204 });
    ok.cookies.set(
      "access_token",
      tokens.access_token,
      sessionCookieOptions(tokens.expires_in ?? ACCESS_TOKEN_FALLBACK_SECONDS),
    );
    // Keycloak rotates refresh tokens on every use; storing the new one keeps
    // the session alive instead of letting the next refresh fail.
    if (tokens.refresh_token) {
      ok.cookies.set(
        "refresh_token",
        tokens.refresh_token,
        sessionCookieOptions(REFRESH_TOKEN_SECONDS),
      );
    }
    return ok;
  } catch {
    // Could not reach the issuer at all. Leave the cookies in place so the
    // client can retry without forcing the user to sign in again.
    return new NextResponse(null, { status: 401 });
  }
}

/**
 * Renew a session against the Aifya API's own refresh endpoint.
 *
 * @param refreshToken - Refresh token from the httpOnly cookie
 * @returns Fresh tokens, or null when the API rejected the refresh
 */
async function refreshWithAifyaApi(
  refreshToken: string,
): Promise<OidcTokens | null> {
  const response = await fetch(`${getBackendApiBase()}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  if (!response.ok) {
    return null;
  }
  return (await response.json().catch(() => null)) as OidcTokens | null;
}
