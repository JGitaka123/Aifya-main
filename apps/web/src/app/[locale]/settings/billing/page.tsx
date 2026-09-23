"use client";

import { useTranslations } from "next-intl";
import {
  Check,
  CreditCard,
  Crown,
  Shield,
  Sparkles,
  Star,
  Zap,
} from "lucide-react";
import { useLicenseContext } from "@/components/licensing/LicenseProvider";
import { useMPesaStatus } from "@/hooks/useMPesa";
import { cn } from "@/lib/utils";

interface PlanFeature {
  text: string;
  included: boolean;
}

interface PlanCard {
  tier: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bgColor: string;
  borderColor: string;
  monthlyKES: number;
  annualKES: number;
  maxUsers: number;
  maxPatients: string;
  features: PlanFeature[];
}

/**
 * Formats KES amount from cents to display string.
 *
 * @param cents - Amount in KES cents
 * @returns Formatted KES string
 */
function formatKES(cents: number): string {
  if (cents === 0) return "Free";
  return `KES ${(cents / 100).toLocaleString("en-KE")}`;
}

/** Environment variables the API reads to reach Safaricom Daraja. */
const MPESA_SETUP_VARIABLES: readonly string[] = [
  "MPESA_CONSUMER_KEY",
  "MPESA_CONSUMER_SECRET",
  "MPESA_SHORTCODE",
  "MPESA_PASSKEY",
  "MPESA_CALLBACK_URL",
  "MPESA_ENVIRONMENT",
];

/**
 * Billing & upgrade page — shows current plan, tier comparison, and upgrade path.
 * Linked from sidebar upgrade prompt and locked module icons.
 *
 * @returns Billing page component
 */
