"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Activity, AlertTriangle, Lock, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/components/providers/AuthProvider";
import { formatKES, formatDate, todayISO } from "@/lib/utils";
import {
  useAccrueAifyaUsage,
  useAifyaUsageConfig,
  useAifyaUsageSummary,
  useFinalizeAifyaUsage,
  useIssueAifyaUsageInvoice,
  usePayAifyaUsageInvoice,
  useRaiseAifyaUsageInvoice,
  useUpdateAifyaUsageConfig,
  useVoidAifyaUsageInvoice,
} from "@/hooks/useAifyaUsage";

const CLOSING_ROLES = [
  "admin",
  "facility_admin",
  "hospital_administrator",
  "hr_admin",
];

/** First and last day of a month as YYYY-MM-DD strings. */
function monthRange(year: number, month: number) {
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    start: `${year}-${pad(month)}-01`,
    end: `${year}-${pad(month)}-${pad(last)}`,
    lastDay: `${year}-${pad(month)}-${pad(last)}`,
  };
}

/**
 * Aifya usage billing - what the hospital owes Aifya, not what a patient owes.
 *
 * Aifya charges the hospital per patient-day: one patient seen on one day is
 * one patient-day, priced at the agreed rate. A patient who appears in both
 * Registration and Emergency on the same day is still a single patient-day.
 *
 * @returns The Aifya usage page
 */
