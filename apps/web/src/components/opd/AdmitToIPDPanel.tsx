"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, XCircle } from "lucide-react";
import { useAdmitPatient, useBeds, useWards } from "@/hooks/useIPD";
import type { AdmissionResponse, Encounter } from "@aifya/shared";

/**
 * Inline "Admit to IPD" panel used on the OPD encounter page.
 *
 * Lets the clinician pick a ward + available bed, then creates a real IPD
 * admission via POST /ipd/admissions so the patient appears on the ward board.
 */
export function AdmitToIPDPanel({
  encounter,
  onAdmitted,
  onCancel,
}: {
  encounter: Encounter;
  onAdmitted: (admission: AdmissionResponse) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("opd");
  const [wardId, setWardId] = useState("");
  const [bedId, setBedId] = useState("");
  const [reason, setReason] = useState(encounter.chief_complaint ?? "");
  const [error, setError] = useState<string | null>(null);

  const {
    data: wards,
    isLoading: wardsLoading,
    isError: wardsError,
    error: wardsLoadError,
  } = useWards();
  const { data: beds, isLoading: bedsLoading } = useBeds(
    wardId || undefined,
    wardId ? "available" : undefined
  );
  const admitPatient = useAdmitPatient();

  const selectedWard = useMemo(
    () => (wards ?? []).find((ward) => ward.id === wardId),
    [wards, wardId]
  );
  const availableBeds = useMemo(
    () => (beds ?? []).filter((bed) => bed.ward_id === wardId),
    [beds, wardId]
  );

  const handleWardChange = (nextWardId: string) => {
    setWardId(nextWardId);
    setBedId("");
    setError(null);
  };

  const handleAdmit = () => {
    if (!wardId || !bedId) {
      setError(t("admitSelectError"));
      return;
    }
    setError(null);
    admitPatient.mutate(
      {
        encounter_id: encounter.id,
        patient_id: encounter.patient_id,
        ward_id: wardId,
        bed_id: bedId,
        admitted_from: "opd",
        admission_reason: reason.trim() || null,
      },
      {
        onSuccess: onAdmitted,
        onError: (err) => setError(err.message ?? t("admitFailed")),
      }
    );
  };

  const selectClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background disabled:cursor-not-allowed disabled:opacity-60";

  return (
    <div className="rounded-xl border border-purple-300 bg-purple-50/40 p-4 shadow-[var(--shadow-card)] dark:border-purple-800 dark:bg-purple-950/20">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-foreground">
          {t("admitPanelTitle")}
        </h3>
        <button
          onClick={onCancel}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <XCircle className="h-3.5 w-3.5" />
          {t("admitCancel")}
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-muted-foreground">
            {t("admitWardLabel")}
          </span>
          <select
            value={wardId}
            onChange={(e) => handleWardChange(e.target.value)}
            className={selectClasses}
            disabled={wardsLoading}
          >
            <option value="">{t("admitWardPlaceholder")}</option>
            {(wards ?? []).map((ward) => (
              <option key={ward.id} value={ward.id}>
                {ward.name} ({ward.available_beds} {t("admitBedsAvailable")})
              </option>
            ))}
          </select>
          {wardsLoading && (
            <span className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              {t("admitWardsLoading")}
            </span>
          )}
          {wardsError && !wardsLoading && (
            <span className="mt-1 block text-xs text-red-600 dark:text-red-400">
              {t("admitWardsError")}
              {wardsLoadError && ` (${wardsLoadError.message})`}
            </span>
          )}
          {!wardsError && !wardsLoading && (wards ?? []).length === 0 && (
            <span className="mt-1 block text-xs text-amber-600 dark:text-amber-400">
              {t("admitNoWards")}
            </span>
          )}
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-muted-foreground">
            {t("admitBedLabel")}
          </span>
          <select
            value={bedId}
            onChange={(e) => setBedId(e.target.value)}
            className={selectClasses}
            disabled={!wardId || bedsLoading}
          >
            <option value="">{t("admitBedPlaceholder")}</option>
            {availableBeds.map((bed) => (
              <option key={bed.id} value={bed.id}>
                {bed.bed_number}
              </option>
            ))}
          </select>
          {bedsLoading && wardId && (
            <span className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              {t("admitBedsLoading")}
            </span>
          )}
          {wardId && !bedsLoading && availableBeds.length === 0 && (
            <span className="mt-1 block text-xs text-amber-600 dark:text-amber-400">
              {selectedWard && selectedWard.available_beds > 0
                ? t("admitNoBeds")
                : t("admitNoAvailableBedsInWard")}
            </span>
          )}
        </label>
      </div>

      <label className="mt-3 block">
        <span className="mb-1 block text-xs font-medium text-muted-foreground">
          {t("admitReasonLabel")}
        </span>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background"
        />
      </label>

      {error && <p className="mt-3 text-xs text-red-600 dark:text-red-400">{error}</p>}

      <div className="mt-4 flex items-center justify-end gap-2">
        <button
          onClick={handleAdmit}
          disabled={admitPatient.isPending || wardsLoading || !wardId || !bedId}
          className="inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-xs font-semibold text-white hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {admitPatient.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {admitPatient.isPending ? t("admitSubmitting") : t("admitConfirm")}
        </button>
      </div>
    </div>
  );
}