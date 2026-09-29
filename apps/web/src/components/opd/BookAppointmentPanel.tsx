"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CalendarPlus,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useAvailableSlots,
  useCreateAppointment,
  useDoctorSchedules,
} from "@/hooks/useAppointments";
import { useStaffDirectory } from "@/hooks/useHR";
import { cn, todayISO } from "@/lib/utils";
import type {
  AppointmentPriority,
  AppointmentType,
  AvailableSlot,
  Encounter,
} from "@aifya/shared";

const APPOINTMENT_TYPES: readonly {
  value: AppointmentType;
  labelKey: string;
}[] = [
  { value: "follow_up", labelKey: "type_follow_up" },
  { value: "consultation", labelKey: "type_consultation" },
  { value: "procedure", labelKey: "type_procedure" },
  { value: "lab", labelKey: "type_lab" },
  { value: "radiology", labelKey: "type_radiology" },
  { value: "anc", labelKey: "type_anc" },
  { value: "dental", labelKey: "type_dental" },
  { value: "vaccination", labelKey: "type_vaccination" },
];

const PRIORITIES: readonly {
  value: AppointmentPriority;
  labelKey: string;
}[] = [
  { value: "routine", labelKey: "priority_routine" },
  { value: "urgent", labelKey: "priority_urgent" },
  { value: "emergency", labelKey: "priority_emergency" },
];

/**
 * Consultation-room booking: the doctor arranges the patient's next visit.
 *
 * The patient is already known from the encounter, so the doctor only chooses
 * who should see them and when. Slots come from the receiving doctor's weekly
 * schedule, so the next visit lands inside hours that doctor actually works
 * instead of on a time nobody is in the room for.
 *
 * @param props - The encounter the next appointment belongs to
 * @returns The follow-up booking content
 */
