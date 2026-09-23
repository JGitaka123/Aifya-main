"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { BarChart3 } from "lucide-react";
import {
  useGeneralLedger,
  useTrialBalance,
  useProfitLoss,
  useBalanceSheet,
  useCashFlow,
  useARAging,
  useBudgetVsActual,
} from "@/hooks/useFinance";
import { PageHeader } from "@/components/ui/PageHeader";
import { TabGroup } from "@/components/ui/TabGroup";
import { MoneyDisplay } from "@/components/finance/MoneyDisplay";
import { AccountSelect } from "@/components/finance/AccountSelect";
import { PeriodSelect } from "@/components/finance/PeriodSelect";
import {
  DateRangePicker,
  type DateRange,
} from "@/components/finance/DateRangePicker";
import {
  PrintableReport,
  downloadCsv,
} from "@/components/finance/PrintableReport";
import { cn, formatDate } from "@/lib/utils";
import { moneyEquals, toCents } from "@/lib/money";

type ReportTab = "gl" | "tb" | "pl" | "bs" | "cf" | "ar" | "bva";

function asNumber(v: string | number | null | undefined): number {
  if (v == null) return 0;
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : 0;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function startOfMonthIso(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}

/**
 * Reports hub page — General Ledger, Trial Balance, P&L, Balance Sheet,
 * Cash Flow, AR Aging, and Budget vs Actual.
 *
 * @returns Reports page
 */
export default function ReportsPage() {
  const t = useTranslations("finance");
  const [tab, setTab] = useState<ReportTab>("gl");

  const tabs = [
    { key: "gl", label: t("reports.gl") },
    { key: "tb", label: t("reports.tb") },
    { key: "pl", label: t("reports.pl") },
    { key: "bs", label: t("reports.bs") },
    { key: "cf", label: t("reports.cf") },
    { key: "ar", label: t("reports.ar") },
    { key: "bva", label: t("reports.bva") },
  ];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-5 p-6 lg:p-8">
      <PageHeader
        icon={BarChart3}
        title={t("reports.title")}
        breadcrumbs={[
          { label: t("title"), href: "/finance" },
          { label: t("reports.title") },
        ]}
      />

      <TabGroup
        tabs={tabs}
        activeTab={tab}
        onTabChange={(k) => setTab(k as ReportTab)}
        variant="underline"
      />

      <div className="print:p-0">
        {tab === "gl" && <GeneralLedgerTab />}
        {tab === "tb" && <TrialBalanceTab />}
        {tab === "pl" && <ProfitLossTab />}
        {tab === "bs" && <BalanceSheetTab />}
        {tab === "cf" && <CashFlowTab />}
        {tab === "ar" && <ARAgingTab />}
        {tab === "bva" && <BudgetVsActualTab />}
      </div>
    </div>
  );
}

// ── General Ledger ───────────────────────────────────────────────────────

