"use client";

import type { ComponentType } from "react";
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
  Siren,
  Scissors,
  SmilePlus,
  Package,
  Shield,
  PersonStanding,
  ArrowUpRight,
  Wallet,
  MessageSquare,
  Microscope,
  Gauge,
  Calculator,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useFacilityDashboard,
  useDashboardTrends,
  useTopDiagnoses,
  useReportsSummary,
  useUsageBilling,
} from "@/hooks/useReports";
import { useWardBoardSummary } from "@/hooks/useIPD";
import { useEmergencySummary } from "@/hooks/useEmergency";
import { useTheatreSummary } from "@/hooks/useTheatre";
import { useDentalSummary } from "@/hooks/useDental";
import { useMCHSummary } from "@/hooks/useMCH";
import { useTrialsSummary } from "@/hooks/useClinicalTrials";
import { useRadiologySummary } from "@/hooks/useRadiology";
import { useInventorySummary } from "@/hooks/useInventory";
import { useBillingSummary } from "@/hooks/useBilling";
import { useInsuranceSummary } from "@/hooks/useInsurance";
import { useAppointmentSummary } from "@/hooks/useAppointments";
import { useReferralSummary } from "@/hooks/useReferrals";
import { useHRSummary } from "@/hooks/useHR";
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

      {/* Facility usage billing -- the platform charge for this month */}
      <UsageBillingCallout />

      {/* General module reports -- one card per module tab in the system */}
      <ModuleReportsSection />

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

/**
 * Facility usage billing callout.
 *
 * Aifya charges the hospital per metered patient event (reception
 * registration, emergency registration, inpatient bed-day). This is the
 * month-end figure the hospital has to settle, so it belongs on the reports
 * landing page rather than buried behind a sub-menu.
 *
 * @returns Usage billing summary card
 */
function UsageBillingCallout() {
  const t = useTranslations("reports");
  const { data: usage, isLoading } = useUsageBilling();

  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-emerald-50 p-2 dark:bg-emerald-950/50">
            <Calculator className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              {t("usageBilling.calloutTitle")}
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              {t("usageBilling.calloutBody")}
            </p>
          </div>
        </div>
        <Link
          href="/reports/usage-billing"
          className="inline-flex items-center gap-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          {t("usageBilling.openCalculator")}
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-muted-foreground">
          {t("usageBilling.loading")}
        </p>
      ) : (
        <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {(usage?.lines ?? []).map((line) => (
            <div key={line.key}>
              <dt className="text-xs text-muted-foreground">
                {t(`usageBilling.line_${line.key}`)}
              </dt>
              <dd className="text-xl font-semibold tabular-nums text-foreground">
                {line.quantity.toLocaleString("en-KE")}
              </dd>
            </div>
          ))}
          <div>
            <dt className="text-xs text-muted-foreground">
              {t("usageBilling.totalDue")}
            </dt>
            <dd className="text-xl font-semibold tabular-nums text-foreground">
              {formatKES(usage?.total_cents ?? 0)}
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}

/** Compact KES for dense module cards, e.g. "KES 1.2M". */
function formatKESCompact(cents: number): string {
  const amount = cents / 100;
  if (Math.abs(amount) >= 1_000_000)
    return `KES ${(amount / 1_000_000).toFixed(1)}M`;
  if (Math.abs(amount) >= 1_000) return `KES ${(amount / 1_000).toFixed(0)}k`;
  return `KES ${amount.toFixed(0)}`;
}

interface ModuleMetric {
  label: string;
  value: string | number | undefined;
}

interface ModuleCardSpec {
  key: string;
  title: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  metrics: ModuleMetric[];
  list?: string[];
}

/**
 * One module's report card: live figures, the reports it offers, and a way in.
 *
 * @param card - Module card definition
 * @param openLabel - Localized "open module" call to action
 * @returns Module report card
 */
