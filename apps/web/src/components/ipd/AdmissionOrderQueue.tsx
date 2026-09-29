"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { BedDouble, Check, Loader2, Send, XCircle } from "lucide-react";
import {
  useAcceptAdmissionOrder,
  useAdmissionOrders,
  useAdmitFromOrder,
  useBeds,
  useCancelAdmissionOrder,
  useDeclineAdmissionOrder,
  useWards,
} from "@/hooks/useIPD";
import { cn, formatDateTime } from "@/lib/utils";
import type { AdmissionOrderListItem, AdmissionOrderStatus } from "@aifya/shared";

/** Badge styling per order status. */
const STATUS_STYLES: Record<AdmissionOrderStatus, string> = {
  pending: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  bed_pending: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  accepted: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  admitted: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  declined: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  cancelled: "bg-muted text-muted-foreground",
};

/** Priority chip styling. */
const PRIORITY_STYLES: Record<string, string> = {
  emergency: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  urgent: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  routine: "bg-muted text-muted-foreground",
};

type PanelMode = "assign" | "decline" | null;

/**
 * Admission queue for the IPD / admission desk.
 *
 * Works the admission orders clinicians raise during consultation. Accepting
 * or declining is a decision; assigning a ward and bed is what actually
 * creates the inpatient admission.
 *
 * @returns Admission order queue
 */
