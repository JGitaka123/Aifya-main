"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft, Loader2, Save, Scissors } from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useRecordOperativeNotes,
  useSurgicalCase,
  useTheatres,
  useUpdateCaseStatus,
} from "@/hooks/useTheatre";
import { usePatient } from "@/hooks/usePatients";
import { useStaffDirectory } from "@/hooks/useHR";
import { cn } from "@/lib/utils";

/** Statuses a case may move to from its current one. */
const STATUS_FLOW: Record<string, readonly string[]> = {
  scheduled: ["preop", "postponed", "cancelled"],
  preop: ["in_progress", "postponed", "cancelled"],
  in_progress: ["in_recovery", "completed", "cancelled"],
  in_recovery: ["completed"],
  completed: [],
  cancelled: ["scheduled"],
  postponed: ["scheduled"],
};

/** Timestamps shown on the case timeline, in theatre order. */
const TIMESTAMPS = [
  "preop_start",
  "surgery_start",
  "surgery_end",
  "recovery_start",
  "recovery_end",
] as const;

const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  preop: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  in_progress: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  in_recovery: "bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  postponed: "bg-muted text-muted-foreground",
};

/**
 * One surgical case: what is being done, to whom, and how far it has got.
 *
 * The board only lists cases; the work happens here. A clinician moves the case
 * through pre-op, surgery and recovery - the backend stamps the matching time -
 * and records the operative notes that close the case.
 *
 * @returns Surgical case detail page
 */
