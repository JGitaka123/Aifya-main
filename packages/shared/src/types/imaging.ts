/**
 * AI Medical Imaging Analysis types.
 * Chest X-ray TB screening, retinal scans, general radiology AI.
 */

/** Supported AI analysis types. */
export type ImagingAnalysisType = "chest_xray_tb" | "retinal_scan" | "chest_xray_general";

/** Finding severity levels. */
export type FindingSeverity = "normal" | "mild" | "moderate" | "severe" | "critical";

/** Single finding from AI image analysis. */
export interface ImagingFinding {
  label: string;
  description: string;
  confidence: number;
  severity: FindingSeverity;
  location: string | null;
  icd10_code: string | null;
}

/** AI imaging analysis request. */
export interface ImagingAnalysisRequest {
  imaging_order_id: string;
  analysis_type: ImagingAnalysisType;
  image_url: string;
  patient_age?: number | null;
  patient_sex?: string | null;
}

/** Complete AI imaging analysis result. */
export interface ImagingAnalysisResult {
  imaging_order_id: string;
  analysis_type: ImagingAnalysisType;
  findings: ImagingFinding[];
  overall_impression: string;
  recommendation: string;
  confidence_score: number;
  model_version: string;
  requires_clinician_review: boolean;
}

/** Analysis type metadata. */
export interface ImagingAnalysisTypeInfo {
  type: ImagingAnalysisType;
  name: string;
  description: string;
  modality: string;
}
