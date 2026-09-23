"use client";

import { usePathname } from "next/navigation";

import { HelpBot } from "@/components/HelpBot";
import { useAuth } from "@/components/providers/AuthProvider";
import { OfflineIndicator } from "@/components/ui/OfflineIndicator";
import { isLocaleRoot, isPublicAuthPath } from "./Shell";

/**
 * Workspace-only floating overlays (offline/sync badge + AI help bot).
 * Hidden on the full-screen sign-in / registration pages and while the
 * locale root is still confirming a session.
 *
 * @returns Overlay components, or null on public/auth-loading routes
 */
export function RouteOverlays() {
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();
  const sessionPendingOnRoot =
    isLocaleRoot(pathname) && (isLoading || !isAuthenticated);

  if (isPublicAuthPath(pathname) || sessionPendingOnRoot) {
    return null;
  }

  return (
    <>
      <OfflineIndicator />
      <HelpBot />
    </>
  );
}
