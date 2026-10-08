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
  Stethoscope,
  UserCheck,
} from "lucide-react";
import {
  useDepartments,
  useEncounterRoutes,
  useProviders,
  useRouteEncounter,
} from "@/hooks/useEncounters";
import { cn, formatDateTime } from "@/lib/utils";
import type { Encounter, ProviderWorkStatus, RouteUrgency } from "@aifya/shared";

const URGENCY_LABEL_KEYS = {
  emergency: "referUrgencyEmergency",
  urgent: "referUrgencyUrgent",
  routine: "referUrgencyRoutine",
} as const;

const URGENCIES: readonly RouteUrgency[] = ["emergency", "urgent", "routine"];

/**
 * The availability picker's values: a coarse "can be assigned now" filter, an
 * explicit work status, or everyone in the unit.
 */
type AvailabilityFilter = "available" | "all" | ProviderWorkStatus;

const AVAILABILITY_OPTIONS: readonly AvailabilityFilter[] = [
  "available",
  "all",
  "busy",
  "on_leave",
  "off_duty",
  "unavailable",
];

const AVAILABILITY_LABEL_KEYS: Record<AvailabilityFilter, string> = {
  available: "referAvailabilityAvailable",
  all: "referAvailabilityAll",
  busy: "referStatusBusy",
  on_leave: "referStatusOnLeave",
  off_duty: "referStatusOffDuty",
  unavailable: "referStatusUnavailable",
};

