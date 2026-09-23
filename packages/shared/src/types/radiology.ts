/** Imaging modality types. */
export type ImagingModality =
  | "xray"
  | "ultrasound"
  | "ct"
  | "mri"
  | "fluoroscopy"
  | "mammography"
  | "ecg"
  | "echo";

/** Imaging order status. */
export type ImagingOrderStatus =
  | "ordered"
  | "scheduled"
  | "in_progress"
  | "completed"
  | "cancelled";

/** Imaging result/report status. */
export type ImagingResultStatus = "draft" | "preliminary" | "final" | "addendum";

/** Imaging urgency classification. */
export type ImagingUrgency = "normal" | "abnormal" | "critical" | "incidental";

/** Imaging order priority. */
export type ImagingPriority = "stat" | "urgent" | "routine";

/** Laterality. */
export type Laterality = "left" | "right" | "bilateral" | "na";

/** Pregnancy status for radiation safety. */
export type PregnancyStatus = "not_pregnant" | "pregnant" | "unknown" | "na";

/** Imaging order response from API. */
export interface ImagingOrderResponse {
  id: string;
  encounter_id: string;
  patient_id: string;
  ordered_by: string;
  order_number: string;
  accession_number: string | null;
  modality: ImagingModality;
  body_part: string;
  laterality: Laterality | null;
  views_requested: string | null;
  study_description: string;
  priority: ImagingPriority;
  clinical_indication: string | null;
  contrast_required: boolean;
  pregnancy_status: PregnancyStatus | null;
  status: ImagingOrderStatus;
  scheduled_at: string | null;
  room: string | null;
  performed_by: string | null;
  performed_at: string | null;
  total_cost_cents: number | null;
  created_at: string;
}

/** Imaging worklist item with patient info. */
export interface ImagingWorklistItem {
  id: string;
  order_number: string;
  accession_number: string | null;
  encounter_id: string;
  patient_id: string;
  patient_name: string | null;
  patient_mrn: string | null;
  ordered_by: string;
  modality: ImagingModality;
  body_part: string;
  laterality: Laterality | null;
  study_description: string;
  priority: ImagingPriority;
  status: ImagingOrderStatus;
  contrast_required: boolean;
  has_result: boolean;
  result_status: ImagingResultStatus | null;
  is_critical: boolean;
  scheduled_at: string | null;
  room: string | null;
  created_at: string;
}

/** Imaging worklist response. */
export interface ImagingWorklistResponse {
  items: ImagingWorklistItem[];
  total: number;
}

/** Create imaging order request. */
export interface ImagingOrderCreate {
  encounter_id: string;
  patient_id: string;
  modality: ImagingModality;
  body_part: string;
  laterality?: Laterality | null;
  views_requested?: string | null;
  study_description: string;
  priority?: ImagingPriority;
  clinical_indication?: string | null;
  clinical_history?: string | null;
  contrast_required?: boolean;
  contrast_type?: string | null;
  pregnancy_status?: PregnancyStatus | null;
  allergies_noted?: string | null;
}

/** Schedule imaging request. */
export interface ImagingScheduleRequest {
  scheduled_at: string;
  room?: string | null;
}

/** Perform imaging study request. */
export interface ImagingPerformRequest {
  accession_number?: string | null;
  notes?: string | null;
}

/** Imaging result / report response. */
export interface ImagingResultResponse {
  id: string;
  order_id: string;
  patient_id: string;
  reported_by: string | null;
  verified_by: string | null;
  findings: string | null;
  impression: string | null;
  recommendations: string | null;
  technique: string | null;
  comparison: string | null;
  urgency: ImagingUrgency;
  is_critical: boolean;
  critical_notified: boolean;
  critical_notified_to: string | null;
  critical_notified_at: string | null;
  status: ImagingResultStatus;
  reported_at: string | null;
  verified_at: string | null;
  image_keys: Array<Record<string, string>> | null;
  dicom_study_uid: string | null;
  dicom_series_count: number | null;
  dicom_instance_count: number | null;
  notes: string | null;
  created_at: string;
}

/** Create / enter imaging report. */
export interface ImagingResultCreate {
  findings?: string | null;
  impression?: string | null;
  recommendations?: string | null;
  technique?: string | null;
  comparison?: string | null;
  urgency?: ImagingUrgency;
  is_critical?: boolean;
  notes?: string | null;
}

/** Verify imaging report. */
export interface ImagingResultVerify {
  notes?: string | null;
}

/** Critical imaging finding notification. */
export interface CriticalImagingNotifyRequest {
  notified_to: string;
}

/** Full imaging order detail with result. */
export interface ImagingOrderDetail {
  order: ImagingOrderResponse;
  result: ImagingResultResponse | null;
  patient_name: string | null;
  patient_mrn: string | null;
}

/** Radiology department summary stats. */
export interface RadiologySummary {
  total_orders_today: number;
  pending_orders: number;
  in_progress: number;
  completed_today: number;
  pending_reports: number;
  critical_findings: number;
}
