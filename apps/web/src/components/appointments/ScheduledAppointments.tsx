"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { CalendarClock } from "lucide-react";
import type { AppointmentListItem } from "@aifya/shared";
import { useAppointmentsByType } from "@/hooks/useAppointments";
import { cn, formatDate } from "@/lib/utils";

/** Appointment statuses that still need clinical attention in this department. */
const ACTIVE_STATUSES: string[] = ["scheduled", "confirmed", "checked_in"];

/** Priority badge styling. */
const PRIORITY_STYLES: Record<string, string> = {
  routine: "bg-muted text-muted-foreground",
  urgent: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  emergency: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/** Status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-muted text-muted-foreground",
  confirmed: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  checked_in: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
};

/**
 * A patient who owes a visit, taken from a department register rather than a
 * booked appointment. MCH follow-ups work this way: registering a pregnancy or
 * a child card schedules the next contact, so the department panel must show
 * the register instead of reporting an empty appointment book.
 */
export interface RegisterWorklistItem {
  /** Stable React key */
  id: string;
  /** Patient display name */
  patientName: string | null;
  /** Patient medical record number */
  patientMrn?: string | null;
  /** Register reference, e.g. ANC-20260910-0001 */
  reference: string;
  /** Short clinical summary, e.g. "G2P1 · 28 weeks" */
  detail: string;
  /** What the patient owes next, e.g. "EDD 2027-07-05" */
  due: string;
  /** Highlight tone for the "due" cell */
  tone?: "due" | "overdue" | "ok";
  /** Optional per-row action */
  action?: ReactNode;
}

interface ScheduledAppointmentsProps {
  /** Appointment type this department receives (dental, lab, radiology, anc, vaccination). */
  appointmentType: string;
  /** Optional per-row action renderer, e.g. a button that starts the clinical visit. */
  renderAction?: (appointment: AppointmentListItem) => ReactNode;
  /** Register-derived rows shown under the booked appointments. */
  registerItems?: RegisterWorklistItem[];
  /** Heading for the register section */
  registerTitle?: string;
}

/**
 * Panel listing booked appointments of one clinical type so department tabs
 * (dental, laboratory, radiology, MCH) can see what reception booked for them.
 *
 * @param props - Component props
 * @returns Scheduled appointment panel
 */
export function ScheduledAppointments({
  appointmentType,
  renderAction,
  registerItems,
  registerTitle,
}: ScheduledAppointmentsProps) {
  const t = useTranslations("appointments");
  const tc = useTranslations("common");
  const { data, isLoading, isError, refetch } =
    useAppointmentsByType(appointmentType);

  const items = (data?.items ?? []).filter((a) =>
    ACTIVE_STATUSES.includes(a.status)
  );
  const register = registerItems ?? [];
  const total = items.length + register.length;
  const hasAction = !!renderAction || register.some((row) => row.action);

  /** Tone classes for a register row's "due" cell. */
  const dueTone = (tone: RegisterWorklistItem["tone"]) => {
    if (tone === "overdue") return "text-red-700 dark:text-red-300";
    if (tone === "ok") return "text-green-700 dark:text-green-300";
    return "text-foreground";
  };

  return (
    <section className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-5 w-5 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">
            {t("scheduledAppointments")}
          </h2>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {isLoading || isError ? (total > 0 ? total : "—") : total}
          </span>
        </div>
        <span className="rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
          {t(`type_${appointmentType}`)}
        </span>
      </header>

      {isLoading ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">
          {tc("loading")}
        </p>
      ) : isError && register.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-4 py-6 text-center">
          <p className="text-sm text-red-600 dark:text-red-400">
            {t("loadFailed")}
          </p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted"
          >
            {tc("retrySync")}
          </button>
        </div>
      ) : total === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">
          {t("noAppointments")}
        </p>
      ) : (
        <>
        {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("appointmentNumber")}</th>
                <th className="px-4 py-3">{t("patient")}</th>
                <th className="px-4 py-3">{t("date")}</th>
                <th className="px-4 py-3">{t("time")}</th>
                <th className="px-4 py-3">{t("doctor")}</th>
                <th className="px-4 py-3">{t("priority")}</th>
                <th className="px-4 py-3">{t("visitReason")}</th>
                <th className="px-4 py-3">{t("status")}</th>
                {renderAction && <th className="px-4 py-3">{tc("actions")}</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {items.map((a) => (
                <tr key={a.id} className="bg-card hover:bg-muted/50">
                  <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">
                    {a.appointment_number}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {a.patient_name ?? a.patient_id}
                    {a.patient_mrn && (
                      <span className="block text-xs text-muted-foreground">
                        {a.patient_mrn}
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-foreground">
                    {formatDate(a.appointment_date)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-foreground">
                    {a.start_time.slice(0, 5)} - {a.end_time.slice(0, 5)}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {a.doctor_name ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        PRIORITY_STYLES[a.priority]
                      )}
                    >
                      {t(`priority_${a.priority}`)}
                    </span>
                  </td>
                  <td className="max-w-[220px] truncate px-4 py-3 text-foreground">
                    {a.visit_reason || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        STATUS_STYLES[a.status]
                      )}
                    >
                      {t(`status_${a.status}`)}
                    </span>
                  </td>
                  {renderAction && (
                    <td className="px-4 py-3">{renderAction(a)}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}

        {register.length > 0 && (
          <div className={cn(items.length > 0 && "border-t border-border")}>
            <h3 className="px-4 pt-4 text-xs font-semibold uppercase text-muted-foreground">
              {registerTitle ?? t("dueForReview")}
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">{t("reference")}</th>
                    <th className="px-4 py-3">{t("patient")}</th>
                    <th className="px-4 py-3">{t("detail")}</th>
                    <th className="px-4 py-3">{t("nextDue")}</th>
                    {hasAction && (
                      <th className="px-4 py-3">{tc("actions")}</th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {register.map((row) => (
                    <tr key={row.id} className="bg-card hover:bg-muted/50">
                      <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">
                        {row.reference}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {row.patientName ?? "—"}
                        {row.patientMrn && (
                          <span className="block text-xs text-muted-foreground">
                            {row.patientMrn}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {row.detail}
                      </td>
                      <td
                        className={cn(
                          "whitespace-nowrap px-4 py-3 font-medium",
                          dueTone(row.tone)
                        )}
                      >
                        {row.due}
                      </td>
                      {hasAction && (
                        <td className="px-4 py-3">{row.action ?? "—"}</td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        </>
      )}
    </section>
  );
}
