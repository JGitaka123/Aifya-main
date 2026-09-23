"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { CheckCircle2, Loader2, Printer, Smartphone } from "lucide-react";
import {
  useMPesaStatus,
  useReconcileSTKPush,
  useSTKPush,
  useSTKRequestStatus,
} from "@/hooks/useMPesa";
import { ApiError } from "@/lib/api-client";
import { formatKES, receiptHref } from "@/lib/utils";

/** Kenyan mobile numbers, local (07/01) or international (2547/2541). */
const PHONE_PATTERN = /^(?:\+?254|0)[17]\d{8}$/;

/**
 * Normalise a Kenyan number to the 2547XXXXXXXX form Daraja expects.
 *
 * @param raw - Number typed at the desk
 * @returns MSISDN, or null when it is not a Kenyan mobile number
 */
export function normalizeKenyanPhone(raw: string): string | null {
  const compact = raw.replace(/[\s()-]/g, "");
  if (!PHONE_PATTERN.test(compact)) {
    return null;
  }
  const digits = compact.replace(/^\+/, "");
  return digits.startsWith("254") ? digits : "254" + digits.slice(1);
}

interface MpesaPaymentPanelProps {
  /** Invoice the money is posted against, when the visit has one. */
  invoiceId?: string | null;
  /** Amount to ask the patient for, in KES cents. */
  amountCents: number;
  /** Ordered service being paid for, so the callback releases it. */
  referenceType?: string | null;
  referenceId?: string | null;
  /** Called once the money is confirmed, with the M-Pesa receipt. */
  onPaid?: (receipt: string) => void;
}

/**
 * "Pay by M-Pesa" control for a transaction at the desk.
 *
 * The patient reads out their number, M-Pesa prompts them for their PIN, and
 * the panel keeps polling until it can say, in no uncertain terms, that the
 * payment went through. Success is only claimed once our own records show the
 * money on the bill, so a prompt that was ignored or cancelled never looks
 * like a payment.
 *
 * @param props - Amount to collect, and what the money is paying for
 * @returns The M-Pesa prompt control, or a note when M-Pesa is unconfigured
 */
