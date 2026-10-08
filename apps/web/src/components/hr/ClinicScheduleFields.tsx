"use client";

import { useTranslations } from "next-intl";
import { Plus, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { cn, generateId } from "@/lib/utils";
import type {
  AvailabilitySlot,
  DayOfWeek,
  DoctorScheduleCreate,
  DoctorScheduleResponse,
  StaffDirectoryResponse,
} from "@aifya/shared";

/**
 * Marker stored in a schedule's notes by the database fallback that gives every
 * new doctor a generic Mon-Fri 08:00-17:00 week.
 */
const DEFAULT_AVAILABILITY_NOTE = "Auto-created default availability";

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
 * Job-title words that make the API create a clinical ``doctor``.
 *
 * Mirrors ``_DOCTOR_KEYWORDS`` in
 * ``services/api-gateway/app/services/payroll/employee_staff_sync.py`` so the
 * form only asks for a clinic schedule for the people who will actually be
 * bookable. Nursing and midwifery titles are deliberately absent: they map to
 * their own roles.
 */
const DOCTOR_KEYWORDS = [
  "doctor",
  "physician",
  "medical officer",
  "consultant",
  "general practitioner",
  "medical practitioner",
  "family practitioner",
  "medical specialist",
  "registrar",
  "surgeon",
  "pediatric",
  "paediatric",
  "gynecolog",
  "gynaecolog",
  "obstetric",
  "dermatolog",
  "cardiolog",
  "neurolog",
  "psychiatr",
  "anesthes",
  "anaesthet",
  "ophthalmolog",
  "otolaryng",
  "orthoped",
  "orthopaed",
  "gastroenterolog",
  "urolog",
  "endocrinolog",
  "nephrolog",
  "pulmonolog",
  "rheumatolog",
  "oncolog",
  "hematolog",
  "haematolog",
  "internist",
  "family medicine",
  "emergency medicine",
];

/**
 * Job-title words that name a specialty rather than general practice.
 *
 * Only specialists run booked clinics of their own, so only they are asked for
 * a clinic schedule while HR registers them. Everyone else is a general doctor
 * and keeps the default availability the API seeds.
 */
const SPECIALIST_KEYWORDS = [
  "specialist",
  "consultant",
  "surgeon",
  "pediatric",
  "paediatric",
  "gynecolog",
  "gynaecolog",
  "obstetric",
  "dermatolog",
  "cardiolog",
  "neurolog",
  "psychiatr",
  "anesthes",
  "anaesthet",
  "ophthalmolog",
  "otolaryng",
  "orthoped",
  "orthopaed",
  "gastroenterolog",
  "urolog",
  "endocrinolog",
  "nephrolog",
  "pulmonolog",
  "rheumatolog",
  "oncolog",
  "hematolog",
  "haematolog",
  "internist",
  "family medicine",
];

/**
 * Whether a job title will register as a clinical doctor.
 *
 * @param jobTitle - Job title typed on the employee form
 * @returns True when the title maps to the doctor role
 */
export function looksLikeDoctor(jobTitle?: string): boolean {
  if (!jobTitle) return false;
  const title = jobTitle.toLowerCase();
  if (title.includes("nurse") || title.includes("midwife")) return false;
  return DOCTOR_KEYWORDS.some((keyword) => title.includes(keyword));
}

/**
 * Whether a job title names a specialist doctor.
 *
 * A general doctor works the facility's general clinic and needs no schedule of
 * their own; a specialist such as a cardiologist or consultant surgeon runs a
 * named clinic, and appointments for that clinic have to be written down.
 *
 * @param jobTitle - Job title typed on the employee form
 * @returns True when the title is a doctor in a named specialty
 */
export function looksLikeSpecialist(jobTitle?: string): boolean {
  if (!looksLikeDoctor(jobTitle)) return false;
  const title = (jobTitle ?? "").toLowerCase();
  return SPECIALIST_KEYWORDS.some((keyword) => title.includes(keyword));
}

/** One weekly clinic session being drafted while the doctor is registered. */
export interface ClinicSessionDraft {
  /** Row identity for React, stable while the row is edited. */
  key: string;
  dayOfWeek: DayOfWeek;
  startTime: string;
  endTime: string;
  slotMinutes: string;
  room: string;
}

/**
 * A blank weekly session to start a doctor off with.
 *
 * @returns A draft session covering a normal morning clinic
 */
export function emptyClinicSession(): ClinicSessionDraft {
  return {
    key: generateId(),
    dayOfWeek: 0,
    startTime: "08:00",
    endTime: "13:00",
    slotMinutes: "15",
    room: "",
  };
}

/**
 * Whether a draft is complete enough to be saved.
 *
 * @param draft - Session being edited
 * @returns True when the times are present and ordered
 */
export function isClinicSessionComplete(draft: ClinicSessionDraft): boolean {
  return (
    Boolean(draft.startTime) &&
    Boolean(draft.endTime) &&
    draft.endTime > draft.startTime
  );
}

/**
 * Turn stored sessions into editable drafts.
 *
 * The row id becomes the draft key, so a session that survives a save keeps
 * its row - and any appointment already booked against it - instead of being
 * deleted and recreated.
 *
 * @param slots - Sessions read from the API
 * @returns Drafts ready for the editor
 */
export function scheduleToDrafts(
  slots: DoctorScheduleResponse[],
): ClinicSessionDraft[] {
  return slots.map((slot) => ({
    key: slot.id,
    dayOfWeek: slot.day_of_week,
    startTime: slot.start_time.slice(0, 5),
    endTime: slot.end_time.slice(0, 5),
    slotMinutes: String(slot.slot_duration_minutes ?? 15),
    room: slot.room ?? "",
  }));
}

/**
 * Turn edited drafts into the shared week payload.
 *
 * Incomplete rows are dropped rather than rejected: a half-typed session is
 * not a claim that the clinician works those hours.
 *
 * @param drafts - Sessions being edited
 * @returns Only the complete sessions, in the API's slot shape
 */
export function draftsToSlots(drafts: ClinicSessionDraft[]): AvailabilitySlot[] {
  return drafts.filter(isClinicSessionComplete).map((draft) => ({
    day_of_week: draft.dayOfWeek,
    start_time: draft.startTime,
    end_time: draft.endTime,
  }));
}

/**
 * Find the clinical staff row the API created for a payroll employee.
 *
 * Registering an employee mirrors it into the clinical staff directory, and the
 * appointment schedules hang off that staff row rather than the payroll one, so
 * the id has to be resolved before a session can be attached.
 *
 * @param employeeNumber - Payroll staff number, e.g. "EMP-014"
 * @returns Staff UUID, or null when no matching staff row exists yet
 */
export async function findStaffIdByEmployeeNumber(
  employeeNumber: string,
): Promise<string | null> {
  const trimmed = employeeNumber.trim();
  if (!trimmed) return null;
  const directory = await apiClient.get<StaffDirectoryResponse>(
    `/hr/staff?search=${encodeURIComponent(trimmed)}`,
  );
  const match = (directory?.items ?? []).find(
    (item) => item.employee_number?.toLowerCase() === trimmed.toLowerCase(),
  );
  return match?.id ?? null;
}

/**
 * Save the drafted weekly sessions against a doctor.
 *
 * The database gives every new doctor a generic Mon-Fri 08:00-17:00 fallback so
 * they are bookable the moment they exist. Once HR has written the real clinic
 * hours those fallbacks are switched off, so the schedule appointments are
 * offered in is the one that was actually agreed.
 *
 * Sessions are written one at a time so a failure names the session it stopped
 * on rather than silently dropping the rest.
 *
 * @param staffId - Clinical staff UUID of the doctor
 * @param drafts - Complete sessions to save
 * @returns Resolves once every session is stored
 */
export async function saveClinicSchedules(
  staffId: string,
  drafts: ClinicSessionDraft[],
): Promise<void> {
  const existing = await apiClient.get<DoctorScheduleResponse[]>(
    "/appointments/schedules",
    { doctor_id: staffId },
  );
  const fallbacks = existing.filter(
    (schedule) =>
      schedule.is_active &&
      (schedule.notes ?? "").includes(DEFAULT_AVAILABILITY_NOTE),
  );
  for (const schedule of fallbacks) {
    await apiClient.patch(
      `/appointments/schedules/${schedule.id}`,
      { is_active: false },
      generateId(),
    );
  }

  for (const draft of drafts) {
    const payload: DoctorScheduleCreate = {
      doctor_id: staffId,
      day_of_week: draft.dayOfWeek,
      start_time: draft.startTime,
      end_time: draft.endTime,
      slot_duration_minutes: Number(draft.slotMinutes) || 15,
      room: draft.room.trim() || null,
      consultation_type: "general",
    };
    await apiClient.post("/appointments/schedules", payload, generateId());
  }
}

/**
 * A specialist's weekly clinic hours, collected while the employee is
 * registered.
 *
 * Appointments are only offered inside these sessions, so capturing them here
 * means a specialist clinic is bookable the moment HR finishes registering the
 * doctor instead of being discovered as unbookable later.
 *
 * @param props - The drafted sessions and their change handler
 * @returns Clinic schedule editor
 */
export function ClinicScheduleFields({
  drafts,
  onChange,
  showClinicDetails = true,
}: {
  drafts: ClinicSessionDraft[];
  onChange: (drafts: ClinicSessionDraft[]) => void;
  /**
   * Whether to show the clinic-only fields (slot length, room).
   *
   * Clinician self-service and HR oversight edit a working week, not a
   * bookable clinic, so those fields are hidden there to keep the edit within
   * the days and hours the API actually accepts.
   */
  showClinicDetails?: boolean;
}) {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");

  const update = (key: string, patch: Partial<ClinicSessionDraft>) => {
    onChange(
      drafts.map((draft) =>
        draft.key === key ? { ...draft, ...patch } : draft,
      ),
    );
  };

  const remove = (key: string) => {
    onChange(drafts.filter((draft) => draft.key !== key));
  };

  const fieldClasses =
    "w-full rounded-lg border border-border bg-card px-3 py-2 text-sm";

  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/20 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-foreground">
            {t("clinicSchedule")}
          </h4>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t("clinicScheduleHint")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onChange([...drafts, emptyClinicSession()])}
          className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
        >
          <Plus className="h-3.5 w-3.5" />
          {t("addSession")}
        </button>
      </div>

      {drafts.length === 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          {t("noClinicSessions")}
        </p>
      ) : (
        <div className="mt-3 space-y-2">
          {drafts.map((draft) => (
            <div
              key={draft.key}
              className={cn(
                "grid gap-2",
                showClinicDetails
                  ? "sm:grid-cols-[1.2fr_1fr_1fr_0.8fr_1fr_auto]"
                  : "sm:grid-cols-[1.2fr_1fr_1fr_auto]",
              )}
            >
              <select
                aria-label={t("sessionDay")}
                value={draft.dayOfWeek}
                onChange={(event) =>
                  update(draft.key, {
                    dayOfWeek: Number(event.target.value) as DayOfWeek,
                  })
                }
                className={fieldClasses}
              >
                {WEEKDAYS.map((day, index) => (
                  <option key={day} value={index}>
                    {t(`weekday.${day}`)}
                  </option>
                ))}
              </select>
              <input
                aria-label={t("sessionStart")}
                type="time"
                value={draft.startTime}
                onChange={(event) =>
                  update(draft.key, { startTime: event.target.value })
                }
                className={fieldClasses}
              />
              <input
                aria-label={t("sessionEnd")}
                type="time"
                value={draft.endTime}
                onChange={(event) =>
                  update(draft.key, { endTime: event.target.value })
                }
                className={fieldClasses}
              />
              {showClinicDetails && (
                <>
                  <input
                    aria-label={t("sessionSlotMinutes")}
                    type="number"
                    min={5}
                    value={draft.slotMinutes}
                    onChange={(event) =>
                      update(draft.key, { slotMinutes: event.target.value })
                    }
                    className={fieldClasses}
                  />
                  <input
                    aria-label={t("sessionRoom")}
                    type="text"
                    value={draft.room}
                    onChange={(event) =>
                      update(draft.key, { room: event.target.value })
                    }
                    placeholder={t("sessionRoom")}
                    className={fieldClasses}
                  />
                </>
              )}
              <button
                type="button"
                onClick={() => remove(draft.key)}
                aria-label={tc("remove")}
                className="flex items-center justify-center rounded-lg border border-border bg-card px-2 text-muted-foreground hover:bg-muted"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}