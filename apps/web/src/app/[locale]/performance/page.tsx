"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bed,
  CalendarDays,
  Clock,
  DollarSign,
  Download,
  HeartPulse,
  Smile,
  Stethoscope,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { StatCard } from "@/components/ui/StatCard";
import { PageHeader } from "@/components/ui/PageHeader";
import {
  type PerformancePeriod,
  useFacilityKPIs,
  useMetricTrend,
  usePeriodComparison,
} from "@/hooks/usePerformance";
import { cn } from "@/lib/utils";

const PERIODS: { value: PerformancePeriod; label: string }[] = [
  { value: "last_7_days", label: "Last 7 days" },
  { value: "last_30_days", label: "Last 30 days" },
  { value: "last_quarter", label: "Last quarter" },
  { value: "last_year", label: "Last year" },
];

/**
 * Hospital Performance dashboard.
 * Displays the 10 facility-wide KPIs with trend deltas vs the prior period
 * and four supporting charts (volume, revenue, occupancy, claim rejection).
 *
 * @returns Performance page component
 */
export default function PerformancePage() {
  const t = useTranslations("performance");
  const [period, setPeriod] = useState<PerformancePeriod>("last_30_days");

  const kpisQuery = useFacilityKPIs(period);
  const compareQuery = usePeriodComparison("last_month");
  const volumeTrend = useMetricTrend("patient_volume", period);
  const revenueTrend = useMetricTrend("revenue", period);
  const occupancyTrend = useMetricTrend("bed_occupancy_rate", period);
  const rejectionTrend = useMetricTrend("claim_rejection_rate", period);

  const k = kpisQuery.data;
  const deltas = compareQuery.data?.delta_pct ?? {};

  /**
   * Delta read for a metric. Some metrics are "lower is better" — we flip the
   * sign for display so that positive trend always means "good news."
   *
   * @param metric - Metric name from the API
   * @returns Signed delta percent for display, or undefined
   */
  const trendOf = (metric: string): number | undefined => {
    const d = deltas[metric];
    if (typeof d !== "number") return undefined;
    const lowerIsBetter = new Set([
      "average_length_of_stay",
      "readmission_rate",
      "claim_rejection_rate",
      "lab_turnaround_time",
      "emergency_response_time",
    ]);
    return lowerIsBetter.has(metric) ? -Math.round(d) : Math.round(d);
  };

  /** Open the browser print dialog for the executive report. */
  const handlePrint = () => {
    if (typeof window !== "undefined") window.print();
  };

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="print:hidden">
        <PageHeader
          icon={BarChart3}
          title={t("title")}
          subtitle={t("subtitle")}
          breadcrumbs={[{ label: t("title") }]}
          actions={
            <>
              <label htmlFor="performance-period" className="sr-only">
                {t("title")}
              </label>
              <select
                id="performance-period"
                value={period}
                onChange={(e) => setPeriod(e.target.value as PerformancePeriod)}
                className="rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm dark:bg-card"
              >
                {PERIODS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handlePrint}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
              >
                <Download className="h-4 w-4" />
                {t("exportReport")}
              </button>
            </>
          }
        />
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <StatCard
          icon={Users}
          label={t("patientVolume")}
          value={k ? k.patient_volume.toFixed(1) : "—"}
          subtitle={t("perDayAvg")}
          trend={trendOf("patient_volume")}
          color="blue"
        />
        <StatCard
          icon={Bed}
          label={t("bedOccupancy")}
          value={k ? `${k.bed_occupancy_rate.toFixed(1)}%` : "—"}
          trend={trendOf("bed_occupancy_rate")}
          color="purple"
        />
        <StatCard
          icon={CalendarDays}
          label={t("avgLengthStay")}
          value={k ? `${k.average_length_of_stay.toFixed(1)} ${t("days")}` : "—"}
          trend={trendOf("average_length_of_stay")}
          color="indigo"
        />
        <StatCard
          icon={Activity}
          label={t("readmissionRate")}
          value={k ? `${k.readmission_rate.toFixed(1)}%` : "—"}
          trend={trendOf("readmission_rate")}
          color="amber"
        />
        <StatCard
          icon={DollarSign}
          label={t("revenuePerPatient")}
          value={k ? `KES ${k.revenue_per_patient.toLocaleString()}` : "—"}
          trend={trendOf("revenue_per_patient")}
          color="green"
        />
        <StatCard
          icon={AlertTriangle}
          label={t("claimRejection")}
          value={k ? `${k.claim_rejection_rate.toFixed(1)}%` : "—"}
          trend={trendOf("claim_rejection_rate")}
          color="rose"
        />
        <StatCard
          icon={Clock}
          label={t("labTurnaround")}
          value={k ? `${k.lab_turnaround_time.toFixed(1)} ${t("hours")}` : "—"}
          trend={trendOf("lab_turnaround_time")}
          color="cyan"
        />
        <StatCard
          icon={HeartPulse}
          label={t("erResponse")}
          value={
            k ? `${k.emergency_response_time.toFixed(1)} ${t("minutes")}` : "—"
          }
          trend={trendOf("emergency_response_time")}
          color="red"
        />
        <StatCard
          icon={Stethoscope}
          label={t("staffAttendance")}
          value={k ? `${k.staff_attendance_rate.toFixed(1)}%` : "—"}
          trend={trendOf("staff_attendance_rate")}
          color="emerald"
        />
        <StatCard
          icon={Smile}
          label={t("patientSatisfaction")}
          value={k ? `${k.patient_satisfaction.toFixed(0)}/100` : "—"}
          color="teal"
        />
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard
          title={t("chartPatientVolume")}
          icon={Users}
          loading={volumeTrend.isLoading}
        >
          <ResponsiveContainer width="100%" height={220}>
            <LineChart
              data={volumeTrend.data?.points ?? []}
              margin={{ top: 5, right: 12, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="bucket" fontSize={11} tickMargin={4} />
              <YAxis fontSize={11} tickMargin={4} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#2563eb"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title={t("chartRevenue")}
          icon={DollarSign}
          loading={revenueTrend.isLoading}
        >
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={revenueTrend.data?.points ?? []}
              margin={{ top: 5, right: 12, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="bucket" fontSize={11} tickMargin={4} />
              <YAxis fontSize={11} tickMargin={4} />
              <Tooltip />
              <Bar dataKey="value" fill="#16a34a" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title={t("chartBedOccupancy")}
          icon={Bed}
          loading={occupancyTrend.isLoading}
        >
          <ResponsiveContainer width="100%" height={220}>
            <LineChart
              data={occupancyTrend.data?.points ?? []}
              margin={{ top: 5, right: 12, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="bucket" fontSize={11} tickMargin={4} />
              <YAxis fontSize={11} tickMargin={4} domain={[0, 100]} />
              <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#9333ea"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title={t("chartClaimRejection")}
          icon={AlertTriangle}
          loading={rejectionTrend.isLoading}
        >
          <ResponsiveContainer width="100%" height={220}>
            <LineChart
              data={rejectionTrend.data?.points ?? []}
              margin={{ top: 5, right: 12, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="bucket" fontSize={11} tickMargin={4} />
              <YAxis fontSize={11} tickMargin={4} />
              <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#e11d48"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}

/**
 * Chart card wrapper.
 *
 * @param title - Card title
 * @param icon - Lucide icon component
 * @param loading - Whether chart data is loading
 * @param children - Recharts container
 * @returns Chart card
 */
function ChartCard({
  title,
  icon: Icon,
  loading,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  loading?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
      <div
        className={cn(
          "transition-opacity",
          loading ? "opacity-40" : "opacity-100",
        )}
      >
        {children}
      </div>
    </div>
  );
}