function GeneralLedgerTab() {
  const t = useTranslations("finance");
  const [accountId, setAccountId] = useState("");
  const [range, setRange] = useState<DateRange>({
    start: startOfMonthIso(),
    end: todayIso(),
  });
  const { data, isLoading } = useGeneralLedger(accountId, range.start, range.end);

  const onCsv = () => {
    if (!data) return;
    downloadCsv(
      `general-ledger-${data.account_code}-${range.start}-${range.end}.csv`,
      data.rows.map((r) => ({
        date: r.date,
        reference: r.reference,
        description: r.description,
        debit: r.debit,
        credit: r.credit,
        balance: r.balance,
      })),
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-72">
          <AccountSelect value={accountId} onChange={setAccountId} />
        </div>
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      <PrintableReport
        title={t("reports.gl")}
        subtitle={
          data
            ? `${data.account_code} ${data.account_name} · ${formatDate(range.start)} – ${formatDate(range.end)}`
            : undefined
        }
        onExportCsv={data ? onCsv : undefined}
      >
        {!accountId ? (
          <p className="text-sm text-muted-foreground">{t("selectAccountFirst")}</p>
        ) : isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">{t("noData")}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">{t("date")}</th>
                  <th className="px-3 py-2 text-left">{t("reference")}</th>
                  <th className="px-3 py-2 text-left">{t("description")}</th>
                  <th className="px-3 py-2 text-right">{t("debit")}</th>
                  <th className="px-3 py-2 text-right">{t("credit")}</th>
                  <th className="px-3 py-2 text-right">{t("balance")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr className="bg-muted/10 text-xs italic">
                  <td colSpan={5} className="px-3 py-2 text-muted-foreground">
                    {t("openingBalance")}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay
                      value={data.opening_balance}
                      showCurrency={false}
                      colorize={false}
                      bold
                    />
                  </td>
                </tr>
                {data.rows.map((row, i) => (
                  <tr key={i}>
                    <td className="px-3 py-2 text-foreground">{formatDate(row.date)}</td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {row.reference}
                    </td>
                    <td className="px-3 py-2 text-foreground">{row.description}</td>
                    <td className="px-3 py-2 text-right">
                      <MoneyDisplay value={row.debit} showCurrency={false} colorize={false} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <MoneyDisplay value={row.credit} showCurrency={false} colorize={false} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <MoneyDisplay value={row.balance} showCurrency={false} colorize={false} />
                    </td>
                  </tr>
                ))}
                <tr className="bg-muted/10 font-semibold">
                  <td colSpan={5} className="px-3 py-2 text-foreground">
                    {t("closingBalance")}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay
                      value={data.closing_balance}
                      showCurrency={false}
                      colorize={false}
                      bold
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </PrintableReport>
    </div>
  );
}

// ── Trial Balance ───────────────────────────────────────────────────────

function TrialBalanceTab() {
  const t = useTranslations("finance");
  const [periodId, setPeriodId] = useState("");
  const { data, isLoading } = useTrialBalance(periodId);

  const totalsBalance = data && moneyEquals(data.total_debit, data.total_credit);

  const onCsv = () => {
    if (!data) return;
    downloadCsv(
      `trial-balance-${periodId}.csv`,
      data.rows.map((r) => ({
        code: r.account_code,
        name: r.account_name,
        debit: r.debit_total,
        credit: r.credit_total,
        balance: r.balance,
      })),
    );
  };

  return (
    <div className="space-y-4">
      <div className="w-72">
        <PeriodSelect value={periodId} onChange={setPeriodId} />
      </div>
      <PrintableReport
        title={t("reports.tb")}
        onExportCsv={data ? onCsv : undefined}
      >
        {!periodId ? (
          <p className="text-sm text-muted-foreground">{t("selectPeriodFirst")}</p>
        ) : isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">{t("noData")}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">{t("code")}</th>
                  <th className="px-3 py-2 text-left">{t("account")}</th>
                  <th className="px-3 py-2 text-right">{t("debit")}</th>
                  <th className="px-3 py-2 text-right">{t("credit")}</th>
                  <th className="px-3 py-2 text-right">{t("balance")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.rows.map((row, i) => (
                  <tr key={i}>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {row.account_code}
                    </td>
                    <td className="px-3 py-2 text-foreground">{row.account_name}</td>
                    <td className="px-3 py-2 text-right">
                      <MoneyDisplay value={row.debit_total} showCurrency={false} colorize={false} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <MoneyDisplay value={row.credit_total} showCurrency={false} colorize={false} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <MoneyDisplay value={row.balance} showCurrency={false} colorize={false} />
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot
                className={cn(
                  "border-t-2 font-bold",
                  totalsBalance ? "border-green-500" : "border-red-500",
                )}
              >
                <tr>
                  <td colSpan={2} className="px-3 py-2 text-foreground">
                    {t("total")}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay value={data.total_debit} showCurrency={false} colorize={false} bold />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay value={data.total_credit} showCurrency={false} colorize={false} bold />
                  </td>
                  <td
                    className={cn(
                      "px-3 py-2 text-right",
                      totalsBalance ? "text-green-600" : "text-red-600",
                    )}
                  >
                    {totalsBalance ? t("balanced") : t("imbalanced")}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </PrintableReport>
    </div>
  );
}

// ── Profit & Loss ───────────────────────────────────────────────────────

function ProfitLossTab() {
  const t = useTranslations("finance");
  const [range, setRange] = useState<DateRange>({
    start: startOfMonthIso(),
    end: todayIso(),
  });
  const [departmentId, setDepartmentId] = useState("");
  const { data, isLoading } = useProfitLoss(range.start, range.end, departmentId || undefined);

  const onCsv = () => {
    if (!data) return;
    const rows = [
      ...data.income.map((r) => ({ section: "Income", code: r.account_code, name: r.account_name, amount: r.amount })),
      ...data.expenses.map((r) => ({ section: "Expense", code: r.account_code, name: r.account_name, amount: r.amount })),
    ];
    downloadCsv(`pl-${range.start}-${range.end}.csv`, rows);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <DateRangePicker value={range} onChange={setRange} />
        <input
          type="text"
          value={departmentId}
          onChange={(e) => setDepartmentId(e.target.value)}
          placeholder={t("departmentId")}
          className="rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground"
        />
      </div>
      <PrintableReport
        title={t("reports.pl")}
        subtitle={`${formatDate(range.start)} – ${formatDate(range.end)}`}
        onExportCsv={data ? onCsv : undefined}
      >
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">{t("noData")}</p>
        ) : (
          <div className="space-y-4">
            <PnLSection title={t("income")} rows={data.income} total={data.total_income} />
            <PnLSection title={t("expenses")} rows={data.expenses} total={data.total_expenses} />
            <div
              className={cn(
                "flex items-center justify-between rounded-lg border-2 px-4 py-3 text-base font-bold",
                asNumber(data.net_profit) >= 0
                  ? "border-green-500 bg-green-50 dark:bg-green-950/30"
                  : "border-red-500 bg-red-50 dark:bg-red-950/30",
              )}
            >
              <span className="text-foreground">{t("netProfit")}</span>
              <MoneyDisplay value={data.net_profit} bold />
            </div>
          </div>
        )}
      </PrintableReport>
    </div>
  );
}

function PnLSection({
  title,
  rows,
  total,
}: {
  title: string;
  rows: { account_code: string; account_name: string; amount: string | number }[];
  total: string | number;
}) {
  return (
    <div className="rounded-lg border border-border">
      <div className="bg-muted/30 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </div>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-border">
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{r.account_code}</td>
              <td className="px-3 py-2 text-foreground">{r.account_name}</td>
              <td className="px-3 py-2 text-right">
                <MoneyDisplay value={r.amount} showCurrency={false} colorize={false} />
              </td>
            </tr>
          ))}
          <tr className="bg-muted/20 font-semibold">
            <td colSpan={2} className="px-3 py-2 text-foreground">
              Total
            </td>
            <td className="px-3 py-2 text-right">
              <MoneyDisplay value={total} showCurrency={false} colorize={false} bold />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ── Balance Sheet ───────────────────────────────────────────────────────

function BalanceSheetTab() {
  const t = useTranslations("finance");
  const [asOf, setAsOf] = useState(todayIso());
  const { data, isLoading } = useBalanceSheet(asOf);

  const balanced =
    data &&
    toCents(data.total_assets) ===
      toCents(data.total_liabilities) + toCents(data.total_equity);

  const onCsv = () => {
    if (!data) return;
    const rows = [
      ...data.assets.map((r) => ({ section: "Asset", code: r.account_code, name: r.account_name, amount: r.amount })),
      ...data.liabilities.map((r) => ({ section: "Liability", code: r.account_code, name: r.account_name, amount: r.amount })),
      ...data.equity.map((r) => ({ section: "Equity", code: r.account_code, name: r.account_name, amount: r.amount })),
    ];
    downloadCsv(`balance-sheet-${asOf}.csv`, rows);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-foreground">{t("asOf")}</label>
        <input
          type="date"
          value={asOf}
          onChange={(e) => setAsOf(e.target.value)}
          className="rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground"
        />
      </div>
      <PrintableReport
        title={t("reports.bs")}
        subtitle={formatDate(asOf)}
        onExportCsv={data ? onCsv : undefined}
      >
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">{t("noData")}</p>
        ) : (
          <div className="space-y-4">
            <PnLSection
              title={t("assets")}
              rows={data.assets}
              total={data.total_assets}
            />
            <PnLSection
              title={t("liabilities")}
              rows={data.liabilities}
              total={data.total_liabilities}
            />
            <PnLSection
              title={t("equity")}
              rows={data.equity}
              total={data.total_equity}
            />
            <div
              className={cn(
                "flex items-center justify-between rounded-lg border-2 px-4 py-3 text-sm font-semibold",
                balanced
                  ? "border-green-500 bg-green-50 dark:bg-green-950/30"
                  : "border-red-500 bg-red-50 dark:bg-red-950/30",
              )}
            >
              <span className="text-foreground">
                {t("assetsEqualEquity")}
              </span>
              <span className={cn(balanced ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400")}>
                {balanced ? t("balancedCheck") : t("imbalanced")}
              </span>
            </div>
          </div>
        )}
      </PrintableReport>
    </div>
  );
}

// ── Cash Flow ──────────────────────────────────────────────────────────

function CashFlowTab() {
  const t = useTranslations("finance");
  const [range, setRange] = useState<DateRange>({
    start: startOfMonthIso(),
    end: todayIso(),
  });
  const [method, setMethod] = useState<"direct" | "indirect">("direct");
  const { data, isLoading } = useCashFlow(range.start, range.end, method);

  const onCsv = () => {
    if (!data) return;
    const rows = [
      ...data.operating.rows.map((r) => ({ section: "Operating", desc: r.account_name, amount: r.amount })),
      ...data.investing.rows.map((r) => ({ section: "Investing", desc: r.account_name, amount: r.amount })),
      ...data.financing.rows.map((r) => ({ section: "Financing", desc: r.account_name, amount: r.amount })),
    ];
    downloadCsv(`cash-flow-${range.start}-${range.end}.csv`, rows);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <DateRangePicker value={range} onChange={setRange} />
        <div className="inline-flex rounded-md border border-input bg-card p-1">
          <button
            onClick={() => setMethod("direct")}
            className={cn(
              "rounded px-3 py-1 text-xs font-medium",
              method === "direct" ? "bg-primary text-primary-foreground" : "text-muted-foreground",
            )}
          >
            {t("direct")}
          </button>
          <button
            onClick={() => setMethod("indirect")}
            className={cn(
              "rounded px-3 py-1 text-xs font-medium",
              method === "indirect" ? "bg-primary text-primary-foreground" : "text-muted-foreground",
            )}
          >
            {t("indirect")}
          </button>
        </div>
      </div>
      <PrintableReport
        title={t("reports.cf")}
        subtitle={`${formatDate(range.start)} – ${formatDate(range.end)}`}
        onExportCsv={data ? onCsv : undefined}
      >
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">{t("noData")}</p>
        ) : (
          <div className="space-y-4">
            <CashFlowSection
              title={t("operating")}
              lines={data.operating.rows}
              total={data.net_operating}
            />
            <CashFlowSection
              title={t("investing")}
              lines={data.investing.rows}
              total={data.net_investing}
            />
            <CashFlowSection
              title={t("financing")}
              lines={data.financing.rows}
              total={data.net_financing}
            />
            <div className="rounded-lg border-2 border-primary/30 bg-primary/5 px-4 py-3 text-base font-bold">
              <div className="flex items-center justify-between">
                <span className="text-foreground">{t("netCashChange")}</span>
                <MoneyDisplay value={data.net_change} bold />
              </div>
              <div className="mt-1 flex items-center justify-between text-xs font-normal text-muted-foreground">
                <span>{t("openingCash")}: <MoneyDisplay value={data.opening_cash} colorize={false} /></span>
                <span>{t("closingCash")}: <MoneyDisplay value={data.closing_cash} colorize={false} /></span>
              </div>
            </div>
          </div>
        )}
      </PrintableReport>
    </div>
  );
}

function CashFlowSection({
  title,
  lines,
  total,
}: {
  title: string;
  lines: { account_name: string; amount: string | number }[];
  total: string | number;
}) {
  const safeLines = Array.isArray(lines) ? lines : [];
  return (
    <div className="rounded-lg border border-border">
      <div className="bg-muted/30 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </div>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-border">
          {safeLines.map((l, i) => (
            <tr key={i}>
              <td className="px-3 py-2 text-foreground">{l.account_name}</td>
              <td className="px-3 py-2 text-right">
                <MoneyDisplay value={l.amount} showCurrency={false} />
              </td>
            </tr>
          ))}
          <tr className="bg-muted/20 font-semibold">
            <td className="px-3 py-2 text-foreground">Net</td>
            <td className="px-3 py-2 text-right">
              <MoneyDisplay value={total} showCurrency={false} bold />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ── AR Aging ───────────────────────────────────────────────────────────

function ARAgingTab() {
  const t = useTranslations("finance");
  const [asOf, setAsOf] = useState(todayIso());
  const { data, isLoading } = useARAging(asOf);

  const cellClass = (val: string | number, threshold: "low" | "med" | "high"): string => {
    const n = asNumber(val);
    if (n <= 0) return "";
    if (threshold === "high") return "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400";
    if (threshold === "med") return "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400";
    return "bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400";
  };

  const onCsv = () => {
    if (!data) return;
    downloadCsv(
      `ar-aging-${asOf}.csv`,
      data.rows.map((r) => ({
        insurer: r.insurer_name,
        current: r.current,
        days_30: r.days_30,
        days_60: r.days_60,
        days_90: r.days_90,
        days_120_plus: r.days_120_plus,
        total: r.total,
      })),
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-foreground">{t("asOf")}</label>
        <input
          type="date"
          value={asOf}
          onChange={(e) => setAsOf(e.target.value)}
          className="rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground"
        />
      </div>
      <PrintableReport
        title={t("reports.ar")}
        subtitle={formatDate(asOf)}
        onExportCsv={data ? onCsv : undefined}
      >
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">{t("noData")}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">{t("insurer")}</th>
                  <th className="px-3 py-2 text-right">{t("current")}</th>
                  <th className="px-3 py-2 text-right">{t("days30")}</th>
                  <th className="px-3 py-2 text-right">{t("days60")}</th>
                  <th className="px-3 py-2 text-right">{t("days90")}</th>
                  <th className="px-3 py-2 text-right">{t("days120Plus")}</th>
                  <th className="px-3 py-2 text-right">{t("total")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.rows.map((row) => (
                  <tr key={row.insurer_id}>
                    <td className="px-3 py-2 text-foreground">{row.insurer_name}</td>
                    <td className={cn("px-3 py-2 text-right", cellClass(row.current, "low"))}>
                      <MoneyDisplay value={row.current} showCurrency={false} colorize={false} />
                    </td>
                    <td className={cn("px-3 py-2 text-right", cellClass(row.days_30, "low"))}>
                      <MoneyDisplay value={row.days_30} showCurrency={false} colorize={false} />
                    </td>
                    <td className={cn("px-3 py-2 text-right", cellClass(row.days_60, "med"))}>
                      <MoneyDisplay value={row.days_60} showCurrency={false} colorize={false} />
                    </td>
                    <td className={cn("px-3 py-2 text-right", cellClass(row.days_90, "med"))}>
                      <MoneyDisplay value={row.days_90} showCurrency={false} colorize={false} />
                    </td>
                    <td className={cn("px-3 py-2 text-right", cellClass(row.days_120_plus, "high"))}>
                      <MoneyDisplay value={row.days_120_plus} showCurrency={false} colorize={false} />
                    </td>
                    <td className="px-3 py-2 text-right font-semibold">
                      <MoneyDisplay value={row.total} showCurrency={false} bold colorize={false} />
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-border bg-muted/20 font-bold">
                <tr>
                  <td className="px-3 py-2 text-foreground">{t("grandTotal")}</td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay value={data.total_current} showCurrency={false} colorize={false} bold />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay value={data.total_30} showCurrency={false} colorize={false} bold />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay value={data.total_60} showCurrency={false} colorize={false} bold />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay value={data.total_90} showCurrency={false} colorize={false} bold />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay value={data.total_120_plus} showCurrency={false} colorize={false} bold />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <MoneyDisplay value={data.grand_total} showCurrency={false} colorize={false} bold />
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </PrintableReport>
    </div>
  );
}

// ── Budget vs Actual ───────────────────────────────────────────────────

function BudgetVsActualTab() {
  const t = useTranslations("finance");
  const [periodId, setPeriodId] = useState("");
  const { data, isLoading } = useBudgetVsActual(periodId);

  const sortedRows = useMemo(() => {
    if (!data?.rows) return [];
    return [...data.rows].sort(
      (a, b) => Math.abs(asNumber(b.variance)) - Math.abs(asNumber(a.variance)),
    );
  }, [data]);

  const onCsv = () => {
    if (!data) return;
    downloadCsv(
      `budget-vs-actual-${periodId}.csv`,
      data.rows.map((r) => ({
        code: r.account_code,
        name: r.account_name,
        department: r.department_name ?? "",
        budget: r.budget,
        actual: r.actual,
        variance: r.variance,
        pct_used: r.pct_used,
      })),
    );
  };

  return (
    <div className="space-y-4">
      <div className="w-72">
        <PeriodSelect value={periodId} onChange={setPeriodId} />
      </div>
      <PrintableReport
        title={t("reports.bva")}
        onExportCsv={data ? onCsv : undefined}
      >
        {!periodId ? (
          <p className="text-sm text-muted-foreground">{t("selectPeriodFirst")}</p>
        ) : isLoading ? (
          <p className="text-sm text-muted-foreground">{t("loading")}</p>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">{t("noData")}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">{t("account")}</th>
                  <th className="px-3 py-2 text-left">{t("department")}</th>
                  <th className="px-3 py-2 text-right">{t("budget")}</th>
                  <th className="px-3 py-2 text-right">{t("actual")}</th>
                  <th className="px-3 py-2 text-right">{t("variance")}</th>
                  <th className="px-3 py-2 text-right">{t("pctUsed")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedRows.map((row) => {
                  const variance = asNumber(row.variance);
                  const pct = asNumber(row.pct_used);
                  const overBudget = variance < 0;
                  const warning = pct >= 90 && pct < 100;
                  return (
                    <tr key={row.account_id}>
                      <td className="px-3 py-2 text-foreground">
                        <span className="font-mono text-xs text-muted-foreground">
                          {row.account_code}
                        </span>{" "}
                        {row.account_name}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {row.department_name ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <MoneyDisplay value={row.budget} showCurrency={false} colorize={false} />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <MoneyDisplay value={row.actual} showCurrency={false} colorize={false} />
                      </td>
                      <td
                        className={cn(
                          "px-3 py-2 text-right font-medium",
                          overBudget && "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400",
                          warning && "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400",
                        )}
                      >
                        <MoneyDisplay value={row.variance} showCurrency={false} />
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-foreground">
                        {pct.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </PrintableReport>
    </div>
  );
}
