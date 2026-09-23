"use client";

import { useTranslations } from "next-intl";
import {
  Users,
  Stethoscope,
  BedDouble,
  Calendar,
  FlaskConical,
  Pill,
  Receipt,
  Scan,
  Baby,
  FileText,
  BarChart3,
  Activity,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useFacilityDashboard,
  useDashboardTrends,
  useTopDiagnoses,
  useReportsSummary,
} from "@/hooks/useReports";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton } from "@/components/ui/Skeleton";

/**
 * Format KES cents to display string.
 *
 * @param cents - Amount in KES cents
 * @returns Formatted string like "KES 1,234.56"
 */
function formatKES(cents: number): string {
  return `KES ${(cents / 100).toLocaleString("en-KE", { minimumFractionDigits: 2 })}`;
}

/**
 * Sparkline-style bar chart for trend data.
 *
 * @param data - Array of count values
 * @param color - Tailwind color class
 * @returns Mini bar chart component
 */
function MiniChart({
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
    <div className="rounded-xl border border-border bg-card p-3 shadow-[var(--shadow-card)]">
      <div className="flex items-end gap-0.5 h-12">
        {sorted.map((d, i) => (
          <div
            key={i}
            className={cn("w-2 rounded-t", color)}
            style={{ height: `${(d.count / max) * 100}%`, minHeight: "2px" }}
            title={`${d.date}: ${d.count}`}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Reports & Analytics Dashboard -- facility-wide KPIs, trends, top diagnoses,
 * and links to report generation.
 *
 * @returns Reports dashboard page
 */
export default function ReportsDashboardPage() {
  const t = useTranslations("reports");

  const { data: dashboard, isLoading } = useFacilityDashboard();
  const { data: trends } = useDashboardTrends(14);
  const { data: topDx } = useTopDiagnoses();
  const { data: reportsSummary } = useReportsSummary();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-8 p-5 sm:p-6 lg:p-8">
        <PageHeader
          icon={BarChart3}
          title={t("title")}
          breadcrumbs={[{ label: t("title") }]}
        />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <StatCardSkeleton count={6} />
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCardSkeleton count={5} />
        </div>
      </div>
    );
  }

  const d = dashboard;

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-8 p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <PageHeader
        icon={BarChart3}
        title={t("title")}
        breadcrumbs={[{ label: t("title") }]}
        actions={
          <>
            <Link
              href="/reports/templates"
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              <FileText className="h-4 w-4" />
              {t("reportTemplates")}
            </Link>
            <Link
              href="/reports/generated"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <BarChart3 className="h-4 w-4" />
              {t("generatedReports")}
            </Link>
          </>
        }
      />

      {/* KPI Cards -- Row 1: Patient & OPD */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard
          icon={Users}
          label={t("totalPatients")}
          value={d?.total_patients ?? 0}
          subtitle={t("todayCount", { count: d?.patients_today ?? 0 })}
          color="blue"
        />
        <StatCard
          icon={Stethoscope}
          label={t("opdVisits")}
          value={d?.opd_visits_today ?? 0}
          subtitle={t("monthCount", { count: d?.opd_visits_month ?? 0 })}
          color="green"
        />
        <StatCard
          icon={BedDouble}
          label={t("activeAdmissions")}
          value={d?.active_admissions ?? 0}
          subtitle={`${d?.bed_occupancy_rate ?? 0}% ${t("occupancy")}`}
          color="purple"
        />
        <StatCard
          icon={Calendar}
          label={t("appointmentsToday")}
          value={d?.appointments_today ?? 0}
          subtitle={t("completedCount", { count: d?.appointments_completed ?? 0 })}
          color="indigo"
        />
        <StatCard
          icon={FlaskConical}
          label={t("labOrders")}
          value={d?.lab_orders_today ?? 0}
          subtitle={t("pendingCount", { count: d?.lab_pending ?? 0 })}
          color="teal"
          alert={d?.lab_critical ? `${d.lab_critical} ${t("critical")}` : undefined}
        />
        <StatCard
          icon={Pill}
          label={t("prescriptions")}
          value={d?.prescriptions_today ?? 0}
          subtitle={t("dispensedCount", { count: d?.dispensed_today ?? 0 })}
          color="orange"
          alert={d?.stock_alerts ? `${d.stock_alerts} ${t("stockAlerts")}` : undefined}
        />
      </div>

      {/* KPI Cards -- Row 2: Financial & Specialty */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          icon={Receipt}
          label={t("revenueToday")}
          value={formatKES(d?.revenue_today ?? 0)}
          subtitle={`${t("month")}: ${formatKES(d?.revenue_month ?? 0)}`}
          color="emerald"
        />
        <StatCard
          icon={Receipt}
          label={t("outstanding")}
          value={formatKES(d?.outstanding_balance ?? 0)}
          color="red"
        />
        <StatCard
          icon={Scan}
          label={t("imagingToday")}
          value={d?.imaging_orders_today ?? 0}
          subtitle={t("pendingReports", { count: d?.imaging_pending_reports ?? 0 })}
          color="violet"
        />
        <StatCard
          icon={Baby}
          label={t("activeANC")}
          value={d?.active_anc_profiles ?? 0}
          subtitle={t("deliveriesMonth", { count: d?.deliveries_month ?? 0 })}
          color="pink"
        />
        <StatCard
          icon={Activity}
          label={t("immunizations")}
          value={d?.immunizations_month ?? 0}
          subtitle={t("thisMonth")}
          color="cyan"
        />
      </div>

      {/* Trends + Top Diagnoses */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Trend Charts */}
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <h2 className="mb-4 text-lg font-semibold text-foreground">
              {t("trends14Days")}
            </h2>
            <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  {t("opdVisits")}
                </p>
                <MiniChart
                  data={trends?.opd_visits ?? []}
                  color="bg-green-500 dark:bg-green-400"
                />
              </div>
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  {t("admissions")}
                </p>
                <MiniChart
                  data={trends?.admissions ?? []}
                  color="bg-purple-500 dark:bg-purple-400"
                />
              </div>
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  {t("revenue")}
                </p>
                <MiniChart
                  data={trends?.revenue ?? []}
                  color="bg-emerald-500 dark:bg-emerald-400"
                />
              </div>
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  {t("labOrders")}
                </p>
                <MiniChart
                  data={trends?.lab_orders ?? []}
                  color="bg-teal-500 dark:bg-teal-400"
                />
              </div>
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  {t("appointments")}
                </p>
                <MiniChart
                  data={trends?.appointments ?? []}
                  color="bg-indigo-500 dark:bg-indigo-400"
                />
              </div>
            </div>
          </div>

          {/* Reports Summary */}
          <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <h2 className="mb-4 text-lg font-semibold text-foreground">
              {t("reportsOverview")}
            </h2>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <p className="text-2xl font-bold text-foreground">
                  {reportsSummary?.total_templates ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("totalTemplates")}
                </p>
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">
                  {reportsSummary?.moh_templates ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("mohTemplates")}
                </p>
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">
                  {reportsSummary?.generated_today ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("generatedToday")}
                </p>
              </div>
              <div>
                <p className="text-2xl font-bold text-foreground">
                  {reportsSummary?.generated_month ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("generatedMonth")}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Top Diagnoses */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("topDiagnoses")}
          </h2>
          {!topDx?.length ? (
            <p className="text-sm text-muted-foreground">
              {t("noDiagnoses")}
            </p>
          ) : (
            <div className="space-y-3">
              {topDx.map((dx) => {
                const maxCount = topDx[0]?.count ?? 1;
                const pct = maxCount > 0 ? (dx.count / maxCount) * 100 : 0;
                return (
                  <div key={dx.icd_code}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-foreground">
                        {dx.icd_code}
                      </span>
                      <span className="text-muted-foreground">
                        {dx.count}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {dx.description}
                    </p>
                    <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
                      <div
                        className="h-1.5 rounded-full bg-primary"
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
    </div>
  );
}
