/**
 * The permission vocabulary, mirroring `app/auth/permissions.py`.
 *
 * These strings are the API's contract for "may this person open this part of
 * Aifya?". The web app only mirrors them so the sidebar and the clinical
 * workspace can hide what the API would refuse anyway - never treat this list
 * as the control. A typo here degrades the menu, not security, which is why
 * every permission the API can return is spelled out in one place.
 */
export const PERMISSIONS = {
  PATIENTS_VIEW: "patients.view",
  PATIENTS_REGISTER: "patients.register",
  PATIENTS_UPDATE: "patients.update",
  ENCOUNTERS_CREATE: "encounters.create",
  CLINICAL_VIEW: "clinical.view",
  CLINICAL_CONSULT: "clinical.consult",
  TRIAGE_RECORD: "triage.record",
  OPD_VIEW: "opd.view",
  OPD_MANAGE: "opd.manage",
  IPD_VIEW: "ipd.view",
  IPD_RECORD: "ipd.record",
  EMERGENCY_VIEW: "emergency.view",
  EMERGENCY_RECORD: "emergency.record",
  DENTAL_VIEW: "dental.view",
  DENTAL_RECORD: "dental.record",
  MCH_VIEW: "mch.view",
  MCH_RECORD: "mch.record",
  THEATRE_VIEW: "theatre.view",
  THEATRE_RECORD: "theatre.record",
  PHARMACY_VIEW: "pharmacy.view",
  PHARMACY_DISPENSE: "pharmacy.dispense",
  LABORATORY_VIEW: "laboratory.view",
  LABORATORY_RESULT: "laboratory.result",
  RADIOLOGY_VIEW: "radiology.view",
  RADIOLOGY_RESULT: "radiology.result",
  BILLING_VIEW: "billing.view",
  BILLING_CHARGE: "billing.charge",
  BILLING_PAYMENT: "billing.payment",
  INSURANCE_VIEW: "insurance.view",
  INSURANCE_MANAGE: "insurance.manage",
  FINANCE_VIEW: "finance.view",
  FINANCE_MANAGE: "finance.manage",
  INVENTORY_VIEW: "inventory.view",
  INVENTORY_MANAGE: "inventory.manage",
  HR_VIEW: "hr.view",
  HR_MANAGE: "hr.manage",
  APPOINTMENTS_VIEW: "appointments.view",
  APPOINTMENTS_MANAGE: "appointments.manage",
  REFERRALS_VIEW: "referrals.view",
  REFERRALS_MANAGE: "referrals.manage",
  REPORTS_VIEW: "reports.view",
  ANALYTICS_VIEW: "analytics.view",
  COMMUNICATIONS_VIEW: "communications.view",
  TRIALS_VIEW: "trials.view",
  KNOWLEDGE_VIEW: "knowledge.view",
  SETTINGS_MANAGE: "settings.manage",
} as const;

/** One of the permission strings above, or a string the API added later. */
export type PermissionString = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

/** Every permission, for the public beta walkthrough account. */
export const ALL_PERMISSIONS: readonly string[] = Object.values(PERMISSIONS);
