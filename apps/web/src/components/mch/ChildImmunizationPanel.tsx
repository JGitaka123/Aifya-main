"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CheckCircle2,
  Pencil,
  Plus,
  Syringe,
  Trash2,
} from "lucide-react";
import type {
  ChildRecordListItem,
  ImmunizationCreate,
  ImmunizationResponse,
  ImmunizationScheduleItem,
  ImmunizationUpdate,
} from "@aifya/shared";
import {
  useDeleteImmunization,
  useImmunizations,
  useImmunizationSchedule,
  useRecordImmunization,
  useUpdateImmunization,
} from "@/hooks/useMCH";
import { ApiError } from "@/lib/api-client";
import { cn, formatDate } from "@/lib/utils";

/** Weeks of grace before a due dose is called overdue (mirrors the API). */
const GRACE_WEEKS = 2;

/** Injection and oral sites accepted by the API. */
const SITES = ["left_thigh", "right_thigh", "left_arm", "right_arm", "oral"] as const;

/** Administration routes accepted by the API. */
const ROUTES = ["im", "sc", "oral", "id"] as const;

type SiteKey =
  | "site_left_thigh"
  | "site_right_thigh"
  | "site_left_arm"
  | "site_right_arm"
  | "site_oral";
type RouteKey = "route_im" | "route_sc" | "route_oral" | "route_id";

/**
 * Read the dose number encoded in a schedule code, e.g. PENTA_3 gives 3.
 *
 * @param vaccineCode - Schedule vaccine code
 * @returns Dose number, defaulting to 1
 */
function doseNumberOf(vaccineCode: string): number {
  const match = vaccineCode.match(/_(\d+)$/);
  // OPV_0 is the birth dose, so clamp to 1 (the API requires dose >= 1).
  return match ? Math.max(1, Number(match[1])) : 1;
}

/**
 * Whole weeks between a date of birth and today.
 *
 * @param dateOfBirth - Child date of birth in YYYY-MM-DD form
 * @returns Completed weeks of age
 */
function ageInWeeks(dateOfBirth: string): number {
  const born = new Date(dateOfBirth).getTime();
  if (Number.isNaN(born)) return 0;
  return Math.max(0, Math.floor((Date.now() - born) / (7 * 24 * 60 * 60 * 1000)));
}

/**
 * Today as a YYYY-MM-DD string in local time.
 *
 * @returns Local ISO date
 */
