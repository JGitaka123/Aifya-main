"use client";

import { useTranslations } from "next-intl";
import type { ProviderWorkStatus } from "@aifya/shared";

/** Background and text colour per effective work status. */
const STATUS_BADGE: Record<ProviderWorkStatus, string> = {
  available:
    "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  busy: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  on_leave: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  off_duty:
    "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  unavailable: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/** Dot colour per effective work status, matching the patient picker. */
const STATUS_DOT: Record<ProviderWorkStatus, string> = {
  available: "bg-green-500",
  busy: "bg-amber-500",
  on_leave: "bg-blue-500",
  off_duty: "bg-slate-400",
  unavailable: "bg-red-500",
};

/**
 * The live working availability of one clinician.
 *
 * This is the effective status the patient picker would use right now -
 * approved leave, an open consultation and today's roster already folded in -
 * so the badge on a profile cannot promise availability the picker denies.
 *
 * @param props.status - Effective work status from the availability API
 * @returns A coloured status pill
 */
export function WorkStatusBadge({ status }: { status: ProviderWorkStatus }) {
  const t = useTranslations("availability");
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_BADGE[status]}`}
    >
      <span className={`h-2 w-2 rounded-full ${STATUS_DOT[status]}`} />
      {t(`status_${status}`)}
    </span>
  );
}