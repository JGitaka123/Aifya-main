/** Staff role */
export type StaffRole =
  | "doctor"
  | "nurse"
  | "pharmacist"
  | "lab_tech"
  | "radiologist"
  | "admin"
  | "cashier"
  | "records"
  | "receptionist"
  | "midwife";

/** Employment type */
export type EmploymentType =
  | "permanent"
  | "contract"
  | "casual"
  | "intern"
  | "locum";

/** Leave type */
export type LeaveType =
  | "annual"
  | "sick"
  | "maternity"
  | "paternity"
  | "compassionate"
  | "study"
  | "unpaid";

/** Leave request status */
export type LeaveStatus = "pending" | "approved" | "rejected" | "cancelled";

/** Attendance status */
export type AttendanceStatus =
  | "present"
  | "absent"
  | "late"
  | "half_day"
  | "on_leave"
  | "holiday";

/** Shift assignment status */
export type ShiftAssignmentStatus =
  | "assigned"
  | "confirmed"
  | "completed"
  | "swapped"
  | "cancelled";

/** Staff directory item */
export interface StaffDirectoryItem {
  id: string;
  employee_number: string;
  first_name: string;
  last_name: string;
  title: string | null;
  role: StaffRole;
  specialization: string | null;
  department_name: string | null;
  phone: string | null;
  email: string;
  is_active: boolean;
  license_number: string | null;
}

/** Staff directory response */
export interface StaffDirectoryResponse {
  items: StaffDirectoryItem[];
  total: number;
}

/** Staff profile response */
export interface StaffProfileResponse {
  id: string;
  staff_id: string;
  date_of_birth: string | null;
  gender: string | null;
  national_id: string | null;
  kra_pin: string | null;
  nhif_number: string | null;
  nssf_number: string | null;
  address: string | null;
  county: string | null;
  sub_county: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_contact_relationship: string | null;
  employment_type: EmploymentType;
  employment_date: string | null;
  contract_end_date: string | null;
  probation_end_date: string | null;
  basic_salary: number | null;
  allowances: Record<string, number> | null;
  qualifications: Array<Record<string, string>> | null;
  certifications: Array<Record<string, string>> | null;
  annual_leave_balance: number;
  sick_leave_balance: number;
  maternity_leave_balance: number;
  paternity_leave_balance: number;
  photo_url: string | null;
  notes: string | null;
  created_at: string;
}

/** Staff profile create/update */
export interface StaffProfileCreate {
  staff_id: string;
  date_of_birth?: string | null;
  gender?: string | null;
  national_id?: string | null;
  kra_pin?: string | null;
  nhif_number?: string | null;
  nssf_number?: string | null;
  address?: string | null;
  county?: string | null;
  sub_county?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  emergency_contact_relationship?: string | null;
  employment_type?: EmploymentType;
  employment_date?: string | null;
  contract_end_date?: string | null;
  basic_salary?: number | null;
  allowances?: Record<string, number> | null;
  qualifications?: Array<Record<string, string>> | null;
  certifications?: Array<Record<string, string>> | null;
  notes?: string | null;
}

/** Shift definition */
export interface ShiftResponse {
  id: string;
  code: string;
  name: string;
  start_time: string;
  end_time: string;
  duration_hours: number;
  is_night_shift: boolean;
  department_id: string | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}

/** Shift create */
export interface ShiftCreate {
  code: string;
  name: string;
  start_time: string;
  end_time: string;
  duration_hours: number;
  is_night_shift?: boolean;
  department_id?: string | null;
  notes?: string | null;
}

/** Shift assignment response */
export interface ShiftAssignmentResponse {
  id: string;
  staff_id: string;
  staff_name: string | null;
  shift_id: string;
  shift_name: string | null;
  department_id: string | null;
  assignment_date: string;
  status: ShiftAssignmentStatus;
  swapped_with_id: string | null;
  swap_reason: string | null;
  notes: string | null;
  created_at: string;
}

/** Shift assignment create */
export interface ShiftAssignmentCreate {
  staff_id: string;
  shift_id: string;
  department_id?: string | null;
  assignment_date: string;
  notes?: string | null;
}

/** Shift assignment list response */
export interface ShiftAssignmentListResponse {
  items: ShiftAssignmentResponse[];
  total: number;
}

/** Leave request response */
export interface LeaveRequestResponse {
  id: string;
  staff_id: string;
  staff_name: string | null;
  leave_type: LeaveType;
  start_date: string;
  end_date: string;
  days_requested: number;
  reason: string | null;
  status: LeaveStatus;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  handover_to: string | null;
  handover_notes: string | null;
  notes: string | null;
  created_at: string;
}

/** Leave request create */
export interface LeaveRequestCreate {
  leave_type: LeaveType;
  start_date: string;
  end_date: string;
  days_requested: number;
  reason?: string | null;
  handover_to?: string | null;
  handover_notes?: string | null;
}

/** Leave approval request */
export interface LeaveApprovalRequest {
  action: "approve" | "reject";
  rejection_reason?: string | null;
}

/** Leave request list response */
export interface LeaveRequestListResponse {
  items: LeaveRequestResponse[];
  total: number;
}

/** Attendance response */
export interface AttendanceResponse {
  id: string;
  staff_id: string;
  staff_name: string | null;
  shift_id: string | null;
  shift_name: string | null;
  attendance_date: string;
  clock_in: string | null;
  clock_out: string | null;
  status: AttendanceStatus;
  overtime_minutes: number;
  notes: string | null;
}

/** Attendance clock in */
export interface AttendanceClockIn {
  shift_id?: string | null;
  notes?: string | null;
}

/** Attendance clock out */
export interface AttendanceClockOut {
  notes?: string | null;
}

/** Attendance list response */
export interface AttendanceListResponse {
  items: AttendanceResponse[];
  total: number;
}

/** HR module summary */
export interface HRSummary {
  total_staff: number;
  active_staff: number;
  doctors: number;
  nurses: number;
  on_duty_today: number;
  on_leave_today: number;
  pending_leave_requests: number;
  expiring_contracts: number;
}
