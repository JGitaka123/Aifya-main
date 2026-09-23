"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { CalendarPlus, Plus } from "lucide-react";
import type { DayOfWeek, DoctorScheduleCreate } from "@aifya/shared";
import {
  useCreateSchedule,
  useDoctorSchedules,
  useUpdateSchedule,
} from "@/hooks/useAppointments";
import { useStaffDirectory } from "@/hooks/useHR";
import { cn } from "@/lib/utils";

/** Weekday keys indexed by DayOfWeek, where 0 is Monday. */
const WEEKDAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
] as const;

/** Clinic type every schedule created here belongs to. */
const DENTAL = "dental";

interface ScheduleActiveToggleProps {
  /** Schedule UUID */
  scheduleId: string;
  /** Whether the session is currently switched on */
  isActive: boolean;
}

/**
 * Switch a dentist clinic session on or off.
 *
 * @param props - Component props
 * @returns Toggle button with inline error state
 */
function ScheduleActiveToggle({
  scheduleId,
  isActive,
}: ScheduleActiveToggleProps) {
  const t = useTranslations("dental");
  const tc = useTranslations("common");
  const mutation = useUpdateSchedule();

  /** Flip the schedule's active flag. */
  const toggle = async () => {
    try {
      await mutation.mutateAsync({ scheduleId, is_active: !isActive });
    } catch {
      // Surfaced through the mutation error state below.
    }
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        type="button"
        disabled={mutation.isPending}
        onClick={toggle}
        className={cn(
          "whitespace-nowrap rounded-lg px-2.5 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
          isActive
            ? "border border-border text-muted-foreground hover:bg-muted"
            : "bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-950 dark:text-green-200"
        )}
      >
        {isActive ? t("deactivate") : t("activate")}
      </button>
      {mutation.isError && (
        <span className="text-xs text-red-600 dark:text-red-400">
          {tc("retrySync")}
        </span>
      )}
    </div>
  );
}

/**
 * Dental clinic rota: shows which doctors run a dental clinic and lets an
 * admin pick a doctor plus their weekly session. A doctor enrolled here is
 * what makes slots bookable for dental appointments, and what makes them
 * selectable as the dentist on a treatment plan.
 *
 * @returns Dentist schedule management panel
 */
export function DentistSchedulesPanel() {
  const t = useTranslations("dental");
  const tc = useTranslations("common");

  const [showForm, setShowForm] = useState(false);
  const [doctorId, setDoctorId] = useState("");
  const [dayOfWeek, setDayOfWeek] = useState<DayOfWeek>(0);
  const [startTime, setStartTime] = useState("08:00");
  const [endTime, setEndTime] = useState("13:00");
  const [slotMinutes, setSlotMinutes] = useState("15");
  const [room, setRoom] = useState("");
  const [error, setError] = useState("");

  const { data: schedules, isLoading } = useDoctorSchedules(
    undefined,
    DENTAL,
    true
  );
  const { data: directory } = useStaffDirectory("doctor");
  const createSchedule = useCreateSchedule();

  const doctors = (directory?.items ?? [])
    .filter((staff) => staff.is_active)
    .map((staff) => ({
      id: staff.id,
      name: [staff.title, staff.first_name, staff.last_name]
        .filter(Boolean)
        .join(" ")
        .trim(),
    }));

  /** Validate and save the new weekly session. */
  const handleSubmit = async () => {
    if (!doctorId) {
      setError(t("doctorRequired"));
      return;
    }
    if (endTime <= startTime) {
      setError(t("timeRangeInvalid"));
      return;
    }
    setError("");

    const payload: DoctorScheduleCreate = {
      doctor_id: doctorId,
      day_of_week: dayOfWeek,
      start_time: startTime,
      end_time: endTime,
      slot_duration_minutes: Number(slotMinutes) || 15,
      room: room || null,
      consultation_type: DENTAL,
    };

    try {
      await createSchedule.mutateAsync(payload);
      setShowForm(false);
      setRoom("");
    } catch {
      setError(tc("retrySync"));
    }
  };

  const items = schedules ?? [];
  const inputClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm";
  const labelClass = "mb-1 block text-sm font-medium text-foreground";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-foreground">
          {t("dentistSchedules")}
        </h2>
        <button
          type="button"
          onClick={() => setShowForm((open) => !open)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          {showForm ? tc("cancel") : t("addSchedule")}
        </button>
      </div>

      {items.length === 0 && !showForm && (
        <p className="rounded-xl border border-dashed border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
          {t("noSchedules")}
        </p>
      )}

      {showForm && (
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="lg:col-span-3">
              <label className={labelClass}>{t("dentist")}</label>
              <select
                value={doctorId}
                onChange={(e) => setDoctorId(e.target.value)}
                className={inputClass}
              >
                <option value="">{t("doctorRequired")}</option>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>{t("dayOfWeek")}</label>
              <select
                value={dayOfWeek}
                onChange={(e) =>
                  setDayOfWeek(Number(e.target.value) as DayOfWeek)
                }
                className={inputClass}
              >
                {WEEKDAYS.map((day, index) => (
                  <option key={day} value={index}>
                    {t(`weekday.${day}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>{t("startTime")}</label>
              <input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>{t("endTime")}</label>
              <input
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>{t("slotMinutes")}</label>
              <input
                inputMode="numeric"
                value={slotMinutes}
                onChange={(e) => setSlotMinutes(e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>{t("room")}</label>
              <input
                value={room}
                onChange={(e) => setRoom(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          <div className="mt-5 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
            >
              {tc("cancel")}
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={createSchedule.isPending}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90",
                createSchedule.isPending && "cursor-not-allowed opacity-60"
              )}
            >
              <CalendarPlus className="h-4 w-4" />
              {createSchedule.isPending ? tc("saving") : t("addSchedule")}
            </button>
          </div>

          {error && (
            <p className="mt-3 text-sm text-red-600 dark:text-red-400">
              {error}
            </p>
          )}
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-3">{t("dentist")}</th>
              <th className="px-4 py-3">{t("dayOfWeek")}</th>
              <th className="px-4 py-3">{t("startTime")}</th>
              <th className="px-4 py-3">{t("endTime")}</th>
              <th className="px-4 py-3">{t("slotMinutes")}</th>
              <th className="px-4 py-3">{t("room")}</th>
              <th className="px-4 py-3">{t("statusLabel")}</th>
              <th className="px-4 py-3">{tc("actions")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">
                  {tc("loading")}
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">
                  {t("noSchedules")}
                </td>
              </tr>
            ) : (
              items.map((schedule) => (
                <tr key={schedule.id} className="bg-card hover:bg-muted/50">
                  <td className="px-4 py-3 text-foreground">
                    {schedule.doctor_name ?? schedule.doctor_id}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {t(`weekday.${WEEKDAYS[schedule.day_of_week]}`)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-foreground">
                    {schedule.start_time.slice(0, 5)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-foreground">
                    {schedule.end_time.slice(0, 5)}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {schedule.slot_duration_minutes}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {schedule.room || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        schedule.is_active
                          ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      {schedule.is_active
                        ? t("scheduleActive")
                        : t("scheduleInactive")}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <ScheduleActiveToggle
                      scheduleId={schedule.id}
                      isActive={schedule.is_active}
                    />
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