export default function AifyaUsagePage() {
  const t = useTranslations("aifyaUsage");
  const tc = useTranslations("common");
  const { user } = useAuth();

  const today = todayISO();
  const [year, setYear] = useState(() => Number(today.slice(0, 4)));
  const [month, setMonth] = useState(() => Number(today.slice(5, 7)));
  const [rateInput, setRateInput] = useState("");
  const [payAmount, setPayAmount] = useState("");
  const [payRef, setPayRef] = useState("");

  const canManage = useMemo(
    () => (user?.roles ?? []).some((r) => CLOSING_ROLES.includes(r)),
    [user],
  );

  const range = monthRange(year, month);
  const accrue = useAccrueAifyaUsage();
  const summary = useAifyaUsageSummary(year, month);
  const config = useAifyaUsageConfig();
  const saveRate = useUpdateAifyaUsageConfig();
  const finalize = useFinalizeAifyaUsage();
  const raiseInvoice = useRaiseAifyaUsageInvoice();
  const issueInvoice = useIssueAifyaUsageInvoice();
  const payInvoice = usePayAifyaUsageInvoice();
  const voidInvoice = useVoidAifyaUsageInvoice();

  // Fold the month's encounters into the ledger whenever the month changes.
  // The call is idempotent, so re-running it can never double-count.
  useEffect(() => {
    accrue.mutate({ start_date: range.start, end_date: range.end });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, month]);

  useEffect(() => {
    if (config.data) setRateInput(String(config.data.rate_cents / 100));
  }, [config.data]);

  const monthEnded = range.lastDay < today;
  const days = summary.data?.days ?? [];
  const patientDays = summary.data?.total_patient_days ?? 0;
  const chargeCents = summary.data?.total_amount_cents ?? 0;
  const rateCents = summary.data?.rate_cents ?? config.data?.rate_cents ?? 0;
  const isClosed = summary.data?.is_finalized ?? false;
  const rateConfirmed = summary.data?.rate_is_confirmed ?? true;
  const invoice = summary.data?.invoice ?? null;
  const busy = accrue.isPending || summary.isLoading;

  /** Status label without a dynamic translation key. */
  const invoiceStatusLabel = (status: string) =>
    status === "issued"
      ? t("statusIssued")
      : status === "paid"
        ? t("statusPaid")
        : status === "void"
          ? t("statusVoid")
          : t("statusDraft");

  const onSaveRate = () => {
    const kes = Number(rateInput);
    if (!Number.isFinite(kes) || kes < 0) return;
    saveRate.mutate({ rate_cents: Math.round(kes * 100), currency: "KES" });
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={Activity}
        title={t("title")}
        subtitle={t("subtitle")}
        breadcrumbs={[
          { label: t("hrLabel"), href: "/hr" },
          { label: t("title") },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <input
              type="month"
              value={`${year}-${String(month).padStart(2, "0")}`}
              onChange={(e) => {
                const [y, m] = e.target.value.split("-");
                setYear(Number(y));
                setMonth(Number(m));
              }}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() =>
                accrue.mutate({ start_date: range.start, end_date: range.end })
              }
              disabled={accrue.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium hover:bg-muted/50 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${accrue.isPending ? "animate-spin" : ""}`} />
              {t("refresh")}
            </button>
          </div>
        }
      />

      <div className="rounded-xl border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
        {t("ruleNote")}
      </div>

      {summary.data && !rateConfirmed ? (
        <div className="flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{t("rateUnconfirmed")}</span>
        </div>
      ) : null}

      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <p className="text-xs uppercase text-muted-foreground">{t("period")}</p>
          <p className="mt-1 text-lg font-semibold text-foreground">
            {summary.data?.period_label ?? `${year}-${month}`}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {summary.data?.facility_name}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <p className="text-xs uppercase text-muted-foreground">{t("rate")}</p>
          <p className="mt-1 text-lg font-semibold text-foreground">
            {formatKES(rateCents)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{t("rateUnit")}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <p className="text-xs uppercase text-muted-foreground">{t("patientDays")}</p>
          <p className="mt-1 text-lg font-semibold text-foreground tabular-nums">
            {patientDays.toLocaleString()}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {t("split", {
              registration: summary.data?.registration_patient_days ?? 0,
              emergency: summary.data?.emergency_patient_days ?? 0,
              inpatient: summary.data?.inpatient_patient_days ?? 0,
            })}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <p className="text-xs uppercase text-muted-foreground">{t("totalCharge")}</p>
          <p className="mt-1 text-lg font-semibold text-primary tabular-nums">
            {formatKES(chargeCents)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {isClosed ? t("closed") : t("open")}
          </p>
        </div>
      </div>

      {/* Rate + close controls (administrators only) */}
      {canManage ? (
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h2 className="text-sm font-semibold text-foreground">{t("rateTitle")}</h2>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">
                {t("ratePerPatientDay")}
              </span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={rateInput}
                onChange={(e) => setRateInput(e.target.value)}
                className="w-40 rounded-lg border border-border bg-card px-3 py-2 text-sm"
              />
            </label>
            <button
              type="button"
              onClick={onSaveRate}
              disabled={saveRate.isPending}
              className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {saveRate.isPending ? tc("saving") : t("saveRate")}
            </button>
            <button
              type="button"
              onClick={() => finalize.mutate({ year, month })}
              disabled={!monthEnded || isClosed || finalize.isPending}
              title={!monthEnded ? t("closeMonthNotEnded") : undefined}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium hover:bg-muted/50 disabled:opacity-50"
            >
              <Lock className="h-4 w-4" />
              {isClosed ? t("closed") : t("closeMonth")}
            </button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {t("rateHistoryNote")}
          </p>
          {summary.data?.rate_changed_mid_month ? (
            <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
              {t("rateChangedMidMonth")}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Daily breakdown */}
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold text-foreground">
            {t("dailyBreakdown")}
          </h2>
        </div>
        {busy && !days.length ? (
          <div className="p-8 text-center text-muted-foreground">{tc("loading")}</div>
        ) : !days.length ? (
          <div className="p-8 text-center text-muted-foreground">{t("noUsage")}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("date")}</th>
                  <th className="px-4 py-3 text-right">{t("registrationPatients")}</th>
                  <th className="px-4 py-3 text-right">{t("emergencyPatients")}</th>
                  <th className="px-4 py-3 text-right">{t("inpatientPatients")}</th>
                  <th className="px-4 py-3 text-right">{t("totalBillable")}</th>
                  <th className="px-4 py-3 text-right">{t("rate")}</th>
                  <th className="px-4 py-3 text-right">{t("amount")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {days.map((d) => (
                  <tr key={d.usage_date} className="hover:bg-muted/30">
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(d.usage_date)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {d.registration_patients}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {d.emergency_patients}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {d.inpatient_patients}
                    </td>
                    <td className="px-4 py-3 text-right font-medium tabular-nums">
                      {d.total_billable_patients}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                      {formatKES(d.rate_cents)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(d.amount_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-border bg-muted/20">
                <tr>
                  <td className="px-4 py-3 font-semibold" colSpan={4}>
                    {t("monthlyTotal")}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums">
                    {patientDays.toLocaleString()}
                  </td>
                  <td className="px-4 py-3" />
                  <td className="px-4 py-3 text-right font-semibold tabular-nums text-primary">
                    {formatKES(chargeCents)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* Aifya invoice to the hospital */}
      <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-foreground">
            {t("invoiceTitle")}
          </h2>
          {invoice ? (
            <span className="rounded-full border border-border px-2 py-0.5 text-xs font-medium text-muted-foreground">
              {invoiceStatusLabel(invoice.status)}
            </span>
          ) : null}
        </div>

        {!invoice ? (
          <>
            <p className="mt-2 text-sm text-muted-foreground">
              {t("invoiceNone")}
            </p>
            {canManage ? (
              <button
                type="button"
                onClick={() => raiseInvoice.mutate({ year, month })}
                disabled={!patientDays || raiseInvoice.isPending}
                className="mt-3 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {raiseInvoice.isPending ? tc("saving") : t("raiseInvoice")}
              </button>
            ) : null}
          </>
        ) : (
          <>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-xs uppercase text-muted-foreground">
                  {t("invoiceNumber")}
                </dt>
                <dd className="mt-0.5 font-medium tabular-nums">
                  {invoice.invoice_number}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-muted-foreground">
                  {t("invoiceAmount")}
                </dt>
                <dd className="mt-0.5 font-medium tabular-nums">
                  {formatKES(invoice.amount_cents)}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-muted-foreground">
                  {t("invoicePaid")}
                </dt>
                <dd className="mt-0.5 font-medium tabular-nums">
                  {formatKES(invoice.paid_cents)}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase text-muted-foreground">
                  {t("invoiceBalance")}
                </dt>
                <dd className="mt-0.5 font-semibold tabular-nums text-primary">
                  {formatKES(invoice.balance_cents)}
                </dd>
              </div>
            </dl>
            {invoice.due_at ? (
              <p className="mt-2 text-xs text-muted-foreground">
                {t("invoiceDue", { date: formatDate(invoice.due_at) })}
              </p>
            ) : null}

            {canManage ? (
              <div className="mt-4 flex flex-wrap items-end gap-3">
                {invoice.status === "draft" ? (
                  <button
                    type="button"
                    onClick={() => issueInvoice.mutate(invoice.id)}
                    disabled={issueInvoice.isPending}
                    className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
                  >
                    {issueInvoice.isPending ? tc("saving") : t("issueInvoice")}
                  </button>
                ) : null}

                {invoice.status === "issued" ? (
                  <>
                    <label className="block text-sm">
                      <span className="mb-1 block text-muted-foreground">
                        {t("paymentAmount")}
                      </span>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={payAmount}
                        onChange={(e) => setPayAmount(e.target.value)}
                        className="w-40 rounded-lg border border-border bg-card px-3 py-2 text-sm"
                      />
                    </label>
                    <label className="block text-sm">
                      <span className="mb-1 block text-muted-foreground">
                        {t("paymentReference")}
                      </span>
                      <input
                        type="text"
                        value={payRef}
                        onChange={(e) => setPayRef(e.target.value)}
                        className="w-48 rounded-lg border border-border bg-card px-3 py-2 text-sm"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        const kes = Number(payAmount);
                        if (!Number.isFinite(kes) || kes <= 0) return;
                        payInvoice.mutate({
                          id: invoice.id,
                          amount_cents: Math.round(kes * 100),
                          reference: payRef || null,
                        });
                        setPayAmount("");
                        setPayRef("");
                      }}
                      disabled={payInvoice.isPending}
                      className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
                    >
                      {payInvoice.isPending ? tc("saving") : t("recordPayment")}
                    </button>
                  </>
                ) : null}

                {invoice.status === "draft" || invoice.status === "issued" ? (
                  <button
                    type="button"
                    onClick={() => voidInvoice.mutate(invoice.id)}
                    disabled={voidInvoice.isPending}
                    className="rounded-lg border border-border px-3 py-2 text-sm font-medium hover:bg-muted/50 disabled:opacity-50"
                  >
                    {voidInvoice.isPending ? tc("saving") : t("voidInvoice")}
                  </button>
                ) : null}
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
