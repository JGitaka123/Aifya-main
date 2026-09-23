import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_ROUTES = ["/clinician", "/billing", "/admin", "/analytics"];
const AUTH_ROUTES = ["/login"];
const PUBLIC_PATHS = ["/", "/login", "/_next", "/api", "/favicon.ico", "/robots.txt", "/manifest.json"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("aifya_access_token")?.value;

  const isProtectedRoute = PROTECTED_ROUTES.some((route) => pathname.startsWith(route));
  const isAuthRoute = AUTH_ROUTES.some((route) => pathname.startsWith(route));

  // For protected routes without cookie: redirect to login with return URL
  if (isProtectedRoute && !token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // If logged in and trying to access login page, redirect to home
  if (isAuthRoute && token) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // Add security headers to all responses
  const response = NextResponse.next();
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-DNS-Prefetch-Control", "off");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(self), geolocation=()");

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
