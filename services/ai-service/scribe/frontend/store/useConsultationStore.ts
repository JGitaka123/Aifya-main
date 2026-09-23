import { create } from "zustand";
import { api, ApiError } from "@/lib/api";

export interface VitalSign { name: string; value: string; loinc_code?: string; confidence: number; }
export interface Diagnosis { name: string; icd11_suggested?: string; icd11_validated?: string; is_primary: boolean; confidence: number; }
export interface LabOrder { test_name: string; loinc_code?: string; urgency: string; }
export interface Procedure { name: string; ichi_code?: string; requires_preauth: boolean; }
export interface Medication { name: string; dose: string; route: string; frequency: string; duration: string; is_new: boolean; }
export interface ClinicalExtraction {
  chief_complaint?: string;
  reporting_problem?: string;
  symptoms?: string;
  hpi?: string;
  vitals: VitalSign[];
  physical_exam?: string;
  diagnoses: Diagnosis[];
  lab_orders: LabOrder[];
  suggested_tests?: string[];
  medications: Medication[];
  procedures: Procedure[];
  disposition?: string;
  follow_up?: string;
  warnings: string[];
}
export interface ScrubViolation {
  rule_id: string;
  rule_name: string;
  severity: string;
  message: string;
  suggested_fix: string;
}
export interface ScrubResult {
  status: "pending" | "passed" | "blocked" | "warnings_only" | "overridden";
  violations: ScrubViolation[];
  can_submit: boolean;
}
export interface Patient {
  national_id: string;
  insurance_no: string;
  full_name: string;
  insurance_status: string;
  insurance_package: string;
  max_benefit_cap: number;
}

export interface ConsultationState {
  patient: Patient | null;
  patientLoading: boolean;
  patientError: string | null;

  isRecording: boolean;
  audioBlobUrl: string | null;
  recordingDuration: number;

  transcript: string;
  isTranscribing: boolean;

  extraction: ClinicalExtraction | null;
  isExtracting: boolean;
  extractionError: string | null;

  scrubResult: ScrubResult | null;
  isScrubbing: boolean;

  encounterStatus: "idle" | "recording" | "transcribing" | "extracting" | "scrubbed" | "syncing" | "finalized";
  syncError: string | null;

  lookupPatient: (identifier: string) => Promise<void>;
  startRecording: () => void;
  stopRecording: (objectUrl: string) => void;
  setTranscript: (transcript: string) => void;
  extractNote: () => Promise<void>;
  scrubClaim: () => Promise<void>;
  updateExtraction: (field: string, value: any) => void;
  finalizeAndSync: (encounterId: string) => Promise<void>;
  reset: () => void;
}

const initialState = {
  patient: null,
  patientLoading: false,
  patientError: null,
  isRecording: false,
  audioBlobUrl: null,
  recordingDuration: 0,
  transcript: "",
  isTranscribing: false,
  extraction: null,
  isExtracting: false,
  extractionError: null,
  scrubResult: null,
  isScrubbing: false,
  encounterStatus: "idle" as const,
  syncError: null,
};

export const useConsultationStore = create<ConsultationState>((set, get) => ({
  ...initialState,

  lookupPatient: async (identifier) => {
    set({ patientLoading: true, patientError: null });
    try {
      const patient = await api.patients.lookup(identifier);
      set({
        patient: {
          national_id: patient.national_id || identifier,
          insurance_no: patient.insurance_no || "",
          full_name: patient.full_name || "Unknown",
          insurance_status: patient.insurance_status || "UNKNOWN",
          insurance_package: patient.insurance_package || "SHIF",
          max_benefit_cap: patient.max_benefit_cap || 0,
        },
        encounterStatus: "idle",
      });
    } catch (err: any) {
      const message = err instanceof ApiError ? err.message : "Patient lookup failed";
      set({ patientError: message });
    } finally {
      set({ patientLoading: false });
    }
  },

  startRecording: () => set({ isRecording: true, encounterStatus: "recording", audioBlobUrl: null, extraction: null, scrubResult: null, extractionError: null }),
  stopRecording: (objectUrl: string) => set({ isRecording: false, audioBlobUrl: objectUrl }),

  setTranscript: (transcript: string) => set({ transcript }),

  extractNote: async () => {
    const { transcript, audioBlobUrl } = get();
    set({ isExtracting: true, encounterStatus: "extracting", extractionError: null });
    try {
      let text = transcript;

      // If no manual transcript but we have audio, transcribe it first
      if (!text && audioBlobUrl) {
        set({ encounterStatus: "transcribing", isTranscribing: true });
        const audioResponse = await fetch(audioBlobUrl);
        const audioBlob = await audioResponse.blob();
        text = await api.scribe.transcribe(audioBlob);
        set({ transcript: text, isTranscribing: false });
      }

      if (!text || text.length < 10) {
        throw new Error("No clinical information provided in the transcript.");
      }

      const extraction = await api.scribe.extract(text);
      set({ extraction, encounterStatus: "scrubbed" });
    } catch (err: any) {
      console.error("Extraction error:", err);
      const message = err instanceof ApiError ? err.message : (err.message || String(err) || "Extraction failed");
      set({ extractionError: message, encounterStatus: "idle" });
    } finally {
      set({ isExtracting: false, isTranscribing: false });
    }
  },

  scrubClaim: async () => {
    const { extraction, patient } = get();
    if (!extraction || !patient) return;

    set({ isScrubbing: true });
    try {
      const result = await api.claims.scrub({
        extraction,
        sha_status: patient.insurance_status,
        sha_package: patient.insurance_package,
        amount: 5000,
        encounter_date: new Date().toISOString(),
        encounter_type: "outpatient",
        has_preauth: false,
      });
      set({ scrubResult: result });
    } catch (err: any) {
      set({
        scrubResult: {
          status: "blocked",
          violations: [{ rule_id: "ERR", rule_name: "Error", severity: "BLOCK", message: err.message || "Scrub failed", suggested_fix: "Try again" }],
          can_submit: false,
        },
      });
    } finally {
      set({ isScrubbing: false });
    }
  },

  updateExtraction: (field, value) =>
    set((state) => ({
      extraction: state.extraction ? { ...state.extraction, [field]: value } : null,
    })),

  finalizeAndSync: async (encounterId: string) => {
    const { extraction } = get();
    if (!extraction) return;

    set({ encounterStatus: "syncing", syncError: null });
    try {
      await api.sync.clinicalNote(encounterId, {
        subjective: extraction.chief_complaint || "",
        objective: { vitals: extraction.vitals, physical_exam: extraction.physical_exam || "" },
        assessment: {
          diagnoses: extraction.diagnoses,
          primary_diagnosis_icd11: extraction.diagnoses.find((d) => d.is_primary)?.icd11_validated || "",
        },
        plan: {
          medications: extraction.medications,
          lab_orders: extraction.lab_orders,
          procedures: extraction.procedures,
          disposition: extraction.disposition || "",
        },
      });
      set({ encounterStatus: "finalized" });
    } catch (err: any) {
      set({ syncError: err.message || "Sync failed", encounterStatus: "scrubbed" });
    }
  },

  reset: () => set(initialState),
}));
