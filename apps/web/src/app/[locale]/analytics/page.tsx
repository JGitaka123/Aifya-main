"use client";

import { useTranslations } from "next-intl";
import {
  BarChart3,
  AlertTriangle,
  Bed,
  DollarSign,
  Package,
  Activity,
  TrendingUp,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton, Skeleton } from "@/components/ui/Skeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAnalyticsDashboard } from "@/hooks/useAnalytics";
import { cn } from "@/lib/utils";
import type { StockoutUrgency, RiskLevel } from "@aifya/shared";

/**
 * Map stockout urgency to StatusBadge variant.
 *
 * @param urgency - Stockout urgency level
 * @returns StatusBadge variant string
 */
function urgencyVariant(
  urgency: StockoutUrgency
): "error" | "warning" | "info" | "success" {
  switch (urgency) {
    case "critical":
      return "error";
    case "high":
      return "warning";
    case "medium":
      return "info";
    case "low":
      return "success";
  }
}

/**
 * Map risk level to a color class for progress bars.
 *
 * @param level - Risk level
 * @returns Tailwind background color class
 */
function riskBarColor(level: RiskLevel): string {
  switch (level) {
    case "critical":
      return "bg-red-500 dark:bg-red-400";
    case "high":
      return "bg-orange-500 dark:bg-orange-400";
    case "medium":
      return "bg-amber-500 dark:bg-amber-400";
    case "low":
      return "bg-green-500 dark:bg-green-400";
  }
}

/**
 * Map risk level to StatusBadge variant.
 *
 * @param level - Risk level
 * @returns StatusBadge variant string
 */
function riskVariant(
  level: RiskLevel
): "error" | "warning" | "info" | "success" {
  switch (level) {
    case "critical":
      return "error";
    case "high":
      return "warning";
    case "medium":
      return "info";
    case "low":
      return "success";
  }
}

/**
 * Format KES cents to a human-readable string (e.g., "KES 1.2M").
 *
 * @param cents - Amount in KES cents
 * @returns Formatted currency string
 */
function formatKES(cents: number): string {
  const amount = cents / 100;
  if (amount >= 1_000_000) {
    return `KES ${(amount / 1_000_000).toFixed(1)}M`;
  }
  if (amount >= 1_000) {
    return `KES ${(amount / 1_000).toFixed(0)}K`;
  }
  return `KES ${amount.toFixed(0)}`;
}

/**
 * Predictive Analytics dashboard page.
 * Displays AI-driven forecasts: bed occupancy, revenue, stockouts, and readmission risks.
 *
 * @returns Analytics dashboard page
 */
