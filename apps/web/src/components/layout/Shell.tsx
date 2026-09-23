"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "./AppShell";
import { useAuth } from "@/components/providers/AuthProvider";

/**
 * Public pages that render without the hospital workspace chrome (sidebar,
 * header, command palette) so the sign-in / registration screens are
 * full-screen branded pages.
 */
const PUBLIC_AUTH_SUFFIXES = ["/login", "/signup", "/auth/callback"];

/**
 * True when pathname is a full-screen auth route (locale-prefixed or bare).
 *
 * @param pathname - Current URL pathname
 * @returns Whether the route renders without workspace chrome
 */
export function isPublicAuthPath(pathname: string): boolean {
  return PUBLIC_AUTH_SUFFIXES.some(
    (suffix) => pathname === suffix || pathname.endsWith(suffix),
  );
}

/**
 * True when pathname is the locale root ("/", "/en", "/sw") that hosts the
 * post-login dashboard.
 *
 * @param pathname - Current URL pathname
 * @returns Whether the route is a locale root
 */
export function isLocaleRoot(pathname: string): boolean {
  return /^\/(?:[a-z]{2}\/?)?$/.test(pathname);
}

/**
 * Route shell: full-screen for auth pages, workspace chrome everywhere else.
 * The locale root stays chrome-free until the session is confirmed, so the
 * dashboard never flashes before an unauthenticated visitor is redirected.
 *
 * @param props.children - Page content
 * @returns Shell wrapper for the current route
 */
export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();
  const isPublicAuth = isPublicAuthPath(pathname);
  const waitingForSession =
    isLocaleRoot(pathname) && (isLoading || !isAuthenticated);

  if (isPublicAuth || waitingForSession) {
    return <>{children}</>;
  }
  return <AppShell>{children}</AppShell>;
}
