"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Loader2,
  Send,
  Share2,
} from "lucide-react";
import { useDepartments, useEncounterRoutes, useRouteEncounter } from "@/hooks/useEncounters";
import { useStaffDirectory } from "@/hooks/useHR";
import { formatDateTime } from "@/lib/utils";
import type { Encounter, RouteUrgency } from "@aifya/shared";

const URGENCY_LABEL_KEYS = {
  emergency: "referUrgencyEmergency",
  urgent: "referUrgencyUrgent",
  routine: "referUrgencyRoutine",
} as const;

const URGENCIES: readonly RouteUrgency[] = ["emergency", "urgent", "routine"];

/**
 * Consultation-room hand-off: the clinician directs the patient to the unit
 * that should see them next (Dental, Physiotherapy, Laboratory, Pharmacy...).
 *
 * Routing records an internal referral and re-queues the encounter in the
 * destination unit, so the patient actually turns up in that unit's queue
 * rather than merely being marked as sent.
 *
 * @param props - The encounter being routed, and the routing trail
 * @returns The consultation-room routing content
 */
export function RoutePatientPanel({ encounter }: { encounter: Encounter }) {
  const t = useTranslations("opd");

  const [departmentId, setDepartmentId] = useState("");
  const [doctorId, setDoctorId] = useState("");
  const [urgency, setUrgency] = useState<RouteUrgency>("routine");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [sentTo, setSentTo] = useState<{ name: string; number: string } | null>(
    null
  );

  // Only units the facility has actually configured can be a destination, so
  // a routed patient always lands in a real queue.
  const { data: departmentDirectory } = useDepartments();
  const departments = useMemo(
    () => departmentDirectory ?? [],
    [departmentDirectory]
  );
  const destinations = useMemo(
    () => departments.filter((d) => d.id !== encounter.department_id),
    [departments, encounter.department_id]
  );
  const destination = destinations.find((d) => d.id === departmentId);
  // A unit with nobody assigned cannot pick the patient up, so the hand-off
  // would quietly strand them. Warn, but still allow the doctor to send them.
  const destinationUnstaffed = Boolean(
    destination && destination.staff_count === 0
  );

  // Clinicians are narrowed to the chosen unit, so a patient sent to Dental is
  // not handed to a general clinician.
  const { data: doctorDirectory } = useStaffDirectory(
    "doctor",
    departmentId || undefined
  );
  const doctors = (doctorDirectory?.items ?? []).filter((d) => d.is_active);

  const { data: routes } = useEncounterRoutes(encounter.id);
  const routePatient = useRouteEncounter(encounter.id);

  const handleDepartmentChange = (nextId: string) => {
    setDepartmentId(nextId);
    setDoctorId("");
    setError("");
    setSentTo(null);
  };

  const handleSubmit = () => {
    if (!departmentId) {
      setError(t("referDestinationRequired"));
      return;
    }
    if (!reason.trim()) {
      setError(t("referReasonRequired"));
      return;
    }
    setError("");
    routePatient.mutate(
      {
        receiving_department_id: departmentId,
        receiving_doctor_id: doctorId || null,
        urgency,
        reason: reason.trim(),
        notes: notes.trim() || null,
      },
      {
        onSuccess: (result) => {
          setSentTo({
            name: result.receiving_department_name ?? t("referUnassigned"),
            number: result.referral_number,
          });
          setDepartmentId("");
          setDoctorId("");
          setUrgency("routine");
          setReason("");
          setNotes("");
        },
        onError: (err: Error) => {
          setError(err.message || t("referFailed"));
        },
      }
    );
  };

  const fieldClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background disabled:cursor-not-allowed disabled:opacity-60";

  if (departments.length === 0) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950">
        <p className="flex items-center gap-2 text-sm text-amber-800 dark:text-amber-200">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {t("noDepartmentsConfigured")}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <div className="mb-1 flex items-center gap-2">
          <Share2 className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">
            {t("referTitle")}
          </h3>
        </div>
        <p className="mb-4 text-xs text-muted-foreground">{t("referSubtitle")}</p>

        {sentTo && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-300 bg-green-50 px-3 py-2 dark:border-green-800 dark:bg-green-950">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            <p className="text-sm text-green-800 dark:text-green-200">
              {t("referSuccess", { department: sentTo.name, number: sentTo.number })}
            </p>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("referDestination")}
            </label>
            <select
              value={departmentId}
              onChange={(e) => handleDepartmentChange(e.target.value)}
              className={fieldClasses}
            >
              <option value="">{t("referDestinationPlaceholder")}</option>
              {destinations.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                </option>
              ))}
            </select>
            {destinations.length === 0 && (
              <p className="mt-1 text-xs text-muted-foreground">
                {t("referAlreadyThere")}
              </p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("referClinician")}
            </label>
            <select
              value={doctorId}
              onChange={(e) => setDoctorId(e.target.value)}
              disabled={!departmentId || doctors.length === 0}
              className={fieldClasses}
            >
              <option value="">{t("referAnyClinician")}</option>
              {doctors.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {`${doctor.first_name} ${doctor.last_name}`.trim()}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("referUrgency")}
            </label>
            <select
              value={urgency}
              onChange={(e) => setUrgency(e.target.value as RouteUrgency)}
              className={fieldClasses}
            >
              {URGENCIES.map((value) => (
                <option key={value} value={value}>
                  {t(URGENCY_LABEL_KEYS[value])}
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("referReason")}
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              placeholder={t("referReasonPlaceholder")}
              className={fieldClasses}
            />
          </div>

          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("referNotes")}
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className={fieldClasses}
            />
          </div>
        </div>

        {destinationUnstaffed && !error && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 dark:border-amber-800 dark:bg-amber-950">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <p className="text-sm text-amber-800 dark:text-amber-200">
              {t("referNoClinician", {
                department: destination?.name ?? "",
              })}
            </p>
          </div>
        )}

        {error && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 dark:border-red-800 dark:bg-red-950">
            <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
            <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={routePatient.isPending || destinations.length === 0}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow transition-all hover:opacity-90 disabled:opacity-50"
          >
            {routePatient.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {routePatient.isPending ? t("referSubmitting") : t("referSubmit")}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h3 className="mb-3 text-sm font-semibold text-foreground">
          {t("referHistoryTitle")}
        </h3>
        {!routes || routes.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("referHistoryEmpty")}</p>
        ) : (
          <ul className="space-y-3">
            {routes.map((route) => (
              <li
                key={route.id}
                className="rounded-lg border border-border bg-muted/40 p-3"
              >
                <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                  <span>{route.referring_department_name ?? t("referUnassigned")}</span>
                  <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                  <span>{route.receiving_department_name ?? t("referUnassigned")}</span>
                  <span className="ml-auto font-mono text-xs text-muted-foreground">
                    {route.referral_number}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{route.reason}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t(URGENCY_LABEL_KEYS[route.urgency])} ·{" "}
                  {formatDateTime(route.referral_date)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}