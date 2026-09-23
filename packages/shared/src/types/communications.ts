/**
 * Patient Communication Hub types.
 * Used for SMS/WhatsApp messaging, templates, and patient preferences.
 */

/** Supported communication channels. */
export type MessageChannel = "sms" | "whatsapp" | "email";

/** Message delivery lifecycle states. */
export type MessageStatus = "queued" | "sent" | "delivered" | "read" | "failed";

/** Message classification for routing and preferences. */
export type MessageCategory =
  | "appointment_reminder"
  | "lab_result"
  | "prescription_alert"
  | "anc_reminder"
  | "immunization_reminder"
  | "discharge_instructions"
  | "follow_up"
  | "billing_notification"
  | "custom";

/** Message template with placeholder support. */
export interface MessageTemplate {
  id: string;
  name: string;
  category: MessageCategory;
  channel: MessageChannel;
  body_template: string;
  is_active: boolean;
  language: string;
  created_at: string;
}

/** A sent or queued patient message. */
export interface PatientMessage {
  id: string;
  patient_id: string;
  facility_id: string;
  channel: MessageChannel;
  category: MessageCategory;
  recipient_phone: string;
  recipient_email: string | null;
  subject: string | null;
  template_id: string | null;
  body: string;
  status: MessageStatus;
  retry_count: number;
  sent_at: string | null;
  delivered_at: string | null;
  read_at: string | null;
  error_message: string | null;
  created_at: string;
}

/** Request to send a message. */
export interface SendMessageRequest {
  patient_id: string;
  channel: MessageChannel;
  category: MessageCategory;
  template_id?: string | null;
  template_params?: Record<string, string>;
  body?: string | null;
  subject?: string | null;
  language?: string;
  scheduled_at?: string | null;
}

/** Bulk message request. */
export interface BulkMessageRequest {
  patient_ids: string[];
  channel: MessageChannel;
  category: MessageCategory;
  template_id: string;
  template_params?: Record<string, string>;
  language?: string;
}

/** Single message API response. */
export interface MessageResponse {
  id: string;
  patient_id: string;
  facility_id: string;
  channel: MessageChannel;
  category: MessageCategory;
  recipient_phone: string;
  recipient_email: string | null;
  subject: string | null;
  template_id: string | null;
  body: string;
  status: MessageStatus;
  retry_count: number;
  sent_at: string | null;
  delivered_at: string | null;
  error_message: string | null;
  created_at: string;
}

/** Paginated message list. */
export interface MessageListResponse {
  items: MessageResponse[];
  total: number;
  page: number;
  per_page: number;
}

/** Patient communication preferences. */
export interface CommunicationPreference {
  patient_id: string;
  preferred_channel: MessageChannel;
  opt_out_categories: MessageCategory[];
  consent_given: boolean;
  consent_date: string | null;
  preferred_language: string;
}

/** Template creation request. */
export interface MessageTemplateCreate {
  name: string;
  category: MessageCategory;
  channel: MessageChannel;
  body_template: string;
  language: string;
}
