import { NextRequest, NextResponse } from "next/server";

import {
  getAppBaseUrl,
  getKeycloakClientId,
  getKeycloakClientSecret,
  getKeycloakIssuer,
  getLoginPageUrl,
  getOidcRedirectUri,
} from "@/lib/auth/config";
import {
  OIDC_RETURN_TO_COOKIE,
  OIDC_STATE_COOKIE,
  OIDC_VERIFIER_COOKIE,
  exchangeCodeForTokens,
  safeEquals,
} from "@/lib/auth/oidc";
import { safeReturnTo, sessionCookieOptions } from "@/lib/auth/session";

// The code exchange and the PKCE comparison use node:crypto.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Lifetime of the access_token cookie when Keycloak omits expires_in. */
const ACCESS_TOKEN_FALLBACK_SECONDS = 300;
/** Lifetime of the refresh_token cookie. */
const REFRESH_TOKEN_SECONDS = 30 * 24 * 60 * 60;

/**
 * Finish a Keycloak sign-in.
 *
 * Verifies the anti-CSRF state against the cookie set by /start, trades the
 * one-time code for tokens over the back channel, stores them in the same
 * httpOnly cookies the internal flow uses, and returns the browser to where
 * it was originally heading.
 *
 * Every failure path lands back on the sign-in page with a machine-readable
 * ``error`` code, never with a partially applied session.
 *
 * @param request - Callback request carrying code/state (or an OIDC error)
 * @returns A redirect into the app, or back to sign-in with an error code
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const params = request.nextUrl.searchParams;
  const returnTo = safeReturnTo(
    request.cookies.get(OIDC_RETURN_TO_COOKIE)?.value ?? null,
  );

  const providerError = params.get("error");
  if (providerError) {
    console.error(
      "[auth/callback] Keycloak returned an error:",
      providerError,
      params.get("error_description"),
    );
    // access_denied means the user pressed "cancel" on the Keycloak page;
    // anything else is a realm/client misconfiguration we cannot fix here.
    const code =
      providerError === "access_denied" ? "cancelled" : "provider_error";
    return fail(returnTo, code);
  }

  const code = params.get("code");
  const state = params.get("state") ?? undefined;
  const cookieState = request.cookies.get(OIDC_STATE_COOKIE)?.value;
  const codeVerifier = request.cookies.get(OIDC_VERIFIER_COOKIE)?.value;

  if (!code || !codeVerifier || !cookieState) {
    console.error("[auth/callback] missing code/verifier/state cookie", {
      hasCode: Boolean(code),
      hasVerifier: Boolean(codeVerifier),
      hasState: Boolean(cookieState),
    });
    return fail(returnTo, "session_expired");
  }

  // The state ties this callback to a login we started. A mismatch means the
  // response did not come from our own redirect, so it is discarded.
  if (!safeEquals(state, cookieState)) {
    return fail(returnTo, "invalid_state");
  }

  const tokens = await exchangeCodeForTokens({
    issuer: getKeycloakIssuer(),
    clientId: getKeycloakClientId(),
    clientSecret: getKeycloakClientSecret(),
    redirectUri: getOidcRedirectUri(),
    code,
    codeVerifier,
  });

  if (!tokens) {
    console.error("[auth/callback] token exchange failed");
    return fail(returnTo, "exchange_failed");
  }

  const response = NextResponse.redirect(new URL(returnTo, getAppBaseUrl()));
  response.cookies.set(
    "access_token",
    tokens.access_token,
    sessionCookieOptions(tokens.expires_in ?? ACCESS_TOKEN_FALLBACK_SECONDS),
  );
  if (tokens.refresh_token) {
    response.cookies.set(
      "refresh_token",
      tokens.refresh_token,
      sessionCookieOptions(REFRESH_TOKEN_SECONDS),
    );
  }

  clearTransactionCookies(response);
  return response;
}

/**
 * Redirect back to the sign-in page with an error code.
 *
 * Also clears the transaction cookies: a half-finished login must not be
 * reusable, and a stale verifier would otherwise linger for ten minutes.
 *
 * @param returnTo - Where the user was heading, restored after sign-in
 * @param code - Short machine-readable failure reason
 * @returns Redirect to the sign-in page
 */
function fail(returnTo: string, code: string): NextResponse {
  const target = new URL(getLoginPageUrl(), getAppBaseUrl());
  target.searchParams.set("error", code);
  if (returnTo !== "/") {
    target.searchParams.set("returnTo", returnTo);
  }
  const response = NextResponse.redirect(target);
  clearTransactionCookies(response);
  return response;
}

/**
 * Expire the three short-lived OIDC transaction cookies.
 *
 * @param response - Response the cookies are being cleared on
 */
function clearTransactionCookies(response: NextResponse): void {
  const expired = sessionCookieOptions(0);
  for (const name of [
    OIDC_STATE_COOKIE,
    OIDC_VERIFIER_COOKIE,
    OIDC_RETURN_TO_COOKIE,
  ]) {
    response.cookies.set(name, "", expired);
  }
}
