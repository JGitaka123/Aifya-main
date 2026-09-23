"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Calendar,
  Clock,
  Stethoscope,
  MapPin,
  FileText,
  CheckCircle,
  XCircle,
  ArrowLeft,
  UserCheck,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useAppointmentDetail,
  useUpdateAppointment,
  useCheckInAppointment,
} from "@/hooks/useAppointments";
import { cn } from "@/lib/utils";

/** Status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  confirmed: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  checked_in: "bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-200",
  in_consultation: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-muted text-muted-foreground",
  no_show: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/** Priority badge styling. */
const PRIORITY_STYLES: Record<string, string> = {
  emergency: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  urgent: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  routine: "bg-muted text-foreground",
};

/**
 * Appointment Detail Page — view, check-in, reschedule, cancel.
 *
 * @returns Appointment detail page
 */
export default function AppointmentDetailPage() {
  const t = useTranslations("appointments");
  const tc = useTranslations("common");
  const params = useParams();
  const appointmentId = params.appointmentId as string;

  const { data: appt, isLoading } = useAppointmentDetail(appointmentId);
  const updateMutation = useUpdateAppointment(appointmentId);
  const checkInMutation = useCheckInAppointment(appointmentId);

  // Reschedule form state
  const [showReschedule, setShowReschedule] = useState(false);
  const [newDate, setNewDate] = useState("");
  const [newStartTime, setNewStartTime] = useState("");
  const [newEndTime, setNewEndTime] = useState("");
  const [newRoom, setNewRoom] = useState("");

  // Cancel form state
  const [showCancel, setShowCancel] = useState(false);
  const [cancelReason, setCancelReason] = useState("");

  /**
   * Handle patient check-in.
   */
  async function handleCheckIn() {
    await checkInMutation.mutateAsync({ notes: null });
  }

  /**
   * Handle appointment confirmation.
   */
  async function handleConfirm() {
    await updateMutation.mutateAsync({ status: "confirmed" });
  }

  /**
   * Handle marking as no-show.
   */
  async function handleNoShow() {
    await updateMutation.mutateAsync({ status: "no_show" });
  }

  /**
   * Handle marking as completed.
   */
  async function handleComplete() {
    await updateMutation.mutateAsync({ status: "completed" });
  }

  /**
   * Handle reschedule submission.
   */
  async function handleReschedule() {
    await updateMutation.mutateAsync({
      appointment_date: newDate || null,
      start_time: newStartTime || null,
      end_time: newEndTime || null,
      room: newRoom || null,
      status: "scheduled",
    });
    setShowReschedule(false);
  }

  /**
   * Handle cancellation submission.
   */
  async function handleCancel() {
    await updateMutation.mutateAsync({
      status: "cancelled",
      cancellation_reason: cancelReason || null,
    });
    setShowCancel(false);
  }

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {tc("loading")}
      </div>
    );
  }

  if (!appt) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {t("notFound")}
      </div>
    );
  }

  const isActive = !["completed", "cancelled", "no_show"].includes(appt.status);
  const canCheckIn = ["scheduled", "confirmed"].includes(appt.status);
  const canConfirm = appt.status === "scheduled";
  const canComplete = appt.status === "in_consultation";

  return (
    <div className="space-y-6 p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/appointments"
          className="rounded-lg p-2 hover:bg-muted/50"
        >
          <ArrowLeft className="h-5 w-5 text-muted-foreground" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-foreground">
            {appt.appointment_number}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-block rounded-full px-2.5 py-0.5 text-xs font-medium",
                STATUS_STYLES[appt.status] ?? STATUS_STYLES.scheduled
              )}
            >
              {t(`status_${appt.status}`)}
            </span>
            <span
              className={cn(
                "inline-block rounded-full px-2.5 py-0.5 text-xs font-medium",
                PRIORITY_STYLES[appt.priority] ?? PRIORITY_STYLES.routine
              )}
            >
              {t(`priority_${appt.priority}`)}
            </span>
            {appt.is_recurring && (
              <span className="inline-block rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-medium text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200">
                {t("recurring")}
              </span>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        {isActive && (
          <div className="flex flex-wrap gap-2">
            {canConfirm && (
              <button
                onClick={handleConfirm}
                disabled={updateMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-3 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50 dark:bg-purple-500 dark:hover:bg-purple-600"
              >
                <CheckCircle className="h-4 w-4" />
                {t("confirm")}
              </button>
            )}
            {canCheckIn && (
              <button
                onClick={handleCheckIn}
                disabled={checkInMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-600 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-700 disabled:opacity-50 dark:bg-cyan-500 dark:hover:bg-cyan-600"
              >
                <UserCheck className="h-4 w-4" />
                {t("checkIn")}
              </button>
            )}
            {canComplete && (
              <button
                onClick={handleComplete}
                disabled={updateMutation.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 dark:bg-green-500 dark:hover:bg-green-600"
              >
                <CheckCircle className="h-4 w-4" />
                {t("markCompleted")}
              </button>
            )}
            <button
              onClick={() => setShowReschedule(!showReschedule)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
            >
              <Calendar className="h-4 w-4" />
              {t("reschedule")}
            </button>
            <button
              onClick={() => handleNoShow()}
              disabled={updateMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-card px-3 py-2 text-sm font-medium text-amber-700 hover:bg-amber-50 dark:border-amber-600 dark:text-amber-400 dark:hover:bg-muted"
            >
              {t("noShow")}
            </button>
            <button
              onClick={() => setShowCancel(!showCancel)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-card px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-600 dark:text-red-400 dark:hover:bg-muted"
            >
              <XCircle className="h-4 w-4" />
              {tc("cancel")}
            </button>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Appointment Info */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("appointmentInfo")}
          </h2>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="flex items-center gap-1.5 text-muted-foreground">
                <Calendar className="h-4 w-4" />
                {t("date")}
              </dt>
              <dd className="mt-1 font-medium text-foreground">
                {appt.appointment_date}
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-1.5 text-muted-foreground">
                <Clock className="h-4 w-4" />
                {t("time")}
              </dt>
              <dd className="mt-1 font-medium text-foreground">
                {appt.start_time?.slice(0, 5)} - {appt.end_time?.slice(0, 5)}
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-1.5 text-muted-foreground">
                <Stethoscope className="h-4 w-4" />
                {t("type")}
              </dt>
              <dd className="mt-1 font-medium text-foreground">
                {t(`type_${appt.appointment_type}`)}
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-1.5 text-muted-foreground">
                <Clock className="h-4 w-4" />
                {t("duration")}
              </dt>
              <dd className="mt-1 font-medium text-foreground">
                {appt.duration_minutes} {t("minutes")}
              </dd>
            </div>
            {appt.room && (
              <div>
                <dt className="flex items-center gap-1.5 text-muted-foreground">
                  <MapPin className="h-4 w-4" />
                  {t("room")}
                </dt>
                <dd className="mt-1 font-medium text-foreground">
                  {appt.room}
                </dd>
              </div>
            )}
            {appt.checked_in_at && (
              <div>
                <dt className="flex items-center gap-1.5 text-muted-foreground">
                  <UserCheck className="h-4 w-4" />
                  {t("checkedInAt")}
                </dt>
                <dd className="mt-1 font-medium text-foreground">
                  {new Date(appt.checked_in_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </dd>
              </div>
            )}
          </dl>

          {appt.visit_reason && (
            <div className="mt-4 border-t border-border pt-4">
              <dt className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <FileText className="h-4 w-4" />
                {t("visitReason")}
              </dt>
              <dd className="mt-1 text-sm text-foreground">
                {appt.visit_reason}
              </dd>
            </div>
          )}

          {appt.notes && (
            <div className="mt-4 border-t border-border pt-4">
              <dt className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <FileText className="h-4 w-4" />
                {t("notes")}
              </dt>
              <dd className="mt-1 text-sm text-foreground">
                {appt.notes}
              </dd>
            </div>
          )}

          {/* Cancellation info */}
          {appt.status === "cancelled" && appt.cancelled_at && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950/30">
              <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
                {t("cancellationInfo")}
              </h3>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">
                {t("cancelledAt")}: {new Date(appt.cancelled_at).toLocaleString()}
              </p>
              {appt.cancellation_reason && (
                <p className="mt-1 text-sm text-red-700 dark:text-red-300">
                  {t("reason")}: {appt.cancellation_reason}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Reschedule Form */}
        {showReschedule && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <h2 className="mb-4 text-lg font-semibold text-foreground">
              {t("reschedule")}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("newDate")}
                </label>
                <input
                  type="date"
                  value={newDate}
                  onChange={(e) => setNewDate(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("startTime")}
                  </label>
                  <input
                    type="time"
                    value={newStartTime}
                    onChange={(e) => setNewStartTime(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-foreground">
                    {t("endTime")}
                  </label>
                  <input
                    type="time"
                    value={newEndTime}
                    onChange={(e) => setNewEndTime(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("room")}
                </label>
                <input
                  type="text"
                  value={newRoom}
                  onChange={(e) => setNewRoom(e.target.value)}
                  placeholder={t("roomPlaceholder")}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleReschedule}
                  disabled={updateMutation.isPending}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
                >
                  {t("confirmReschedule")}
                </button>
                <button
                  onClick={() => setShowReschedule(false)}
                  className="rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
                >
                  {tc("cancel")}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Cancel Form */}
        {showCancel && (
          <div className="rounded-xl border border-red-200 bg-card p-6 dark:border-red-800">
            <h2 className="mb-4 text-lg font-semibold text-red-700 dark:text-red-400">
              {t("cancelAppointment")}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("cancellationReason")}
                </label>
                <textarea
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  rows={3}
                  placeholder={t("cancellationReasonPlaceholder")}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCancel}
                  disabled={updateMutation.isPending}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 dark:bg-red-500 dark:hover:bg-red-600"
                >
                  {t("confirmCancel")}
                </button>
                <button
                  onClick={() => setShowCancel(false)}
                  className="rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
                >
                  {tc("back")}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
