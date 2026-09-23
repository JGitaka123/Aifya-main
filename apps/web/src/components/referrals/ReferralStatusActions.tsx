"use client";

import { useTranslations } from "next-intl";
import { useUpdateReferralStatus } from "@/hooks/useReferrals";
import type { ReferralStatus } from "@aifya/shared";

/** Allowed next statuses for each referral status. */
const NEXT_STATUSES: Record<string, ReferralStatus[]> = {
  draft: ["sent", "cancelled"],
  sent: ["received", "accepted", "declined", "cancelled"],
  received: ["accepted", "declined", "cancelled"],
  accepted: ["completed", "cancelled"],
  declined: ["sent", "cancelled"],
  completed: [],
  cancelled: ["sent"],
};

interface ReferralStatusActionsProps {
  referralId: string;
  status: string;
}

/**
 * Inline status picker that moves a referral through its workflow.
 *
 * @param props - Referral id and its current status
 * @returns A select of the statuses this referral may move to, or null
 */
export function ReferralStatusActions({ referralId, status }: ReferralStatusActionsProps) {
  const t = useTranslations("referrals");
  const updateStatus = useUpdateReferralStatus(referralId);
  const options = NEXT_STATUSES[status] ?? [];

  if (!options.length) return null;

  return (
    <select
      value=""
      disabled={updateStatus.isPending}
      onChange={(event) => {
        const next = event.target.value;
        if (!next) return;
        updateStatus.mutate({ status: next as ReferralStatus });
      }}
      className="rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground disabled:cursor-not-allowed disabled:opacity-50"
    >
      <option value="">{t("changeStatus")}</option>
      {options.map((option) => (
        <option key={option} value={option}>
          {t(`status.${option}`)}
        </option>
      ))}
    </select>
  );
}