export default function BillingPage() {
  const t = useTranslations("settings.billing");
  const { tier: currentTier, license, daysRemaining, inGracePeriod } = useLicenseContext();
  const mpesa = useMPesaStatus();

  const plans: PlanCard[] = [
    {
      tier: "community",
      icon: Shield,
      color: "text-gray-600 dark:text-gray-400",
      bgColor: "bg-gray-50 dark:bg-gray-900",
      borderColor: "border-gray-200 dark:border-gray-800",
      monthlyKES: 0,
      annualKES: 0,
      maxUsers: 5,
      maxPatients: "500",
      features: [
        { text: t("features.patients"), included: true },
        { text: t("features.opd"), included: true },
        { text: t("features.billing"), included: true },
        { text: t("features.offline"), included: true },
        { text: t("features.ipd"), included: false },
        { text: t("features.pharmacy"), included: false },
        { text: t("features.laboratory"), included: false },
        { text: t("features.ai"), included: false },
        { text: t("features.trials"), included: false },
      ],
    },
    {
      tier: "professional",
      icon: Star,
      color: "text-blue-600 dark:text-blue-400",
      bgColor: "bg-blue-50 dark:bg-blue-950/30",
      borderColor: "border-blue-200 dark:border-blue-800",
      monthlyKES: 25_000_00,
      annualKES: 250_000_00,
      maxUsers: 50,
      maxPatients: "50,000",
      features: [
        { text: t("features.patients"), included: true },
        { text: t("features.opd"), included: true },
        { text: t("features.billing"), included: true },
        { text: t("features.offline"), included: true },
        { text: t("features.ipd"), included: true },
        { text: t("features.pharmacy"), included: true },
        { text: t("features.laboratory"), included: true },
        { text: t("features.ai"), included: false },
        { text: t("features.trials"), included: false },
      ],
    },
    {
      tier: "enterprise",
      icon: Crown,
      color: "text-purple-600 dark:text-purple-400",
      bgColor: "bg-purple-50 dark:bg-purple-950/30",
      borderColor: "border-purple-200 dark:border-purple-800",
      monthlyKES: 150_000_00,
      annualKES: 1_500_000_00,
      maxUsers: 500,
      maxPatients: "500,000",
      features: [
        { text: t("features.patients"), included: true },
        { text: t("features.opd"), included: true },
        { text: t("features.billing"), included: true },
        { text: t("features.offline"), included: true },
        { text: t("features.ipd"), included: true },
        { text: t("features.pharmacy"), included: true },
        { text: t("features.laboratory"), included: true },
        { text: t("features.ai"), included: true },
        { text: t("features.trials"), included: true },
      ],
    },
    {
      tier: "government",
      icon: Zap,
      color: "text-green-600 dark:text-green-400",
      bgColor: "bg-green-50 dark:bg-green-950/30",
      borderColor: "border-green-200 dark:border-green-800",
      monthlyKES: 0,
      annualKES: 0,
      maxUsers: 10_000,
      maxPatients: "5,000,000",
      features: [
        { text: t("features.patients"), included: true },
        { text: t("features.opd"), included: true },
        { text: t("features.billing"), included: true },
        { text: t("features.offline"), included: true },
        { text: t("features.ipd"), included: true },
        { text: t("features.pharmacy"), included: true },
        { text: t("features.laboratory"), included: true },
        { text: t("features.ai"), included: true },
        { text: t("features.trials"), included: true },
      ],
    },
  ];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Current plan banner */}
      <div className="flex items-center gap-4 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <CreditCard className="h-6 w-6 text-blue-600 dark:text-blue-400" />
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">{t("currentPlan")}</p>
          <p className="text-lg font-bold capitalize text-foreground">{currentTier}</p>
        </div>
        {daysRemaining !== null && (
          <div className="text-right">
            <p className={cn(
              "text-sm font-medium",
              daysRemaining <= 7 ? "text-red-600 dark:text-red-400" :
              daysRemaining <= 30 ? "text-amber-600 dark:text-amber-400" :
              "text-muted-foreground",
            )}>
              {inGracePeriod
                ? t("expired")
                : t("daysLeft", { days: daysRemaining })}
            </p>
            {license?.expires_at && (
              <p className="text-xs text-muted-foreground">
                {t("expiresOn", { date: new Date(license.expires_at).toLocaleDateString() })}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Plan comparison cards */}
      <div className="grid gap-6 lg:grid-cols-4">
        {plans.map((plan) => {
          const isCurrent = plan.tier === currentTier;
          const isGovernment = plan.tier === "government";

          return (
            <div
              key={plan.tier}
              className={cn(
                "relative flex flex-col rounded-xl border-2 p-5 transition-all",
                isCurrent
                  ? "border-blue-500 shadow-lg dark:border-blue-400"
                  : plan.borderColor,
                plan.bgColor,
              )}
            >
              {isCurrent && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-3 py-0.5 text-xs font-bold text-white">
                  {t("currentLabel")}
                </div>
              )}

              {/* Plan header */}
              <div className="flex items-center gap-2">
                <plan.icon className={cn("h-5 w-5", plan.color)} />
                <h3 className="text-lg font-bold capitalize text-foreground">
                  {plan.tier}
                </h3>
              </div>

              {/* Pricing */}
              <div className="mt-3">
                {isGovernment ? (
                  <p className="text-2xl font-bold text-foreground">{t("customPricing")}</p>
                ) : (
                  <>
                    <p className="text-2xl font-bold text-foreground">
                      {formatKES(plan.monthlyKES)}
                      {plan.monthlyKES > 0 && (
                        <span className="text-sm font-normal text-muted-foreground">
                          /{t("month")}
                        </span>
                      )}
                    </p>
                    {plan.annualKES > 0 && (
                      <p className="text-xs text-muted-foreground">
                        {formatKES(plan.annualKES)}/{t("year")}
                      </p>
                    )}
                  </>
                )}
              </div>

              {/* Limits */}
              <div className="mt-3 space-y-1 border-t border-border pt-3">
                <p className="text-xs text-muted-foreground">
                  {t("maxUsers", { count: plan.maxUsers.toLocaleString() })}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("maxPatients", { count: plan.maxPatients })}
                </p>
              </div>

              {/* Features */}
              <ul className="mt-3 flex-1 space-y-1.5 border-t border-border pt-3">
                {plan.features.map((f) => (
                  <li key={f.text} className="flex items-center gap-2 text-xs">
                    {f.included ? (
                      <Check className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                    ) : (
                      <span className="h-3.5 w-3.5 text-center text-muted-foreground/40">
                        —
                      </span>
                    )}
                    <span
                      className={cn(
                        f.included
                          ? "text-foreground"
                          : "text-muted-foreground/50",
                      )}
                    >
                      {f.text}
                    </span>
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <div className="mt-4">
                {isCurrent ? (
                  <div className="rounded-lg bg-muted px-4 py-2 text-center text-sm font-medium text-muted-foreground">
                    {t("currentPlanButton")}
                  </div>
                ) : isGovernment ? (
                  <button className="w-full rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700">
                    {t("contactSales")}
                  </button>
                ) : (
                  <button className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700">
                    {plan.tier === "community" ? t("downgrade") : (
                      <>
                        <Sparkles className="mr-1 inline h-3.5 w-3.5" />
                        {t("upgradeTo", { tier: plan.tier })}
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* M-Pesa payment info */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h2 className="text-lg font-semibold text-foreground">{t("paymentMethods")}</h2>
        <div className="mt-3 flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-100 dark:bg-green-950">
            <span className="text-lg font-bold text-green-700 dark:text-green-300">M</span>
          </div>
          <div>
            <p className="font-medium text-foreground">{t("mpesa")}</p>
            <p className="text-xs text-muted-foreground">{t("mpesaDescription")}</p>
          </div>
        </div>

        {/* Daraja credentials */}
        <div className="mt-5 border-t border-border pt-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-medium text-foreground">{t("mpesaSetup")}</h3>
            <span
              className={cn(
                "rounded-full px-2.5 py-1 text-xs font-medium",
                mpesa.data?.configured
                  ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
              )}
            >
              {mpesa.isLoading
                ? t("mpesaChecking")
                : mpesa.data?.configured
                  ? t("mpesaConfigured")
                  : t("mpesaNotConfigured")}
            </span>
          </div>

          {mpesa.data?.configured && (
            <dl className="mt-3 grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted-foreground">
                  {t("mpesaEnvironmentLabel")}
                </dt>
                <dd className="text-sm font-medium text-foreground">
                  {mpesa.data.environment}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">
                  {t("mpesaShortcodeLabel")}
                </dt>
                <dd className="text-sm font-medium text-foreground">
                  {mpesa.data.shortcode}
                </dd>
              </div>
            </dl>
          )}

          <p className="mt-3 text-xs text-muted-foreground">
            {t("mpesaSetupHint")}
          </p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {MPESA_SETUP_VARIABLES.map((name) => (
              <li key={name}>
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs text-foreground">
                  {name}
                </code>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
