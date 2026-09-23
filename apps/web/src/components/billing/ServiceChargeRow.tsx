"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Printer, Wallet } from "lucide-react";
import { MpesaPaymentPanel } from "@/components/billing/MpesaPaymentPanel";
import { useCollectServicePayment } from "@/hooks/useBilling";
import { ApiError } from "@/lib/api-client";
import { formatKES, receiptHref } from "@/lib/utils";
import type { PaymentMethod, ServiceCharge } from "@aifya/shared";

/** Payment methods the front desk accepts for an ordered service. */
const PAYMENT_METHODS: readonly PaymentMethod[] = [
  "cash",
  "mpesa",
  "insurance",
  "exemption",
];

interface ServiceChargeRowProps {
  charge: ServiceCharge;
  onCollected?: () => void;
}

/**
 * One ordered service waiting to be paid for, with its collection control.
 *
 * The row owns its own payment mutation because a payment is recorded against
 * the encounter that raised the charge, and a patient's outstanding requests
 * can span more than one visit.
 *
 * @param props - Charge to display, plus an optional settle callback
 * @returns Point-of-sale row
 */
export function ServiceChargeRow({
  charge,
  onCollected,
}: ServiceChargeRowProps) {
  const t = useTranslations("billing");
  const collect = useCollectServicePayment(charge.encounter_id);

  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [reference, setReference] = useState("");
  const [receiptPath, setReceiptPath] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const typeLabel = t(
    ("pos.requestTypes." + charge.reference_type) as Parameters<typeof t>[0],
  );

  /**
   * Collect the outstanding balance for this request.
   *
   * @returns Promise that settles once the request is paid
   */
  const handleCollect = async () => {
    setError("");
    setNotice("");
    setReceiptPath("");
    try {
      const result = await collect.mutateAsync({
        payment_method: method,
        reference_type: charge.reference_type,
        reference_id: charge.reference_id,
        reference_number: reference.trim() || null,
      });
      if (result.already_paid) {
        setNotice(t("pos.alreadyPaid"));
      } else {
        setReceiptPath(result.receipt_url);
        setNotice(t("pos.collected"));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("pos.collectFailed"));
    } finally {
      onCollected?.();
    }
  };

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-foreground">{charge.description}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {typeLabel} &middot; {charge.invoice_number}
          </p>
        </div>
        <div className="text-right">
          <p className="text-lg font-semibold text-foreground">
            {formatKES(charge.balance_cents)}
          </p>
          <p className="text-xs text-muted-foreground">
            {t("pos.outstanding")} / {formatKES(charge.total_cents)}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <select
          value={method}
          onChange={(event) => setMethod(event.target.value as PaymentMethod)}
          aria-label={t("paymentMethod")}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm"
        >
          {PAYMENT_METHODS.map((option) => (
            <option key={option} value={option}>
              {t(option as Parameters<typeof t>[0])}
            </option>
          ))}
        </select>

        <input
          value={reference}
          onChange={(event) => setReference(event.target.value)}
          placeholder={t("pos.referencePlaceholder")}
          className="min-w-[12rem] flex-1 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm"
        />

        <button
          type="button"
          onClick={handleCollect}
          disabled={collect.isPending}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          <Wallet className="h-4 w-4" />
          {collect.isPending ? t("pos.collecting") : t("pos.collect")}
        </button>

        {receiptPath && (
          <a
            href={receiptHref(receiptPath)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
          >
            <Printer className="h-4 w-4" />
            {t("pos.printReceipt")}
          </a>
        )}
      </div>

      {!charge.paid && (
        <MpesaPaymentPanel
          invoiceId={charge.invoice_id}
          amountCents={charge.balance_cents}
          referenceType={charge.reference_type}
          referenceId={charge.reference_id}
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
