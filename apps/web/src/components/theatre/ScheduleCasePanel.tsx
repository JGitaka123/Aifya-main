"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, Send, XCircle } from "lucide-react";
import { useScheduleCase, useTheatres } from "@/hooks/useTheatre";
import { usePatientSearch } from "@/hooks/usePatients";
import { useStaffDirectory } from "@/hooks/useHR";
import type { SurgicalPriority } from "@aifya/shared";

/** Priorities a scheduler may pick, most routine first. */
const PRIORITIES: readonly SurgicalPriority[] = ["elective", "urgent", "emergency"];

/**
 * Book a patient into theatre.
 *
 * Theatre cases are raised here as well as from the consultation room, so the
 * form takes a patient, a procedure and an optional room. The case number the
 * backend allocates is handed back so the board can confirm what was booked.
 *
 * @param props.onScheduled - Called with the new case number
 * @param props.onCancel - Called when the operator closes the form
 * @returns Schedule-case form
 */
export function ScheduleCasePanel({
  onScheduled,
  onCancel,
}: {
  onScheduled: (caseNumber: string) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("theatre");
  const [query, setQuery] = useState("");
  const [patientId, setPatientId] = useState("");
  const [patientLabel, setPatientLabel] = useState("");
  const [procedure, setProcedure] = useState("");
  const [scheduledDate, setScheduledDate] = useState(() => {
    const next = new Date(Date.now() + 60 * 60 * 1000);
    next.setMinutes(0, 0, 0);
    const pad = (n: number) => String(n).padStart(2, "0");
    return [
      next.getFullYear(),
      "-",
      pad(next.getMonth() + 1),
      "-",
      pad(next.getDate()),
      "T",
      pad(next.getHours()),
      ":",
      pad(next.getMinutes()),
    ].join("");
  });
  const [theatreId, setTheatreId] = useState("");
  const [surgeonId, setSurgeonId] = useState("");
  const [priority, setPriority] = useState<SurgicalPriority>("elective");
  const [duration, setDuration] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: matches, isFetching } = usePatientSearch(query, 1, 6, {
    enabled: query.trim().length >= 2,
  });
  const { data: theatres } = useTheatres();
  const { data: surgeons } = useStaffDirectory("doctor");
  const schedule = useScheduleCase();

  const handleSubmit = () => {
    if (!patientId) {
      setError(t("patientRequired"));
      return;
    }
    if (!procedure.trim()) {
      setError(t("procedureRequired"));
      return;
    }
    if (!surgeonId) {
      setError(t("surgeonRequired"));
      return;
    }
    setError(null);
    schedule.mutate(
      {
        patient_id: patientId,
        procedure_name: procedure.trim(),
        scheduled_date: new Date(scheduledDate).toISOString(),
        lead_surgeon_id: surgeonId,
        theatre_id: theatreId || null,
        priority,
        estimated_duration_min: duration ? Number(duration) : undefined,
        notes: notes.trim() || null,
      },
      {
        onSuccess: (created) => onScheduled(created.case_number),
        onError: (err) => setError(err.message ?? t("scheduleFailed")),
      }
    );
  };

  const selectClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background";
  const labelClasses = "mb-1 block text-xs font-medium text-muted-foreground";
  const results = matches?.items ?? [];

  return (
    <div className="rounded-xl border border-blue-300 bg-blue-50/40 p-4 shadow-[var(--shadow-card)] dark:border-blue-800 dark:bg-blue-950/20">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{t("scheduleCase")}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">{t("scheduleSubtitle")}</p>
        </div>
        <button
          onClick={onCancel}
          className="inline-flex shrink-0 items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <XCircle className="h-3.5 w-3.5" />
          {t("cancel")}
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="block sm:col-span-2">
          <span className={labelClasses}>{t("schedulePatient")}</span>
          {patientId ? (
            <div className="flex items-center justify-between gap-2 rounded-lg border border-input bg-background px-3 py-2 text-sm">
              <span className="font-medium text-foreground">{patientLabel}</span>
              <button
                onClick={() => {
                  setPatientId("");
                  setPatientLabel("");
                }}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {t("changePatient")}
              </button>
            </div>
          ) : (
            <>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("schedulePatientPlaceholder")}
                className={selectClasses}
              />
              {query.trim().length >= 2 && (
                <div className="mt-1 max-h-40 overflow-y-auto rounded-lg border border-border bg-card">
                  {isFetching && results.length === 0 ? (
                    <p className="px-3 py-2 text-xs text-muted-foreground">{t("loading")}</p>
                  ) : results.length === 0 ? (
                    <p className="px-3 py-2 text-xs text-muted-foreground">{t("noPatientMatch")}</p>
                  ) : (
                    results.map((patient) => (
                      <button
                        key={patient.id}
                        onClick={() => {
                          setPatientId(patient.id);
                          setPatientLabel(
                            patient.first_name +
                              " " +
                              patient.last_name +
                              " \u00b7 " +
                              patient.mrn
                          );
                          setQuery("");
                        }}
                        className="block w-full px-3 py-2 text-left text-sm text-foreground hover:bg-muted/60"
                      >
                        {patient.first_name} {patient.last_name}
                        <span className="ml-2 text-xs text-muted-foreground">{patient.mrn}</span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </>
          )}
        </div>

        <label className="block sm:col-span-2">
          <span className={labelClasses}>{t("scheduleProcedure")}</span>
          <input
            value={procedure}
            onChange={(e) => setProcedure(e.target.value)}
            placeholder={t("scheduleProcedurePlaceholder")}
            className={selectClasses}
          />
        </label>

        <label className="block">
          <span className={labelClasses}>{t("scheduleWhen")}</span>
          <input
            type="datetime-local"
            value={scheduledDate}
            onChange={(e) => setScheduledDate(e.target.value)}
            className={selectClasses}
          />
        </label>

        <label className="block">
          <span className={labelClasses}>{t("schedulePriority")}</span>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as SurgicalPriority)}
            className={selectClasses}
          >
            {PRIORITIES.map((value) => (
              <option key={value} value={value}>
                {t("priorityType." + value)}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className={labelClasses}>{t("scheduleSurgeon")}</span>
          <select
            value={surgeonId}
            onChange={(e) => setSurgeonId(e.target.value)}
            className={selectClasses}
          >
            <option value="">{t("scheduleSurgeonPlaceholder")}</option>
            {(surgeons?.items ?? []).map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.title ? doctor.title + " " : ""}
                {doctor.first_name} {doctor.last_name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className={labelClasses}>{t("scheduleTheatre")}</span>
          <select
            value={theatreId}
            onChange={(e) => setTheatreId(e.target.value)}
            className={selectClasses}
          >
            <option value="">{t("unassigned")}</option>
            {(theatres ?? []).map((room) => (
              <option key={room.id} value={room.id}>
                {room.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className={labelClasses}>{t("scheduleDuration")}</span>
          <input
            type="number"
            min={1}
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            className={selectClasses}
          />
        </label>

        <label className="block sm:col-span-2">
          <span className={labelClasses}>{t("scheduleNotes")}</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className={selectClasses}
          />
        </label>
      </div>

      {error && <p className="mt-3 text-xs text-red-600 dark:text-red-400">{error}</p>}

      <div className="mt-4 flex items-center justify-end">
        <button
          onClick={handleSubmit}
          disabled={schedule.isPending}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {schedule.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
          {schedule.isPending ? t("scheduling") : t("scheduleCase")}
        </button>
      </div>
    </div>
  );
}
