"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft,
  Pill,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  CreditCard,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { MpesaPaymentPanel } from "@/components/billing/MpesaPaymentPanel";
import { usePatientServiceCharges } from "@/hooks/useBilling";
import { usePharmacyQueue, useDispense, usePharmacyInventory } from "@/hooks/usePharmacy";
import { formatKES } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { findStockMatches } from "@/lib/drugStock";

const dispenseSchema = z.object({
  quantity_dispensed: z.coerce.number().min(1, "Quantity must be at least 1"),
  pharmacy_item_id: z.string().nullable().optional(),
  substitution_drug: z.string().nullable().optional(),
  substitution_reason: z.string().nullable().optional(),
  dosage_instructions: z.string().nullable().optional(),
  counseling_done: z.boolean(),
  counseling_notes: z.string().nullable().optional(),
  payment_method: z.string().nullable().optional(),
});

type DispenseFormData = z.infer<typeof dispenseSchema>;

/**
 * Dispensing page — verify stock, review interactions, counsel patient, dispense.
 * Multi-step workflow: stock check > interaction review > counseling > dispense.
 *
 * @returns Dispensing page
 */
export default function DispensePage({
  params,
}: {
  params: Promise<{ prescriptionId: string }>;
}) {
  const { prescriptionId } = use(params);
  const t = useTranslations("pharmacy");
  const tb = useTranslations("billing");
  const tc = useTranslations("common");
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  const { data: queue } = usePharmacyQueue();
  const { data: inventory } = usePharmacyInventory();
  const dispense = useDispense();

  // Find the prescription in queue
  const rx = queue?.items.find((i) => i.prescription_id === prescriptionId);

  // The counter cannot let the medicine go until this prescription is paid
  // for, so surface what is still owed and take it here if the patient asks.
  const { data: chargeData, refetch: refetchCharges } =
    usePatientServiceCharges(rx?.patient_id ?? "");
  const rxCharge = (chargeData?.items ?? []).find(
    (charge) =>
      charge.reference_type === "prescription" &&
      charge.reference_id === prescriptionId,
  );

  // Find matching inventory item — match on first keyword
  const matchingItems = useMemo(
    () => findStockMatches(inventory?.items, rx?.drug_name, rx?.generic_name),
    [inventory?.items, rx?.drug_name, rx?.generic_name],
  );

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<DispenseFormData>({
    resolver: zodResolver(dispenseSchema),
    defaultValues: {
      quantity_dispensed: (() => {
        if (rx?.quantity) return rx.quantity;
        const fm: Record<string, number> = { od:1, bd:2, tds:3, qds:4, prn:1, stat:1, nocte:1, weekly:0.143, monthly:0.033 };
        const f = fm[rx?.frequency ?? 'od'] ?? 1;
        return rx?.duration_days ? Math.ceil(f * rx.duration_days) : 1;
      })(),
      counseling_done: false,
      dosage_instructions: rx ? `${rx.dosage} — ${rx.route} — ${rx.frequency}${rx.duration_days ? ` for ${rx.duration_days} days` : ""}` : "",
    },
  });

  const selectedItemId = watch("pharmacy_item_id");
  const counselingDone = watch("counseling_done");

  // Auto-select first matching stock item when page loads
  useEffect(() => {
    if (matchingItems && matchingItems.length > 0 && !selectedItemId) {
      const firstItem = matchingItems[0];
      if (firstItem) {
        setValue("pharmacy_item_id", firstItem.id);
      }
    }
  }, [matchingItems, selectedItemId, setValue]);

  const selectedItem = matchingItems?.find((i) => i.id === selectedItemId);

  const onSubmit = (data: DispenseFormData) => {
    if (!rx) return;
    setError(null);

    dispense.mutate(
      {
        prescription_id: prescriptionId,
        patient_id: rx.patient_id,
        pharmacy_item_id: data.pharmacy_item_id || undefined,
        quantity_dispensed: data.quantity_dispensed,
        substitution_drug: data.substitution_drug || undefined,
        substitution_reason: data.substitution_reason || undefined,
        dosage_instructions: data.dosage_instructions || undefined,
        counseling_done: data.counseling_done,
        counseling_notes: data.counseling_notes || undefined,
        payment_method: data.payment_method || undefined,
      },
      {
        onSuccess: (result) => {
          // useOfflineMutation echoes the request (no server id) when it
          // queues offline instead of dispensing. Never report that as a
          // completed dispense — stock/payment have not been committed.
          if (!result || !(result as { id?: string }).id) {
            setError(t("dispenseQueuedOffline"));
            return;
          }
          router.push("/pharmacy");
        },
        onError: (err) => {
          setError(err.message);
        },
      }
    );
  };

  if (!rx) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <Link href="/pharmacy" className="flex items-center gap-1 text-sm text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" />
          {tc("back")}
        </Link>
        <p className="mt-4 text-muted-foreground">{tc("loading")}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {/* Header */}
      <Link href="/pharmacy" className="mb-4 inline-flex items-center gap-1 text-sm text-primary hover:underline">
        <ArrowLeft className="h-4 w-4" />
        {t("queue")}
      </Link>

      <div className="mb-6 flex items-center gap-3">
        <Pill className="h-6 w-6 text-primary" />
        <h1 className="text-xl font-bold text-foreground">{t("dispense")}</h1>
      </div>

      {/* Prescription summary */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <h2 className="mb-2 text-sm font-medium text-muted-foreground">{t("prescriptionDetails")}</h2>
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-foreground">{rx.drug_name}</span>
          {rx.is_keml && (
            <span className="flex items-center gap-0.5 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-200">
              <ShieldCheck className="h-3 w-3" />
              {t("keml")}
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {rx.dosage} — {rx.route} — {rx.frequency}
          {rx.duration_days ? ` — ${rx.duration_days} days` : ""}
        </p>
        {rx.instructions && (
          <p className="mt-1 text-sm italic text-muted-foreground">{rx.instructions}</p>
        )}
        <div className="mt-2 flex items-center gap-4 text-sm text-muted-foreground">
          <span>{rx.patient_name}</span>
          {rx.patient_mrn && <span className="font-mono">{rx.patient_mrn}</span>}
          {rx.quantity && <span>{t("quantityRequested")}: {rx.quantity}</span>}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Stock selection */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 font-semibold text-foreground">{t("currentStock")}</h3>
          {matchingItems && matchingItems.length > 0 ? (
            <div className="space-y-2">
              {matchingItems.map((item) => (
                <label
                  key={item.id}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors",
                    selectedItemId === item.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-muted/30"
                  )}
                >
                  <input
                    type="radio"
                    value={item.id}
                    {...register("pharmacy_item_id")}
                    className="text-primary"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{item.drug_name}</span>
                      {item.strength && <span className="text-sm text-muted-foreground">{item.strength}</span>}
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{t("currentStock")}: {item.current_quantity} {item.unit_of_measure}</span>
                      {item.batch_number && <span>Batch: {item.batch_number}</span>}
                      {item.expiry_date && <span>Exp: {item.expiry_date}</span>}
                      {item.selling_price_cents != null && (
                        <span>{formatKES(item.selling_price_cents)}/{item.unit_of_measure}</span>
                      )}
                    </div>
                  </div>
                  {item.current_quantity === 0 && (
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-950 dark:text-red-300">
                      {t("outOfStock")}
                    </span>
                  )}
                  {item.current_quantity > 0 && item.current_quantity <= item.reorder_level && (
                    <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300">
                      {t("lowStock")}
                    </span>
                  )}
                </label>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No matching stock found</p>
          )}
        </div>

        {/* Quantity & dosage instructions */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">{t("quantityDispensed")}</label>
            <input
              type="number"
              {...register("quantity_dispensed")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
            />
            {errors.quantity_dispensed && (
              <p className="mt-1 text-xs text-red-500">{errors.quantity_dispensed.message}</p>
            )}
          </div>
          {selectedItem?.selling_price_cents != null && (
            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">{t("totalCost")}</label>
              <div className="flex h-[38px] items-center rounded-md border border-input bg-muted/30 px-3 text-sm font-medium text-foreground">
                {formatKES(selectedItem.selling_price_cents * (watch("quantity_dispensed") || 0))}
              </div>
            </div>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-foreground">{t("dosageLabel")}</label>
          <textarea
            {...register("dosage_instructions")}
            rows={2}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
          />
        </div>

        {/* Substitution (optional) */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 font-semibold text-foreground">{t("substitution")}</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("substitutionDrug")}</label>
              <input
                {...register("substitution_drug")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("substitutionReason")}</label>
              <input
                {...register("substitution_reason")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
          </div>
        </div>

        {/* Patient counseling */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 font-semibold text-foreground">{t("counseling")}</h3>
          <label className="mb-3 flex items-center gap-2 text-sm text-foreground">
            <input type="checkbox" {...register("counseling_done")} className="rounded border-input text-primary" />
            <CheckCircle2 className={cn("h-4 w-4", counselingDone ? "text-green-500" : "text-muted-foreground")} />
            {t("counselingDone")}
          </label>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("counselingNotes")}</label>
            <textarea
              {...register("counseling_notes")}
              rows={2}
              placeholder="Dosage reminders, side effects, missed dose instructions..."
              className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
            />
          </div>
        </div>

        {/* Payment */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
            <CreditCard className="h-5 w-5 text-muted-foreground" />
            {t("payment")}
          </h3>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("paymentMethod")}</label>
            <select
              {...register("payment_method")}
              className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
            >
              <option value="">—</option>
              <option value="cash">{t("cash")}</option>
              <option value="mpesa">{t("mpesa")}</option>
              <option value="insurance">{t("insurance")}</option>
              <option value="exemption">{t("exemption")}</option>
            </select>
          </div>

          {rxCharge && (
            <div className="mt-4 border-t border-border pt-3">
              <p className="text-xs text-muted-foreground">
                {tb("pos.outstanding")}:{" "}
                <span className="font-semibold text-foreground">
                  {formatKES(rxCharge.balance_cents)}
                </span>
              </p>
              <MpesaPaymentPanel
                invoiceId={rxCharge.invoice_id}
                amountCents={rxCharge.balance_cents}
                referenceType="prescription"
                referenceId={prescriptionId}
                onPaid={() => {
                  void refetchCharges();
                }}
              />
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={dispense.isPending}
            className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
          >
            <Pill className="h-4 w-4" />
            {dispense.isPending ? t("dispensing") : t("dispense")}
          </button>
          <Link
            href="/pharmacy"
            className="rounded-lg border border-input px-4 py-2.5 text-sm font-medium text-foreground hover:bg-muted"
          >
            {tc("cancel")}
          </Link>
        </div>
      </form>
    </div>
  );
}
