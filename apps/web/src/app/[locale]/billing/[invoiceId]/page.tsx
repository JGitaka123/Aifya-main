"use client";

import { use, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft,
  Receipt,
  User,
  CheckCircle2,
  AlertTriangle,
  DollarSign,
  CreditCard,
  FileText,
  Printer,
  ShieldCheck,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { MpesaPaymentPanel } from "@/components/billing/MpesaPaymentPanel";
import {
  useInvoiceDetail,
  useFinalizeInvoice,
  useRecordPayment,
  useWaiveInvoice,
} from "@/hooks/useBilling";
import { formatKES, formatDateTime, receiptHref } from "@/lib/utils";
import { cn } from "@/lib/utils";

const paymentSchema = z.object({
  amount_cents: z.coerce.number().min(0.01, "Amount must be at least 0.01"),
  payment_method: z.enum(["cash", "mpesa", "insurance", "exemption"]),
  reference_number: z.string().nullable().optional(),
  mpesa_transaction_id: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
});

type PaymentFormData = z.infer<typeof paymentSchema>;

/** Status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  draft: "bg-muted text-foreground",
  finalized: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  partially_paid: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  paid: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  waived: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
};

/**
 * Invoice detail page — view items, record payments, finalize, waive.
 *
 * @returns Invoice detail page
 */
export default function InvoiceDetailPage({
  params,
}: {
  params: Promise<{ invoiceId: string }>;
}) {
  const { invoiceId } = use(params);
  const queryClient = useQueryClient();
  const t = useTranslations("billing");
  const tc = useTranslations("common");
  const [error, setError] = useState<string | null>(null);
  const [showPayment, setShowPayment] = useState(false);
  const [showWaive, setShowWaive] = useState(false);
  const [waiveReason, setWaiveReason] = useState("");
  // Set once an M-Pesa prompt is confirmed, so the desk keeps a lasting
  // "payment received" confirmation after the invoice reloads as settled.
  const [mpesaReceipt, setMpesaReceipt] = useState<string | null>(null);

  const { data, isLoading } = useInvoiceDetail(invoiceId);
  const finalizeInvoice = useFinalizeInvoice();
  const recordPayment = useRecordPayment();
  const waiveInvoice = useWaiveInvoice();

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors: formErrors },
  } = useForm<PaymentFormData>({
    resolver: zodResolver(paymentSchema),
    defaultValues: { payment_method: "cash" },
  });

  const paymentMethod = watch("payment_method");

  const handleFinalize = () => {
    setError(null);
    finalizeInvoice.mutate(
      { invoice_id: invoiceId },
      { onError: (err) => setError(err.message) }
    );
  };

  const handlePayment = (formData: PaymentFormData) => {
    setError(null);
    recordPayment.mutate({ invoice_id: invoiceId, ...formData, amount_cents: Math.round(formData.amount_cents * 100) },
      {
        onSuccess: () => {
          setShowPayment(false);
          reset();
          queryClient.invalidateQueries({ queryKey: ["billing"] });
        },
        onError: (err) => setError(err.message),
      }
    );
  };

  const handleWaive = () => {
    if (!waiveReason.trim() || waiveReason.length < 5) return;
    setError(null);
    waiveInvoice.mutate(
      { invoice_id: invoiceId, reason: waiveReason },
      {
        onSuccess: () => {
          setShowWaive(false);
          setWaiveReason("");
        },
        onError: (err) => setError(err.message),
      }
    );
  };

  if (isLoading || !data) {
    return (
      <div className="mx-auto max-w-4xl p-6 lg:p-8">
        <Link
          href="/billing"
          className="flex items-center gap-1 text-sm text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          {tc("back")}
        </Link>
        <p className="mt-4 text-muted-foreground">{tc("loading")}</p>
      </div>
    );
  }

  const inv = data.invoice;
  const canFinalize = inv.status === "draft";
  const canPay = ["finalized", "partially_paid"].includes(inv.status);
  const canWaive = ["finalized", "partially_paid"].includes(inv.status);

  return (
    <div className="mx-auto max-w-4xl p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Back link */}
      <Link
        href="/billing"
        className="mb-4 inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("invoices")}
      </Link>

      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <Receipt className="h-6 w-6 text-primary" />
        <h1 className="text-xl font-bold text-foreground">{t("invoiceDetail")}</h1>
        <span className="font-mono text-sm text-muted-foreground">
          {inv.invoice_number}
        </span>
        <span
          className={cn(
            "rounded-full px-2.5 py-0.5 text-xs font-medium",
            STATUS_STYLES[inv.status] ?? STATUS_STYLES.draft
          )}
        >
          {t(inv.status === "partially_paid" ? "partiallyPaid" : inv.status as "draft" | "finalized" | "paid" | "cancelled" | "waived")}
        </span>
        {inv.status === "paid" && (
          <CheckCircle2 className="h-5 w-5 text-green-500" />
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-xl bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* M-Pesa confirmation, kept after the invoice reloads as settled */}
      {mpesaReceipt !== null && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border-2 border-green-500 bg-green-50 p-3 text-sm dark:border-green-600 dark:bg-green-950">
          <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-300" />
          <p className="font-semibold text-green-800 dark:text-green-200">
            {t("mpesaPanel.paid")}
          </p>
          {mpesaReceipt && (
            <p className="text-green-800 dark:text-green-200">
              {t("mpesaPanel.paidReceipt", { receipt: mpesaReceipt })}
            </p>
          )}
          <p className="text-green-800 dark:text-green-200">
            {t("mpesaPanel.paidHint")}
          </p>
        </div>
      )}

      {/* Patient info card */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <h2 className="mb-2 text-sm font-medium text-muted-foreground">
          {t("patientInfo")}
        </h2>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <div className="flex items-center gap-1">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="font-semibold text-foreground">
              {data.patient_name ?? "—"}
            </span>
          </div>
          {data.patient_mrn && (
            <span className="font-mono text-muted-foreground">
              {data.patient_mrn}
            </span>
          )}
          {inv.payment_method && (
            <span className="text-muted-foreground">
              {t("paymentMethod")}: {t(inv.payment_method as "cash" | "mpesa" | "insurance" | "exemption")}
            </span>
          )}
          {inv.insurance_provider && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5" />
              {inv.insurance_provider}
              {inv.insurance_member_no && ` (${inv.insurance_member_no})`}
            </span>
          )}
        </div>
        {inv.notes && (
          <p className="mt-2 text-sm italic text-muted-foreground">{inv.notes}</p>
        )}
      </div>

      {/* Line items table */}
      <div className="mb-6">
        <h3 className="mb-3 font-semibold text-foreground">{t("lineItems")}</h3>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 dark:bg-muted/20">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                  {t("description")}
                </th>
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                  {t("itemType")}
                </th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                  {t("quantity")}
                </th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                  {t("unitPrice")}
                </th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                  {t("discount")}
                </th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                  {t("lineTotal")}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr
                  key={item.id}
                  className="border-t border-border"
                >
                  <td className="px-4 py-2 text-foreground">{item.description}</td>
                  <td className="px-4 py-2 capitalize text-muted-foreground">
                    {item.item_type}
                  </td>
                  <td className="px-4 py-2 text-right text-foreground">
                    {item.quantity}
                  </td>
                  <td className="px-4 py-2 text-right text-foreground">
                    {formatKES(item.unit_price_cents)}
                  </td>
                  <td className="px-4 py-2 text-right text-muted-foreground">
                    {item.discount_cents > 0 ? `-${formatKES(item.discount_cents)}` : "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-medium text-foreground">
                    {formatKES(item.total_cents - item.discount_cents)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Totals */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <div className="space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("subtotal")}</span>
            <span className="text-foreground">{formatKES(inv.subtotal_cents)}</span>
          </div>
          {inv.discount_cents > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("discount")}</span>
              <span className="text-green-600 dark:text-green-400">
                -{formatKES(inv.discount_cents)}
              </span>
            </div>
          )}
          {inv.tax_cents > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("tax")}</span>
              <span className="text-foreground">{formatKES(inv.tax_cents)}</span>
            </div>
          )}
          <div className="flex justify-between border-t border-border pt-1 text-base font-bold">
            <span className="text-foreground">{t("total")}</span>
            <span className="text-foreground">{formatKES(inv.total_cents)}</span>
          </div>
          {inv.paid_cents > 0 && (
            <div className="flex justify-between">
              <span className="text-green-600 dark:text-green-400">{t("paidAmount")}</span>
              <span className="text-green-600 dark:text-green-400">
                {formatKES(inv.paid_cents)}
              </span>
            </div>
          )}
          {inv.balance_cents > 0 && (
            <div className="flex justify-between text-base font-bold">
              <span className="text-amber-700 dark:text-amber-400">{t("balance")}</span>
              <span className="text-amber-700 dark:text-amber-400">
                {formatKES(inv.balance_cents)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        {canFinalize && (
          <button
            onClick={handleFinalize}
            disabled={finalizeInvoice.isPending}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
          >
            <FileText className="h-4 w-4" />
            {finalizeInvoice.isPending ? t("finalizing") : t("finalize")}
          </button>
        )}
        {canPay && (
          <button
            onClick={() => {
              // D10: prefill the amount with the outstanding balance as a real,
              // editable value so it can be submitted without retyping.
              if (!showPayment) {
                reset({
                  payment_method: "cash",
                  amount_cents: inv.balance_cents / 100,
                });
              }
              setShowPayment(!showPayment);
            }}
            className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-green-700"
          >
            <DollarSign className="h-4 w-4" />
            {t("recordPayment")}
          </button>
        )}
        {inv.paid_cents > 0 && (
          <a
            href={receiptHref("/billing/invoices/" + invoiceId + "/receipt")}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
          >
            <Printer className="h-4 w-4" />
            {t("pos.printReceipt")}
          </a>
        )}
        {canWaive && (
          <button
            onClick={() => setShowWaive(!showWaive)}
            className="flex items-center gap-2 rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
          >
            {t("waive")}
          </button>
        )}
      </div>

      {/* Payment form */}
      {showPayment && (
        <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
            <CreditCard className="h-5 w-5 text-muted-foreground" />
            {t("recordPayment")}
          </h3>
          <form onSubmit={handleSubmit(handlePayment)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("amount")} *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={inv.balance_cents / 100}
                  {...register("amount_cents")}
                  placeholder={String(inv.balance_cents / 100)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background"
                />
                {formErrors.amount_cents && (
                  <p className="mt-1 text-xs text-red-500">
                    {formErrors.amount_cents.message}
                  </p>
                )}
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("paymentMethod")} *
                </label>
                <select
                  {...register("payment_method")}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background"
                >
                  <option value="cash">{t("cash")}</option>
                  <option value="mpesa">{t("mpesa")}</option>
                  <option value="insurance">{t("insurance")}</option>
                  <option value="exemption">{t("exemption")}</option>
                </select>
              </div>
            </div>

            {paymentMethod === "mpesa" && (
              <MpesaPaymentPanel
                invoiceId={invoiceId}
                amountCents={inv.balance_cents}
                onPaid={(receipt) => {
                  setMpesaReceipt(receipt);
                  queryClient.invalidateQueries({ queryKey: ["billing"] });
                }}
              />
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("referenceNumber")}
                </label>
                <input
                  {...register("reference_number")}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background"
                />
              </div>
              {paymentMethod === "mpesa" && (
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("mpesaCode")}
                  </label>
                  <input
                    {...register("mpesa_transaction_id")}
                    placeholder="e.g. SHK1234ABC"
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background"
                  />
                </div>
              )}
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">
                {t("paymentNotes")}
              </label>
              <textarea
                {...register("notes")}
                rows={2}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background"
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={recordPayment.isPending}
                className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-green-700 disabled:opacity-50"
              >
                <DollarSign className="h-4 w-4" />
                {recordPayment.isPending ? t("recording") : t("recordPayment")}
              </button>
              <button
                type="button"
                onClick={() => setShowPayment(false)}
                className="rounded-lg border border-input px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
              >
                {tc("cancel")}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Waive form */}
      {showWaive && (
        <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 font-semibold text-foreground">{t("waive")}</h3>
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">
              {t("waiveReason")} *
            </label>
            <textarea
              value={waiveReason}
              onChange={(e) => setWaiveReason(e.target.value)}
              rows={2}
              placeholder="Reason for waiving balance (min 5 characters)..."
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background"
            />
          </div>
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={handleWaive}
              disabled={waiveInvoice.isPending || waiveReason.length < 5}
              className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-purple-700 disabled:opacity-50"
            >
              {waiveInvoice.isPending ? t("waiving") : t("waive")}
            </button>
            <button
              onClick={() => setShowWaive(false)}
              className="rounded-lg border border-input px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
            >
              {tc("cancel")}
            </button>
          </div>
        </div>
      )}

      {/* Finalized timestamp */}
      {inv.finalized_at && (
        <div className="text-xs text-muted-foreground">
          {t("finalizedAt")}: {formatDateTime(inv.finalized_at)}
        </div>
      )}
    </div>
  );
}







