/** Report category */
export type ReportCategory =
  | "operational"
  | "clinical"
  | "financial"
  | "compliance"
  | "moh";

/** Report type */
export type ReportType = "tabular" | "chart" | "summary" | "register";

/** Report output format */
export type ReportFormat = "json" | "pdf" | "csv" | "xlsx";

/** Generated report status */
export type GeneratedReportStatus =
  | "generating"
  | "completed"
  | "failed"
  | "expired";

/** Reporting period */
export type ReportingPeriod =
  | "daily"
  | "weekly"
  | "monthly"
  | "quarterly"
  | "annual";

/** Report template list item */
export interface ReportTemplateListItem {
  id: string;
  name: string;
  code: string;
  category: ReportCategory;
  department: string | null;
  report_type: ReportType;
  moh_form_number: string | null;
  reporting_period: ReportingPeriod | null;
  is_scheduled: boolean;
  is_active: boolean;
}

/** Report template full response */
export interface ReportTemplateResponse {
  id: string;
  name: string;
  code: string;
  description: string | null;
  category: ReportCategory;
  department: string | null;
  report_type: ReportType;
  parameters_schema: Record<string, unknown> | null;
  columns_config: Record<string, unknown> | null;
  is_scheduled: boolean;
  schedule_cron: string | null;
  is_active: boolean;
  moh_form_number: string | null;
  reporting_period: ReportingPeriod | null;
  created_at: string;
}

/** Report template create request */
export interface ReportTemplateCreate {
  name: string;
  code: string;
  description?: string | null;
  category?: ReportCategory;
  department?: string | null;
  report_type?: ReportType;
  parameters_schema?: Record<string, unknown> | null;
  query_config?: Record<string, unknown> | null;
  columns_config?: Record<string, unknown> | null;
  is_scheduled?: boolean;
  schedule_cron?: string | null;
  moh_form_number?: string | null;
  reporting_period?: ReportingPeriod | null;
}

/** Report generate request */
export interface ReportGenerateRequest {
  template_id: string;
  date_from: string;
  date_to: string;
  parameters?: Record<string, unknown> | null;
  format?: ReportFormat;
}

/** Generated report response */
export interface GeneratedReportResponse {
  id: string;
  template_id: string;
  title: string;
  report_number: string;
  parameters: Record<string, unknown> | null;
  date_from: string;
  date_to: string;
  result_data: Record<string, unknown> | null;
  summary_data: Record<string, unknown> | null;
  row_count: number;
  status: GeneratedReportStatus;
  format: ReportFormat;
  file_key: string | null;
  generated_by: string;
  generated_at: string;
  expires_at: string | null;
}

/** Generated report list item */
export interface GeneratedReportListItem {
  id: string;
  template_id: string;
  title: string;
  report_number: string;
  date_from: string;
  date_to: string;
  row_count: number;
  status: GeneratedReportStatus;
  format: ReportFormat;
  generated_at: string;
}

/** Generated report list response */
export interface GeneratedReportListResponse {
  items: GeneratedReportListItem[];
  total: number;
}

/** Facility dashboard analytics */
export interface FacilityDashboard {
  total_patients: number;
  patients_today: number;
  patients_this_month: number;
  opd_visits_today: number;
  opd_visits_month: number;
  active_admissions: number;
  admissions_today: number;
  discharges_today: number;
  bed_occupancy_rate: number;
  appointments_today: number;
  appointments_completed: number;
  appointments_no_show: number;
  lab_orders_today: number;
  lab_pending: number;
  lab_critical: number;
  prescriptions_today: number;
  dispensed_today: number;
  stock_alerts: number;
  revenue_today: number;
  revenue_month: number;
  outstanding_balance: number;
  imaging_orders_today: number;
  imaging_pending_reports: number;
  active_anc_profiles: number;
  deliveries_month: number;
  immunizations_month: number;
}

/** Department stat data point */
export interface DepartmentStat {
  date: string;
  count: number;
  label?: string | null;
}

/** Dashboard trend data */
export interface DashboardTrends {
  opd_visits: DepartmentStat[];
  admissions: DepartmentStat[];
  revenue: DepartmentStat[];
  lab_orders: DepartmentStat[];
  appointments: DepartmentStat[];
}

/** Top diagnosis entry */
export interface TopDiagnosis {
  icd_code: string;
  description: string;
  count: number;
}

/** Reports module summary */
export interface ReportsSummary {
  total_templates: number;
  moh_templates: number;
  generated_today: number;
  generated_month: number;
}

/** One metered event type on the facility's monthly usage charge. */
export interface UsageBillingLine {
  /** Line key: reception_registrations | emergency_registrations | ipd_bed_days */
  key: string;
  label: string;
  quantity: number;
  rate_cents: number;
  amount_cents: number;
}

/** What the facility owes Aifya for one billing month. */
export interface UsageBillingReport {
  facility_id: string;
  /** Billing month as YYYY-MM */
  month: string;
  date_from: string;
  date_to: string;
  currency: string;
  /** Charge per metered event, in the currency minor units (cents) */
  rate_cents: number;
  lines: UsageBillingLine[];
  total_quantity: number;
  total_cents: number;
  due_date: string;
  generated_at: string;
}

/** One month in the rolling usage-billing trend. */
export interface UsageBillingMonth {
  month: string;
  reception_registrations: number;
  emergency_registrations: number;
  ipd_bed_days: number;
  total_quantity: number;
  total_cents: number;
}

/** Rolling monthly usage charges, oldest month first. */
export interface UsageBillingTrend {
  currency: string;
  rate_cents: number;
  months: UsageBillingMonth[];
  total_cents: number;
}
