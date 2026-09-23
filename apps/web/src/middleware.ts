import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";
import { NextRequest, NextResponse } from "next/server";
import { BETA_PUBLIC_ACCESS_ENABLED } from "./lib/auth/beta";

const intlMiddleware = createMiddleware(routing);

// Unauthenticated routes: the auth BFF and the in-app login/sign-up
// landings (locale-prefixed, e.g. /en/login).
const PUBLIC_PATHS = ["/api/auth", "/login", "/signup"];

export default function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths (with or without a leading /<locale> segment).
  const withoutLocale = pathname.replace(/^\/[a-z]{2}(?=\/|$)/, "");
  if (
    PUBLIC_PATHS.some(
      (p) => pathname.startsWith(p) || withoutLocale.startsWith(p),
    )
  ) {
    return intlMiddleware(request);
  }

  if (BETA_PUBLIC_ACCESS_ENABLED) {
    return intlMiddleware(request);
  }

  // Check for access token cookie
  const token = request.cookies.get("access_token");

  if (!token) {
    const returnTo = `${pathname}${request.nextUrl.search}`;
    const loginUrl = new URL("/api/auth/login", request.url);
    loginUrl.searchParams.set("returnTo", returnTo);
    return NextResponse.redirect(loginUrl);
  }

  return intlMiddleware(request);
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