export function BookAppointmentPanel({ encounter }: { encounter: Encounter }) {
  const t = useTranslations("opd");
  const ta = useTranslations("appointments");
  const tc = useTranslations("common");

  const [date, setDate] = useState(todayISO());
  const [doctorId, setDoctorId] = useState("");
  const [slot, setSlot] = useState<AvailableSlot | null>(null);
  const [appointmentType, setAppointmentType] =
    useState<AppointmentType>("follow_up");
  const [priority, setPriority] = useState<AppointmentPriority>("routine");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [booked, setBooked] = useState<{
    id: string;
    number: string;
    doctor: string;
    date: string;
    time: string;
  } | null>(null);

  const { data: schedules } = useDoctorSchedules();
  const { data: slots, isLoading } = useAvailableSlots(
    date,
    doctorId || undefined,
  );
  const { data: directory } = useStaffDirectory("doctor");
  const createAppointment = useCreateAppointment();

  // A doctor can be known from the staff directory or from an existing weekly
  // schedule. Merging both means a schedule with no directory entry still
  // offers bookable time instead of silently disappearing.
  const doctors = useMemo(() => {
    const entries: Array<{ id: string; name: string | null }> = [
      ...(schedules ?? []).map((schedule) => ({
        id: schedule.doctor_id,
        name: schedule.doctor_name,
      })),
      ...(directory?.items ?? [])
        .filter((staff) => staff.is_active)
        .map((staff) => ({
          id: staff.id,
          name: [staff.title, staff.first_name, staff.last_name]
            .filter(Boolean)
            .join(" ")
            .trim(),
        })),
    ];
    return Array.from(new Map(entries.map((entry) => [entry.id, entry])).values());
  }, [schedules, directory]);

  const hasFreeSlot = (slots ?? []).some((option) => option.available);

  const handleBook = () => {
    if (!slot) {
      setError(t("bookFollowUpSelectSlot"));
      return;
    }
    setError("");
    setBooked(null);
    createAppointment.mutate(
      {
        patient_id: encounter.patient_id,
        doctor_id: slot.doctor_id,
        schedule_id: slot.schedule_id,
        appointment_date: slot.date,
        start_time: slot.start_time,
        end_time: slot.end_time,
        appointment_type: appointmentType,
        priority,
        visit_reason: reason.trim() || null,
        room: slot.room,
      },
      {
        onSuccess: (appointment) => {
          setBooked({
            id: appointment.id,
            number: appointment.appointment_number,
            doctor: slot.doctor_name ?? ta("doctor"),
            date: appointment.appointment_date,
            time: appointment.start_time.slice(0, 5),
          });
          setSlot(null);
          setReason("");
        },
        onError: (err: Error) => {
          setError(err.message || t("bookFollowUpFailed"));
        },
      },
    );
  };

  const fieldClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm";

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
      <div className="mb-1 flex items-center gap-2">
        <CalendarPlus className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">
          {t("bookFollowUpTitle")}
        </h3>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">
        {t("bookFollowUpHint")}
      </p>

      {booked && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-green-300 bg-green-50 px-3 py-2 dark:border-green-800 dark:bg-green-950">
          <p className="flex items-center gap-2 text-sm text-green-800 dark:text-green-200">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            {t("bookFollowUpSuccess", {
              number: booked.number,
              doctor: booked.doctor,
              date: booked.date,
              time: booked.time,
            })}
          </p>
          <Link
            href={`/appointments/${booked.id}`}
            className="text-xs font-semibold text-green-800 underline dark:text-green-200"
          >
            {t("bookFollowUpView")}
          </Link>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label
            htmlFor="follow-up-date"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            {ta("date")}
          </label>
          <input
            id="follow-up-date"
            type="date"
            value={date}
            onChange={(event) => {
              setDate(event.target.value);
              setSlot(null);
            }}
            className={fieldClasses}
          />
        </div>
        <div>
          <label
            htmlFor="follow-up-doctor"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            {ta("doctor")}
          </label>
          <select
            id="follow-up-doctor"
            value={doctorId}
            onChange={(event) => {
              setDoctorId(event.target.value);
              setSlot(null);
            }}
            className={fieldClasses}
          >
            <option value="">{ta("allDoctors")}</option>
            {doctors.map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.name ?? ta("doctor")}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4">
        <p className="mb-2 text-xs font-medium text-muted-foreground">
          {ta("availableSlots")}
        </p>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{tc("loading")}</p>
        ) : (slots ?? []).length === 0 ? (
          <p className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            {t("bookFollowUpNoSchedule")}
          </p>
        ) : !hasFreeSlot ? (
          <p className="text-sm text-muted-foreground">{ta("noSlots")}</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {(slots ?? []).map((option, index) => (
              <button
                key={`${option.schedule_id}-${option.start_time}-${index}`}
                type="button"
                disabled={!option.available}
                onClick={() => {
                  setSlot(option);
                  setError("");
                }}
                className={cn(
                  "rounded-lg border p-2 text-left text-xs transition",
                  !option.available
                    ? "cursor-not-allowed border-border bg-muted/30 text-muted-foreground/70 line-through"
                    : slot?.schedule_id === option.schedule_id &&
                        slot?.start_time === option.start_time
                      ? "border-primary bg-primary/10"
                      : "border-border bg-card hover:border-primary/60 hover:bg-muted",
                )}
              >
                <span className="block font-semibold text-foreground">
                  {option.start_time.slice(0, 5)} - {option.end_time.slice(0, 5)}
                </span>
                <span className="block text-muted-foreground">
                  {option.doctor_name ?? ta("doctor")}
                </span>
                {option.room && (
                  <span className="block text-muted-foreground/70">
                    {option.room}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {slot && (
        <>
          <div className="mt-4 rounded-lg border border-primary/40 bg-primary/5 px-3 py-2 text-xs text-foreground">
            {ta("selectedSlot")}: {slot.date} &middot;{" "}
            {slot.start_time.slice(0, 5)} - {slot.end_time.slice(0, 5)}
            {" — "}
            {slot.doctor_name ?? ta("doctor")}
            {slot.room ? ` · ${slot.room}` : ""}
          </div>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="follow-up-type"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {ta("type")}
              </label>
              <select
                id="follow-up-type"
                value={appointmentType}
                onChange={(event) =>
                  setAppointmentType(event.target.value as AppointmentType)
                }
                className={fieldClasses}
              >
                {APPOINTMENT_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {ta(option.labelKey)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="follow-up-priority"
                className="mb-1 block text-xs font-medium text-muted-foreground"
              >
                {ta("priority")}
              </label>
              <select
                id="follow-up-priority"
                value={priority}
                onChange={(event) =>
                  setPriority(event.target.value as AppointmentPriority)
                }
                className={fieldClasses}
              >
                {PRIORITIES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {ta(option.labelKey)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-3">
            <label
              htmlFor="follow-up-reason"
              className="mb-1 block text-xs font-medium text-muted-foreground"
            >
              {ta("visitReason")}
            </label>
            <textarea
              id="follow-up-reason"
              rows={2}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={ta("visitReasonPlaceholder")}
              className={fieldClasses}
            />
          </div>
        </>
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
          onClick={handleBook}
          disabled={!slot || createAppointment.isPending}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow transition-all hover:opacity-90 disabled:opacity-50"
        >
          {createAppointment.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CalendarPlus className="h-4 w-4" />
          )}
          {ta("bookAppointment")}
        </button>
      </div>
    </div>
  );
}