export function MpesaPaymentPanel({
  invoiceId,
  amountCents,
  referenceType,
  referenceId,
  onPaid,
}: MpesaPaymentPanelProps) {
  const t = useTranslations("billing");

  const { data: mpesaStatus } = useMPesaStatus();
  const sendPush = useSTKPush();
  const { mutate: reconcile } = useReconcileSTKPush();

  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState(
    amountCents > 0 ? String(Math.ceil(amountCents / 100)) : "",
  );

  const [checkoutId, setCheckoutId] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState("");
  const [phase, setPhase] = useState<"idle" | "waiting" | "paid">("idle");
  const [receipt, setReceipt] = useState("");
  const [error, setError] = useState("");

  const poll = checkoutId !== null && phase === "waiting";
  const status = useSTKRequestStatus(checkoutId, poll);
  const snapshot = status.data;

  // The receipt the desk prints, whichever side told us the invoice id first.
  const receiptInvoiceId = invoiceId ?? snapshot?.invoice_id ?? "";
  const refetchStatus = useRef(status.refetch);
  refetchStatus.current = status.refetch;

  // Stop polling as soon as the money is on the bill, or the prompt failed.
  useEffect(() => {
    if (!checkoutId || phase !== "waiting" || !snapshot) {
      return;
    }
    if (snapshot.status === "success") {
      const mpesaReceipt = snapshot.receipt_number ?? "";
      setReceipt(mpesaReceipt);
      setPhase("paid");
      onPaid?.(mpesaReceipt);
    } else if (snapshot.status === "failed" || snapshot.status === "timeout") {
      setPhase("idle");
      setError(snapshot.result_desc || t("mpesaPanel.failed"));
    }
  }, [checkoutId, phase, snapshot, onPaid, t]);

  // Callbacks can be delayed. Ask Safaricom directly if nothing has landed.
  useEffect(() => {
    if (!checkoutId || phase !== "waiting") {
      return;
    }
    const timer = setTimeout(() => {
      reconcile(
        { checkout_request_id: checkoutId },
        {
          onSuccess: (state) => {
            if (state.status !== "pending") {
              void refetchStatus.current();
            }
          },
        },
      );
    }, 15_000);
    return () => clearTimeout(timer);
  }, [checkoutId, phase, reconcile]);

  /**
   * Send the M-Pesa prompt to the number the patient read out.
   *
   * @returns Promise that settles once the prompt has been requested
   */
  const handleSend = async () => {
    setError("");
    const msisdn = normalizeKenyanPhone(phone);
    if (!msisdn) {
      setError(t("mpesaPanel.badPhone"));
      return;
    }
    const shillings = Math.ceil(Number(amount));
    if (!Number.isFinite(shillings) || shillings <= 0) {
      setError(t("mpesaPanel.badAmount"));
      return;
    }
    try {
      const response = await sendPush.mutateAsync({
        phone_number: msisdn,
        amount_kes: shillings,
        invoice_id: invoiceId ?? null,
        reference_type: referenceType ?? null,
        reference_id: referenceId ?? null,
        description: t("mpesaPanel.description"),
      });
      if (!response.success) {
        setError(
          response.error ||
            response.response_description ||
            t("mpesaPanel.sendFailed"),
        );
        return;
      }
      setSentTo(msisdn);
      setCheckoutId(response.checkout_request_id);
      setPhase("waiting");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("mpesaPanel.sendFailed"));
    }
  };

  /**
   * Ask Safaricom to confirm a payment the callback has not reported yet.
   *
   * @returns Nothing
   */
  const handleVerify = () => {
    if (!checkoutId) {
      return;
    }
    setError("");
    reconcile(
      { checkout_request_id: checkoutId },
      {
        onSuccess: (state) => {
          if (state.status === "pending") {
            setError(t("mpesaPanel.stillWaiting"));
          }
          void refetchStatus.current();
        },
      },
    );
  };

  if (mpesaStatus && !mpesaStatus.configured) {
    return (
      <p className="mt-3 text-xs text-amber-700 dark:text-amber-400">
        {t("mpesaPanel.notConfigured")}
      </p>
    );
  }

  if (phase === "paid") {
    return (
      <div className="mt-3 rounded-lg border-2 border-green-500 bg-green-50 p-3 dark:border-green-600 dark:bg-green-950">
        <p className="flex items-center gap-2 text-base font-semibold text-green-800 dark:text-green-200">
          <CheckCircle2 className="h-5 w-5" />
          {t("mpesaPanel.paid")}
        </p>
        <p className="mt-1 text-sm font-medium text-green-800 dark:text-green-200">
          {t("mpesaPanel.paidReceipt", { receipt: receipt || "-" })}
          {sentTo ? " \u00b7 " + t("mpesaPanel.paidFrom", { phone: sentTo }) : ""}
        </p>
        <p className="mt-0.5 text-xs text-green-700 dark:text-green-300">
          {t("mpesaPanel.paidHint")}
        </p>
        {receiptInvoiceId && (
          <a
            href={receiptHref(`/billing/invoices/${receiptInvoiceId}/receipt`)}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-2 rounded-lg bg-green-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-green-700"
          >
            <Printer className="h-4 w-4" />
            {t("mpesaPanel.printReceipt")}
          </a>
        )}
      </div>
    );
  }

  if (phase === "waiting") {
    return (
      <div className="mt-3 rounded-lg border border-blue-300 bg-blue-50 p-3 dark:border-blue-800 dark:bg-blue-950">
        <p className="flex items-center gap-2 text-sm font-medium text-blue-800 dark:text-blue-200">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("mpesaPanel.promptSent", { phone: sentTo })}
        </p>
        <p className="mt-1 text-xs text-blue-700 dark:text-blue-300">
          {t("mpesaPanel.promptHint")}
        </p>
        <button
          type="button"
          onClick={handleVerify}
          className="mt-2 rounded-lg border border-blue-400 bg-white px-3 py-1.5 text-xs font-medium text-blue-800 shadow-sm hover:bg-blue-100 dark:border-blue-700 dark:bg-blue-900 dark:text-blue-100"
        >
          {t("mpesaPanel.checkNow")}
        </button>
        {error && (
          <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-primary/30 bg-primary/5 p-3">
      <p className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Smartphone className="h-4 w-4 text-primary" />
        {t("mpesaPanel.title")}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">
        {t("mpesaPanel.hint")}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <input
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          inputMode="tel"
          autoComplete="off"
          placeholder={t("mpesaPanel.phonePlaceholder")}
          aria-label={t("mpesaPanel.phoneLabel")}
          className="min-w-[11rem] flex-1 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm"
        />
        <input
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          inputMode="decimal"
          aria-label={t("mpesaPanel.amountLabel")}
          className="w-24 rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={sendPush.isPending}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          <Smartphone className="h-4 w-4" />
          {sendPush.isPending ? t("mpesaPanel.sending") : t("mpesaPanel.send")}
        </button>
      </div>
      {Number(amount) > 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          {t("mpesaPanel.askingFor", {
            amount: formatKES(Math.ceil(Number(amount)) * 100),
          })}
        </p>
      )}
      {error && (
        <p className="mt-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      )}
    </div>
  );
}
