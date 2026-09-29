"use client";

import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";

import { usePermissions } from "@/hooks/usePermissions";
import {
  getDestinationForPath,
  isPathAllowed,
  normalizeNavigationPath,
} from "@/lib/navigation";

/**
 * Refuse a destination the signed-in role does not work in.
 *
 * The sidebar hides a tab the user's role does not own, but hiding is not a
 * control: a typed URL or an old bookmark would still render the page. This
 * wrapper asks the route being rendered the same question the sidebar asks -
 * `isNavigationVisible` - and replaces the page with a 403 panel when the
 * answer is no. The API refuses the same calls again server-side, so this is
 * the readable half of the boundary rather than the whole of it.
 *
 * Only a destination's own page is refused. A record inside a room - a lab
 * result, an imaging report, an appointment, an invoice - is reached from the
 * room that raised it, so it is judged by its permission alone; the API refuses
 * the same call again on the server. A route that matches no destination at all
 * is left to Next.js, and a session that has not reported its roles yet is let
 * through, so a slow sign-in never flashes a refusal at someone who is allowed
 * in.
 *
 * @param props.children - Page content, rendered when the destination is allowed
 * @returns The page, or the access-denied panel
 */
export function DestinationGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { hasPermission, roles } = usePermissions();
  const t = useTranslations("accessDenied");

  const item = getDestinationForPath(pathname);

  if (!item || isPathAllowed(pathname, { roles, hasPermission })) {
    return <>{children}</>;
  }

  return (
    <div
      className="flex min-h-[60vh] items-center justify-center p-6"
      role="alert"
      data-destination={item.key}
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
          <ShieldAlert className="h-6 w-6 text-destructive" aria-hidden="true" />
        </div>
        <p className="mt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {t("code")}
        </p>
        <h1 className="mt-1 text-lg font-semibold text-foreground">
          {t("title")}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("description")}</p>
        <p className="mt-4 font-mono text-xs text-muted-foreground">
          {normalizeNavigationPath(pathname)}
        </p>
      </div>
    </div>
  );
}
