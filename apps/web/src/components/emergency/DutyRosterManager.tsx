"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckCircle2,
  Clock,
  Loader2,
  PlusCircle,
  Stethoscope,
  XCircle,
} from "lucide-react";
import { useAuth } from "@/components/providers/AuthProvider";
import {
  useStaffDirectory,
  useShifts,
  useCreateShift,
  useCreateShiftAssignment,
} from "@/hooks/useHR";
import { useDoctorsOnDuty } from "@/hooks/useEmergency";
import type { ShiftCreate } from "@aifya/shared";

/** Standard shifts created when a facility has no shift definitions yet. */
const STANDARD_SHIFTS: ShiftCreate[] = [
  {
    code: "M",
    name: "Morning",
    start_time: "07:00",
    end_time: "15:00",
    duration_hours: 8,
    is_night_shift: false,
  },
  {
    code: "E",
    name: "Evening",
    start_time: "15:00",
    end_time: "23:00",
    duration_hours: 8,
    is_night_shift: false,
  },
  {
    code: "N",
    name: "Night",
    start_time: "23:00",
    end_time: "07:00",
    duration_hours: 8,
    is_night_shift: true,
  },
];

const inputClasses =
  "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm";

/**
 * Duty roster manager for the emergency department.
 *
 * Lets facility admins mark active doctors as on duty for a chosen date by
 * assigning them to a shift. The same assignments power the "Doctors on
 * duty" chip list and the on-duty doctor group in the Assign Doctor panel.
 *
 * @returns Roster manager card, or nothing for non-admin users
 */
