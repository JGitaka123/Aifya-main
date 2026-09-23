"use client";

import { useTranslations } from "next-intl";
import {
  Building2,
  CreditCard,
  Globe,
  Lock,
  Palette,
  Shield,
  Users,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useLicenseContext } from "@/components/licensing/LicenseProvider";
import { cn } from "@/lib/utils";

interface SettingsCard {
  key: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}

/**
 * Settings hub page — links to facility config, billing, users, security, etc.
 *
 * @returns Settings page component
 */
export default function SettingsPage() {
  const t = useTranslations("settings");
  const { tier, daysRemaining, inGracePeriod } = useLicenseContext();

  const cards: SettingsCard[] = [
    { key: "facility", href: "/settings/facility", icon: Building2, color: "text-blue-600 dark:text-blue-400" },
    { key: "billing", href: "/settings/billing", icon: CreditCard, color: "text-purple-600 dark:text-purple-400" },
    { key: "users", href: "/settings/users", icon: Users, color: "text-green-600 dark:text-green-400" },
    { key: "security", href: "/settings/security", icon: Lock, color: "text-red-600 dark:text-red-400" },
    { key: "appearance", href: "/settings/appearance", icon: Palette, color: "text-amber-600 dark:text-amber-400" },
    { key: "language", href: "/settings/language", icon: Globe, color: "text-cyan-600 dark:text-cyan-400" },
    { key: "roles", href: "/settings/roles", icon: Shield, color: "text-indigo-600 dark:text-indigo-400" },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* License status banner */}
      {(inGracePeriod || (daysRemaining !== null && daysRemaining <= 30)) && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
          <CreditCard className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
              {inGracePeriod
                ? t("licenseExpired")
                : t("licenseExpiring", { days: daysRemaining })}
            </p>
            <p className="text-xs text-amber-600 dark:text-amber-400">
              {t("renewPrompt")}
            </p>
          </div>
          <Link
            href="/settings/billing"
            className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700"
          >
            {t("renewNow")}
          </Link>
        </div>
      )}

      {/* Settings cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {cards.map((card) => (
          <Link
            key={card.key}
            href={card.href}
            className="group rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)] transition-all hover:border-blue-300 hover:shadow-md dark:hover:border-blue-700"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted/50">
                <card.icon className={cn("h-5 w-5", card.color)} />
              </div>
              <div>
                <h3 className="font-semibold text-foreground group-hover:text-blue-600 dark:group-hover:text-blue-400">
                  {t(`${card.key}.title`)}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {t(`${card.key}.description`)}
                </p>
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* Current plan summary */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h2 className="text-lg font-semibold text-foreground">{t("currentPlan")}</h2>
        <div className="mt-3 flex items-center gap-4">
          <span className="rounded-lg bg-blue-100 px-3 py-1 text-sm font-bold capitalize text-blue-800 dark:bg-blue-950 dark:text-blue-200">
            {tier}
          </span>
          {daysRemaining !== null && (
            <span className="text-sm text-muted-foreground">
              {t("daysRemaining", { days: daysRemaining })}
            </span>
          )}
          <Link
            href="/settings/billing"
            className="ml-auto text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            {tier === "community" ? t("upgrade") : t("managePlan")}
          </Link>
        </div>
      </div>
    </div>
  );
}
