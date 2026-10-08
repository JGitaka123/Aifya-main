/**
 * Provider assignment types.
 *
 * The consultation room hands a patient to a qualified person, not to a
 * department. These are the shapes behind that picker: the specialty that
 * makes someone relevant and the working availability that makes them free.
 */

/** The work states a clinician can be in, independent of account activation. */
export type ProviderWorkStatus =
  | "available"
  | "busy"
  | "on_leave"
  | "off_duty"
  | "unavailable";

/** One clinician a patient can be handed to. */
export interface Provider {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  title: string | null;
  role: string;
  /** The specialty that qualifies them for the referral, e.g. Orthodontics. */
  specialty: string | null;
  department_id: string | null;
  department_name: string | null;
  /**
   * Effective availability, not merely the declared one: approved leave and an
   * in-flight consultation override what the staff record says.
   */
  work_status: ProviderWorkStatus;
  is_active: boolean;
  /** True when an approved leave covers today. */
  is_on_leave: boolean;
  /** True when the clinician is already holding a consultation. */
  is_occupied: boolean;
}

/** Providers matching the picker's filters, plus what else is selectable. */
export interface ProviderDirectoryResponse {
  items: Provider[];
  total: number;
  /** Distinct specialties present among the candidates in the unit. */
  specialties: string[];
}
