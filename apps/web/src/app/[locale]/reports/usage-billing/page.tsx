"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  BedDouble,
  Calculator,
  Loader2,
  Printer,
  Receipt,
  Siren,
  UserPlus,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useUsageBilling, useUsageBillingTrend } from "@/hooks/useReports";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { StatCardSkeleton } from "@/components/ui/Skeleton";

/**
 * Icon and colour per patient-day channel, keyed by the API's stable line key.
 * Anything the backend adds later still renders, using the receipt defaults.
 */
const LINE_STYLES: Record<
  string,
  {
    icon: typeof UserPlus;
    color: "blue" | "red" | "purple";
  }
> = {
  reception_registrations: { icon: UserPlus, color: "blue" },
  emergency_registrations: { icon: Siren, color: "red" },
  ipd_bed_days: { icon: BedDouble, color: "purple" },
};

/**
 * The billing month the page opens on.
 *
 * @returns Current month as YYYY-MM
 */
function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

/**
 * Render integer cents as money for display.
 *
 * @param cents - Amount in the currency's minor units
 * @param currency - ISO currency code
 * @returns Formatted amount, e.g. "KES 1,234.00"
 */
function formatMoney(cents: number, currency: string): string {
  return `${currency} ${(cents / 100).toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Turn the operator's rate input into integer cents.
 *
 * An empty box means "use the rate this facility is billed at", and anything
 * that is not a usable amount does the same rather than sending a broken query.
 *
 * @param value - Raw text from the rate input, in whole currency units
 * @returns Rate in cents, or undefined to use the facility's billed rate
 */
function parseRateCents(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const amount = Number(trimmed);
  if (!Number.isFinite(amount) || amount < 0) return undefined;
  return Math.round(amount * 100);
}

/**
 * Facility usage billing: what this hospital owes Aifya for a billing month.
 *
 * Aifya charges the hospital per patient-day: a patient seen at reception, a
 * patient who arrived through emergency, and every day an inpatient spends on
 * a ward. The figures come from the same ledger as the HR Aifya Usage screen,
 * so the two can never quote different usage; the page exists to show the
 * arithmetic line by line, let the reader test a different rate, and give them
 * a month-end figure they can settle.
 *
 * @returns Usage billing calculator page
 */
export default function UsageBillingPage() {
  const t = useTranslations("reports.usageBilling");
  const [month, setMonth] = useState<string>(currentMonth);
  const [rate, setRate] = useState("");

  const rateCents = parseRateCents(rate);
  const report = useUsageBilling(month, rateCents);
  const trend = useUsageBillingTrend(12, month, rateCents);

  const currency = report.data?.currency ?? "KES";
  const lines = report.data?.lines ?? [];
  const trendMonths = trend.data?.months ?? [];

  return (
    <div className="mx-auto max-w-[1200px] animate-[fade-in_0.3s_ease-out] space-y-8 p-5 sm:p-6 lg:p-8">
      <PageHeader
        icon={Calculator}
        title={t("title")}
        subtitle={t("subtitle")}
        breadcrumbs={[
          { label: t("breadcrumbReports"), href: "/reports" },
          { label: t("title") },
        ]}
        actions={
          <>
            <Link
              href="/reports"
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              {t("backToReports")}
            </Link>
            <button
              type="button"
              onClick={() => window.print()}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Printer className="h-4 w-4" />
              {t("print")}
            </button>
          </>
        }
      />

      {/* Inputs -- pick the month, optionally test a different rate */}
      <div className="grid gap-4 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)] sm:grid-cols-2">
        <div>
          <label
            htmlFor="billing-month"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            {t("billingMonth")}
          </label>
          <input
            id="billing-month"
            type="month"
            value={month}
            onChange={(event) => setMonth(event.target.value || currentMonth())}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background"
          />
        </div>
        <div>
          <label
            htmlFor="billing-rate"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            {t("rateLabel", { currency })}
          </label>
          <input
            id="billing-rate"
            type="number"
            min={0}
            step="0.01"
            inputMode="decimal"
            value={rate}
            placeholder={t("ratePlaceholder")}
            onChange={(event) => setRate(event.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {report.data
              ? t("rateInForce", {
                  amount: formatMoney(report.data.rate_cents, currency),
                })
              : t("rateLoading")}
          </p>
        </div>
      </div>

      {report.isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCardSkeleton count={4} />
        </div>
      ) : report.isError || !report.data ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {t("loadFailed")}
        </div>
      ) : (
        <>
          {/* Headline figures */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {lines.map((line) => {
              const style = LINE_STYLES[line.key];
              return (
                <StatCard
                  key={line.key}
                  icon={style?.icon ?? Receipt}
                  color={style?.color ?? "emerald"}
                  label={t(`line_${line.key}`)}
                  value={line.quantity}
                  subtitle={t("atRate", {
                    amount: formatMoney(line.rate_cents, currency),
                  })}
                />
              );
            })}
            <StatCard
              icon={Receipt}
              color="emerald"
              label={t("totalDue")}
              value={formatMoney(report.data.total_cents, currency)}
              subtitle={t("dueBy", { date: report.data.due_date })}
            />
          </div>

          {/* The sum, laid out so it can be checked */}
          <div className="overflow-hidden rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border px-5 py-4">
              <h2 className="text-lg font-semibold text-foreground">
                {t("breakdownTitle")}
              </h2>
              <p className="text-xs text-muted-foreground">
                {t("periodCovered", {
                  from: report.data.date_from,
                  to: report.data.date_to,
                })}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-5 py-3 text-left font-medium">
                      {t("columnEvent")}
                    </th>
                    <th className="px-5 py-3 text-right font-medium">
                      {t("columnQuantity")}
                    </th>
                    <th className="px-5 py-3 text-right font-medium">
                      {t("columnRate")}
                    </th>
                    <th className="px-5 py-3 text-right font-medium">
                      {t("columnAmount")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {lines.map((line) => (
                    <tr key={line.key}>
                      <td className="px-5 py-3 text-foreground">
                        {t(`line_${line.key}`)}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-foreground">
                        {line.quantity.toLocaleString("en-KE")}
                      </td>
                      <td className="px-5 py-3 text-right tabular-nums text-muted-foreground">
                        {formatMoney(line.rate_cents, currency)}
                      </td>
                      <td className="px-5 py-3 text-right font-medium tabular-nums text-foreground">
                        {formatMoney(line.amount_cents, currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="border-t-2 border-border bg-muted/30">
                  <tr>
                    <td className="px-5 py-3 font-semibold text-foreground">
                      {t("totalDue")}
                    </td>
                    <td className="px-5 py-3 text-right font-semibold tabular-nums text-foreground">
                      {report.data.total_quantity.toLocaleString("en-KE")}
                    </td>
                    <td className="px-5 py-3" />
                    <td className="px-5 py-3 text-right text-base font-bold tabular-nums text-foreground">
                      {formatMoney(report.data.total_cents, currency)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Why the numbers are what they are */}
          <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
            <h2 className="mb-3 text-lg font-semibold text-foreground">
              {t("methodTitle")}
            </h2>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>{t("methodReception")}</li>
              <li>{t("methodEmergency")}</li>
              <li>
                {t("methodBedDays", {
                  amount: formatMoney(report.data.rate_cents * 4, currency),
                  days: 4,
                })}
              </li>
              <li>{t("methodSettlement")}</li>
            </ul>
          </div>
        </>
      )}

      {/* Rolling months -- the month-end demand view */}
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border px-5 py-4">
          <h2 className="text-lg font-semibold text-foreground">
            {t("trendTitle")}
          </h2>
          {trend.data && (
            <p className="text-xs text-muted-foreground">
              {t("trendTotal", {
                amount: formatMoney(trend.data.total_cents, currency),
              })}
            </p>
          )}
        </div>
        {trend.isLoading ? (
          <div className="flex items-center gap-2 p-5 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t("loading")}
          </div>
        ) : trendMonths.length === 0 ? (
          <p className="p-5 text-sm text-muted-foreground">{t("noTrend")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-medium">
                    {t("columnMonth")}
                  </th>
                  <th className="px-5 py-3 text-right font-medium">
                    {t("line_reception_registrations")}
                  </th>
                  <th className="px-5 py-3 text-right font-medium">
                    {t("line_emergency_registrations")}
                  </th>
                  <th className="px-5 py-3 text-right font-medium">
                    {t("line_ipd_bed_days")}
                  </th>
                  <th className="px-5 py-3 text-right font-medium">
                    {t("totalDue")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {trendMonths.map((entry) => (
                  <tr
                    key={entry.month}
                    className={entry.month === month ? "bg-primary/5" : undefined}
                  >
                    <td className="px-5 py-3 font-medium text-foreground">
                      {entry.month}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-foreground">
                      {entry.reception_registrations.toLocaleString("en-KE")}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-foreground">
                      {entry.emergency_registrations.toLocaleString("en-KE")}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-foreground">
                      {entry.ipd_bed_days.toLocaleString("en-KE")}
                    </td>
                    <td className="px-5 py-3 text-right font-medium tabular-nums text-foreground">
                      {formatMoney(entry.total_cents, currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
