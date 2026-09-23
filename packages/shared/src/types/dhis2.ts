/**
 * DHIS2 / MOH Reporting types.
 * Used for automated MOH form generation and DHIS2 sync.
 */

/** Available MOH form codes. */
export type MOHFormCode =
  | "MOH_705A"
  | "MOH_705B"
  | "MOH_710"
  | "MOH_711"
  | "MOH_713"
  | "MOH_718";

/** MOH form metadata. */
export interface MOHFormInfo {
  code: MOHFormCode;
  name: string;
  title: string;
  period: string;
}

/** MOH report generation request. */
export interface MOHReportRequest {
  form_code: MOHFormCode;
  date_from: string;
  date_to: string;
}

/** MOH report period metadata. */
export interface MOHReportPeriod {
  from: string;
  to: string;
}

/** MOH 705A row — OPD diagnosis by age and sex. */
export interface MOH705ARow {
  icd10_code: string;
  description: string;
  under_1: number;
  age_1_4: number;
  age_5_9: number;
  age_10_19: number;
  age_20_plus: number;
  male: number;
  female: number;
  total: number;
}

/** MOH 705B row — inpatient diagnosis. */
export interface MOH705BRow {
  icd10_code: string;
  description: string;
  male: number;
  female: number;
  total: number;
}

/** MOH 710 row — immunization data. */
export interface MOH710Row {
  vaccine: string;
  dose_number: number;
  doses_given: number;
}

/** MOH 713 row — lab test summary. */
export interface MOH713Row {
  test_name: string;
  total: number;
  completed: number;
  critical: number;
}

/** Generic MOH report response. */
export interface MOHReport {
  form: string;
  title: string;
  period: MOHReportPeriod;
  rows?: Record<string, unknown>[];
  indicators?: Record<string, number>;
  summary: Record<string, unknown>;
}

/** All MOH reports response. */
export interface MOHAllReportsResponse {
  reports: Record<MOHFormCode, MOHReport>;
  period: MOHReportPeriod;
}

/** DHIS2 connection status. */
export interface DHIS2ConnectionStatus {
  connected: boolean;
  message: string;
}
