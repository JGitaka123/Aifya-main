import { NextRequest, NextResponse } from "next/server";

import { getBackendApiBase } from "@/lib/auth/config";
import {
  getSessionCookieDomain,
  sessionCookieOptions,
} from "@/lib/auth/session";

/**
 * Exchange the httpOnly refresh_token cookie for a new access token.
 * Called by the API client when a request returns 401 - sessions would
 * otherwise silently die when the short-lived access token expires.
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
    const response = await fetch(`${getBackendApiBase()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    const data = (await response.json().catch(() => ({}))) as {
      access_token?: string;
      refresh_token?: string;
      expires_in?: number;
    };

    if (!response.ok || !data.access_token) {
      const failed = new NextResponse(null, { status: 401 });
      failed.cookies.set("access_token", "", { path: "/", maxAge: 0, domain: cookieDomain });
      failed.cookies.set("refresh_token", "", { path: "/", maxAge: 0, domain: cookieDomain });
      return failed;
    }

    const ok = new NextResponse(null, { status: 204 });
    ok.cookies.set("access_token", data.access_token, sessionCookieOptions(data.expires_in ?? 300));
    if (data.refresh_token) {
      ok.cookies.set("refresh_token", data.refresh_token, sessionCookieOptions(30 * 24 * 60 * 60));
    }
    return ok;
  } catch {
    return new NextResponse(null, { status: 401 });
  }
}