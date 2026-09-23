"use client";

import { useTranslations } from "next-intl";
import { ArrowRight, Clock } from "lucide-react";
import { Link } from "@/i18n/routing";
import { cn } from "@/lib/utils";

/**
 * Quick action link card used across all role home screens.
 *
 * @param href - Destination URL
 * @param icon - Lucide icon component
 * @param label - Action label
 * @param color - Icon background/text color classes
 * @returns Quick action card
 */
export function QuickAction({
  href,
  icon: Icon,
  label,
  color,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  color: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-all duration-200 hover:shadow-[var(--shadow-card-hover)] hover:border-primary/20"
    >
      <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg", color)}>
        <Icon className="h-5 w-5" />
      </div>
      <span className="flex-1 text-sm font-medium text-foreground">{label}</span>
      <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

/**
 * Greeting header shared by every home screen: localized time-of-day
 * greeting, the signed-in user's name, and today's date.
 *
 * @param name - Signed-in user's display name
 * @param subtitle - Localized subtitle line
 * @returns Home page header
 */
export function HomeHeader({
  name,
  subtitle,
}: {
  name: string | null | undefined;
  subtitle: string;
}) {
  const t = useTranslations("home");
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? t("goodMorning") : hour < 17 ? t("goodAfternoon") : t("goodEvening");

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          {greeting}
          {name ? (
            <>
              , <span className="text-gradient">{name}</span>
            </>
          ) : null}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
      </div>
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Clock className="h-3.5 w-3.5" />
        {new Date().toLocaleDateString("en-KE", {
          weekday: "long",
          year: "numeric",
          month: "long",
          day: "numeric",
          timeZone: "Africa/Nairobi",
        })}
      </div>
    </div>
  );
}

/**
 * Resolve which home screen a user's roles map to.
 * Managers keep the executive dashboard; clinical and front-office
 * staff land on their queue/worklist.
 *
 * @param roles - Roles from the JWT/session
 * @returns Home screen key
 */
export function pickHomeRole(
  roles: string[]
): "executive" | "clinician" | "pharmacy" | "lab" | "reception" {
  const has = (r: string): boolean => roles.includes(r);
  if (has("admin") || has("facility_admin")) return "executive";
  if (has("doctor") || has("nurse") || has("midwife") || has("clinical_officer"))
    return "clinician";
  if (has("pharmacist")) return "pharmacy";
  if (has("lab_tech")) return "lab";
  if (has("records") || has("receptionist")) return "reception";
  return "executive";
}