const STATUS_BADGE: Record<ProviderWorkStatus, string> = {
  available:
    "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  busy: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  on_leave: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  off_duty:
    "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  unavailable: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

const STATUS_DOT: Record<ProviderWorkStatus, string> = {
  available: "bg-green-500",
  busy: "bg-amber-500",
  on_leave: "bg-blue-500",
  off_duty: "bg-slate-400",
  unavailable: "bg-red-500",
};

const STATUS_LABEL_KEYS: Record<ProviderWorkStatus, string> = {
  available: "referStatusAvailable",
  busy: "referStatusBusy",
  on_leave: "referStatusOnLeave",
  off_duty: "referStatusOffDuty",
  unavailable: "referStatusUnavailable",
};

/**
 * Consultation-room hand-off: the clinician directs the patient to the unit
 * that should see them next and, where it matters, to the specific qualified
 * provider in that unit.
 *
 * Routing records an internal referral and re-queues the encounter in the
 * destination unit, so the patient actually turns up in that unit's queue
 * rather than merely being marked as sent. The picker narrows by department,
 * then specialty, then working availability - account activation is never
 * enough, because an active clinician can still be on leave or already busy.
 *
 * @param props - The encounter being routed
 * @returns The consultation-room routing content
 */
export function RoutePatientPanel({ encounter }: { encounter: Encounter }) {
  const t = useTranslations("opd");

  const [departmentId, setDepartmentId] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [availability, setAvailability] =
    useState<AvailabilityFilter>("available");
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

  // The provider list is the heart of the hand-off: clinical staff of the
  // chosen unit, filtered by specialty and by what they can actually take.
  const providersQuery = useProviders({
    departmentId: departmentId || undefined,
    specialty: specialty || undefined,
    workStatus:
      availability !== "available" && availability !== "all"
        ? availability
        : undefined,
    availableOnly: availability === "available",
    enabled: !!departmentId,
  });
  const providers = providersQuery.data?.items ?? [];
  const specialties = providersQuery.data?.specialties ?? [];
  const selectedProvider = providers.find((p) => p.id === doctorId) ?? null;

  const { data: routes } = useEncounterRoutes(encounter.id);
  const routePatient = useRouteEncounter(encounter.id);

  const handleDepartmentChange = (nextId: string) => {
    setDepartmentId(nextId);
    setSpecialty("");
    setDoctorId("");
    setError("");
    setSentTo(null);
  };

  const handleSpecialtyChange = (nextSpecialty: string) => {
    setSpecialty(nextSpecialty);
    setDoctorId("");
  };

  const handleAvailabilityChange = (next: AvailabilityFilter) => {
    setAvailability(next);
    setDoctorId("");
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
          setSpecialty("");
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

        {/* Department -> specialty -> availability, the order the question is
            actually asked at the bedside. */}
        <div className="grid gap-4 sm:grid-cols-3">
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
              {t("referSpecialty")}
            </label>
            <select
              value={specialty}
              onChange={(e) => handleSpecialtyChange(e.target.value)}
              disabled={!departmentId || specialties.length === 0}
              className={fieldClasses}
            >
              <option value="">{t("referSpecialtyAll")}</option>
              {specialties.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("referAvailability")}
            </label>
            <select
              value={availability}
              onChange={(e) =>
                handleAvailabilityChange(e.target.value as AvailabilityFilter)
              }
              disabled={!departmentId}
              className={fieldClasses}
            >
              {AVAILABILITY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {t(AVAILABILITY_LABEL_KEYS[option])}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Who is available to take the patient. */}
        <div className="mt-4">
          <div className="mb-1 flex items-center gap-2">
            <UserCheck className="h-4 w-4 text-primary" />
            <span className="text-xs font-medium text-muted-foreground">
              {t("referProvidersTitle")}
            </span>
            {departmentId && providers.length > 0 && (
              <span className="ml-auto text-xs text-muted-foreground">
                {t("referProviderCount", { count: providers.length })}
              </span>
            )}
          </div>

          {!departmentId ? (
            <p className="rounded-lg border border-dashed border-border px-3 py-3 text-sm text-muted-foreground">
              {t("referProviderChooseUnit")}
            </p>
          ) : providersQuery.isLoading ? (
            <p className="px-1 py-3 text-sm text-muted-foreground">
              {t("referProviderLoading")}
            </p>
          ) : providers.length === 0 ? (
            <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 dark:border-amber-800 dark:bg-amber-950">
              <p className="text-sm text-amber-800 dark:text-amber-200">
                {t("referProviderEmpty")}
              </p>
            </div>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2">
              {providers.map((provider) => {
                const selected = provider.id === doctorId;
                return (
                  <li key={provider.id}>
                    <button
                      type="button"
                      onClick={() => setDoctorId(selected ? "" : provider.id)}
                      aria-pressed={selected}
                      className={cn(
                        "w-full rounded-lg border p-3 text-left transition-colors",
                        selected
                          ? "border-primary bg-primary/5 ring-1 ring-primary"
                          : "border-border bg-background hover:bg-muted/50"
                      )}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-semibold text-foreground">
                          {provider.full_name}
                        </span>
                        <span
                          className={cn(
                            "inline-flex flex-shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
                            STATUS_BADGE[provider.work_status]
                          )}
                        >
                          <span
                            className={cn(
                              "h-1.5 w-1.5 rounded-full",
                              STATUS_DOT[provider.work_status]
                            )}
                          />
                          {t(STATUS_LABEL_KEYS[provider.work_status])}
                        </span>
                      </span>
                      <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                        {[provider.title, provider.role, provider.specialty]
                          .filter(Boolean)
                          .join(" \u00b7 ")}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <p className="mt-2 text-xs text-muted-foreground">
            {t("referProviderAnyHint")}
          </p>
        </div>

        {selectedProvider && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/5 px-3 py-2">
            <Stethoscope className="h-4 w-4 shrink-0 text-primary" />
            <p className="text-sm text-foreground">
              {t("referProviderSelected", {
                name: selectedProvider.full_name,
              })}
            </p>
          </div>
        )}

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
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
        </div>

        <div className="mt-4 grid gap-4">
          <div>
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

          <div>
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
                  {t(URGENCY_LABEL_KEYS[route.urgency])}{" "}
                  {"\u00b7"} {formatDateTime(route.referral_date)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
