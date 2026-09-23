"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { ArrowUpCircle, Lock, Sparkles } from "lucide-react";
import type { SubscriptionTier } from "@aifya/shared";
import { cn } from "@/lib/utils";

const TIER_ORDER: SubscriptionTier[] = ["community", "professional", "enterprise", "government"];

const TIER_COLORS: Record<SubscriptionTier, string> = {
  community: "border-gray-300 dark:border-gray-600",
  professional: "border-blue-400 dark:border-blue-600",
  enterprise: "border-purple-400 dark:border-purple-600",
  government: "border-green-400 dark:border-green-600",
};

/**
 * Upgrade prompt shown when a user tries to access a tier-gated feature.
 * Encourages upgrade with clear value proposition.
 *
 * @param module - Module name that's locked
 * @param feature - Feature flag that's locked
 * @param currentTier - User's current subscription tier
 * @returns Upgrade prompt card
 */
export function UpgradePrompt({
  module,
  feature,
  currentTier,
}: {
  module?: string;
  feature?: string;
  currentTier: SubscriptionTier;
}) {
  const t = useTranslations("licensing");

  const nextTier = TIER_ORDER[Math.min(
    TIER_ORDER.indexOf(currentTier) + 1,
    TIER_ORDER.length - 1,
  )];

  const lockedItem = module || feature || "this feature";

  return (
    <div
      className={cn(
        "mx-auto max-w-lg rounded-xl border-2 bg-white p-8 text-center shadow-sm dark:bg-gray-800",
        TIER_COLORS[currentTier]
      )}
    >
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100 dark:bg-gray-700">
        <Lock className="h-8 w-8 text-gray-400 dark:text-gray-500" />
      </div>

      <h2 className="mb-2 text-xl font-bold text-gray-900 dark:text-white">
        {t("upgradeRequired")}
      </h2>

      <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
        {t("upgradeDescription", { feature: lockedItem, tier: nextTier })}
      </p>

      <div className="mb-6 rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
        <div className="flex items-center justify-center gap-2 text-sm text-gray-600 dark:text-gray-300">
          <Sparkles className="h-4 w-4 text-amber-500" />
          <span>{t("currentPlan")}: <strong className="capitalize">{currentTier}</strong></span>
          <ArrowUpCircle className="h-4 w-4 text-blue-500" />
          <span>{t("recommendedPlan")}: <strong className="capitalize">{nextTier}</strong></span>
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
        <Link
          href="/settings/billing"
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
        >
          <ArrowUpCircle className="h-4 w-4" />
          {t("upgradePlan")}
        </Link>

        <Link
          href="/settings/billing#compare"
          className="inline-flex items-center justify-center rounded-lg border border-gray-300 px-6 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
        >
          {t("comparePlans")}
        </Link>
      </div>
    </div>
  );
}

/**
 * Banner shown when license is expiring soon or in grace period.
 *
 * @param daysRemaining - Days until license expires
 * @param inGracePeriod - Whether the license is in grace period
 * @returns Warning/error banner or null
 */
export function LicenseExpiryBanner({
  daysRemaining,
  inGracePeriod,
}: {
  daysRemaining: number | null;
  inGracePeriod: boolean;
}) {
  const t = useTranslations("licensing");

  if (daysRemaining === null || daysRemaining > 30) {
    return null;
  }

  const isUrgent = daysRemaining <= 7 || inGracePeriod;

  return (
    <div
      className={cn(
        "flex items-center justify-between rounded-lg px-4 py-2 text-sm",
        isUrgent
          ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200"
          : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
      )}
    >
      <span>
        {inGracePeriod
          ? t("gracePeriodWarning")
          : t("expiringWarning", { days: daysRemaining })}
      </span>
      <Link
        href="/settings/billing"
        className={cn(
          "rounded-md px-3 py-1 text-xs font-medium",
          isUrgent
            ? "bg-red-600 text-white hover:bg-red-700"
            : "bg-amber-600 text-white hover:bg-amber-700"
        )}
      >
        {t("renewNow")}
      </Link>
    </div>
  );
}
