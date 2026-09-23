"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft } from "lucide-react";
import { Link } from "@/i18n/routing";
import { PatientLookup } from "@/components/patients/PatientLookup";
import {
  useAvailableSlots,
  useCreateAppointment,
  useDoctorSchedules,
} from "@/hooks/useAppointments";
import { useStaffDirectory } from "@/hooks/useHR";
import { cn } from "@/lib/utils";
import type { AppointmentPriority, AppointmentType, AvailableSlot, Patient } from "@aifya/shared";

/**
 * New Appointment Booking Page — select date, doctor, slot, and book.
 *
 * @returns Appointment booking page
 */
export default function NewAppointmentPage() {
  const t = useTranslations("appointments");
  const tc = useTranslations("common");
  const router = useRouter();

  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("");
  const [selectedSlot, setSelectedSlot] = useState<AvailableSlot | null>(null);

  // Form fields
  const [patient, setPatient] = useState<Patient | null>(null);
  const [appointmentType, setAppointmentType] = useState<AppointmentType>("consultation");
  const [priority, setPriority] = useState<AppointmentPriority>("routine");
  const [visitReason, setVisitReason] = useState("");
  const [notes, setNotes] = useState("");

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

  /**
   * Handle booking submission.
   */
  async function handleBook() {
    if (!selectedSlot || !patient) return;

    await createMutation.mutateAsync({
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
    router.push("/appointments");
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
