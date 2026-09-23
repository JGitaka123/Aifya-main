/**
 * ScribeAI ambient clinical documentation types.
 * Matches the backend ClinicalExtraction model from services/ai-service/scribe/backend/.
 */

/** A vital sign extracted from ambient audio. */
export interface ScribeVitalSign {
  /** Display name of the vital sign (e.g., "Blood Pressure"). */
  name: string;
  /** Recorded value (e.g., "120/80 mmHg"). */
  value: string;
  /** LOINC code for the vital sign, if identified. */
  loinc_code: string | null;
  /** Confidence score from AI extraction (0-1). */
  confidence: number;
}

/** A diagnosis extracted from ambient audio. */
export interface ScribeDiagnosis {
  /** Diagnosis name as spoken or interpreted. */
  name: string;
  /** ICD-11 code suggested by AI. */
  icd11_suggested: string | null;
  /** ICD-11 code after validation lookup. */
  icd11_validated: string | null;
  /** Whether this is the primary diagnosis. */
  is_primary: boolean;
  /** Confidence score from AI extraction (0-1). */
  confidence: number;
}

/** A medication extracted from ambient audio. */
export interface ScribeMedication {
  /** Drug name. */
  name: string;
  /** Dosage (e.g., "500mg"). */
  dose: string | null;
  /** Route of administration (e.g., "oral", "IV"). */
  route: string | null;
  /** Frequency (e.g., "TDS", "BD"). */
  frequency: string | null;
  /** Duration (e.g., "5 days"). */
  duration: string | null;
  /** Whether this is a new prescription or existing medication. */
  is_new: boolean;
}

/** A lab order extracted from ambient audio. */
export interface ScribeLabOrder {
  /** Test name (e.g., "CBC", "Urinalysis"). */
  test_name: string;
  /** LOINC code for the lab test, if identified. */
  loinc_code: string | null;
  /** Urgency level of the lab order. */
  urgency: "routine" | "urgent" | "stat";
}

/** A procedure extracted from ambient audio. */
export interface ScribeProcedure {
  /** Procedure name. */
  name: string;
  /** ICHI code for the procedure, if identified. */
  ichi_code: string | null;
  /** Whether the procedure requires pre-authorization (e.g., SHA). */
  requires_preauth: boolean;
}

/**
 * Full clinical extraction from ScribeAI ambient documentation.
 * AI NEVER auto-commits to patient records — clinician sign-off required.
 */
export interface ClinicalExtraction {
  /** Chief complaint as stated by patient. */
  chief_complaint: string | null;
  /** Reporting problem / reason for visit. */
  reporting_problem: string | null;
  /** Symptoms described during the encounter. */
  symptoms: string | null;
  /** History of present illness narrative. */
  hpi: string | null;
  /** Vital signs extracted from audio. */
  vitals: ScribeVitalSign[];
  /** Physical examination findings. */
  physical_exam: string | null;
  /** Diagnoses discussed or determined. */
  diagnoses: ScribeDiagnosis[];
  /** Lab orders mentioned. */
  lab_orders: ScribeLabOrder[];
  /** Medications prescribed or discussed. */
  medications: ScribeMedication[];
  /** Procedures mentioned or ordered. */
  procedures: ScribeProcedure[];
  /** Patient disposition (e.g., "discharge", "admit", "refer"). */
  disposition: string | null;
  /** Follow-up instructions. */
  follow_up: string | null;
  /** Additional tests suggested by AI based on clinical context. */
  suggested_tests: string[];
  /** Clinical warnings or alerts from AI. */
  warnings: string[];
  /** ISO 8601 timestamp of when extraction was performed. */
  extraction_timestamp: string;
}

/** Input payload for the /scribe/extract endpoint. */
export interface TranscriptInput {
  /** Transcript text to extract clinical data from. */
  transcript: string;
  /** Encounter ID to associate with the extraction. */
  encounter_id: string;
}

/** Response from /scribe/process (full pipeline). */
export interface ScribeProcessResponse {
  /** Structured clinical extraction from the transcript. */
  extraction: ClinicalExtraction;
  /** Guidance message from the pipeline. */
  message?: string;
}