export function DutyRosterManager() {
  const t = useTranslations("emergency");
  const { user } = useAuth();
  const canManage =
    !!user &&
    user.roles.some((role) => role === "admin" || role === "facility_admin");

  const today = new Date().toISOString().slice(0, 10);
  const [open, setOpen] = useState(false);
  const [rosterDate, setRosterDate] = useState(today);
  const [staffId, setStaffId] = useState("");
  const [shiftId, setShiftId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const qc = useQueryClient();
  const { data: onDuty, isLoading: onDutyLoading } = useDoctorsOnDuty(rosterDate);
  const { data: directory } = useStaffDirectory("doctor");
  const { data: shifts, isLoading: shiftsLoading } = useShifts();
  const createAssignment = useCreateShiftAssignment();
  const createShift = useCreateShift();

  if (!canManage) return null;

  const rosteredIds = new Set((onDuty ?? []).map((doc) => doc.id));
  const doctors = (directory?.items ?? []).filter((staff) => staff.is_active);
  const availableDoctors = doctors.filter((staff) => !rosteredIds.has(staff.id));
  const existingShiftCodes = new Set(
    (shifts ?? []).map((shift) => shift.code.toUpperCase())
  );
  const missingStandardShifts = STANDARD_SHIFTS.filter(
    (shift) => !existingShiftCodes.has(shift.code.toUpperCase())
  );

  const resetFeedback = () => {
    setError(null);
    setNotice(null);
  };

  const handleAssign = async () => {
    resetFeedback();
    if (!staffId || !shiftId) {
      setError(t("rosterSelectionRequired"));
      return;
    }
    try {
      await createAssignment.mutateAsync({
        staff_id: staffId,
        shift_id: shiftId,
        assignment_date: rosterDate,
      });
      setStaffId("");
      setShiftId("");
      setNotice(t("rosterAdded"));
      qc.invalidateQueries({ queryKey: ["emergency", "on-duty"] });
      qc.invalidateQueries({ queryKey: ["hr", "shift-assignments"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("rosterError"));
    }
  };

  const handleCreateStandardShifts = async () => {
    resetFeedback();
    try {
      for (const shift of missingStandardShifts) {
        await createShift.mutateAsync(shift);
      }
      setNotice(t("rosterShiftsCreated"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("rosterError"));
    }
  };

  const handleDateChange = (value: string) => {
    setRosterDate(value);
    resetFeedback();
    setStaffId("");
    setShiftId("");
  };

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <CalendarDays className="h-4 w-4 text-primary" />
          {t("manageRoster")}
        </h2>
        <button
          onClick={() => setOpen((value) => !value)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {open ? t("rosterCollapse") : t("rosterExpand")}
        </button>
      </div>

      {open && (
        <>
          <p className="mb-4 mt-1 text-xs text-muted-foreground">
            {t("rosterHint")}
          </p>

          <div className="flex flex-wrap items-end gap-3">
            <label>
              <span className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("rosterDate")}
              </span>
              <input
                type="date"
                value={rosterDate}
                onChange={(e) => handleDateChange(e.target.value)}
                className={inputClasses}
              />
            </label>
          </div>

          {/* Rostered doctors for the selected date */}
          <div className="mt-4">
            <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Stethoscope className="h-3.5 w-3.5" />
              {t("doctorsOnDuty")}
            </h3>
            {onDutyLoading ? (
              <p className="flex items-center gap-1 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                {t("loading")}
              </p>
            ) : !onDuty || onDuty.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                {t("rosterNoDoctorsForDate")}
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {onDuty.map((doc) => (
                  <span
                    key={doc.id}
                    className="inline-flex items-center gap-1.5 rounded-md border border-green-200 bg-green-50 px-2.5 py-1 text-xs font-medium text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-300"
                  >
                    <Stethoscope className="h-3.5 w-3.5" />
                    {doc.title ? doc.title + " " : ""}
                    {doc.first_name} {doc.last_name}
                    {doc.specialization ? "\u00B7 " + doc.specialization : ""}
                    {doc.shift_name ? (
                      <span className="ml-1 rounded-sm bg-green-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-green-700 dark:bg-green-900 dark:text-green-200">
                        {doc.shift_name}
                      </span>
                    ) : null}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Assignment form */}
          {shiftsLoading ? (
            <p className="mt-4 flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              {t("loading")}
            </p>
          ) : !shifts || shifts.length === 0 ? (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950">
              <p className="text-xs text-amber-800 dark:text-amber-200">
                {t("rosterNoShifts")}
              </p>
              <button
                onClick={handleCreateStandardShifts}
                disabled={createShift.isPending || missingStandardShifts.length === 0}
                className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {createShift.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <PlusCircle className="h-3 w-3" />
                )}
                {t("rosterCreateShifts")}
              </button>
            </div>
          ) : (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <label>
                <span className="mb-1 block text-xs font-medium text-muted-foreground">
                  {t("rosterDoctor")}
                </span>
                <select
                  value={staffId}
                  onChange={(e) => setStaffId(e.target.value)}
                  className={inputClasses}
                >
                  <option value="">{t("selectDoctor")}</option>
                  {availableDoctors.map((staff) => (
                    <option key={staff.id} value={staff.id}>
                      {staff.title ? staff.title + " " : ""}
                      {staff.first_name} {staff.last_name}
                      {staff.specialization ? " - " + staff.specialization : ""}
                    </option>
                  ))}
                </select>
                {availableDoctors.length === 0 && (
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {doctors.length === 0
                      ? t("rosterNoActiveDoctors")
                      : t("rosterAllAssigned")}
                  </span>
                )}
              </label>
              <label>
                <span className="mb-1 block text-xs font-medium text-muted-foreground">
                  {t("rosterShift")}
                </span>
                <select
                  value={shiftId}
                  onChange={(e) => setShiftId(e.target.value)}
                  className={inputClasses}
                >
                  <option value="">{t("selectShift")}</option>
                  {(shifts ?? []).map((shift) => (
                    <option key={shift.id} value={shift.id}>
                      {shift.name} ({shift.code}) &middot;{" "}
                      {(shift.start_time || "").slice(0, 5)} -{" "}
                      {(shift.end_time || "").slice(0, 5)}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex items-end">
                <button
                  onClick={handleAssign}
                  disabled={
                    createAssignment.isPending || !staffId || !shiftId
                  }
                  className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {createAssignment.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Clock className="h-3.5 w-3.5" />
                  )}
                  {createAssignment.isPending ? t("saving") : t("rosterAdd")}
                </button>
              </div>
            </div>
          )}

          {error && (
            <p className="mt-3 flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
              <XCircle className="h-3.5 w-3.5" />
              {error}
            </p>
          )}
          {notice && (
            <p className="mt-3 flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {notice}
            </p>
          )}
        </>
      )}
    </div>
  );
}
