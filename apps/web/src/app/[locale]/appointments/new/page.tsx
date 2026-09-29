"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle, ArrowLeft, CheckCircle2 } from "lucide-react";
import { Link } from "@/i18n/routing";
import { PatientLookup } from "@/components/patients/PatientLookup";
import {
  useAvailableSlots,
  useCreateAppointment,
  useDoctorSchedules,
} from "@/hooks/useAppointments";
import { useStaffDirectory } from "@/hooks/useHR";
import { cn, formatDate, todayISO } from "@/lib/utils";
import type { AppointmentPriority, AppointmentType, AvailableSlot, Patient } from "@aifya/shared";

/**
 * New Appointment Booking Page — select date, doctor, slot, and book.
 *
 * @returns Appointment booking page
 */
export default function NewAppointmentPage() {
  const t = useTranslations("appointments");
  const tc = useTranslations("common");

  const [selectedDate, setSelectedDate] = useState<string>(todayISO());
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("");
  const [selectedSlot, setSelectedSlot] = useState<AvailableSlot | null>(null);

  // Form fields
  const [patient, setPatient] = useState<Patient | null>(null);
  const [appointmentType, setAppointmentType] = useState<AppointmentType>("consultation");
  const [priority, setPriority] = useState<AppointmentPriority>("routine");
  const [visitReason, setVisitReason] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [booked, setBooked] = useState<{
    id: string;
    number: string;
    date: string;
    time: string;
  } | null>(null);

  const { data: schedules } = useDoctorSchedules();
  const { data: slots, isLoading: slotsLoading } = useAvailableSlots(
    selectedDate,
    selectedDoctorId || undefined
  );
  const { data: directory } = useStaffDirectory("doctor");
  const createMutation = useCreateAppointment();

  // Unique doctors from the active doctor directory plus any doctor with a
  // weekly availability schedule. A doctor added under Employees (job title
  // Doctor) therefore appears here immediately.
  const scheduleDoctors = (schedules ?? []).map((s) => ({
    id: s.doctor_id,
    name: s.doctor_name,
  }));
  const directoryDoctors = (directory?.items ?? [])
    .filter((staff) => staff.is_active)
    .map((staff) => ({
      id: staff.id,
      name: [staff.title, staff.first_name, staff.last_name]
        .filter(Boolean)
        .join(" ")
        .trim(),
    }));
  const doctorEntries: Array<{ id: string; name?: string | null }> = [
    ...scheduleDoctors,
    ...directoryDoctors,
  ];
  const doctors = Array.from(
    new Map(doctorEntries.map((d) => [d.id, d])).values()
  );
  // The soonest day (today or later) on which at least one doctor holds a
  // clinic session. Offered when the selected date has none, so an empty
  // Sunday sends the user to the next real clinic day instead of a dead end.
  const nextAvailableDate = useMemo(() => {
    const relevant = (schedules ?? []).filter(
      (schedule) =>
        schedule.is_active &&
        (!selectedDoctorId || schedule.doctor_id === selectedDoctorId)
    );
    if (!relevant.length) return null;
    const clinicDays = new Set<number>(
      relevant.map((schedule) => schedule.day_of_week)
    );
    const start = new Date(`${todayISO()}T00:00:00`);
    for (let offset = 0; offset < 14; offset += 1) {
      const candidate = new Date(
        start.getFullYear(),
        start.getMonth(),
        start.getDate() + offset
      );
      // getDay() is 0=Sunday; schedules store 0=Monday.
      const mondayFirst = (candidate.getDay() + 6) % 7;
      if (!clinicDays.has(mondayFirst)) continue;
      const month = String(candidate.getMonth() + 1).padStart(2, `0`);
      const day = String(candidate.getDate()).padStart(2, `0`);
      return `${candidate.getFullYear()}-${month}-${day}`;
    }
    return null;
  }, [schedules, selectedDoctorId]);

  // Opening on a day with no clinic session is a dead end for the desk, so once
  // the schedules are known, land on the next day that can actually book. Once
  // the user picks a date themselves this stops, so their choice always wins.
  const dateChosenByUser = useRef(false);
  useEffect(() => {
    if (dateChosenByUser.current || slotsLoading) return;
    if (!slots || slots.length > 0 || !nextAvailableDate) return;
    setSelectedDate(nextAvailableDate);
  }, [nextAvailableDate, slots, slotsLoading]);

  /**
   * Handle booking submission.
   */
  async function handleBook() {
    if (!selectedSlot || !patient) return;
    setError("");
    setBooked(null);

    try {
      const appointment = await createMutation.mutateAsync({
        patient_id: patient.id,
        doctor_id: selectedSlot.doctor_id,
        schedule_id: selectedSlot.schedule_id,
        appointment_date: selectedSlot.date,
        start_time: selectedSlot.start_time,
        end_time: selectedSlot.end_time,
        appointment_type: appointmentType,
        priority,
        visit_reason: visitReason || undefined,
        notes: notes || undefined,
        room: selectedSlot.room || undefined,
      });
      setBooked({
        id: appointment.id,
        number: appointment.appointment_number,
        date: appointment.appointment_date,
        time: appointment.start_time.slice(0, 5),
      });
      setSelectedSlot(null);
      setVisitReason("");
      setNotes("");
    } catch (err) {
      setError(
        err instanceof Error && err.message ? err.message : t("bookFailed")
      );
    }
  }

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
        <h1 className="text-2xl font-bold text-foreground">
          {t("bookAppointment")}
        </h1>
      </div>

      {booked && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-green-300 bg-green-50 px-4 py-3 dark:border-green-800 dark:bg-green-950">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-green-600 dark:text-green-400" />
          <p className="text-sm text-green-800 dark:text-green-200">
            {t("bookSuccess", {
              number: booked.number,
              date: formatDate(booked.date),
              time: booked.time,
            })}
          </p>
          <Link
            href={`/appointments/${booked.id}`}
            className="text-sm font-semibold text-green-800 underline dark:text-green-200"
          >
            {t("viewAppointment")}
          </Link>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-300 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Date & Slot Selection */}
        <div className="space-y-4">
          {/* Date + Doctor filter */}
          <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <h2 className="mb-4 text-lg font-semibold text-foreground">
              {t("selectSlot")}
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("date")}
                </label>
                <input
                  type="date"
                  value={selectedDate}
                  onChange={(e) => {
                    dateChosenByUser.current = true;
                    setSelectedDate(e.target.value);
                    setSelectedSlot(null);
                  }}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("doctor")}
                </label>
                <select
                  value={selectedDoctorId}
                  onChange={(e) => {
                    setSelectedDoctorId(e.target.value);
                    setSelectedSlot(null);
                  }}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="">{t("allDoctors")}</option>
                  {doctors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name ?? d.id}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Available Slots */}
          <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <h3 className="mb-3 text-sm font-medium text-foreground">
              {t("availableSlots")}
            </h3>
            {slotsLoading ? (
              <p className="text-sm text-muted-foreground">
                {tc("loading")}
              </p>
            ) : !slots?.length ? (
              <div className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 dark:border-amber-800 dark:bg-amber-950">
                <p className="flex items-start gap-2 text-sm text-amber-800 dark:text-amber-200">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  {t("noClinicSessions")}
                </p>
                <p className="pl-6 text-xs text-amber-700 dark:text-amber-300">
                  {t("noClinicSessionsHint")}
                </p>
                {nextAvailableDate && nextAvailableDate !== selectedDate && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedDate(nextAvailableDate);
                      setSelectedSlot(null);
                    }}
                    className="ml-6 rounded-lg border border-amber-400 bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-200 dark:border-amber-700 dark:bg-amber-900 dark:text-amber-100"
                  >
                    {t("nextClinicDay", { date: formatDate(nextAvailableDate) })}
                  </button>
                )}
              </div>
            ) : !slots.some((slot) => slot.available) ? (
              <p className="text-sm text-muted-foreground">
                {t("noSlots")}
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {slots.map((slot, idx) => (
                  <button
                    key={`${slot.schedule_id}-${slot.start_time}-${idx}`}
                    disabled={!slot.available}
                    onClick={() => setSelectedSlot(slot)}
                    className={cn(
                      "rounded-lg border p-3 text-left text-sm transition",
                      !slot.available
                        ? "cursor-not-allowed border-border bg-muted/30 text-muted-foreground/70 line-through"
                        : selectedSlot?.start_time === slot.start_time &&
                            selectedSlot?.doctor_id === slot.doctor_id
                          ? "border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950"
                          : "border-border bg-card hover:border-blue-300 hover:bg-blue-50 dark:hover:border-blue-600 dark:hover:bg-blue-950/30"
                    )}
                  >
                    <div className="font-medium text-foreground">
                      {slot.start_time?.slice(0, 5)} - {slot.end_time?.slice(0, 5)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {slot.doctor_name ?? t("doctor")}
                    </div>
                    {slot.room && (
                      <div className="text-xs text-muted-foreground/70">
                        {slot.room}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Booking Form */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("bookingDetails")}
          </h2>
          <div className="space-y-4">
            <PatientLookup value={patient} onSelect={setPatient} required />

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("type")}
                </label>
                <select
                  value={appointmentType}
                  onChange={(e) => setAppointmentType(e.target.value as AppointmentType)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="consultation">{t("type_consultation")}</option>
                  <option value="follow_up">{t("type_follow_up")}</option>
                  <option value="procedure">{t("type_procedure")}</option>
                  <option value="lab">{t("type_lab")}</option>
                  <option value="radiology">{t("type_radiology")}</option>
                  <option value="anc">{t("type_anc")}</option>
                  <option value="dental">{t("type_dental")}</option>
                  <option value="vaccination">{t("type_vaccination")}</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-foreground">
                  {t("priority")}
                </label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as AppointmentPriority)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="routine">{t("priority_routine")}</option>
                  <option value="urgent">{t("priority_urgent")}</option>
                  <option value="emergency">{t("priority_emergency")}</option>
                </select>
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">
                {t("visitReason")}
              </label>
              <textarea
                value={visitReason}
                onChange={(e) => setVisitReason(e.target.value)}
                rows={2}
                placeholder={t("visitReasonPlaceholder")}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">
                {t("notes")}
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                placeholder={t("notesPlaceholder")}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>

            {/* Selected Slot Summary */}
            {selectedSlot && (
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950/30">
                <h3 className="text-sm font-medium text-blue-800 dark:text-blue-200">
                  {t("selectedSlot")}
                </h3>
                <p className="mt-1 text-sm text-blue-700 dark:text-blue-300">
                  {selectedSlot.date} &middot; {selectedSlot.start_time?.slice(0, 5)} -{" "}
                  {selectedSlot.end_time?.slice(0, 5)}
                </p>
                <p className="text-sm text-blue-700 dark:text-blue-300">
                  {selectedSlot.doctor_name}
                  {selectedSlot.room ? ` — ${selectedSlot.room}` : ""}
                </p>
              </div>
            )}

            <button
              onClick={handleBook}
              disabled={
                !selectedSlot || !patient || createMutation.isPending
              }
              className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
            >
              {createMutation.isPending ? tc("loading") : t("bookAppointment")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
