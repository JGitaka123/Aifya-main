"use client";

import { useTranslations } from "next-intl";
import { formatKES } from "@/lib/utils";
import type { PayrollLineItem } from "@/hooks/usePayroll";

/**
 * Visual gross-to-net breakdown showing earnings, deductions and net pay.
 *
 * @param item - Payroll line item to break down
 * @returns Visual salary breakdown
 */
export function SalaryBreakdown({ item }: { item: PayrollLineItem }) {
  const t = useTranslations("payroll");

  const earnings: { label: string; amount: number }[] = [
    { label: t("basicSalary"), amount: item.basic_salary },
    { label: t("houseAllowance"), amount: item.house_allowance },
    { label: t("transportAllowance"), amount: item.transport_allowance },
    { label: t("otherAllowances"), amount: item.other_allowances },
  ];

  const deductions: { label: string; amount: number }[] = [
    { label: t("nssfEmployee"), amount: item.nssf_employee },
    { label: t("shif"), amount: item.shif },
    { label: t("housingLevy"), amount: item.housing_levy },
    { label: t("paye"), amount: item.paye },
    { label: t("otherDeductions"), amount: item.other_deductions },
  ];

  const grossPct = (n: number) =>
    item.gross_salary > 0 ? (n / item.gross_salary) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Earnings */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          {t("earnings")}
        </h3>
        <div className="space-y-3">
          {earnings.map((row) => (
            <div key={row.label}>
              <div className="flex items-center justify-between text-sm">
                <span className="text-foreground">{row.label}</span>
                <span className="font-medium tabular-nums text-foreground">
                  {formatKES(row.amount * 100)}
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-emerald-500 dark:bg-emerald-400"
                  style={{ width: `${grossPct(row.amount).toFixed(2)}%` }}
                />
              </div>
            </div>
          ))}
          <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-sm font-semibold">
            <span className="text-foreground">{t("grossSalary")}</span>
            <span className="tabular-nums text-foreground">
              {formatKES(item.gross_salary * 100)}
            </span>
          </div>
        </div>
      </div>

      {/* Deductions */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          {t("deductions")}
        </h3>
        <div className="space-y-3">
          {deductions.map((row) => (
            <div key={row.label}>
              <div className="flex items-center justify-between text-sm">
                <span className="text-foreground">{row.label}</span>
                <span className="font-medium tabular-nums text-red-700 dark:text-red-400">
                  -{formatKES(row.amount * 100)}
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-red-500 dark:bg-red-400"
                  style={{ width: `${grossPct(row.amount).toFixed(2)}%` }}
                />
              </div>
            </div>
          ))}
          <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-sm font-semibold">
            <span className="text-foreground">{t("totalDeductions")}</span>
            <span className="tabular-nums text-red-700 dark:text-red-400">
              -{formatKES(item.total_deductions * 100)}
            </span>
          </div>
        </div>
      </div>

      {/* Net */}
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900 dark:bg-emerald-950/30">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
              {t("netSalary")}
            </p>
            <p className="mt-1 text-3xl font-bold tabular-nums text-emerald-800 dark:text-emerald-200">
              {formatKES(item.net_salary * 100)}
            </p>
          </div>
          <div className="text-right text-xs text-emerald-700 dark:text-emerald-300">
            <p>
              {t("netPctOfGross", {
                pct: grossPct(item.net_salary).toFixed(1),
              })}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
