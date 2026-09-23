/**
 * Federated Analytics types.
 * County-level anonymized aggregation, disease surveillance, outbreak detection.
 */

/** Surveillance alert levels. */
export type SurveillanceAlertLevel = "normal" | "watch" | "alert" | "outbreak";

/** Disease surveillance entry with trend. */
export interface DiseaseSurveillanceEntry {
  condition: string;
  icd10_code: string | null;
  case_count: number;
  previous_period_count: number;
  percent_change: number;
  alert_level: SurveillanceAlertLevel;
  county: string | null;
}

/** Outbreak detection alert. */
export interface OutbreakAlert {
  condition: string;
  icd10_code: string | null;
  alert_level: SurveillanceAlertLevel;
  current_cases: number;
  expected_cases: number;
  excess_ratio: number;
  affected_facilities: number;
  recommendation: string;
}

/** Anonymized facility report for county aggregation. */
export interface AnonymizedFacilityReport {
  facility_id: string;
  period_start: string;
  period_end: string;
  total_opd_visits: number;
  total_ipd_admissions: number;
  total_deliveries: number;
  diagnosis_counts: Record<string, number>;
  mortality_count: number;
  lab_tests_count: number;
  immunizations_count: number;
}