export function AdmissionOrderQueue({ onAdmitted }: { onAdmitted?: () => void }) {
  const t = useTranslations("ipd");
  const [statusFilter, setStatusFilter] = useState("open");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [mode, setMode] = useState<PanelMode>(null);
  const [notes, setNotes] = useState("");
  const [wardId, setWardId] = useState("");
  const [bedId, setBedId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useAdmissionOrders(statusFilter);
  const { data: wards } = useWards();
  const { data: beds } = useBeds(wardId || undefined, wardId ? "available" : undefined);

  const acceptOrder = useAcceptAdmissionOrder();
  const declineOrder = useDeclineAdmissionOrder();
  const cancelOrder = useCancelAdmissionOrder();
  const admitFromOrder = useAdmitFromOrder();

  const orders = data?.items ?? [];
  const availableBeds = useMemo(
    () => (beds ?? []).filter((bed) => bed.ward_id === wardId),
    [beds, wardId]
  );

  const reset = () => {
    setActiveId(null);
    setMode(null);
    setNotes("");
    setWardId("");
    setBedId("");
    setError(null);
  };

  const handleAccept = (order: AdmissionOrderListItem, bedPending: boolean) => {
    acceptOrder.mutate(
      { orderId: order.id, bed_pending: bedPending, decision_notes: null },
      { onSuccess: reset, onError: (err) => setError(err.message ?? t("actionFailed")) }
    );
  };

  const handleDecline = (order: AdmissionOrderListItem) => {
    if (!notes.trim()) {
      setError(t("declineReasonRequired"));
      return;
    }
    declineOrder.mutate(
      { orderId: order.id, decision_notes: notes.trim() },
      { onSuccess: reset, onError: (err) => setError(err.message ?? t("actionFailed")) }
    );
  };

  const handleCancel = (order: AdmissionOrderListItem) => {
    cancelOrder.mutate(
      { orderId: order.id, decision_notes: notes.trim() || null },
      { onSuccess: reset, onError: (err) => setError(err.message ?? t("actionFailed")) }
    );
  };

  const handleAdmit = (order: AdmissionOrderListItem) => {
    if (!wardId || !bedId) {
      setError(t("assignBedRequired"));
      return;
    }
    admitFromOrder.mutate(
      {
        orderId: order.id,
        ward_id: wardId,
        bed_id: bedId,
        decision_notes: notes.trim() || null,
      },
      {
        onSuccess: () => {
          reset();
          onAdmitted?.();
        },
        onError: (err) => setError(err.message ?? t("actionFailed")),
      }
    );
  };

  const selectClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background disabled:cursor-not-allowed disabled:opacity-60";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Send className="h-4 w-4 text-primary" />
          <h2 className="font-semibold text-foreground">{t("admissionQueue")}</h2>
          {data && data.total > 0 && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
              {data.total}
            </span>
          )}
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            reset();
          }}
          className="rounded-lg border border-input bg-background px-3 py-1.5 text-xs text-foreground shadow-sm dark:border-border dark:bg-background"
        >
          <option value="open">{t("filterOpen")}</option>
          <option value="pending">{t("statusPending")}</option>
          <option value="accepted">{t("statusAccepted")}</option>
          <option value="bed_pending">{t("statusBedPending")}</option>
          <option value="admitted">{t("statusAdmitted")}</option>
          <option value="declined">{t("statusDeclined")}</option>
          <option value="cancelled">{t("statusCancelled")}</option>
          <option value="">{t("filterAll")}</option>
        </select>
      </div>

      {isLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("loading")}
        </p>
      )}

      {!isLoading && orders.length === 0 && (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
          {t("admissionQueueEmpty")}
        </div>
      )}

      {orders.map((order) => {
        const isActive = activeId === order.id;
        const isOpen =
          order.status === "pending" ||
          order.status === "accepted" ||
          order.status === "bed_pending";
        const busy =
          acceptOrder.isPending ||
          declineOrder.isPending ||
          cancelOrder.isPending ||
          admitFromOrder.isPending;

        return (
          <div
            key={order.id}
            className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-foreground">
                    {order.patient_name ?? t("unknownPatient")}
                  </span>
                  {order.patient_mrn && (
                    <span className="text-xs text-muted-foreground">
                      {order.patient_mrn}
                    </span>
                  )}
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                      STATUS_STYLES[order.status] ?? "bg-muted text-muted-foreground"
                    )}
                  >
                    {t(
                      `status${order.status
                        .split("_")
                        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
                        .join("")}` as "statusPending"
                    )}
                  </span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                      PRIORITY_STYLES[order.priority] ?? "bg-muted text-muted-foreground"
                    )}
                  >
                    {t(`priority_${order.priority}`)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {order.order_number} • {t(`type_${order.admission_type}`)}
                  {order.requested_ward_name
                    ? ` • ${t("requestedWard")}: ${order.requested_ward_name}`
                    : ""}
                  {order.attending_doctor_name
                    ? ` • ${t("attendingDoctor")}: ${order.attending_doctor_name}`
                    : ""}
                </p>
              </div>
              <span className="shrink-0 text-xs text-muted-foreground">
                {formatDateTime(order.created_at)}
              </span>
            </div>

            <p className="mt-2 text-sm text-foreground">{order.reason}</p>
            {order.primary_diagnosis && (
              <p className="mt-1 text-xs text-muted-foreground">
                {t("primaryDiagnosis")}: {order.primary_diagnosis}
              </p>
            )}
            {order.admitted_ward_name && (
              <p className="mt-1 text-xs text-green-700 dark:text-green-400">
                {t("admittedTo", {
                  ward: order.admitted_ward_name,
                  bed: order.admitted_bed_number ?? "—",
                })}
              </p>
            )}
            {order.decision_notes && (
              <p className="mt-1 text-xs text-muted-foreground">
                {t("decisionNotes")}: {order.decision_notes}
              </p>
            )}

            {isOpen && (
              <div className="mt-3 border-t border-border pt-3">
                {isActive && mode === "assign" ? (
                  <div className="grid gap-2 sm:grid-cols-2">
                    <select
                      value={wardId}
                      onChange={(e) => {
                        setWardId(e.target.value);
                        setBedId("");
                      }}
                      className={selectClasses}
                    >
                      <option value="">{t("selectWard")}</option>
                      {(wards ?? []).map((ward) => (
                        <option key={ward.id} value={ward.id}>
                          {ward.name} ({ward.available_beds} {t("available")})
                        </option>
                      ))}
                    </select>
                    <select
                      value={bedId}
                      onChange={(e) => setBedId(e.target.value)}
                      className={selectClasses}
                      disabled={!wardId}
                    >
                      <option value="">{t("selectBed")}</option>
                      {availableBeds.map((bed) => (
                        <option key={bed.id} value={bed.id}>
                          {bed.bed_number}
                        </option>
                      ))}
                    </select>
                    <div className="flex items-center justify-end gap-2 sm:col-span-2">
                      <button
                        onClick={reset}
                        className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted"
                      >
                        {t("cancel")}
                      </button>
                      <button
                        onClick={() => handleAdmit(order)}
                        disabled={busy}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50"
                      >
                        {admitFromOrder.isPending ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <BedDouble className="h-3.5 w-3.5" />
                        )}
                        {t("assignBedConfirm")}
                      </button>
                    </div>
                  </div>
                ) : isActive && mode === "decline" ? (
                  <div className="space-y-2">
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={2}
                      placeholder={t("declineReasonPlaceholder")}
                      className={selectClasses}
                    />
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={reset}
                        className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted"
                      >
                        {t("cancel")}
                      </button>
                      <button
                        onClick={() => handleDecline(order)}
                        disabled={busy}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50"
                      >
                        {declineOrder.isPending && (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        )}
                        {t("decisionDecline")}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    {order.status === "pending" && (
                      <>
                        <button
                          onClick={() => handleAccept(order, false)}
                          disabled={busy}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                        >
                          <Check className="h-3.5 w-3.5" />
                          {t("decisionAccept")}
                        </button>
                        <button
                          onClick={() => handleAccept(order, true)}
                          disabled={busy}
                          className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted disabled:opacity-50"
                        >
                          {t("decisionAcceptNoBed")}
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => {
                        setActiveId(order.id);
                        setMode("assign");
                        setError(null);
                      }}
                      disabled={busy}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50"
                    >
                      <BedDouble className="h-3.5 w-3.5" />
                      {t("assignBed")}
                    </button>
                    <button
                      onClick={() => {
                        setActiveId(order.id);
                        setMode("decline");
                        setNotes("");
                        setError(null);
                      }}
                      disabled={busy}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted disabled:opacity-50"
                    >
                      {t("decisionDecline")}
                    </button>
                    <button
                      onClick={() => handleCancel(order)}
                      disabled={busy}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted disabled:opacity-50"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      {t("decisionCancel")}
                    </button>
                  </div>
                )}
                {isActive && error && (
                  <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                    {error}
                  </p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
