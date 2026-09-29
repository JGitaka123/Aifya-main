import { NextRequest, NextResponse } from "next/server";

import {
  getKeycloakClientId,
  getKeycloakIssuer,
  getOidcRedirectUri,
} from "@/lib/auth/config";
import {
  OIDC_RETURN_TO_COOKIE,
  OIDC_STATE_COOKIE,
  OIDC_TRANSACTION_MAX_AGE_SECONDS,
  OIDC_VERIFIER_COOKIE,
  buildAuthorizeUrl,
  createPkcePair,
  createState,
} from "@/lib/auth/oidc";
import { safeReturnTo, sessionCookieOptions } from "@/lib/auth/session";

// node:crypto mints the PKCE pair, so this route cannot run on the edge.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Begin a Keycloak sign-in.
 *
 * Mints an anti-CSRF state and a PKCE verifier, parks them in short-lived
 * httpOnly cookies, and sends the browser to Keycloak's authorization
 * endpoint. Nothing from the caller is trusted: the returnTo target is
 * sanitised to a same-origin path before it is stored.
 *
 * @param request - Incoming request carrying the optional returnTo target
 * @returns A redirect to Keycloak, with the transaction cookies set
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const returnTo = safeReturnTo(request.nextUrl.searchParams.get("returnTo"));
  const { verifier, challenge } = createPkcePair();
  const state = createState();

  const authorizeUrl = buildAuthorizeUrl({
    issuer: getKeycloakIssuer(),
    clientId: getKeycloakClientId(),
    redirectUri: getOidcRedirectUri(),
    state,
    codeChallenge: challenge,
  });

  const response = NextResponse.redirect(authorizeUrl);
  // The same cookie policy as the session cookies, just short lived: these
  // exist only for the duration of the redirect round trip.
  const options = sessionCookieOptions(OIDC_TRANSACTION_MAX_AGE_SECONDS);

  response.cookies.set(OIDC_STATE_COOKIE, state, options);
  response.cookies.set(OIDC_VERIFIER_COOKIE, verifier, options);
  response.cookies.set(OIDC_RETURN_TO_COOKIE, returnTo, options);

  return response;
}
