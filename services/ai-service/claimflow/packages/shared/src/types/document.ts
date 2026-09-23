// ============================================================================
// DOCUMENT TYPES — Section 13 (Taxonomy) + Section 9 (Schema)
// ============================================================================

export enum DocumentType {
  SHA_CLAIM_FORM_OP = 'SHA_CLAIM_FORM_OP',
  SHA_CLAIM_FORM_IP = 'SHA_CLAIM_FORM_IP',
  SHA_CLAIM_FORM_MATERNITY = 'SHA_CLAIM_FORM_MATERNITY',
  PREAUTH_FORM = 'PREAUTH_FORM',
  DISCHARGE_SUMMARY = 'DISCHARGE_SUMMARY',
  PHYSICIAN_NOTES = 'PHYSICIAN_NOTES',
  LAB_RESULTS = 'LAB_RESULTS',
  PRESCRIPTION = 'PRESCRIPTION',
  REFERRAL_LETTER = 'REFERRAL_LETTER',
  RADIOLOGY_REPORT = 'RADIOLOGY_REPORT',
  OPERATIVE_NOTE = 'OPERATIVE_NOTE',
  NATIONAL_ID_COPY = 'NATIONAL_ID_COPY',
  SHA_CARD_COPY = 'SHA_CARD_COPY',
  CONSENT_FORM = 'CONSENT_FORM',
  OTHER_SUPPORTING = 'OTHER_SUPPORTING',
  FINAL_BILL = 'FINAL_BILL',
  INTERIM_BILL = 'INTERIM_BILL',
  LETTER_OF_UNDERTAKING = 'LETTER_OF_UNDERTAKING',
  MEDICAL_REPORT = 'MEDICAL_REPORT',
  RADIOLOGY_REQUEST = 'RADIOLOGY_REQUEST',
  RADIOLOGICAL_EXAM = 'RADIOLOGICAL_EXAM',
  LAB_ORDER = 'LAB_ORDER',
  LAB_TESTS = 'LAB_TESTS',
  CASE_SUMMARY = 'CASE_SUMMARY',
  PROFORMA_INVOICE = 'PROFORMA_INVOICE',
  THEATRE_LIST = 'THEATRE_LIST',
  CLINICAL_DOCUMENTATION = 'CLINICAL_DOCUMENTATION',
  BIOPSY_RESULT = 'BIOPSY_RESULT',
  IMAGING_RESULT = 'IMAGING_RESULT',
  CONSULTANT_REPORT = 'CONSULTANT_REPORT',
  HISTOPATHOLOGY_RESULTS = 'HISTOPATHOLOGY_RESULTS',
  STAGING_RESULTS = 'STAGING_RESULTS',
  PRIOR_BASIC_DIAGNOSTIC_IMAGES = 'PRIOR_BASIC_DIAGNOSTIC_IMAGES',
}

export enum DocProcessingRoute {
  FULL_OCR_EXTRACT = 'FULL_OCR_EXTRACT',
  EXISTENCE_QUALITY_ONLY = 'EXISTENCE_QUALITY_ONLY',
  STRUCTURED_EXTRACT = 'STRUCTURED_EXTRACT',
  SIGNATURE_DETECT_ONLY = 'SIGNATURE_DETECT_ONLY',
}

export enum DocProcessingStatus {
  PENDING = 'PENDING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  MANUAL_ENTRY_REQUIRED = 'MANUAL_ENTRY_REQUIRED',
}

export enum FieldConfidenceTier {
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

/** Map document type → processing route (Section 13 matrix) */
export const DOC_PROCESSING_ROUTES: Record<DocumentType, DocProcessingRoute> = {
  [DocumentType.SHA_CLAIM_FORM_OP]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.SHA_CLAIM_FORM_IP]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.SHA_CLAIM_FORM_MATERNITY]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.PREAUTH_FORM]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.DISCHARGE_SUMMARY]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.PHYSICIAN_NOTES]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.LAB_RESULTS]: DocProcessingRoute.STRUCTURED_EXTRACT,
  [DocumentType.PRESCRIPTION]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.REFERRAL_LETTER]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.RADIOLOGY_REPORT]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.OPERATIVE_NOTE]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.NATIONAL_ID_COPY]: DocProcessingRoute.EXISTENCE_QUALITY_ONLY,
  [DocumentType.SHA_CARD_COPY]: DocProcessingRoute.EXISTENCE_QUALITY_ONLY,
  [DocumentType.CONSENT_FORM]: DocProcessingRoute.SIGNATURE_DETECT_ONLY,
  [DocumentType.OTHER_SUPPORTING]: DocProcessingRoute.EXISTENCE_QUALITY_ONLY,
  [DocumentType.FINAL_BILL]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.INTERIM_BILL]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.LETTER_OF_UNDERTAKING]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.MEDICAL_REPORT]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.RADIOLOGY_REQUEST]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.RADIOLOGICAL_EXAM]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.LAB_ORDER]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.LAB_TESTS]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.CASE_SUMMARY]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.PROFORMA_INVOICE]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.THEATRE_LIST]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.CLINICAL_DOCUMENTATION]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.BIOPSY_RESULT]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.IMAGING_RESULT]: DocProcessingRoute.EXISTENCE_QUALITY_ONLY,
  [DocumentType.CONSULTANT_REPORT]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.HISTOPATHOLOGY_RESULTS]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.STAGING_RESULTS]: DocProcessingRoute.FULL_OCR_EXTRACT,
  [DocumentType.PRIOR_BASIC_DIAGNOSTIC_IMAGES]: DocProcessingRoute.EXISTENCE_QUALITY_ONLY,
};

/** MIME types accepted for upload */
export const ACCEPTED_MIME_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/tiff',
] as const;

export type AcceptedMimeType = typeof ACCEPTED_MIME_TYPES[number];

export interface Document {
  id: string;
  claimId: string;
  docType: DocumentType;
  processingRoute: DocProcessingRoute;
  mimeType: string;
  originalFilename: string;
  pageCount: number;
  fileSizeBytes: number;
  storagePath: string;
  sha256: string;
  processingStatus: DocProcessingStatus;
  processingError: string | null;
  uploadedBy: string;
  uploadedAt: string;
}

export interface DocumentPage {
  id: string;
  documentId: string;
  pageNumber: number;
  status: DocProcessingStatus;
  ocrEngineUsed: string | null;
  overallConfidence: number | null;
  imageQualityScore: number | null;
  retryCount: number;
  errorMessage: string | null;
  processedAt: string | null;
}

export interface ExtractedField {
  id: string;
  claimId: string;
  documentId: string;
  pageNumber: number;
  fieldKey: string;
  fieldValue: string | null;
  confidence: number;
  confidenceTier: FieldConfidenceTier;
  bbox: { x: number; y: number; w: number; h: number } | null;
  source: 'OCR' | 'MANUAL' | 'CLASSIFIER' | 'HEURISTIC';
  needsReview: boolean;
  reviewed: boolean;
  createdAt: string;
}

export interface Correction {
  id: string;
  extractedFieldId: string;
  originalValue: string | null;
  correctedValue: string;
  correctedBy: string;
  correctedAt: string;
  usedForTraining: boolean;
}
