"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  Users,
  Wallet,
  Receipt,
  Banknote,
  CalendarPlus,
  FileText,
  ListChecks,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Link } from "@/i18n/routing";
import {
  usePayrollRuns,
  useHeadcountReport,
  useCostTrend,
  useCreatePayrollRun,
} from "@/hooks/usePayroll";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { PayrollStatusBadge } from "@/components/payroll/PayrollStatusBadge";
import { formatKES, formatDate } from "@/lib/utils";

const MONTHS_EN = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/**
 * Payroll Dashboard — KPIs, current month status, recent runs, cost trend.
 *
 * @returns Payroll dashboard page
 */
export default function PayrollDashboardPage() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");

  const now = new Date();
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();

  const { data: runs } = usePayrollRuns({});
  const { data: headcount } = useHeadcountReport();
  const { data: trend } = useCostTrend();
  const createRun = useCreatePayrollRun();

  const sortedRuns = useMemo(() => {
    if (!runs?.items) return [];
    return [...runs.items]
      .sort((a, b) =>
        b.year !== a.year ? b.year - a.year : b.month - a.month,
      )
      .slice(0, 12);
  }, [runs]);

  const latestRun = sortedRuns[0];
  const currentMonthRun = sortedRuns.find(
    (r) => r.month === currentMonth && r.year === currentYear,
  );

  const trendData = useMemo(() => {
    if (!trend?.points) return [];
    return trend.points.map((p) => ({
      label: p.label,
      gross: p.gross / 100,
    }));
  }, [trend]);

  const handleCreateRun = () => {
    if (currentMonthRun) return;
    createRun.mutate({ month: currentMonth, year: currentYear });
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={Wallet}
        title={t("dashboardTitle")}
        subtitle={t("dashboardSubtitle")}
        breadcrumbs={[
          { label: t("hrTitle"), href: "/hr" },
          { label: t("payroll") },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              href="/hr/payroll/runs"
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
            >
              {t("viewRuns")}
            </Link>
            <Link
              href="/hr/payroll/reports"
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
            >
              {t("reports")}
            </Link>
          </div>
        }
      />

      {/* Current month status banner */}
      {currentMonthRun ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <div className="flex items-center gap-3">
            <ListChecks className="h-5 w-5 text-primary" />
            <div>
              <p className="text-sm font-medium text-foreground">
                {t("currentMonthRun", {
                  month: MONTHS_EN[currentMonth - 1],
                  year: currentYear,
                })}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("runDate")}: {formatDate(currentMonthRun.run_date)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <PayrollStatusBadge status={currentMonthRun.status} />
            <Link
              href={`/hr/payroll/runs/${currentMonthRun.id}`}
              className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              {t("viewRun")}
            </Link>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
          <div className="flex items-center gap-3">
            <CalendarPlus className="h-5 w-5 text-amber-700 dark:text-amber-400" />
            <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
              {t("noRunForMonth", {
                month: MONTHS_EN[currentMonth - 1],
                year: currentYear,
              })}
            </p>
          </div>
          <button
            type="button"
            onClick={handleCreateRun}
            disabled={createRun.isPending}
            className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {t("runPayrollFor", { month: MONTHS_EN[currentMonth - 1] })}
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Users}
          label={t("headcount")}
          value={headcount?.total ?? 0}
          color="blue"
        />
        <StatCard
          icon={Wallet}
          label={t("totalGross")}
          value={
            latestRun ? formatKES(latestRun.total_gross * 100) : formatKES(0)
          }
          subtitle={
            latestRun
              ? `${MONTHS_EN[latestRun.month - 1]} ${latestRun.year}`
              : tc("none")
          }
          color="emerald"
        />
        <StatCard
          icon={Receipt}
          label={t("totalPaye")}
          value={
            latestRun ? formatKES(latestRun.total_paye * 100) : formatKES(0)
          }
          color="orange"
        />
        <StatCard
          icon={Banknote}
          label={t("totalNet")}
          value={
            latestRun ? formatKES(latestRun.total_net * 100) : formatKES(0)
          }
          color="green"
        />
      </div>

      {/* Trend chart */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          {t("monthlyCostTrend")}
        </h2>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.1} />
              <XAxis dataKey="label" stroke="currentColor" opacity={0.6} fontSize={12} />
              <YAxis stroke="currentColor" opacity={0.6} fontSize={12} />
              <Tooltip
                formatter={(v: number) => formatKES(v * 100)}
                contentStyle={{
                  backgroundColor: "var(--card)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              />
              <Bar dataKey="gross" fill="#10b981" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent runs */}
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold text-foreground">
            {t("recentRuns")}
          </h2>
          <Link
            href="/hr/payroll/runs"
            className="text-xs font-medium text-primary hover:underline"
          >
            {t("viewAll")}
          </Link>
        </div>
        {sortedRuns.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noRuns")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("period")}</th>
                  <th className="px-4 py-3">{t("runDate")}</th>
                  <th className="px-4 py-3">{t("status")}</th>
                  <th className="px-4 py-3 text-right">{t("totalGross")}</th>
                  <th className="px-4 py-3 text-right">{t("totalNet")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedRuns.map((run) => (
                  <tr key={run.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium text-foreground">
                      <Link
                        href={`/hr/payroll/runs/${run.id}`}
                        className="text-primary hover:underline"
                      >
                        {MONTHS_EN[run.month - 1]} {run.year}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(run.run_date)}
                    </td>
                    <td className="px-4 py-3">
                      <PayrollStatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-foreground">
                      {formatKES(run.total_gross * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-foreground">
                      {formatKES(run.total_net * 100)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Quick actions */}
      <div className="grid gap-3 sm:grid-cols-3">
        <Link
          href="/hr/payroll/runs"
          className="group flex items-center gap-3 rounded-xl border border-border bg-card p-4 hover:border-primary/30"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400">
            <ListChecks className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              {t("viewRuns")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("viewRunsHint")}
            </p>
          </div>
        </Link>
        <Link
          href="/hr/employees"
          className="group flex items-center gap-3 rounded-xl border border-border bg-card p-4 hover:border-primary/30"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400">
            <Users className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              {t("manageEmployees")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("manageEmployeesHint")}
            </p>
          </div>
        </Link>
        <Link
          href="/hr/payroll/reports"
          className="group flex items-center gap-3 rounded-xl border border-border bg-card p-4 hover:border-primary/30"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600 dark:bg-purple-950/50 dark:text-purple-400">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">
              {t("generateP9")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("generateP9Hint")}
            </p>
          </div>
        </Link>
      </div>
    </div>
  );
}
