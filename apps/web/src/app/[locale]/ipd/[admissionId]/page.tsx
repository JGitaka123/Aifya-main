"use client";

import { use, useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft,
  Ambulance,
  BedDouble,
  Clock,
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  LogOut,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useRouter } from "next/navigation";
import {
  useAdmissionDetail,
  useNursingNotes,
  useAddNursingNote,
  useDischargePatient,
  useTransferToEmergency,
} from "@/hooks/useIPD";
import { formatDateTime, elapsedDuration } from "@/lib/utils";
import { cn } from "@/lib/utils";

const nursingNoteSchema = z.object({
  note_type: z.enum([
    "observation",
    "medication",
    "procedure",
    "shift_handover",
    "intake_output",
    "pain_assessment",
    "wound_care",
  ]),
  content: z.string().min(1, "Note content is required"),
  shift: z.enum(["morning", "afternoon", "night"]).nullable().optional(),
  severity: z.enum(["normal", "warning", "critical"]).nullable().optional(),
});

type NursingNoteFormData = z.infer<typeof nursingNoteSchema>;

const dischargeSchema = z.object({
  discharge_type: z.enum([
    "improved",
    "recovered",
    "dama",
    "absconded",
    "deceased",
    "transferred",
    "referred",
  ]),
  discharge_diagnosis: z.string().nullable().optional(),
  discharge_summary: z.string().nullable().optional(),
  follow_up_plan: z.string().nullable().optional(),
  discharge_medications: z.string().nullable().optional(),
});

type DischargeFormData = z.infer<typeof dischargeSchema>;

