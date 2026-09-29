"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { CalendarClock, Plus } from "lucide-react";
import {
  useCreateSchedule,
  useDoctorSchedules,
  useUpdateSchedule,
} from "@/hooks/useAppointments";
import { useStaffDirectory } from "@/hooks/useHR";
import { cn } from "@/lib/utils";
import type { DayOfWeek, DoctorScheduleCreate } from "@aifya/shared";

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

/**
 * The weekly clinic sessions every appointment is booked against.
 *
 * A doctor is only bookable inside a session listed here: the booking page and
 * the consultation-room follow-up both expand these sessions into slots, so a
 * doctor with no session is invisible to both. Previously this could only be
 * set up inside the Dental module, which left every other unit unbookable.
 *
 * @returns Doctor availability management panel
 */
export function DoctorAvailabilityPanel() {
  const t = useTranslations("appointments");
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
    undefined,
    true,
  );
  const { data: directory } = useStaffDirectory("doctor");
  const createSchedule = useCreateSchedule();
  const updateSchedule = useUpdateSchedule();

  const doctors = (directory?.items ?? [])
    .filter((staff) => staff.is_active)
    .map((staff) => ({
      id: staff.id,
      name: [staff.title, staff.first_name, staff.last_name]
        .filter(Boolean)
        .join(" ")
        .trim(),
    }));

  const handleSubmit = () => {
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
      room: room.trim() || null,
      consultation_type: "general",
    };
    createSchedule.mutate(payload, {
      onSuccess: () => {
        setShowForm(false);
        setRoom("");
      },
      onError: (err: Error) => {
        setError(err.message || t("availabilitySaveFailed"));
      },
    });
  };

  const handleToggle = (scheduleId: string, isActive: boolean) => {
    updateSchedule.mutate({ scheduleId, is_active: !isActive });
  };

  const fieldClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm";

  return (
    <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <CalendarClock className="h-4 w-4 text-primary" />
            {t("availabilityTitle")}
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t("availabilityHint")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setShowForm((open) => !open);
            setError("");
          }}
          className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium text-foreground transition-colors hover:bg-muted"
        >
          <Plus className="h-3.5 w-3.5" />
          {showForm ? tc("cancel") : t("addSession")}
        </button>
      </div>

      {showForm && (
        <div className="border-b border-border px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label
                htmlFor="availability-doctor"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {t("doctor")}
              </label>
              <select
                id="availability-doctor"
                value={doctorId}
                onChange={(event) => {
                  setDoctorId(event.target.value);
                  setError("");
                }}
                className={fieldClasses}
              >
                <option value="">{t("selectDoctor")}</option>
                {doctors.map((doctor) => (
                  <option key={doctor.id} value={doctor.id}>
                    {doctor.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="availability-day"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {t("dayOfWeek")}
              </label>
              <select
                id="availability-day"
                value={dayOfWeek}
                onChange={(event) =>
                  setDayOfWeek(Number(event.target.value) as DayOfWeek)
                }
                className={fieldClasses}
              >
                {WEEKDAYS.map((day, index) => (
                  <option key={day} value={index}>
                    {t(`weekday.${day}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="availability-room"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {t("room")}
              </label>
              <input
                id="availability-room"
                type="text"
                value={room}
                onChange={(event) => setRoom(event.target.value)}
                className={fieldClasses}
              />
            </div>
            <div>
              <label
                htmlFor="availability-start"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {t("startTime")}
              </label>
              <input
                id="availability-start"
                type="time"
                value={startTime}
                onChange={(event) => setStartTime(event.target.value)}
                className={fieldClasses}
              />
            </div>
            <div>
              <label
                htmlFor="availability-end"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {t("endTime")}
              </label>
              <input
                id="availability-end"
                type="time"
                value={endTime}
                onChange={(event) => setEndTime(event.target.value)}
                className={fieldClasses}
              />
            </div>
            <div>
              <label
                htmlFor="availability-slot"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {t("slotMinutes")}
              </label>
              <input
                id="availability-slot"
                type="number"
                min={5}
                value={slotMinutes}
                onChange={(event) => setSlotMinutes(event.target.value)}
                className={fieldClasses}
              />
            </div>
          </div>

          {error && (
            <p className="mt-3 text-xs text-red-600 dark:text-red-400">
              {error}
            </p>
          )}

          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={createSchedule.isPending}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              {createSchedule.isPending ? tc("loading") : tc("save")}
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="px-5 py-4 text-sm text-muted-foreground">
          {tc("loading")}
        </p>
      ) : (schedules ?? []).length === 0 ? (
        <p className="px-5 py-4 text-sm text-muted-foreground">
          {t("noSchedules")}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2">{t("doctor")}</th>
                <th className="px-4 py-2">{t("dayOfWeek")}</th>
                <th className="px-4 py-2">{t("startTime")}</th>
                <th className="px-4 py-2">{t("endTime")}</th>
                <th className="px-4 py-2">{t("room")}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(schedules ?? []).map((schedule) => (
                <tr
                  key={schedule.id}
                  className={cn(!schedule.is_active && "opacity-60")}
                >
                  <td className="px-4 py-3 font-medium text-foreground">
                    {schedule.doctor_name ?? "-"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {t(`weekday.${WEEKDAYS[schedule.day_of_week]}`)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {schedule.start_time.slice(0, 5)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {schedule.end_time.slice(0, 5)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {schedule.room ?? "-"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      disabled={updateSchedule.isPending}
                      onClick={() =>
                        handleToggle(schedule.id, schedule.is_active)
                      }
                      className={cn(
                        "rounded-lg px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-60",
                        schedule.is_active
                          ? "border border-border text-muted-foreground hover:bg-muted"
                          : "bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-950 dark:text-green-200",
                      )}
                    >
                      {schedule.is_active ? t("deactivate") : t("activate")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}