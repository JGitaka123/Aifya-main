"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  UserCheck,
  AlertTriangle,
  Users,
  Plus,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useAppointmentSummary,
  useAppointmentList,
} from "@/hooks/useAppointments";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";

/** Status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  scheduled:
    "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  confirmed:
    "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  checked_in:
    "bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-200",
  in_consultation:
    "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  completed:
    "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled:
    "bg-muted text-muted-foreground",
  no_show:
    "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/** Priority badge styling. */
const PRIORITY_STYLES: Record<string, string> = {
  emergency: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  urgent: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  routine: "bg-muted text-foreground",
};

/** Appointment type display config. */
const TYPE_STYLES: Record<string, string> = {
  consultation:
    "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  follow_up:
    "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200",
  procedure:
    "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
  lab: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
  radiology:
    "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  anc: "bg-pink-100 text-pink-800 dark:bg-pink-950 dark:text-pink-200",
  dental:
    "bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-200",
  vaccination:
    "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
};

/**
 * Appointments Dashboard — shows today's summary, appointment list with filters.
 * Auto-refreshes for real-time scheduling workflow.
 *
 * @returns Appointments dashboard page
 */
export default function AppointmentsPage() {
  const t = useTranslations("appointments");
  const tc = useTranslations("common");
  const today = new Date().toISOString().slice(0, 10);
  const [dateFilter, setDateFilter] = useState<string>(today);
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data: summary } = useAppointmentSummary();
  const { data: list, isLoading } = useAppointmentList(
    dateFilter || undefined,
    undefined,
    undefined,
    statusFilter || undefined
  );

  const summaryCards = [
    {
      label: t("totalToday"),
      value: summary?.total_today ?? 0,
      icon: Calendar,
      color: "blue" as const,
    },
    {
      label: t("scheduled"),
      value: summary?.scheduled ?? 0,
      icon: Clock,
      color: "purple" as const,
    },
    {
      label: t("confirmed"),
      value: summary?.confirmed ?? 0,
      icon: UserCheck,
      color: "indigo" as const,
    },
    {
      label: t("checkedIn"),
      value: summary?.checked_in ?? 0,
      icon: Users,
      color: "cyan" as const,
    },
    {
      label: t("completedToday"),
      value: summary?.completed_today ?? 0,
      icon: CheckCircle,
      color: "green" as const,
    },
    {
      label: t("cancelledToday"),
      value: summary?.cancelled_today ?? 0,
      icon: XCircle,
      color: "primary" as const,
    },
    {
      label: t("noShowToday"),
      value: summary?.no_show_today ?? 0,
      icon: AlertTriangle,
      color: "red" as const,
    },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <PageHeader
        icon={Calendar}
        title={t("title")}
        breadcrumbs={[{ label: t("title") }]}
        actions={
          <Link
            href="/appointments/new"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
          >
            <Plus className="h-4 w-4" />
            {t("bookAppointment")}
          </Link>
        }
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-7">
        {summaryCards.map((card) => (
          <StatCard
            key={card.label}
            icon={card.icon}
            label={card.label}
            value={card.value}
            color={card.color}
          />
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <input
          type="date"
          value={dateFilter}
          onChange={(e) => setDateFilter(e.target.value)}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
        >
          <option value="">{t("allStatuses")}</option>
          <option value="scheduled">{t("statusScheduled")}</option>
          <option value="confirmed">{t("statusConfirmed")}</option>
          <option value="checked_in">{t("statusCheckedIn")}</option>
          <option value="in_consultation">{t("statusInConsultation")}</option>
          <option value="completed">{t("statusCompleted")}</option>
          <option value="cancelled">{t("statusCancelled")}</option>
          <option value="no_show">{t("statusNoShow")}</option>
        </select>
      </div>

      {/* Appointment List */}
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            {tc("loading")}
          </div>
        ) : !list?.items.length ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noAppointments")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("appointmentNumber")}</th>
                  <th className="px-4 py-3">{t("patient")}</th>
                  <th className="px-4 py-3">{t("doctor")}</th>
                  <th className="px-4 py-3">{t("time")}</th>
                  <th className="px-4 py-3">{t("type")}</th>
                  <th className="px-4 py-3">{t("priority")}</th>
                  <th className="px-4 py-3">{t("status")}</th>
                  <th className="px-4 py-3">{t("room")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.items.map((appt) => (
                  <tr
                    key={appt.id}
                    className="hover:bg-muted/50"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/appointments/${appt.id}`}
                        className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                      >
                        {appt.appointment_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-foreground">
                        {appt.patient_name ?? "-"}
                      </div>
                      {appt.patient_mrn && (
                        <div className="text-xs text-muted-foreground">
                          {appt.patient_mrn}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {appt.doctor_name ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {appt.start_time?.slice(0, 5)} - {appt.end_time?.slice(0, 5)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                          TYPE_STYLES[appt.appointment_type] ?? TYPE_STYLES.consultation
                        )}
                      >
                        {t(`type_${appt.appointment_type}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                          PRIORITY_STYLES[appt.priority] ?? PRIORITY_STYLES.routine
                        )}
                      >
                        {t(`priority_${appt.priority}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                          STATUS_STYLES[appt.status] ?? STATUS_STYLES.scheduled
                        )}
                      >
                        {t(`status_${appt.status}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {appt.room ?? "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {list && (
          <div className="border-t border-border px-4 py-3 text-sm text-muted-foreground">
            {t("totalCount", { count: list.total })}
          </div>
        )}
      </div>
    </div>
  );
}
