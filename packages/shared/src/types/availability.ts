/**
 * Weekly availability types.
 *
 * A clinician's working week decides whether the patient picker offers them
 * today, so both their own edits and HR's oversight speak this one shape.
 */

import type { DoctorScheduleResponse } from "./appointment";
import type { ProviderWorkStatus } from "./provider";

/** One weekly working session: the day and the hours. */
export interface AvailabilitySlot {
  /** Weekday, 0=Monday .. 6=Sunday. */
  day_of_week: number;
  /** Session start, e.g. "08:00" or "08:00:00". */
  start_time: string;
  end_time: string;
}

/** Replace a whole week's availability in one call. */
export interface WeeklyScheduleUpdate {
  slots: AvailabilitySlot[];
}

/** A clinician's stored week, with the status it resolves to now. */
export interface WeeklyScheduleResponse {
  staff_id: string;
  slots: DoctorScheduleResponse[];
  /** The effective work status the patient picker would use right now. */
  work_status: ProviderWorkStatus;
  /** Whether an active roster is in force for this clinician. */
  has_schedule: boolean;
  /** Whether that roster puts them on duty today. */
  scheduled_today: boolean;
}