function todayIso(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60 * 1000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

interface ChildImmunizationPanelProps {
  /** Child whose doses are being tracked. */
  child: ChildRecordListItem;
}

/**
 * Immunization panel for one child: the KEPI doses still due, the doses
 * already given, and a form to record a new dose.
 *
 * @param props - Component props
 * @returns Immunization tracking panel
 */
export function ChildImmunizationPanel({ child }: ChildImmunizationPanelProps) {
  const t = useTranslations("mch");
  const tc = useTranslations("common");
  const { data: immunizations, isLoading } = useImmunizations(child.id);
  const { data: schedule } = useImmunizationSchedule();
  const recordDose = useRecordImmunization();
  const updateDose = useUpdateImmunization();
  const deleteDose = useDeleteImmunization();

  /** Dose currently loaded into the form for correction, if any. */
  const [editing, setEditing] = useState<ImmunizationResponse | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [vaccineCode, setVaccineCode] = useState("");
  const [dateGiven, setDateGiven] = useState(todayIso());
  const [batchNumber, setBatchNumber] = useState("");
  const [site, setSite] = useState("");
  const [route, setRoute] = useState("");
  const [adverseEvent, setAdverseEvent] = useState(false);
  const [adverseDetails, setAdverseDetails] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const givenCodes = new Set(
    (immunizations ?? []).map((dose) => dose.vaccine_code.toUpperCase())
  );
  const givenNames = new Set(
    (immunizations ?? []).map((dose) => dose.vaccine_name.trim().toLowerCase())
  );

  /**
   * Whether a scheduled dose already has a matching record.
   *
   * @param item - Schedule entry to test
   * @returns True when the dose is recorded
   */
  const isGiven = (item: ImmunizationScheduleItem) =>
    givenCodes.has(item.vaccine_code.toUpperCase()) ||
    givenNames.has(item.vaccine_name.trim().toLowerCase());

  const weeks = ageInWeeks(child.date_of_birth);
  const dueDoses = (schedule ?? []).filter((item) => !isGiven(item));
  const overdueDoses = dueDoses.filter(
    (item) => weeks >= item.due_age_weeks + GRACE_WEEKS
  );
  const nextDose = dueDoses[0];

  const selected = (schedule ?? []).find(
    (item) => item.vaccine_code === vaccineCode
  );

  /**
   * Pick a vaccine and prefill the site and route from the schedule.
   *
   * @param code - Selected schedule vaccine code
   */
  const handleVaccineChange = (code: string) => {
    setVaccineCode(code);
    const entry = (schedule ?? []).find((item) => item.vaccine_code === code);
    setSite(entry?.site ?? "");
    setRoute(entry?.route ?? "");
  };

  /** Return the dose form to a blank new-dose state. */
  const resetForm = () => {
    setEditing(null);
    setVaccineCode("");
    setBatchNumber("");
    setSite("");
    setRoute("");
    setAdverseEvent(false);
    setAdverseDetails("");
    setNotes("");
    setDateGiven(todayIso());
    setError("");
  };

  /**
   * Load a recorded dose into the form so it can be corrected.
   *
   * @param dose - Dose to correct
   */
  const startEdit = (dose: ImmunizationResponse) => {
    setEditing(dose);
    setVaccineCode(dose.vaccine_code);
    setDateGiven(dose.date_given);
    setBatchNumber(dose.batch_number ?? "");
    setSite(dose.site ?? "");
    setRoute(dose.route ?? "");
    setAdverseEvent(dose.adverse_event);
    setAdverseDetails(dose.adverse_event_description ?? "");
    setNotes(dose.notes ?? "");
    setError("");
    setShowForm(true);
  };

  /** Record a new dose, or save the correction when one is being edited. */
  const handleSubmit = async () => {
    if (!vaccineCode || (!selected && !editing)) {
      setError(t("vaccineRequired"));
      return;
    }
    if (!dateGiven) {
      setError(t("dateGivenRequired"));
      return;
    }
    setError("");

    const payload: ImmunizationUpdate = {
      vaccine_code: selected?.vaccine_code ?? vaccineCode,
      vaccine_name:
        selected?.vaccine_name ?? editing?.vaccine_name ?? vaccineCode,
      dose_number: selected
        ? doseNumberOf(selected.vaccine_code)
        : (editing?.dose_number ?? 1),
      date_given: dateGiven,
      batch_number: batchNumber || null,
      site: site || null,
      route: route || null,
      adverse_event: adverseEvent,
      adverse_event_description: adverseEvent ? adverseDetails || null : null,
      notes: notes || null,
    };

    try {
      if (editing) {
        await updateDose.mutateAsync({
          immunizationId: editing.id,
          ...payload,
        });
      } else {
        const createPayload: ImmunizationCreate = {
          child_record_id: child.id,
          vaccine_code: payload.vaccine_code ?? vaccineCode,
          vaccine_name: payload.vaccine_name ?? vaccineCode,
          dose_number: payload.dose_number ?? 1,
          date_given: dateGiven,
          batch_number: payload.batch_number ?? null,
          site: payload.site ?? null,
          route: payload.route ?? null,
          adverse_event: adverseEvent,
          adverse_event_description: payload.adverse_event_description ?? null,
          notes: payload.notes ?? null,
        };
        await recordDose.mutateAsync({ ...createPayload, childId: child.id });
      }
      resetForm();
      setShowForm(false);
    } catch (error) {
      setError(
        error instanceof ApiError && error.message
          ? error.message
          : tc("retrySync")
      );
    }
  };

  /**
   * Soft-delete a dose that was recorded in error.
   *
   * @param dose - Dose to remove
   */
  const handleDelete = async (dose: ImmunizationResponse) => {
    if (!window.confirm(t("confirmDeleteDose"))) return;
    setError("");
    try {
      await deleteDose.mutateAsync({ immunizationId: dose.id });
      if (editing?.id === dose.id) {
        resetForm();
        setShowForm(false);
      }
    } catch (error) {
      setError(
        error instanceof ApiError && error.message
          ? error.message
          : tc("retrySync")
      );
    }
  };

  const saving = recordDose.isPending || updateDose.isPending;
  const removing = deleteDose.isPending;

  const inputClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm";
  const labelClass = "mb-1 block text-sm font-medium text-foreground";
  const cellClass = "rounded-lg border border-border bg-muted/20 p-3";

  return (
    <div className="border-t border-border bg-muted/10 px-4 py-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Syringe className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">
            {t("immunizations")}
          </h3>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {immunizations?.length ?? 0} {t("doses")}
          </span>
          {overdueDoses.length > 0 ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800 dark:bg-red-950 dark:text-red-200">
              <AlertTriangle className="h-3 w-3" />
              {overdueDoses.length} {t("overdue")}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-200">
              <CheckCircle2 className="h-3 w-3" />
              {t("upToDate")}
            </span>
          )}
          {nextDose && (
            <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
              {t("nextDose")}: {nextDose.vaccine_name}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => {
            resetForm();
            setShowForm(!showForm);
          }}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          {showForm ? tc("cancel") : t("recordImmunization")}
        </button>
      </div>

      {showForm && (
        <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground md:col-span-2 lg:col-span-3">
            {editing ? t("correctDose") : t("recordImmunization")}
          </p>
          <div className={cellClass}>
            <label className={labelClass}>{t("vaccine")} *</label>
            <select
              value={vaccineCode}
              onChange={(event) => handleVaccineChange(event.target.value)}
              className={inputClass}
            >
              <option value="">{t("selectVaccine")}</option>
              {(schedule ?? []).map((item) => (
                <option key={item.vaccine_code} value={item.vaccine_code}>
                  {item.vaccine_name}
                </option>
              ))}
            </select>
          </div>
          <div className={cellClass}>
            <label className={labelClass}>{t("dateGiven")} *</label>
            <input
              type="date"
              value={dateGiven}
              onChange={(event) => setDateGiven(event.target.value)}
              className={inputClass}
            />
          </div>
          <div className={cellClass}>
            <label className={labelClass}>{t("batchNumber")}</label>
            <input
              value={batchNumber}
              onChange={(event) => setBatchNumber(event.target.value)}
              className={inputClass}
            />
          </div>
          <div className={cellClass}>
            <label className={labelClass}>{t("site")}</label>
            <select
              value={site}
              onChange={(event) => setSite(event.target.value)}
              className={inputClass}
            >
              <option value="">{t("siteNone")}</option>
              {SITES.map((value) => (
                <option key={value} value={value}>
                  {t(`site_${value}` as SiteKey)}
                </option>
              ))}
            </select>
          </div>
          <div className={cellClass}>
            <label className={labelClass}>{t("route")}</label>
            <select
              value={route}
              onChange={(event) => setRoute(event.target.value)}
              className={inputClass}
            >
              <option value="">{t("siteNone")}</option>
              {ROUTES.map((value) => (
                <option key={value} value={value}>
                  {t(`route_${value}` as RouteKey)}
                </option>
              ))}
            </select>
          </div>
          <div className={cn(cellClass, "flex items-center gap-2 md:pt-8")}>
            <input
              id={`adverse-${child.id}`}
              type="checkbox"
              checked={adverseEvent}
              onChange={(event) => setAdverseEvent(event.target.checked)}
              className="h-4 w-4 rounded border-input"
            />
            <label
              htmlFor={`adverse-${child.id}`}
              className="text-sm font-medium text-foreground"
            >
              {t("adverseEvent")}
            </label>
          </div>
          {adverseEvent && (
            <div className={cn(cellClass, "md:col-span-2 lg:col-span-3")}>
              <label className={labelClass}>{t("adverseEventDescription")}</label>
              <textarea
                value={adverseDetails}
                onChange={(event) => setAdverseDetails(event.target.value)}
                rows={2}
                className={inputClass}
              />
            </div>
          )}
          <div className={cn(cellClass, "md:col-span-2 lg:col-span-3")}>
            <label className={labelClass}>{tc("notes")}</label>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={2}
              className={inputClass}
            />
          </div>
          <div className="flex items-center justify-end gap-2 md:col-span-2 lg:col-span-3">
            <button
              type="button"
              onClick={() => {
                resetForm();
                setShowForm(false);
              }}
              className="rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
            >
              {tc("cancel")}
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={saving}
              className={cn(
                "rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90",
                saving && "cursor-not-allowed opacity-60"
              )}
            >
              {saving ? tc("saving") : editing ? tc("save") : t("saveDose")}
            </button>
          </div>
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400 md:col-span-2 lg:col-span-3">
              {error}
            </p>
          )}
        </div>
      )}

      {dueDoses.length > 0 && (
        <div className="mb-4">
          <h4 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
            {t("dueSchedule")}
          </h4>
          <div className="flex flex-wrap gap-2">
            {dueDoses.map((item) => {
              const isOverdue = weeks >= item.due_age_weeks + GRACE_WEEKS;
              return (
                <span
                  key={item.vaccine_code}
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-medium",
                    isOverdue
                      ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200"
                      : "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200"
                  )}
                >
                  {item.vaccine_name} · {t("dueAtWeeks", { weeks: item.due_age_weeks })}
                  {isOverdue ? ` · ${t("overdue")}` : ""}
                </span>
              );
            })}
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">{t("vaccine")}</th>
              <th className="px-4 py-2">{t("doseNumber")}</th>
              <th className="px-4 py-2">{t("dateGiven")}</th>
              <th className="px-4 py-2">{t("site")}</th>
              <th className="px-4 py-2">{t("adverseEvent")}</th>
              <th className="px-4 py-2">{tc("actions")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  {tc("loading")}
                </td>
              </tr>
            ) : !immunizations?.length ? (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  {t("noImmunizations")}
                </td>
              </tr>
            ) : (
              immunizations.map((dose) => (
                <tr key={dose.id} className="hover:bg-muted/40">
                  <td className="px-4 py-2 text-foreground">{dose.vaccine_name}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {dose.dose_number}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-foreground">
                    {formatDate(dose.date_given)}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {dose.site ? t(`site_${dose.site}` as SiteKey) : "—"}
                  </td>
                  <td className="px-4 py-2">
                    {dose.adverse_event ? (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200">
                        {t("adverseEvent")}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => startEdit(dose)}
                        title={tc("edit")}
                        className="inline-flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-xs font-medium text-foreground hover:bg-muted"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        {tc("edit")}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDelete(dose)}
                        disabled={removing}
                        title={tc("delete")}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-lg border border-red-300 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950",
                          removing && "cursor-not-allowed opacity-60"
                        )}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {tc("delete")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}