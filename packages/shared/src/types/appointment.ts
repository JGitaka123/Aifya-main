/** Day of the week: 0=Monday, 6=Sunday */
export type DayOfWeek = 0 | 1 | 2 | 3 | 4 | 5 | 6;

/** Consultation type for doctor schedules */
export type ConsultationType =
  | "general"
  | "specialist"
  | "follow_up"
  | "procedure"
  | "anc"
  | "dental";

/** Appointment type */
export type AppointmentType =
  | "consultation"
  | "follow_up"
  | "procedure"
  | "lab"
  | "radiology"
  | "anc"
  | "dental"
  | "vaccination";

/** Appointment priority */
export type AppointmentPriority = "routine" | "urgent" | "emergency";

/** Appointment status lifecycle */
export type AppointmentStatus =
  | "scheduled"
  | "confirmed"
  | "checked_in"
  | "in_consultation"
  | "completed"
  | "cancelled"
  | "no_show";

/** Doctor schedule response */
export interface DoctorScheduleResponse {
  id: string;
  doctor_id: string;
  department_id: string | null;
  day_of_week: DayOfWeek;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  max_patients: number | null;
  room: string | null;
  consultation_type: ConsultationType;
  is_active: boolean;
  effective_from: string | null;
  effective_until: string | null;
  notes: string | null;
  created_at: string;
  doctor_name: string | null;
}

/** Doctor schedule create request */
export interface DoctorScheduleCreate {
  doctor_id: string;
  department_id?: string | null;
  day_of_week: DayOfWeek;
  start_time: string;
  end_time: string;
  slot_duration_minutes?: number;
  max_patients?: number | null;
  room?: string | null;
  consultation_type?: ConsultationType;
  effective_from?: string | null;
  effective_until?: string | null;
  notes?: string | null;
}

/** Doctor schedule update request */
export interface DoctorScheduleUpdate {
  day_of_week?: DayOfWeek | null;
  start_time?: string | null;
  end_time?: string | null;
  slot_duration_minutes?: number | null;
  max_patients?: number | null;
  room?: string | null;
  consultation_type?: ConsultationType | null;
  is_active?: boolean | null;
  effective_from?: string | null;
  effective_until?: string | null;
  notes?: string | null;
}

/** Available time slot for booking */
export interface AvailableSlot {
  schedule_id: string;
  doctor_id: string;
  doctor_name: string | null;
  date: string;
  start_time: string;
  end_time: string;
  room: string | null;
  consultation_type: ConsultationType;
  available: boolean;
}

/** Appointment create request */
export interface AppointmentCreate {
  patient_id: string;
  doctor_id: string;
  department_id?: string | null;
  schedule_id?: string | null;
  appointment_date: string;
  start_time: string;
  end_time?: string | null;
  duration_minutes?: number;
  appointment_type?: AppointmentType;
  visit_reason?: string | null;
  priority?: AppointmentPriority;
  room?: string | null;
  notes?: string | null;
  is_recurring?: boolean;
}

/** Appointment detail response */
export interface AppointmentResponse {
  id: string;
  patient_id: string;
  doctor_id: string;
  department_id: string | null;
  schedule_id: string | null;
  encounter_id: string | null;
  appointment_number: string;
  appointment_date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  appointment_type: AppointmentType;
  visit_reason: string | null;
  priority: AppointmentPriority;
  status: AppointmentStatus;
  checked_in_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  reminder_sent: boolean;
  is_recurring: boolean;
  room: string | null;
  notes: string | null;
  booked_by: string;
  created_at: string;
}

/** Appointment list item with patient/doctor names */
export interface AppointmentListItem {
  id: string;
  appointment_number: string;
  patient_id: string;
  patient_name: string | null;
  patient_mrn: string | null;
  doctor_id: string;
  doctor_name: string | null;
  appointment_date: string;
  start_time: string;
  end_time: string;
  appointment_type: AppointmentType;
  priority: AppointmentPriority;
  status: AppointmentStatus;
  room: string | null;
  visit_reason: string | null;
  created_at: string;
}

/** Paginated appointment list response */
export interface AppointmentListResponse {
  items: AppointmentListItem[];
  total: number;
}

/** Appointment update request */
export interface AppointmentUpdate {
  appointment_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  status?: AppointmentStatus | null;
  room?: string | null;
  notes?: string | null;
  cancellation_reason?: string | null;
}

/** Check-in request */
export interface AppointmentCheckIn {
  notes?: string | null;
}

/** Dashboard summary stats */
export interface AppointmentSummary {
  total_today: number;
  scheduled: number;
  confirmed: number;
  checked_in: number;
  completed_today: number;
  cancelled_today: number;
  no_show_today: number;
}
