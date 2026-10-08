"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle, ArrowRight, Loader2, Stethoscope } from "lucide-react";
import { Link } from "@/i18n/routing";
import { useCreateEncounter } from "@/hooks/useEncounters";
import { ConsultationFeePanel } from "@/components/billing/ConsultationFeePanel";
import { usePermissions } from "@/hooks/usePermissions";
import { canOpenDestination } from "@/lib/navigation";
import type { Encounter } from "@aifya/shared";

interface ReceptionVisitPanelProps {
  /** Patient just registered at the front desk. */
  patient: { id: string; name: string };
}

/**
 * Front-desk visit and consultation fee, taken on the Registration tab.
 *
 * Registration is where the patient pays to see a doctor: the receptionist
 * opens the OPD visit, takes the consultation fee and hands over the printed
 * receipt. The desk does not choose a unit and does not assign a doctor - the
 * nurse assesses in OPD and the doctor decides in the consultation room where
 * the patient goes next. OPD therefore only records vitals, and the
 * consultation room only diagnoses, so the receipt is always in hand before
 * the patient is seen.
 *
 * @param props.patient - The patient the visit belongs to
 * @returns Reception visit and fee panel
 */
export function ReceptionVisitPanel({ patient }: ReceptionVisitPanelProps) {
  const t = useTranslations("opd");
  const tp = useTranslations("patients");

  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [visit, setVisit] = useState<Encounter | null>(null);

  const createEncounter = useCreateEncounter();

  // "Send to OPD" is a door into the clinical workspace. The front desk does
  // not own that room, so only draw the link for a role the sidebar would let
  // through - otherwise the hand-off ends on the 403 panel instead of a
  // receipt. The visit itself is already started and queued either way.
  const { roles, hasPermission } = usePermissions();
  const canSendToOpd = canOpenDestination("/opd", {
    roles: roles ?? [],
    hasPermission,
  });

  /**
   * Open the visit this fee is owed on, then let the desk settle it.
   *
   * Reception collects the fee and hands over the receipt. The desk records
   * the reason for the visit and nothing else: which unit the patient goes to
   * is decided by the nurse and the doctor afterwards, so no unit and no
   * doctor are recorded here.
   *
   * @returns Nothing
   */
  const startVisit = () => {
    setError("");
    createEncounter.mutate(
      {
        patient_id: patient.id,
        encounter_type: "opd",
        chief_complaint: reason.trim() || null,
        // The nurse sets the real triage category in OPD; the desk only needs
        // a safe default so the patient is queued rather than left behind.
        triage_category: "non_urgent",
      },
      {
        onSuccess: setVisit,
        onError: (err: Error) =>
          setError(err.message || t("createEncounterError")),
      }
    );
  };

  return (
    <section className="mb-6 rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
      <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        <Stethoscope className="h-4 w-4" />
        {tp("receptionFeeTitle")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {tp("receptionFeeHint")}
      </p>

      {!visit ? (
        <div className="mt-4 space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-foreground">
              {t("chiefComplaint")}
            </label>
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={2}
              placeholder={t("chiefComplaintExample")}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>

          {error && (
            <p className="flex items-center gap-1 text-xs text-red-500">
              <AlertTriangle className="h-3 w-3" /> {error}
            </p>
          )}

          <button
            type="button"
            onClick={startVisit}
            disabled={createEncounter.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {createEncounter.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowRight className="h-4 w-4" />
            )}
            {createEncounter.isPending
              ? t("creatingEncounter")
              : tp("startVisitTakeFee")}
          </button>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <p className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm text-foreground">
            {tp("visitStarted", { queue: visit.queue_number ?? "-" })}
          </p>
          <ConsultationFeePanel encounterId={visit.id} />
          {canSendToOpd ? (
            <Link
              href="/opd"
              className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              {tp("sendToOpd")}
            </Link>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">{tp("sentToOpdNote")}</p>
          )}
        </div>
      )}
    </section>
  );
}
