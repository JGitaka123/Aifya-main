"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, Send, XCircle } from "lucide-react";
import { useCreateAdmissionOrder, useWards } from "@/hooks/useIPD";
import { useDepartments } from "@/hooks/useEncounters";
import { useStaffDirectory } from "@/hooks/useHR";
import type { AdmissionPriority, AdmissionType, Encounter } from "@aifya/shared";

const ADMISSION_TYPES: readonly AdmissionType[] = [
  "emergency",
  "urgent",
  "elective",
];
const PRIORITIES: readonly AdmissionPriority[] = ["emergency", "urgent", "routine"];

/**
 * Admission-order form raised from the consultation room.
 *
 * This deliberately does not pick a bed. The clinician states why the patient
 * needs admitting; the admission desk works the request and only assigns a
 * ward and bed when it accepts — that is when an IPD patient actually exists.
 */
export function RequestAdmissionPanel({
  encounter,
  onSubmitted,
  onCancel,
}: {
  encounter: Encounter;
  onSubmitted: (orderNumber: string) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("opd");
  const { data: departments } = useDepartments();
  const { data: wards } = useWards();
  const { data: doctors } = useStaffDirectory("doctor");

  const [reason, setReason] = useState(encounter.chief_complaint ?? "");
  const [diagnosis, setDiagnosis] = useState("");
  const [admissionType, setAdmissionType] = useState<AdmissionType>("elective");
  const [priority, setPriority] = useState<AdmissionPriority>("routine");
  const [departmentId, setDepartmentId] = useState("");
  const [wardId, setWardId] = useState("");
  const [doctorId, setDoctorId] = useState("");
  const [notes, setNotes] = useState("");
  const [requestedAt, setRequestedAt] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createOrder = useCreateAdmissionOrder();

  const handleSubmit = () => {
    if (!reason.trim()) {
      setError(t("admissionReasonRequired"));
      return;
    }
    setError(null);
    createOrder.mutate(
      {
        encounter_id: encounter.id,
        patient_id: encounter.patient_id,
        reason: reason.trim(),
        primary_diagnosis: diagnosis.trim() || null,
        admission_type: admissionType,
        priority,
        department_id: departmentId || null,
        requested_ward_id: wardId || null,
        attending_doctor_id: doctorId || null,
        clinical_notes: notes.trim() || null,
        requested_at: requestedAt ? new Date(requestedAt).toISOString() : null,
      },
      {
        onSuccess: (order) => onSubmitted(order.order_number),
        onError: (err) => setError(err.message ?? t("admissionSubmitFailed")),
      }
    );
  };

  const selectClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background disabled:cursor-not-allowed disabled:opacity-60";
  const labelClasses = "mb-1 block text-xs font-medium text-muted-foreground";

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50/40 p-4 shadow-[var(--shadow-card)] dark:border-amber-800 dark:bg-amber-950/20">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            {t("requestAdmissionTitle")}
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t("requestAdmissionSubtitle")}
          </p>
        </div>
        <button
          onClick={onCancel}
          className="inline-flex shrink-0 items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <XCircle className="h-3.5 w-3.5" />
          {t("admitCancel")}
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block sm:col-span-2">
          <span className={labelClasses}>{t("admissionReasonLabel")}</span>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            placeholder={t("admissionReasonPlaceholder")}
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background"
          />
        </label>

        <label className="block">
          <span className={labelClasses}>{t("admissionDiagnosisLabel")}</span>
          <input
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
            placeholder={t("admissionDiagnosisPlaceholder")}
            className={selectClasses}
          />
        </label>

        <label className="block">
          <span className={labelClasses}>{t("admissionTypeLabel")}</span>
          <select
            value={admissionType}
            onChange={(e) => setAdmissionType(e.target.value as AdmissionType)}
            className={selectClasses}
          >
            {ADMISSION_TYPES.map((value) => (
              <option key={value} value={value}>
                {t(`admissionType_${value}`)}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className={labelClasses}>{t("admissionPriorityLabel")}</span>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as AdmissionPriority)}
            className={selectClasses}
          >
            {PRIORITIES.map((value) => (
              <option key={value} value={value}>
                {t(`admissionPriority_${value}`)}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className={labelClasses}>{t("admissionDepartmentLabel")}</span>
          <select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className={selectClasses}
          >
            <option value="">{t("admissionAnyDepartment")}</option>
            {(departments ?? []).map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className={labelClasses}>{t("admissionWardLabel")}</span>
          <select
            value={wardId}
            onChange={(e) => setWardId(e.target.value)}
            className={selectClasses}
          >
            <option value="">{t("admissionAnyWard")}</option>
            {(wards ?? []).map((ward) => (
              <option key={ward.id} value={ward.id}>
                {ward.name} ({ward.available_beds} {t("admitBedsAvailable")})
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className={labelClasses}>{t("admissionDoctorLabel")}</span>
          <select
            value={doctorId}
            onChange={(e) => setDoctorId(e.target.value)}
            className={selectClasses}
          >
            <option value="">{t("admissionAnyDoctor")}</option>
            {(doctors?.items ?? []).map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.title ? `${doctor.title} ` : ""}
                {doctor.first_name} {doctor.last_name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className={labelClasses}>{t("admissionRequestedAtLabel")}</span>
          <input
            type="datetime-local"
            value={requestedAt}
            onChange={(e) => setRequestedAt(e.target.value)}
            className={selectClasses}
          />
        </label>

        <label className="block sm:col-span-2">
          <span className={labelClasses}>{t("admissionNotesLabel")}</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder={t("admissionNotesPlaceholder")}
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background"
          />
        </label>
      </div>

      {error && (
        <p className="mt-3 text-xs text-red-600 dark:text-red-400">{error}</p>
      )}

      <div className="mt-4 flex items-center justify-end gap-2">
        <button
          onClick={handleSubmit}
          disabled={createOrder.isPending}
          className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-xs font-semibold text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {createOrder.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
          {createOrder.isPending
            ? t("admissionSubmitting")
            : t("admissionSubmit")}
        </button>
      </div>
    </div>
  );
}