export default function AnalyticsPage() {
  const t = useTranslations("analytics");
  const { data: dashboard, isLoading } = useAnalyticsDashboard();

  // Derived summary stats
  const readmissionAlertCount =
    dashboard?.readmission_risks?.filter(
      (r) => r.risk_level === "high" || r.risk_level === "critical"
    ).length ?? 0;

  const avgOccupancy =
    dashboard?.bed_forecasts && dashboard.bed_forecasts.length > 0
      ? Math.round(
          dashboard.bed_forecasts.reduce(
            (sum, b) => sum + b.predicted_occupancy,
            0
          ) / dashboard.bed_forecasts.length
        )
      : 0;

  const criticalStockouts =
    dashboard?.stockout_predictions?.filter(
      (s) => s.urgency === "critical" || s.urgency === "high"
    ).length ?? 0;

  const totalRevenue =
    dashboard?.revenue_forecasts?.reduce(
      (sum, r) => sum + r.predicted_revenue_cents,
      0
    ) ?? 0;

  // Chart data transforms
  const bedChartData =
    dashboard?.bed_forecasts?.map((b) => ({
      date: b.date.slice(5), // "MM-DD"
      predicted: b.predicted_occupancy,
      lower: b.confidence_lower,
      upper: b.confidence_upper,
      current: b.current_occupancy,
    })) ?? [];

  const revenueChartData =
    dashboard?.revenue_forecasts?.map((r) => ({
      period: r.period,
      revenue: Math.round(r.predicted_revenue_cents / 100),
      lower: Math.round(r.confidence_lower / 100),
      upper: Math.round(r.confidence_upper / 100),
    })) ?? [];

  const sortedStockouts = [
    ...(dashboard?.stockout_predictions ?? []),
  ].sort((a, b) => {
    const urgencyOrder: Record<string, number> = {
      critical: 0,
      high: 1,
      medium: 2,
      low: 3,
    };
    return (urgencyOrder[a.urgency] ?? 4) - (urgencyOrder[b.urgency] ?? 4);
  });

  const topRisks = (dashboard?.readmission_risks ?? [])
    .slice()
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, 5);

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <PageHeader
        icon={BarChart3}
        title={t("title")}
        subtitle={t("subtitle")}
        breadcrumbs={[{ label: t("title") }]}
      />

      {/* Summary stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          <StatCardSkeleton count={4} />
        ) : (
          <>
            <StatCard
              icon={AlertTriangle}
              label={t("readmissionAlerts")}
              value={readmissionAlertCount}
              subtitle={t("highRiskPatients")}
              color="red"
            />
            <StatCard
              icon={Bed}
              label={t("avgBedOccupancy")}
              value={`${avgOccupancy}%`}
              subtitle={t("next7Days")}
              color="blue"
            />
            <StatCard
              icon={Package}
              label={t("criticalStockouts")}
              value={criticalStockouts}
              subtitle={t("itemsAtRisk")}
              color="amber"
            />
            <StatCard
              icon={DollarSign}
              label={t("revenueForecast")}
              value={formatKES(totalRevenue)}
              subtitle={t("next3Months")}
              color="green"
            />
          </>
        )}
      </div>

      {/* Main grid: 2 cols on lg, 1 col on mobile */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Bed Occupancy Forecast */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
          <div className="mb-4 flex items-center gap-2">
            <Bed className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <h2 className="text-base font-semibold text-foreground">
              {t("bedOccupancyForecast")}
            </h2>
          </div>
          {isLoading ? (
            <Skeleton className="h-64 w-full rounded-lg" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={bedChartData}>
                <defs>
                  <linearGradient
                    id="occupancyGrad"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="5%"
                      stopColor="var(--color-primary, #3b82f6)"
                      stopOpacity={0.3}
                    />
                    <stop
                      offset="95%"
                      stopColor="var(--color-primary, #3b82f6)"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  className="stroke-border"
                />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 12 }}
                  className="fill-muted-foreground"
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 12 }}
                  className="fill-muted-foreground"
                  tickFormatter={(v: number) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-card, #fff)",
                    border: "1px solid var(--color-border, #e5e7eb)",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) => [`${value}%`, ""]}
                />
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                <Area
                  type="monotone"
                  dataKey="upper"
                  stroke="none"
                  fill="var(--color-primary, #3b82f6)"
                  fillOpacity={0.1}
                  name={t("confidenceUpper")}
                />
                <Area
                  type="monotone"
                  dataKey="lower"
                  stroke="none"
                  fill="var(--color-card, #fff)"
                  fillOpacity={1}
                  name={t("confidenceLower")}
                />
                <Area
                  type="monotone"
                  dataKey="predicted"
                  stroke="var(--color-primary, #3b82f6)"
                  strokeWidth={2}
                  fill="url(#occupancyGrad)"
                  name={t("predicted")}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Revenue Forecast */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
          <div className="mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-green-600 dark:text-green-400" />
            <h2 className="text-base font-semibold text-foreground">
              {t("revenueForecastTitle")}
            </h2>
          </div>
          {isLoading ? (
            <Skeleton className="h-64 w-full rounded-lg" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={revenueChartData}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  className="stroke-border"
                />
                <XAxis
                  dataKey="period"
                  tick={{ fontSize: 12 }}
                  className="fill-muted-foreground"
                />
                <YAxis
                  tick={{ fontSize: 12 }}
                  className="fill-muted-foreground"
                  tickFormatter={(v: number) =>
                    v >= 1_000_000
                      ? `${(v / 1_000_000).toFixed(1)}M`
                      : v >= 1_000
                        ? `${(v / 1_000).toFixed(0)}K`
                        : String(v)
                  }
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-card, #fff)",
                    border: "1px solid var(--color-border, #e5e7eb)",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) => [
                    `KES ${value.toLocaleString()}`,
                    "",
                  ]}
                />
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                <Bar
                  dataKey="lower"
                  fill="var(--color-primary, #3b82f6)"
                  fillOpacity={0.15}
                  name={t("confidenceLower")}
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="revenue"
                  fill="var(--color-primary, #3b82f6)"
                  name={t("predictedRevenue")}
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="upper"
                  fill="var(--color-primary, #3b82f6)"
                  fillOpacity={0.15}
                  name={t("confidenceUpper")}
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Stockout Alerts */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
          <div className="mb-4 flex items-center gap-2">
            <Package className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            <h2 className="text-base font-semibold text-foreground">
              {t("stockoutAlerts")}
            </h2>
          </div>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full rounded-lg" />
              ))}
            </div>
          ) : sortedStockouts.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t("noStockoutAlerts")}
            </p>
          ) : (
            <div className="max-h-[280px] space-y-2 overflow-y-auto">
              {sortedStockouts.map((item) => (
                <div
                  key={item.item_code}
                  className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2.5 dark:bg-muted/10"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {item.item_name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("stockLabel", { stock: item.current_stock })} &middot;{" "}
                      {t("daysToStockout", {
                        days: item.predicted_days_to_stockout,
                      })}
                    </p>
                  </div>
                  <StatusBadge variant={urgencyVariant(item.urgency)} size="xs">
                    {item.urgency}
                  </StatusBadge>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Readmission Risks */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
          <div className="mb-4 flex items-center gap-2">
            <Activity className="h-5 w-5 text-red-600 dark:text-red-400" />
            <h2 className="text-base font-semibold text-foreground">
              {t("readmissionRisks")}
            </h2>
          </div>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full rounded-lg" />
              ))}
            </div>
          ) : topRisks.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t("noReadmissionRisks")}
            </p>
          ) : (
            <div className="space-y-3">
              {topRisks.map((risk) => (
                <div
                  key={risk.patient_id}
                  className="rounded-lg border border-border bg-muted/30 px-3 py-2.5 dark:bg-muted/10"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">
                      {risk.patient_name}
                    </p>
                    <StatusBadge
                      variant={riskVariant(risk.risk_level)}
                      size="xs"
                    >
                      {t(`riskLevel.${risk.risk_level}`)}
                    </StatusBadge>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-2 flex-1 rounded-full bg-muted dark:bg-muted/50">
                      <div
                        className={cn(
                          "h-2 rounded-full transition-all",
                          riskBarColor(risk.risk_level)
                        )}
                        style={{
                          width: `${Math.round(risk.risk_score * 100)}%`,
                        }}
                      />
                    </div>
                    <span className="text-xs font-semibold tabular-nums text-muted-foreground">
                      {Math.round(risk.risk_score * 100)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
