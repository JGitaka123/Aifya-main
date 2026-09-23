"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { PencilLine, Printer, Wallet } from "lucide-react";
import { useAuth } from "@/components/providers/AuthProvider";
import { MpesaPaymentPanel } from "@/components/billing/MpesaPaymentPanel";
import {
  useCollectConsultationFee,
  useConsultationFee,
  useUpdateConsultationFee,
} from "@/hooks/useEncounters";
import { ApiError } from "@/lib/api-client";
import { formatKES, receiptHref } from "@/lib/utils";
import type { PaymentMethod } from "@aifya/shared";

/** Payment methods reception accepts for the consultation fee. */
const PAYMENT_METHODS: readonly PaymentMethod[] = [
  "cash",
  "mpesa",
  "insurance",
  "exemption",
];

/** Staff the API lets price and settle a consultation fee. */
const FEE_DESK_ROLES: readonly string[] = [
  "receptionist",
  "cashier",
  "billing_clerk",
  "admin",
  "facility_admin",
];

interface ConsultationFeePanelProps {
  encounterId: string;
}

/**
 * Consultation fee gate for a receptionist routing a patient to a clinician.
 *
 * The receptionist takes the fee here and hands over the printed receipt the
 * patient shows before being seen. The quoted amount is editable, because a
 * negotiated or follow-up rate has to reach the patient's bill and the printed
 * receipt, not just the desk. A visit with no fee configured (or one already
 * settled) just reports its state.
 *
 * @param props - Encounter being routed
 * @returns Consultation fee panel
 */
