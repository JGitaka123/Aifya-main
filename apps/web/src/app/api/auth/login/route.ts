import { NextRequest, NextResponse } from "next/server";

import { BETA_PUBLIC_ACCESS_ENABLED } from "@/lib/auth/beta";
import {
  getBackendApiBase,
  getLoginPageUrl,
  isKeycloakAuthEnabled,
} from "@/lib/auth/config";
import { safeReturnTo, sessionCookieOptions } from "@/lib/auth/session";

/**
 * Send the browser to the right sign-in screen, remembering where the user was
 * heading.
 *
 * With AUTH_PROVIDER=keycloak the browser is sent straight into the OIDC
 * authorization code flow; with AUTH_PROVIDER=internal it lands on the branded
 * form. Either way the user ends up on the login page for the same reasons, so
 * the entry point is kept in one place.
 *
 * @param request - Incoming request carrying the optional returnTo target
 * @returns A redirect to Keycloak or to the branded sign-in page
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const returnTo = safeReturnTo(request.nextUrl.searchParams.get("returnTo"));

  if (BETA_PUBLIC_ACCESS_ENABLED) {
    return NextResponse.redirect(new URL(returnTo, request.url));
  }

  if (isKeycloakAuthEnabled()) {
    const keycloakStart = new URL("/api/auth/keycloak/start", request.url);
    keycloakStart.searchParams.set("returnTo", returnTo);
    return NextResponse.redirect(keycloakStart);
  }

  const target = new URL(getLoginPageUrl(), request.url);
  target.searchParams.set("returnTo", returnTo);
  return NextResponse.redirect(target);
}

/**
 * Verify an email and password against the Aifya API and start a session.
 *
 * Only available with AUTH_PROVIDER=internal: the API refuses /auth/login in
 * Keycloak mode, so the check here turns that into an actionable message
 * instead of a bare 405 from the backend.
 *
 * The tokens the API returns are stored in httpOnly cookies, so the browser
 * never sees them and JavaScript cannot exfiltrate them.
 *
 * @param request - Incoming request carrying { email, password, facility }
 * @returns 200 with the session cookies, or an error status with a message
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  if (isKeycloakAuthEnabled()) {
    return NextResponse.json(
      {
        error:
          "Password sign-in is disabled. Use the sign-in button to continue with Keycloak.",
        code: "oidc_required",
      },
      { status: 409 },
    );
  }

  let body: {
    email?: string;
    password?: string;
    facility?: string;
    duty?: string;
  };
  try {
    body = (await request.json()) as {
      email?: string;
      password?: string;
      facility?: string;
      duty?: string;
    };
  } catch {
    return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  }

  if (!body.email || !body.password || !body.facility || !body.duty) {
    return NextResponse.json(
      { error: "Email, password, hospital name and state of duty are required." },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(`${getBackendApiBase()}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: body.email,
        password: body.password,
        facility: body.facility,
        // The state of duty travels with the credentials so the API can match
        // it against the role HR recorded: the duty, not the account, is the
        // key that opens a workspace.
        duty: body.duty,
      }),
      cache: "no-store",
    });

    const data = (await response.json().catch(() => ({}))) as {
      access_token?: string;
      refresh_token?: string;
      expires_in?: number;
      error?: string;
      detail?: string;
      code?: string;
      user?: unknown;
    };

    if (!response.ok || !data.access_token) {
      // 401 means "wrong credentials" and 403 means "HR has to fix this". The
      // sign-in screen words those two differently, so the distinction has to
      // survive this hop rather than collapsing into a generic 400.
      const status =
        response.status === 401 || response.status === 403
          ? response.status
          : 400;
      return NextResponse.json(
        {
          error: data.detail ?? data.error ?? "Invalid email or password.",
          code: data.code ?? null,
        },
        { status },
      );
    }

    const ok = NextResponse.json(
      { authenticated: true, user: data.user ?? null },
      { status: 200 },
    );
    ok.cookies.set(
      "access_token",
      data.access_token,
      sessionCookieOptions(data.expires_in ?? 300),
    );
    if (data.refresh_token) {
      ok.cookies.set(
        "refresh_token",
        data.refresh_token,
        sessionCookieOptions(30 * 24 * 60 * 60),
      );
    }
    return ok;
  } catch {
    return NextResponse.json(
      { error: "Could not reach the sign-in service. Please try again." },
      { status: 502 },
    );
  }
}
