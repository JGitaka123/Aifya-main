"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { useAuth } from "@/components/providers/AuthProvider";
import {
  Users,
  Stethoscope,
  BedDouble,
  CalendarClock,
  FlaskConical,
  Pill,
  Receipt,
  Scan,
  Baby,
  Activity,
  Siren,
  TrendingUp,
  ArrowRight,
  Clock,
} from "lucide-react";
import {
  useFacilityDashboard,
  useDashboardTrends,
  useTopDiagnoses,
} from "@/hooks/useReports";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";

/**
 * Format KES cents to display string.
 *
 * @param cents - Amount in KES cents
 * @returns Formatted string like "KES 1,234"
 */
function formatKES(cents: number): string {
  return `KES ${(cents / 100).toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

/**
 * Sparkline bar chart for 14-day trends.
 *
 * @param data - Array of {date, count} values
 * @param color - Tailwind gradient/bar color
 * @returns Responsive mini chart
 */
function TrendChart({
  data,
  color,
}: {
  data: { date: string; count: number }[];
  color: string;
}) {
  if (!data.length) return null;
  // Always render oldest -> newest so the bars follow a clear timeline.
  const sorted = [...data].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
  );
  const max = Math.max(...sorted.map((d) => d.count), 1);

  return (
    <div className="flex items-end gap-[3px] h-16">
      {sorted.map((d, i) => (
        <div
          key={i}
          className={cn("flex-1 rounded-t-sm transition-all duration-500", color)}
          style={{ height: `${Math.max((d.count / max) * 100, 4)}%` }}
          title={`${d.date}: ${d.count}`}
        />
      ))}
    </div>
  );
}

/**
 * Quick action link card for the dashboard.
 *
 * @param href - Destination URL
 * @param icon - Lucide icon
 * @param label - Action label
 * @param color - Icon color class
 * @returns Quick action card
 */
function QuickAction({
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
      className="group flex items-center gap-3 rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-all duration-200 hover:border-primary/20 hover:shadow-[var(--shadow-card-hover)]"
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
 * Executive dashboard — facility-wide KPIs, trends, quick actions.
 * First screen users see after login. Real-time data.
 *
 * @returns Dashboard page
 */
function DashboardInner() {
  const t = useTranslations("reports");
  const tc = useTranslations("common");
  const tn = useTranslations("nav");
  const locale = useLocale();

  const { data: d, isLoading } = useFacilityDashboard();
  const { data: trends } = useDashboardTrends(14);
  const { data: topDx } = useTopDiagnoses();

  const greeting = tc(getGreetingKey());

  return (
    <div className="mx-auto max-w-[1600px] animate-[fade-in_0.3s_ease-out] space-y-7 p-5 sm:p-6 lg:p-8">
      {/* Welcome header */}
      <div className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="border-l-[3px] border-primary pl-4">
          <h1 className="text-2xl font-bold text-foreground sm:text-3xl">
            {greeting}
          </h1>
          <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">
            {tc("dashboardSubtitle")}
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-[var(--shadow-card)]">
          <Clock className="h-3.5 w-3.5 text-primary" />
          {new Date().toLocaleDateString(locale === "sw" ? "sw-KE" : "en-KE", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
            timeZone: "Africa/Nairobi",
          })}
        </div>
      </div>

      {/* KPI Grid — Row 1 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {isLoading ? (
          <StatCardSkeleton count={6} />
        ) : (
          <>
            <StatCard icon={Users} label={t("totalPatients")} value={d?.total_patients ?? 0} subtitle={t("todayCount", { count: d?.patients_today ?? 0 })} color="blue" />
            <StatCard icon={Stethoscope} label={t("opdVisits")} value={d?.opd_visits_today ?? 0} subtitle={t("monthCount", { count: d?.opd_visits_month ?? 0 })} color="green" />
            <StatCard icon={BedDouble} label={t("activeAdmissions")} value={d?.active_admissions ?? 0} subtitle={`${d?.bed_occupancy_rate ?? 0}% ${t("occupancy")}`} color="purple" alert={d?.bed_occupancy_rate && d.bed_occupancy_rate >= 90 ? t("highOccupancy") : undefined} />
            <StatCard icon={CalendarClock} label={t("appointmentsToday")} value={d?.appointments_today ?? 0} subtitle={t("completedCount", { count: d?.appointments_completed ?? 0 })} color="indigo" />
            <StatCard icon={FlaskConical} label={t("labOrders")} value={d?.lab_orders_today ?? 0} subtitle={t("pendingCount", { count: d?.lab_pending ?? 0 })} color="teal" alert={d?.lab_critical ? `${d.lab_critical} ${t("critical")}` : undefined} />
            <StatCard icon={Pill} label={t("prescriptions")} value={d?.prescriptions_today ?? 0} subtitle={t("dispensedCount", { count: d?.dispensed_today ?? 0 })} color="orange" alert={d?.stock_alerts ? `${d.stock_alerts} ${t("stockAlerts")}` : undefined} />
          </>
        )}
      </div>

      {/* KPI Grid — Row 2: Financial + Specialty */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {isLoading ? (
          <StatCardSkeleton count={5} />
        ) : (
          <>
            <StatCard icon={Receipt} label={t("revenueToday")} value={formatKES(d?.revenue_today ?? 0)} subtitle={`${t("month")}: ${formatKES(d?.revenue_month ?? 0)}`} color="emerald" />
            <StatCard icon={Receipt} label={t("outstanding")} value={formatKES(d?.outstanding_balance ?? 0)} color="red" alert={(d?.outstanding_balance ?? 0) > 0 ? t("collectionsNeeded") : undefined} />
            <StatCard icon={Scan} label={t("imagingToday")} value={d?.imaging_orders_today ?? 0} subtitle={t("pendingReports", { count: d?.imaging_pending_reports ?? 0 })} color="violet" />
            <StatCard icon={Baby} label={t("activeANC")} value={d?.active_anc_profiles ?? 0} subtitle={t("deliveriesMonth", { count: d?.deliveries_month ?? 0 })} color="pink" />
            <StatCard icon={Activity} label={t("immunizations")} value={d?.immunizations_month ?? 0} subtitle={t("thisMonth")} color="cyan" />
          </>
        )}
      </div>

      {/* Middle section: Trends + Top Diagnoses + Quick Actions */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Trends */}
        <div className="rounded-lg border border-border bg-card p-6 shadow-[var(--shadow-card)] lg:col-span-2">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-base font-semibold text-foreground">{t("trends14Days")}</h2>
            <Link href="/reports" className="flex items-center gap-1 text-xs font-medium text-primary hover:underline">
              {t("viewAll")} <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">{t("opdVisits")}</p>
              <TrendChart data={trends?.opd_visits ?? []} color="bg-green-500/80 dark:bg-green-400/80" />
            </div>
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">{t("admissions")}</p>
              <TrendChart data={trends?.admissions ?? []} color="bg-purple-500/80 dark:bg-purple-400/80" />
            </div>
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">{t("revenue")}</p>
              <TrendChart data={trends?.revenue ?? []} color="bg-emerald-500/80 dark:bg-emerald-400/80" />
            </div>
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">{t("labOrders")}</p>
              <TrendChart data={trends?.lab_orders ?? []} color="bg-teal-500/80 dark:bg-teal-400/80" />
            </div>
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">{t("appointments")}</p>
              <TrendChart data={trends?.appointments ?? []} color="bg-indigo-500/80 dark:bg-indigo-400/80" />
            </div>
          </div>
        </div>

        {/* Top Diagnoses */}
        <div className="rounded-lg border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 text-base font-semibold text-foreground">{t("topDiagnoses")}</h2>
          {!topDx?.length ? (
            <p className="text-sm text-muted-foreground">{t("noDiagnoses")}</p>
          ) : (
            <div className="space-y-3">
              {topDx.slice(0, 8).map((dx) => {
                const maxCount = topDx[0]?.count ?? 0;
                const pct = maxCount > 0 ? (dx.count / maxCount) * 100 : 0;
                return (
                  <div key={dx.icd_code}>
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-semibold text-foreground">{dx.icd_code}</span>
                      <span className="tabular-nums text-muted-foreground">{dx.count}</span>
                    </div>
                    <p className="truncate text-[11px] text-muted-foreground">{dx.description}</p>
                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary/60 transition-all duration-700"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="mb-4 text-base font-semibold text-foreground">{tc("quickActions")}</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <QuickAction href="/patients/register" icon={Users} label={tn("registration")} color="bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400" />
          <QuickAction href="/opd" icon={Stethoscope} label={tn("opd")} color="bg-green-50 text-green-600 dark:bg-green-950/50 dark:text-green-400" />
          <QuickAction href="/emergency" icon={Siren} label={tn("emergency")} color="bg-red-50 text-red-600 dark:bg-red-950/50 dark:text-red-400" />
          <QuickAction href="/pharmacy" icon={Pill} label={tn("pharmacy")} color="bg-orange-50 text-orange-600 dark:bg-orange-950/50 dark:text-orange-400" />
          <QuickAction href="/laboratory" icon={FlaskConical} label={tn("laboratory")} color="bg-teal-50 text-teal-600 dark:bg-teal-950/50 dark:text-teal-400" />
          <QuickAction href="/billing" icon={Receipt} label={tn("billing")} color="bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400" />
          <QuickAction href="/appointments/new" icon={CalendarClock} label={tn("appointments")} color="bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400" />
          <QuickAction href="/reports" icon={TrendingUp} label={tn("reports")} color="bg-purple-50 text-purple-600 dark:bg-purple-950/50 dark:text-purple-400" />
        </div>
      </div>
    </div>
  );
}

/**
 * Gate the executive dashboard behind a signed-in session. Users who open the
 * site root without logging in are sent to the full-screen sign-in page so
 * the first thing they see is login/registration - not the dashboard.
 *
 * @returns Dashboard when authenticated, otherwise redirect to /login
 */
function DashboardGate() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <span
          aria-label="Loading"
          className="h-8 w-8 animate-spin rounded-full border-2 border-primary/30 border-t-primary"
        />
      </div>
    );
  }

  return <DashboardInner />;
}

export default function DashboardPage() {
  return <DashboardGate />;
}

/**
 * Get time-of-day greeting.
 *
 * @returns Greeting string
 */
function getGreetingKey(): "greetingMorning" | "greetingAfternoon" | "greetingEvening" {
  const hour = Number(
    new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      hour12: false,
      timeZone: "Africa/Nairobi",
    }).format(new Date()),
  );
  if (hour < 12) return "greetingMorning";
  if (hour < 17) return "greetingAfternoon";
  return "greetingEvening";
}
