"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Download, AlertTriangle, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { BETA_PUBLIC_ACCESS_ENABLED } from "@/lib/auth/beta";
import type { UpdateCheckResponse } from "@aifya/shared";

const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0";
const CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000; // 6 hours

/**
 * Background update checker — polls for new versions and shows banner.
 * Critical/mandatory updates are non-dismissable.
 *
 * @returns Update banner or null
 */
export function UpdateChecker() {
  const t = useTranslations("licensing");
  const [update, setUpdate] = useState<UpdateCheckResponse | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (BETA_PUBLIC_ACCESS_ENABLED) {
      return;
    }

    const checkForUpdate = async () => {
      try {
        const result = await apiFetch<UpdateCheckResponse>(
          `/api/v1/licensing/update-check?current_version=${APP_VERSION}`,
          { method: "POST" },
        );
        if (result.update_available) {
          setUpdate(result);
        }
      } catch {
        // Silently fail — update check is best-effort
      }
    };

    checkForUpdate();
    const interval = setInterval(checkForUpdate, CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  if (!update || (dismissed && !update.is_mandatory)) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-4 rounded-lg px-4 py-3 text-sm",
        update.is_critical
          ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200"
          : "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200"
      )}
    >
      <div className="flex items-center gap-2">
        {update.is_critical ? (
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
        ) : (
          <Download className="h-4 w-4 flex-shrink-0" />
        )}
        <span>
          <strong>{t("updateAvailable")}:</strong>{" "}
          {update.title ?? `v${update.latest_version}`}
          {update.is_mandatory && (
            <span className="ml-1 rounded bg-red-600 px-1.5 py-0.5 text-xs text-white">
              {t("required")}
            </span>
          )}
        </span>
      </div>

      <div className="flex items-center gap-2">
        {update.changelog && (
          <button
            onClick={() => {
              /* TODO: open changelog modal */
            }}
            className="text-xs underline hover:no-underline"
          >
            {t("viewChangelog")}
          </button>
        )}
        {!update.is_mandatory && (
          <button
            onClick={() => setDismissed(true)}
            className="rounded p-1 hover:bg-black/10 dark:hover:bg-white/10"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
    </div>
  );
}