/** Severity badge styling. */
const SEVERITY_STYLES: Record<string, string> = {
  normal: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  warning: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  critical: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/**
 * Admission detail page — patient info, nursing notes, and discharge.
 *
 * @returns Admission detail page
 */
export default function AdmissionDetailPage({
  params,
}: {
  params: Promise<{ admissionId: string }>;
}) {
  const { admissionId } = use(params);
  const t = useTranslations("ipd");
  const tc = useTranslations("common");
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [showDischarge, setShowDischarge] = useState(false);
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [showTransfer, setShowTransfer] = useState(false);
  const [transferReason, setTransferReason] = useState("");

  const { data: admission, isLoading } = useAdmissionDetail(admissionId);
  const { data: notes } = useNursingNotes(admissionId);
  const addNote = useAddNursingNote();
  const dischargePatient = useDischargePatient();
  const transferToEmergency = useTransferToEmergency();

  const noteForm = useForm<NursingNoteFormData>({
    resolver: zodResolver(nursingNoteSchema),
    defaultValues: { note_type: "observation" },
  });

  const dischargeForm = useForm<DischargeFormData>({
    resolver: zodResolver(dischargeSchema),
    defaultValues: { discharge_type: "improved" },
  });

  const handleAddNote = (data: NursingNoteFormData) => {
    setError(null);
    addNote.mutate(
      { admission_id: admissionId, ...data },
      {
        onSuccess: () => {
          setShowNoteForm(false);
          noteForm.reset();
        },
        onError: (err) => setError(err.message),
      }
    );
  };

  const handleDischarge = (data: DischargeFormData) => {
    setError(null);
    dischargePatient.mutate(
      { admission_id: admissionId, ...data },
      {
        onSuccess: () => router.push("/ipd"),
        onError: (err) => setError(err.message),
      }
    );
  };

  const handleTransferToEmergency = () => {
    if (!transferReason.trim()) {
      setError(t("transferReasonRequired"));
      return;
    }
    setError(null);
    transferToEmergency.mutate(
      { admission_id: admissionId, reason: transferReason.trim() },
      {
        onSuccess: (visit) => router.push(`/emergency/${visit.id}`),
        onError: (err) => setError(err.message),
      }
    );
  };

  if (isLoading || !admission) {
    return (
      <div className="mx-auto max-w-4xl p-6 lg:p-8">
        <Link
          href="/ipd"
          className="flex items-center gap-1 text-sm text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          {tc("back")}
        </Link>
        <p className="mt-4 text-muted-foreground">{tc("loading")}</p>
      </div>
    );
  }

  const isActive = ["admitted", "on_leave"].includes(admission.status);
  // Closed episodes stop at discharge; active ones tick up to now.
  const elapsedStay = elapsedDuration(admission.admitted_at, admission.discharged_at);

  return (
    <div className="mx-auto max-w-4xl p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Back link */}
      <Link
        href="/ipd"
        className="mb-4 inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("wardBoard")}
      </Link>

      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <BedDouble className="h-6 w-6 text-primary" />
        <h1 className="text-xl font-bold text-foreground">
          {t("admissionDetail")}
        </h1>
        <span className="font-mono text-sm text-muted-foreground">
          {admission.admission_number}
        </span>
        <span
          className={cn(
            "rounded-full px-2.5 py-0.5 text-xs font-medium",
            admission.status === "admitted"
              ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200"
              : admission.status === "discharged"
                ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200"
                : "bg-muted text-foreground"
          )}
        >
          {t(admission.status === "on_leave" ? "onLeave" : admission.status as "admitted" | "discharged")}
        </span>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-xl bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* Admission info card */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
          <InfoField label={t("admittedAt")} value={formatDateTime(admission.admitted_at)} />
          {admission.admitted_from && (
            <InfoField
              label={t("admittedFrom")}
              value={t(`from${admission.admitted_from === "opd" ? "OPD" : admission.admitted_from.charAt(0).toUpperCase() + admission.admitted_from.slice(1)}` as "fromOPD")}
            />
          )}
          {admission.accommodation_type && (
            <InfoField label={t("accommodationType")} value={admission.accommodation_type} />
          )}
          {admission.admission_diagnosis && (
            <InfoField
              label={t("admissionDiagnosis")}
              value={admission.admission_diagnosis}
              span2
            />
          )}
          {admission.admission_reason && (
            <InfoField
              label={t("admissionReason")}
              value={admission.admission_reason}
              span2
            />
          )}
          {(elapsedStay || admission.length_of_stay_days != null) && (
            <InfoField
              label={t("lengthOfStay")}
              value={
                elapsedStay
                  ? t(elapsedStay.key, { count: elapsedStay.count })
                  : admission.length_of_stay_days + " " + t("days")
              }
            />
          )}
        </div>
      </div>

      {/* Discharge info (if discharged) */}
      {admission.discharged_at && (
        <div className="mb-6 rounded-lg border border-green-300 bg-green-50/50 p-4 dark:border-green-800 dark:bg-green-950/30">
          <h3 className="mb-2 flex items-center gap-2 font-semibold text-foreground">
            <CheckCircle2 className="h-4 w-4 text-green-500" />
            {t("discharge")}
          </h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <InfoField label={t("dischargedAt")} value={formatDateTime(admission.discharged_at)} />
            {admission.discharge_type && (
              <InfoField label={t("dischargeType")} value={admission.discharge_type} />
            )}
            {admission.discharge_diagnosis && (
              <InfoField label={t("dischargeDiagnosis")} value={admission.discharge_diagnosis} span2 />
            )}
          </div>
        </div>
      )}

      {/* Action buttons */}
      {isActive && (
        <div className="mb-6 flex items-center gap-3">
          <button
            onClick={() => setShowNoteForm(!showNoteForm)}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
          >
            <ClipboardList className="h-4 w-4" />
            {t("addNote")}
          </button>
          <button
            onClick={() => setShowDischarge(!showDischarge)}
            className="flex items-center gap-2 rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
          >
            <LogOut className="h-4 w-4" />
            {t("discharge")}
          </button>
          <button
            onClick={() => setShowTransfer(!showTransfer)}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-red-700"
          >
            <Ambulance className="h-4 w-4" />
            {t("transferToEmergency")}
          </button>
        </div>
      )}

      {/* Nursing note form */}
      {showNoteForm && (
        <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 font-semibold text-foreground">{t("addNote")}</h3>
          <form
            onSubmit={noteForm.handleSubmit(handleAddNote)}
            className="space-y-3"
          >
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground">
                  {t("noteType")} *
                </label>
                <select
                  {...noteForm.register("note_type")}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                >
                  <option value="observation">{t("observation")}</option>
                  <option value="medication">{t("medication")}</option>
                  <option value="procedure">{t("procedureNote")}</option>
                  <option value="shift_handover">{t("shiftHandover")}</option>
                  <option value="intake_output">{t("intakeOutput")}</option>
                  <option value="pain_assessment">{t("painAssessment")}</option>
                  <option value="wound_care">{t("woundCare")}</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground">
                  {t("shift")}
                </label>
                <select
                  {...noteForm.register("shift")}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                >
                  <option value="">—</option>
                  <option value="morning">{t("morning")}</option>
                  <option value="afternoon">{t("afternoon")}</option>
                  <option value="night">{t("night")}</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground">
                  {t("severity")}
                </label>
                <select
                  {...noteForm.register("severity")}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                >
                  <option value="">{t("severityNormal")}</option>
                  <option value="normal">{t("severityNormal")}</option>
                  <option value="warning">{t("severityWarning")}</option>
                  <option value="critical">{t("severityCritical")}</option>
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">
                {t("nursingNotes")} *
              </label>
              <textarea
                {...noteForm.register("content")}
                rows={3}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
              />
              {noteForm.formState.errors.content && (
                <p className="mt-0.5 text-xs text-red-500">
                  {noteForm.formState.errors.content.message}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={addNote.isPending}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
              >
                {addNote.isPending ? t("addingNote") : t("addNote")}
              </button>
              <button
                type="button"
                onClick={() => setShowNoteForm(false)}
                className="rounded-lg border border-input px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
              >
                {tc("cancel")}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Discharge form */}
      {showDischarge && (
        <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 font-semibold text-foreground">{t("discharge")}</h3>
          <form
            onSubmit={dischargeForm.handleSubmit(handleDischarge)}
            className="space-y-3"
          >
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground">
                  {t("dischargeType")} *
                </label>
                <select
                  {...dischargeForm.register("discharge_type")}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                >
                  <option value="improved">{t("improved")}</option>
                  <option value="recovered">{t("recovered")}</option>
                  <option value="dama">{t("dama")}</option>
                  <option value="absconded">{t("absconded")}</option>
                  <option value="deceased">{t("deceased")}</option>
                  <option value="transferred">{t("transferred")}</option>
                  <option value="referred">{t("referred")}</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground">
                  {t("dischargeDiagnosis")}
                </label>
                <input
                  {...dischargeForm.register("discharge_diagnosis")}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">
                {t("dischargeSummary")}
              </label>
              <textarea
                {...dischargeForm.register("discharge_summary")}
                rows={3}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground">
                  {t("followUpPlan")}
                </label>
                <textarea
                  {...dischargeForm.register("follow_up_plan")}
                  rows={2}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground">
                  {t("dischargeMedications")}
                </label>
                <textarea
                  {...dischargeForm.register("discharge_medications")}
                  rows={2}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={dischargePatient.isPending}
                className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-red-700 disabled:opacity-50"
              >
                <LogOut className="h-4 w-4" />
                {dischargePatient.isPending ? t("discharging") : t("discharge")}
              </button>
              <button
                type="button"
                onClick={() => setShowDischarge(false)}
                className="rounded-lg border border-input px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
              >
                {tc("cancel")}
              </button>
            </div>
          </form>
        </div>
      )}


      {/* Transfer to Emergency form */}
      {showTransfer && (
        <div className="mb-6 rounded-xl border border-red-300 bg-card p-4 shadow-[var(--shadow-card)] dark:border-red-800">
          <h3 className="mb-1 font-semibold text-foreground">
            {t("transferToEmergency")}
          </h3>
          <p className="mb-3 text-sm text-muted-foreground">{t("transferToEmergencyHint")}</p>
          <div>
            <label className="mb-1 block text-xs font-medium text-foreground">
              {t("transferReason")} *
            </label>
            <textarea
              value={transferReason}
              onChange={(e) => setTransferReason(e.target.value)}
              rows={3}
              placeholder={t("transferReasonPlaceholder")}
              className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
            />
            {transferToEmergency.isError && (
              <p className="mt-0.5 text-xs text-red-500">
                {transferToEmergency.error?.message ?? t("transferError")}
              </p>
            )}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={handleTransferToEmergency}
              disabled={transferToEmergency.isPending}
              className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-red-700 disabled:opacity-50"
            >
              <Ambulance className="h-4 w-4" />
              {transferToEmergency.isPending
                ? t("transferringToEmergency")
                : t("confirmTransferToEmergency")}
            </button>
            <button
              type="button"
              onClick={() => { setShowTransfer(false); setTransferReason(""); }}
              className="rounded-lg border border-input px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
            >
              {tc("cancel")}
            </button>
          </div>
        </div>
      )}

      {/* Nursing notes list */}
      <div>
        <h3 className="mb-3 font-semibold text-foreground">{t("nursingNotes")}</h3>
        {!notes?.length ? (
          <p className="py-8 text-center text-muted-foreground">{t("noNotes")}</p>
        ) : (
          <div className="space-y-3">
            {notes.map((note) => (
              <div
                key={note.id}
                className={cn(
                  "rounded-lg border p-3",
                  note.severity === "critical"
                    ? "border-red-300 bg-red-50/50 dark:border-red-800 dark:bg-red-950/30"
                    : note.severity === "warning"
                      ? "border-amber-300 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-950/30"
                      : "border-border bg-card"
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium capitalize text-foreground">
                      {note.note_type.replace("_", " ")}
                    </span>
                    {note.shift && (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                        {t(note.shift as "morning" | "afternoon" | "night")}
                      </span>
                    )}
                    {note.severity && note.severity !== "normal" && (
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-xs font-medium",
                          SEVERITY_STYLES[note.severity]
                        )}
                      >
                        {t(`severity${note.severity.charAt(0).toUpperCase() + note.severity.slice(1)}` as "severityWarning")}
                      </span>
                    )}
                  </div>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {formatDateTime(note.created_at)}
                  </span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">
                  {note.content}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Info field helper component.
 *
 * @param props - Field props
 * @returns Info field
 */
function InfoField({
  label,
  value,
  span2 = false,
}: {
  label: string;
  value: string;
  span2?: boolean;
}) {
  return (
    <div className={span2 ? "col-span-2" : ""}>
      <span className="text-xs text-muted-foreground">{label}</span>
      <p className="text-foreground">{value}</p>
    </div>
  );
}
