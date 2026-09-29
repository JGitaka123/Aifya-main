"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown, Loader2, Shield } from "lucide-react";
import { useRolesMatrix } from "@/hooks/useSettings";
import { cn } from "@/lib/utils";

/**
 * Settings -> Roles & Permissions: read the role-to-permission matrix that
 * actually applies at this facility, including any local overrides.
 *
 * @returns Roles settings page
 */
export default function RolesSettingsPage() {
  const t = useTranslations("settings.roles");
  const matrix = useRolesMatrix();
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const roles = useMemo(() => {
    const all = matrix.data?.roles ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (entry) =>
        entry.role.toLowerCase().includes(q) ||
        entry.permissions.some((permission) => permission.toLowerCase().includes(q)),
    );
  }, [matrix.data, query]);

  return (
    <div className="mx-auto max-w-4xl p-6 lg:p-8">
      <h1 className="mb-1 flex items-center gap-2 text-2xl font-bold text-foreground">
        <Shield className="h-6 w-6 text-primary" />
        {t("title")}
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">{t("description")}</p>

      {matrix.isLoading ? (
        <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("loading")}
        </div>
      ) : matrix.isError ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {t("loadFailed")}
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("searchPlaceholder")}
              className="w-full max-w-sm rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background"
            />
            <span className="text-xs text-muted-foreground">
              {t("roleCount", { count: matrix.data?.roles.length ?? 0 })}
            </span>
            <span className="text-xs text-muted-foreground">
              {t("permissionCount", { count: matrix.data?.total_permissions ?? 0 })}
            </span>
          </div>

          {roles.length === 0 ? (
            <p className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
              {t("noRoles")}
            </p>
          ) : (
            <div className="space-y-2">
              {roles.map((entry) => {
                const open = expanded === entry.role;
                return (
                  <div
                    key={entry.role}
                    className="overflow-hidden rounded-xl border border-border bg-card shadow-[var(--shadow-card)]"
                  >
                    <button
                      type="button"
                      aria-expanded={open}
                      onClick={() => setExpanded(open ? null : entry.role)}
                      className="flex w-full items-center gap-3 px-4 py-3 text-left"
                    >
                      <ChevronDown
                        className={cn(
                          "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                          open && "rotate-180",
                        )}
                      />
                      <span className="flex-1 font-medium capitalize text-foreground">
                        {entry.role.replace(/_/g, " ")}
                      </span>
                      <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                        {t("grantedCount", { count: entry.permissions.length })}
                      </span>
                    </button>
                    {open && (
                      <div className="flex flex-wrap gap-1.5 border-t border-border bg-muted/20 px-4 py-3">
                        {entry.permissions.map((permission) => (
                          <span
                            key={permission}
                            className="rounded-md bg-background px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-border"
                          >
                            {permission}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
