import { NextResponse } from "next/server";

import { getSessionCookieDomain } from "@/lib/auth/session";

const APP_URL = process.env.NEXTAUTH_URL ?? "http://localhost:3000";

/**
 * End the session and return the user to the sign-in page.
 *
 * @returns A redirect to the sign-in page with the session cookies cleared
 */
export async function GET(): Promise<NextResponse> {
  const domain = getSessionCookieDomain();

  const response = NextResponse.redirect(`${APP_URL}/en/login`);
  // Clear the cookies with the same domain scope they were set with, so a
  // parent-domain (COOKIE_DOMAIN) cookie is actually removed.
  response.cookies.set("access_token", "", { path: "/", maxAge: 0, domain });
  response.cookies.set("refresh_token", "", { path: "/", maxAge: 0, domain });
  return response;
}