function ModuleCard({
  card,
  openLabel,
}: {
  card: ModuleCardSpec;
  openLabel: string;
}) {
  const Icon = card.icon;
  return (
    <div className="flex flex-col rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 shrink-0 text-primary" />
        <h3 className="truncate text-sm font-semibold text-foreground">
          {card.title}
        </h3>
      </div>

      {card.metrics.length > 0 && (
        <div className="mt-3 grid grid-cols-3 gap-2">
          {card.metrics.map((metric) => (
            <div key={metric.label} className="min-w-0">
              <p className="truncate text-lg font-semibold tabular-nums text-foreground">
                {metric.value ?? "—"}
              </p>
              <p className="truncate text-[11px] text-muted-foreground">
                {metric.label}
              </p>
            </div>
          ))}
        </div>
      )}

      {card.list && card.list.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-x-2 gap-y-1">
          {card.list.map((item) => (
            <li key={item} className="text-[11px] text-muted-foreground">
              {item}
            </li>
          ))}
        </ul>
      )}

      <Link
        href={card.href}
        className="mt-auto inline-flex items-center gap-1 pt-3 text-xs font-medium text-primary hover:underline"
      >
        {openLabel}
        <ArrowUpRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

/**
 * General reporting hub.
 *
 * Reports & Analytics is the general tab for the whole system, so every module
 * tab gets a card here with its own live figures and a link into the module.
 * Keep this in step with NAV_ITEMS.
 *
 * @returns Module report cards grouped by area
 */
function ModuleReportsSection() {
  const t = useTranslations("reports");
  const tn = useTranslations("nav");
  const tf = useTranslations("finance");
  const tp = useTranslations("payroll");

  const { data: d } = useFacilityDashboard();
  const { data: wards } = useWardBoardSummary();
  const { data: emergency } = useEmergencySummary();
  const { data: theatre } = useTheatreSummary();
  const { data: dental } = useDentalSummary();
  const { data: mch } = useMCHSummary();
  const { data: trials } = useTrialsSummary();
  const { data: radiology } = useRadiologySummary();
  const { data: inventory } = useInventorySummary();
  const { data: billing } = useBillingSummary();
  const { data: insurance } = useInsuranceSummary();
  const { data: appointments } = useAppointmentSummary();
  const { data: referrals } = useReferralSummary();
  const { data: hr } = useHRSummary();
  const { data: reportsSummary } = useReportsSummary();

  const groups: { title: string; cards: ModuleCardSpec[] }[] = [
    {
      title: t("catClinical"),
      cards: [
        {
          key: "opd",
          title: tn("opd"),
          href: "/opd",
          icon: Stethoscope,
          metrics: [
            { label: t("modToday"), value: d?.opd_visits_today },
            { label: t("modThisMonth"), value: d?.opd_visits_month },
            { label: t("prescriptions"), value: d?.prescriptions_today },
          ],
        },
        {
          key: "patients",
          title: tn("patients"),
          href: "/patients",
          icon: Users,
          metrics: [
            { label: t("modTotal"), value: d?.total_patients },
            { label: t("modToday"), value: d?.patients_today },
            { label: t("modThisMonth"), value: d?.patients_this_month },
          ],
        },
        {
          key: "ipd",
          title: tn("ipd"),
          href: "/ipd",
          icon: BedDouble,
          metrics: [
            { label: t("modActive"), value: wards?.active_admissions },
            {
              label: t("modBeds"),
              value: wards ? `${wards.occupied_beds}/${wards.total_beds}` : undefined,
            },
            { label: t("occupancy"), value: wards ? `${wards.occupancy_rate}%` : undefined },
          ],
        },
        {
          key: "emergency",
          title: tn("emergency"),
          href: "/emergency",
          icon: Siren,
          metrics: [
            { label: t("modToday"), value: emergency?.total_today },
            {
              label: t("modAwaitingTriage"),
              value: emergency?.awaiting_triage,
            },
            { label: t("modCritical"), value: emergency?.critical_red },
          ],
        },
        {
          key: "theatre",
          title: tn("theatre"),
          href: "/theatre",
          icon: Scissors,
          metrics: [
            { label: t("modToday"), value: theatre?.scheduled_today },
            { label: t("modCompleted"), value: theatre?.completed_today },
            { label: t("modActive"), value: theatre?.in_use_theatres },
          ],
        },
        {
          key: "dental",
          title: tn("dental"),
          href: "/dental",
          icon: SmilePlus,
          metrics: [
            { label: t("modTotal"), value: dental?.total_patients },
            { label: t("modToday"), value: dental?.today_visits },
            { label: t("modPending"), value: dental?.pending_treatments },
          ],
        },
        {
          key: "mch",
          title: tn("mch"),
          href: "/mch",
          icon: Baby,
          metrics: [
            { label: t("modActive"), value: mch?.active_anc_profiles },
            {
              label: t("modThisMonth"),
              value: mch?.deliveries_this_month,
            },
            {
              label: t("modOverdue"),
              value: mch?.overdue_immunizations,
            },
          ],
        },
      ],
    },
    {
      title: t("catDiagnostics"),
      cards: [
        {
          key: "laboratory",
          title: tn("laboratory"),
          href: "/laboratory",
          icon: FlaskConical,
          metrics: [
            { label: t("modToday"), value: d?.lab_orders_today },
            { label: t("modPending"), value: d?.lab_pending },
            { label: t("modCritical"), value: d?.lab_critical },
          ],
        },
        {
          key: "radiology",
          title: tn("radiology"),
          href: "/radiology",
          icon: Scan,
          metrics: [
            { label: t("modToday"), value: radiology?.total_orders_today },
            { label: t("modPending"), value: radiology?.pending_orders },
            { label: t("modCompleted"), value: radiology?.completed_today },
          ],
        },
        {
          key: "pharmacy",
          title: tn("pharmacy"),
          href: "/pharmacy",
          icon: Pill,
          metrics: [
            { label: t("modToday"), value: d?.prescriptions_today },
            { label: t("modDispensed"), value: d?.dispensed_today },
            { label: t("stockAlerts"), value: d?.stock_alerts },
          ],
        },
        {
          key: "inventory",
          title: tn("inventory"),
          href: "/inventory",
          icon: Package,
          metrics: [
            { label: t("modTotal"), value: inventory?.total_items },
            { label: t("modLowStock"), value: inventory?.low_stock_items },
            {
              label: t("modValue"),
              value: inventory ? formatKESCompact(inventory.total_stock_value) : undefined,
            },
          ],
        },
      ],
    },
    {
      title: t("catFinancial"),
      cards: [
        {
          key: "billing",
          title: tn("billing"),
          href: "/billing",
          icon: Receipt,
          metrics: [
            { label: t("modTotal"), value: billing?.total_invoices },
            {
              label: t("modBilled"),
              value: billing ? formatKESCompact(billing.total_billed_cents) : undefined,
            },
            {
              label: t("outstanding"),
              value: billing ? formatKESCompact(billing.total_outstanding_cents) : undefined,
            },
          ],
        },
        {
          key: "finance",
          title: tn("finance"),
          href: "/finance/reports",
          icon: Wallet,
          metrics: [],
          list: [
            tf("reports.gl"),
            tf("reports.tb"),
            tf("reports.pl"),
            tf("reports.bs"),
            tf("reports.cf"),
            tf("reports.ar"),
            tf("reports.bva"),
          ],
        },
        {
          key: "insurance",
          title: tn("insurance"),
          href: "/insurance",
          icon: Shield,
          metrics: [
            { label: t("modTotal"), value: insurance?.total_claims },
            { label: t("modPending"), value: insurance?.pending_claims },
            {
              label: t("modValue"),
              value: insurance ? formatKESCompact(insurance.total_claim_value) : undefined,
            },
          ],
        },
        {
          key: "payroll",
          title: tn("payroll"),
          href: "/hr/payroll/reports",
          icon: Gauge,
          metrics: [],
          list: [
            tp("p9"),
            tp("payeSchedule"),
            tp("nssfSchedule"),
            tp("shifSchedule"),
            tp("headcount"),
            tp("costTrend"),
            tp("turnover"),
            tp("leaveUtilisation"),
            tp("insurance"),
          ],
        },
      ],
    },
    {
      title: t("catAdministration"),
      cards: [
        {
          key: "appointments",
          title: tn("appointments"),
          href: "/appointments",
          icon: Calendar,
          metrics: [
            { label: t("modToday"), value: appointments?.total_today },
            { label: t("modCheckedIn"), value: appointments?.checked_in },
            { label: t("modNoShow"), value: appointments?.no_show_today },
          ],
        },
        {
          key: "referrals",
          title: tn("referrals"),
          href: "/referrals",
          icon: ArrowUpRight,
          metrics: [
            { label: t("modIncoming"), value: referrals?.incoming },
            { label: t("modOutgoing"), value: referrals?.outgoing },
            { label: t("modPending"), value: referrals?.pending },
          ],
        },
        {
          key: "hr",
          title: tn("hr"),
          href: "/hr",
          icon: PersonStanding,
          metrics: [
            { label: t("modTotal"), value: hr?.total_staff },
            { label: t("modOnDuty"), value: hr?.on_duty_today },
            {
              label: t("modPending"),
              value: hr?.pending_leave_requests,
            },
          ],
        },
        {
          key: "trials",
          title: tn("trials"),
          href: "/trials",
          icon: Microscope,
          metrics: [
            { label: t("modTotal"), value: trials?.total_trials },
            {
              label: t("modRecruiting"),
              value: trials?.recruiting_trials,
            },
            {
              label: t("modEnrolled"),
              value: trials?.enrolled_participants,
            },
          ],
        },
        {
          key: "reportTemplates",
          title: t("reportTemplates"),
          href: "/reports/templates",
          icon: FileText,
          metrics: [
            {
              label: t("modTotal"),
              value: reportsSummary?.total_templates,
            },
            {
              label: t("mohTemplates"),
              value: reportsSummary?.moh_templates,
            },
            {
              label: t("modThisMonth"),
              value: reportsSummary?.generated_month,
            },
          ],
        },
        {
          key: "communications",
          title: tn("communications"),
          href: "/communications",
          icon: MessageSquare,
          metrics: [],
        },
        {
          key: "performance",
          title: tn("performance"),
          href: "/performance",
          icon: Gauge,
          metrics: [],
        },
        {
          key: "analytics",
          title: tn("analytics"),
          href: "/analytics",
          icon: Activity,
          metrics: [],
        },
      ],
    },
  ];

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-foreground">
          {t("moduleReportsTitle")}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("moduleReportsSubtitle")}
        </p>
      </div>

      {groups.map((group) => (
        <div key={group.title} className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {group.title}
          </h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {group.cards.map((card) => (
              <ModuleCard
                key={card.key}
                card={card}
                openLabel={t("modOpenModule")}
              />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
