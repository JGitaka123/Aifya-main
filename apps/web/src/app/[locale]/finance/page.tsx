"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  Wallet,
  TrendingUp,
  Receipt,
  CreditCard,
  CalendarPlus,
  Calculator,
  RefreshCw,
  Lock,
  AlertTriangle,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Link } from "@/i18n/routing";
import {
  useAccounts,
  useTransactions,
  useProfitLoss,
  useARAging,
  useBudgetVsActual,
  useCashFlow,
  usePeriods,
  useTrialBalance,
} from "@/hooks/useFinance";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton, Skeleton } from "@/components/ui/Skeleton";
import { MoneyDisplay } from "@/components/finance/MoneyDisplay";
import { formatDate } from "@/lib/utils";

/** Convert string|number money into number for math. */
function asNumber(v: string | number | null | undefined): number {
  if (v == null) return 0;
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : 0;
}

/** Format a number for KPI card display (no JSX). */
function formatMoney(v: number): string {
  const sign = v < 0 ? "-" : "";
  const abs = Math.abs(v).toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `KES ${sign}${abs}`;
}

/**
 * Finance dashboard — KPI cards, recent transactions, mini cash flow chart,
 * and budget variance summary.
 *
 * @returns Finance dashboard page
 */
export default function FinanceDashboardPage() {
  const t = useTranslations("finance");

  const today = new Date();
  const sixMonthsAgo = new Date(today.getFullYear(), today.getMonth() - 5, 1);
  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);

  const todayIso = today.toISOString().slice(0, 10);
  const monthStartIso = monthStart.toISOString().slice(0, 10);
  const sixMonthsAgoIso = sixMonthsAgo.toISOString().slice(0, 10);

  const { isLoading: accountsLoading } = useAccounts();
  const { data: trialBalance } = useTrialBalance(undefined, todayIso);
  const { data: transactions } = useTransactions();
  const { data: pnl } = useProfitLoss(monthStartIso, todayIso);
  const { data: arAging } = useARAging(todayIso);
  const { data: cashFlow } = useCashFlow(sixMonthsAgoIso, todayIso, "direct");
  const { data: periods } = usePeriods();
  const openPeriod = Array.isArray(periods)
    ? periods.find((p) => p.status === "open")
    : undefined;
  const { data: budget } = useBudgetVsActual(openPeriod?.id ?? "");

  /** Total cash = sum of asset accounts in cashflow_category=operating with code starting "10". */
  const totalCash = useMemo(() => {
    if (!trialBalance?.rows) return 0;
    return trialBalance.rows
      .filter((r) => r.account_code === "1010" || r.account_code === "1020")
      .reduce((sum, r) => sum + asNumber(r.debit_total) - asNumber(r.credit_total), 0);
  }, [trialBalance]);

  /** AP balance = total payroll statutory liabilities (PAYE + NSSF + SHIF + HL). */
  const apBalance = useMemo(() => {
    if (!trialBalance?.rows) return 0;
    return trialBalance.rows
      .filter((r) => ["2200", "2210", "2220", "2230"].includes(r.account_code))
      .reduce((sum, r) => sum + asNumber(r.credit_total) - asNumber(r.debit_total), 0);
  }, [trialBalance]);

  const netProfit = asNumber(pnl?.net_profit);
  const outstandingAr = asNumber(arAging?.grand_total);

  /** Recent 10 transactions (sorted DESC by date in case backend doesn't). */
  const recentTx = useMemo(() => {
    if (!transactions || !Array.isArray(transactions)) return [];
    return [...transactions]
      .sort((a, b) => (a.date < b.date ? 1 : -1))
      .slice(0, 10);
  }, [transactions]);

  /** Top 5 over-budget rows. */
  const overBudget = useMemo(() => {
    if (!budget?.rows) return [];
    return [...budget.rows]
      .filter((r) => asNumber(r.actual) > asNumber(r.budget))
      .sort((a, b) => asNumber(b.variance) - asNumber(a.variance))
      .slice(0, 5);
  }, [budget]);

  /** Synthesise a 6-month operating cash chart series from cashFlow.operating. */
  const cashSeries = useMemo(() => {
    const rows = cashFlow?.operating;
    if (!Array.isArray(rows) || !rows.length) return [];
    return rows.map((row, i) => ({
      label: String(row.description ?? "").slice(0, 12),
      value: asNumber(row.amount),
      idx: i,
    }));
  }, [cashFlow]);

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <PageHeader
        icon={Wallet}
        title={t("dashboardTitle")}
        subtitle={t("dashboardSubtitle")}
        breadcrumbs={[{ label: t("title") }, { label: t("dashboardTitle") }]}
      />

      {/* KPI cards */}
      {accountsLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCardSkeleton count={4} />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard
            icon={Wallet}
            label={t("totalCash")}
            value={formatMoney(totalCash)}
            color="emerald"
          />
          <StatCard
            icon={TrendingUp}
            label={t("netProfitMtd")}
            value={formatMoney(netProfit)}
            color={netProfit >= 0 ? "green" : "red"}
            subtitle={t("currentPeriod")}
          />
          <StatCard
            icon={Receipt}
            label={t("outstandingAr")}
            value={formatMoney(outstandingAr)}
            color="amber"
            alert={outstandingAr > 0 ? t("requiresFollowUp") : undefined}
          />
          <StatCard
            icon={CreditCard}
            label={t("apBalance")}
            value={formatMoney(apBalance)}
            color="indigo"
          />
        </div>
      )}

      {/* Quick actions */}
      <div className="flex flex-wrap gap-2">
        <Link
          href="/finance/periods"
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
        >
          <CalendarPlus className="h-4 w-4 text-primary" />
          {t("newPeriod")}
        </Link>
        <Link
          href="/finance/assets"
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
        >
          <Calculator className="h-4 w-4 text-primary" />
          {t("runDepreciation")}
        </Link>
        <Link
          href="/finance/reconciliation"
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
        >
          <RefreshCw className="h-4 w-4 text-primary" />
          {t("bankReconcile")}
        </Link>
        <Link
          href="/finance/periods"
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
        >
          <Lock className="h-4 w-4 text-primary" />
          {t("yearEndClose")}
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Mini cash flow chart */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 text-sm font-semibold text-foreground">
            {t("operatingCashFlow6m")}
          </h3>
          {!cashSeries.length ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={cashSeries}>
                <defs>
                  <linearGradient id="cashGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="hsl(160 60% 45%)" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="hsl(160 60% 45%)" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="label" fontSize={11} stroke="currentColor" opacity={0.6} />
                <YAxis fontSize={11} stroke="currentColor" opacity={0.6} />
                <Tooltip
                  contentStyle={{
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="hsl(160 60% 45%)"
                  fill="url(#cashGrad)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Budget variance summary */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            {t("topOverBudget")}
          </h3>
          {!overBudget.length ? (
            <p className="text-sm text-muted-foreground">{t("noBudgetVariance")}</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {overBudget.map((row) => (
                <li
                  key={row.account_id}
                  className="flex items-center justify-between"
                >
                  <span className="truncate text-foreground">
                    {row.account_code} {row.account_name}
                  </span>
                  <MoneyDisplay
                    value={row.variance}
                    showCurrency={false}
                    colorize
                    bold
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Recent transactions */}
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-sm font-semibold text-foreground">
            {t("recentTransactions")}
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2 text-left">{t("date")}</th>
                <th className="px-4 py-2 text-left">{t("reference")}</th>
                <th className="px-4 py-2 text-left">{t("description")}</th>
                <th className="px-4 py-2 text-right">{t("amount")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!recentTx.length ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                    {t("noTransactions")}
                  </td>
                </tr>
              ) : (
                recentTx.map((tx) => (
                  <tr key={tx.id}>
                    <td className="px-4 py-2 text-foreground">{formatDate(tx.date)}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                      {tx.reference_type}
                    </td>
                    <td className="px-4 py-2 text-foreground">{tx.description}</td>
                    <td className="px-4 py-2 text-right">
                      <MoneyDisplay value={tx.amount ?? tx.total_amount} bold />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