export function ConsultationFeePanel({
  encounterId,
}: ConsultationFeePanelProps) {
  const t = useTranslations("billing");
  const tc = useTranslations("common");
  const { user } = useAuth();
  const { data: quote, refetch } = useConsultationFee(encounterId);
  const collect = useCollectConsultationFee(encounterId);
  const updateFee = useUpdateConsultationFee(encounterId);

  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [reference, setReference] = useState("");
  const [receiptPath, setReceiptPath] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [feeInput, setFeeInput] = useState("");
  const [editingFee, setEditingFee] = useState(false);

  if (!quote) {
    return null;
  }

  // A quote with no invoice has nothing billed yet, so it is not settled, even
  // though the API reports a visit with a zero configured fee as paid.
  const locked = quote.paid && quote.invoice_id !== null;
  // Take the money only where the API would accept it. Unknown roles fail open
  // so a deployment whose session omits them keeps working as before.
  const canSettle =
    !user ||
    user.roles.length === 0 ||
    FEE_DESK_ROLES.some((role) => user.roles.includes(role));

  /**
   * Take the outstanding consultation fee at reception.
   *
   * @returns Promise that settles once the fee is paid
   */
  const handleCollect = async () => {
    setError("");
    setNotice("");
    try {
      const result = await collect.mutateAsync({
        payment_method: method,
        reference_number: reference.trim() || null,
      });
      setReceiptPath(result.receipt_url);
      setNotice(t("consultationFee.settled"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("pos.collectFailed"));
    } finally {
      void refetch();
    }
  };

  /** Open the fee editor seeded with the amount currently quoted. */
  const startEditingFee = () => {
    setError("");
    setNotice("");
    setFeeInput((quote.fee_cents / 100).toFixed(2));
    setEditingFee(true);
  };

  /** Close the editor without touching the stored fee. */
  const cancelEditingFee = () => {
    setEditingFee(false);
    setError("");
  };

  /**
   * Save a corrected fee and re-price the visit's consultation invoice.
   *
   * The amount shown afterwards always comes back from the API, so the desk can
   * never display one figure while the patient's bill and receipt carry another.
   *
   * @returns Promise that settles once the new fee is stored
   */
  const handleSaveFee = async () => {
    setError("");
    setNotice("");
    const shillings = Number(feeInput);
    if (!Number.isFinite(shillings) || shillings <= 0) {
      setError(t("consultationFee.invalidAmount"));
      return;
    }
    try {
      const updated = await updateFee.mutateAsync({
        amount_cents: Math.round(shillings * 100),
      });
      setFeeInput((updated.fee_cents / 100).toFixed(2));
      setEditingFee(false);
      setNotice(
        t("consultationFee.feeUpdated", {
          amount: formatKES(updated.fee_cents),
        }),
      );
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : t("consultationFee.updateFailed"),
      );
    } finally {
      void refetch();
    }
  };

  const showReceipt = Boolean(receiptPath || quote.receipt_url);

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-foreground">
            {t("consultationFee.title")}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t("consultationFee.description")}
          </p>
        </div>
        <div className="text-right">
          <p className="text-lg font-semibold text-foreground">
            {formatKES(locked ? quote.fee_cents : quote.balance_cents)}
          </p>
          <p className="text-xs text-muted-foreground">
            {t("consultationFee.amount")} {formatKES(quote.fee_cents)}
            {locked
              ? ""
              : " \u00b7 " + t("balance") + " " + formatKES(quote.balance_cents)}
          </p>
        </div>
      </div>

      {!locked && quote.invoice_id === null && quote.fee_cents <= 0 && (
        <p className="mt-3 text-sm text-muted-foreground">
          {t("consultationFee.notConfigured")}
        </p>
      )}

      {locked && canSettle && (
        <p className="mt-3 rounded-lg border border-border bg-muted px-3 py-2 text-xs text-muted-foreground">
          {t("consultationFee.feeLocked")}
        </p>
      )}

      {canSettle &&
        !locked &&
        (editingFee ? (
          <div className="mt-4 flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-muted-foreground">
                {t("consultationFee.amountLabel")}
              </span>
              <input
                value={feeInput}
                onChange={(event) => setFeeInput(event.target.value)}
                inputMode="decimal"
                aria-label={t("consultationFee.amountLabel")}
                className="w-40 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm"
              />
            </label>
            <button
              type="button"
              onClick={handleSaveFee}
              disabled={updateFee.isPending}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              <Wallet className="h-4 w-4" />
              {updateFee.isPending
                ? t("consultationFee.savingFee")
                : t("consultationFee.saveFee")}
            </button>
            <button
              type="button"
              onClick={cancelEditingFee}
              disabled={updateFee.isPending}
              className="rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted disabled:opacity-50"
            >
              {tc("cancel")}
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={startEditingFee}
            className="mt-3 flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
          >
            <PencilLine className="h-4 w-4" />
            {t("consultationFee.editFee")}
          </button>
        ))}

      {(canSettle || showReceipt) && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {canSettle && (
            <select
              value={method}
              onChange={(event) => setMethod(event.target.value as PaymentMethod)}
              aria-label={t("paymentMethod")}
              disabled={locked}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm disabled:opacity-50"
            >
              {PAYMENT_METHODS.map((option) => (
                <option key={option} value={option}>
                  {t(option as Parameters<typeof t>[0])}
                </option>
              ))}
            </select>
          )}

          {canSettle && (
            <input
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              placeholder={t("consultationFee.referencePlaceholder")}
              disabled={locked}
              className="min-w-[12rem] flex-1 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm disabled:opacity-50"
            />
          )}

          {canSettle && (
            <button
              type="button"
              onClick={handleCollect}
              disabled={
                locked || quote.invoice_id === null || collect.isPending
              }
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              <Wallet className="h-4 w-4" />
              {collect.isPending
                ? t("consultationFee.collecting")
                : t("consultationFee.collect")}
            </button>
          )}

          {showReceipt && (
            <a
              href={receiptHref(receiptPath || quote.receipt_url || "")}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
            >
              <Printer className="h-4 w-4" />
              {t("consultationFee.printReceipt")}
            </a>
          )}
        </div>
      )}

      {canSettle && !locked && quote.invoice_id && (
        <MpesaPaymentPanel
          invoiceId={quote.invoice_id}
          amountCents={quote.balance_cents}
          onPaid={() => {
            void refetch();
          }}
        />
      )}

      {notice && (
        <p className="mt-3 rounded-lg border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200">
          {notice}
        </p>
      )}
      {error && (
        <p className="mt-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      )}
    </div>
  );
}