export default function SurgicalCasePage() {
  const t = useTranslations("theatre");
  const { caseId } = useParams<{ caseId: string }>();
  const { data: surgicalCase, isLoading, isError } = useSurgicalCase(caseId);
  const { data: theatres } = useTheatres();
  const { data: staff } = useStaffDirectory();
  const { data: patient } = usePatient(surgicalCase?.patient_id ?? "");
  const updateStatus = useUpdateCaseStatus(caseId);
  const recordNotes = useRecordOperativeNotes(caseId);

  const [findings, setFindings] = useState("");
  const [notes, setNotes] = useState("");
  const [complications, setComplications] = useState("");
  const [bloodLoss, setBloodLoss] = useState("");
  const [postop, setPostop] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!surgicalCase) return;
    setFindings(surgicalCase.operative_findings ?? "");
    setNotes(surgicalCase.operative_notes ?? "");
    setComplications(surgicalCase.complications ?? "");
    setBloodLoss(
      surgicalCase.blood_loss_ml === null ? "" : String(surgicalCase.blood_loss_ml)
    );
    setPostop(surgicalCase.postop_instructions ?? "");
  }, [surgicalCase]);

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-5xl items-center gap-2 p-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t("loading")}
      </div>
    );
  }

  if (isError || !surgicalCase) {
    return (
      <div className="mx-auto max-w-5xl p-8">
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {t("caseNotFound")}
        </p>
        <Link
          href="/theatre"
          className="mt-4 inline-flex items-center gap-1 text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          <ArrowLeft className="h-4 w-4" />
          {t("back")}
        </Link>
      </div>
    );
  }

  const room = (theatres ?? []).find((item) => item.id === surgicalCase.theatre_id);
  const surgeon = (staff?.items ?? []).find((item) => item.id === surgicalCase.lead_surgeon_id);
  const patientName = patient
    ? patient.first_name + " " + patient.last_name
    : surgicalCase.patient_id;

  const nextStatuses = STATUS_FLOW[surgicalCase.status] ?? [];

  const handleStatus = (next: string) => {
    setSaved(false);
    setError(null);
    updateStatus.mutate(
      { status: next },
      {
        onError: (err) => setError(err.message ?? t("statusUpdateFailed")),
      }
    );
  };

  const handleSaveNotes = () => {
    setError(null);
    setSaved(false);
    recordNotes.mutate(
      {
        operative_findings: findings.trim() || null,
        operative_notes: notes.trim() || null,
        complications: complications.trim() || null,
        blood_loss_ml: bloodLoss ? Number(bloodLoss) : null,
        postop_instructions: postop.trim() || null,
      },
      {
        onSuccess: () => setSaved(true),
        onError: (err) => setError(err.message ?? t("notesSaveFailed")),
      }
    );
  };

  const inputClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background";
  const labelClasses = "mb-1 block text-xs font-medium text-muted-foreground";

  const overview: { label: string; value: string }[] = [
    { label: t("patient"), value: patientName },
    { label: t("patientMrn"), value: patient?.mrn ?? "-" },
    { label: t("procedure"), value: surgicalCase.procedure_name },
    {
      label: t("theatreLabel"),
      value: room?.name ?? t("unassigned"),
    },
    {
      label: t("surgeon"),
      value: surgeon
        ? (surgeon.title ? surgeon.title + " " : "") +
          surgeon.first_name +
          " " +
          surgeon.last_name
        : "-",
    },
    { label: t("priorityType." + surgicalCase.priority), value: t("priority") },
    { label: t("scheduledFor"), value: new Date(surgicalCase.scheduled_date).toLocaleString() },
    {
      label: t("duration"),
      value: t("durationUnit", { count: surgicalCase.estimated_duration_min }),
    },
    { label: t("anaesthesiaLabel"), value: surgicalCase.anaesthesia_type ?? "-" },
    { label: t("diagnosisLabel"), value: surgicalCase.diagnosis ?? "-" },
    { label: t("lateralityLabel"), value: surgicalCase.laterality ?? "-" },
    {
      label: t("statusLabel"),
      value: t("status." + surgicalCase.status),
    },
  ];

  return (
    <div className="mx-auto max-w-5xl animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <div>
        <Link
          href="/theatre"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {t("back")}
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
            <Scissors className="h-5 w-5 text-primary" />
            {surgicalCase.case_number}
          </h1>
          <span
            className={cn(
              "rounded-full px-2.5 py-0.5 text-xs font-medium",
              STATUS_STYLES[surgicalCase.status]
            )}
          >
            {t("status." + surgicalCase.status)}
          </span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{surgicalCase.procedure_name}</p>
      </div>

      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h2 className="mb-3 text-sm font-semibold text-foreground">{t("overview")}</h2>
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
          {overview.map((row) => (
            <div key={row.label + row.value}>
              <dt className="text-xs text-muted-foreground">{row.label}</dt>
              <dd className="text-sm font-medium text-foreground">{row.value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h2 className="mb-3 text-sm font-semibold text-foreground">{t("setStatus")}</h2>
        {nextStatuses.length === 0 ? (
          <p className="text-xs text-muted-foreground">{t("noFurtherSteps")}</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {nextStatuses.map((next) => (
              <button
                key={next}
                onClick={() => handleStatus(next)}
                disabled={updateStatus.isPending}
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground hover:bg-muted/60 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {updateStatus.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {t("status." + next)}
              </button>
            ))}
          </div>
        )}

        <h3 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("timeline")}
        </h3>
        <ul className="space-y-1">
          {TIMESTAMPS.map((key) => (
            <li key={key} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{t("timestamps." + key)}</span>
              <span className="font-medium text-foreground">
                {surgicalCase[key]
                  ? new Date(surgicalCase[key] as string).toLocaleString()
                  : "-"}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h2 className="mb-3 text-sm font-semibold text-foreground">
          {t("operativeNotesTitle")}
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className={labelClasses}>{t("operativeFindingsLabel")}</span>
            <textarea
              value={findings}
              onChange={(e) => setFindings(e.target.value)}
              rows={2}
              className={inputClasses}
            />
          </label>
          <label className="block sm:col-span-2">
            <span className={labelClasses}>{t("operativeNotesLabel")}</span>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className={inputClasses}
            />
          </label>
          <label className="block">
            <span className={labelClasses}>{t("complicationsLabel")}</span>
            <input
              value={complications}
              onChange={(e) => setComplications(e.target.value)}
              className={inputClasses}
            />
          </label>
          <label className="block">
            <span className={labelClasses}>{t("bloodLossLabel")}</span>
            <input
              type="number"
              min={0}
              value={bloodLoss}
              onChange={(e) => setBloodLoss(e.target.value)}
              className={inputClasses}
            />
          </label>
          <label className="block sm:col-span-2">
            <span className={labelClasses}>{t("postopInstructionsLabel")}</span>
            <textarea
              value={postop}
              onChange={(e) => setPostop(e.target.value)}
              rows={2}
              className={inputClasses}
            />
          </label>
        </div>

        {error && <p className="mt-3 text-xs text-red-600 dark:text-red-400">{error}</p>}
        {saved && (
          <p className="mt-3 text-xs text-green-700 dark:text-green-300">{t("notesSaved")}</p>
        )}

        <div className="mt-4 flex items-center justify-end">
          <button
            onClick={handleSaveNotes}
            disabled={recordNotes.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {recordNotes.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            {recordNotes.isPending ? t("saving") : t("saveNotes")}
          </button>
        </div>
      </div>
    </div>
  );
}
