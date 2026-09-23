import { NextRequest, NextResponse } from "next/server";

import { BETA_PUBLIC_ACCESS_ENABLED } from "@/lib/auth/beta";
import { getBackendApiBase, getLoginPageUrl } from "@/lib/auth/config";
import { safeReturnTo, sessionCookieOptions } from "@/lib/auth/session";

/**
 * Send the browser to the branded sign-in page, remembering where the user
 * was heading. Aifya has no external identity provider, so there is no
 * redirect dance to run first.
 *
 * @param request - Incoming request carrying the optional returnTo target
 * @returns A redirect to the sign-in page
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const returnTo = safeReturnTo(request.nextUrl.searchParams.get("returnTo"));

  if (BETA_PUBLIC_ACCESS_ENABLED) {
    return NextResponse.redirect(new URL(returnTo, request.url));
  }

  const target = new URL(getLoginPageUrl(), request.url);
  target.searchParams.set("returnTo", returnTo);
  return NextResponse.redirect(target);
}

/**
 * Verify an email and password against the Aifya API and start a session.
 *
 * The tokens the API returns are stored in httpOnly cookies, so the browser
 * never sees them and JavaScript cannot exfiltrate them.
 *
 * @param request - Incoming request carrying { email, password }
 * @returns 200 with the session cookies, or an error status with a message
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  let body: { email?: string; password?: string };
  try {
    body = (await request.json()) as { email?: string; password?: string };
  } catch {
    return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  }

  if (!body.email || !body.password) {
    return NextResponse.json(
      { error: "Email and password are required." },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(`${getBackendApiBase()}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: body.email, password: body.password }),
      cache: "no-store",
    });

    const data = (await response.json().catch(() => ({}))) as {
      access_token?: string;
      refresh_token?: string;
      expires_in?: number;
      error?: string;
      detail?: string;
      user?: unknown;
    };

    if (!response.ok || !data.access_token) {
      return NextResponse.json(
        { error: data.detail ?? data.error ?? "Invalid email or password." },
        { status: response.status === 401 ? 401 : 400 },
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