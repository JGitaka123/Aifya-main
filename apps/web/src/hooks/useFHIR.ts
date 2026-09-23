"use client";

import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import type {
  FHIRBundle,
  FHIRCapabilityStatement,
} from "@aifya/shared";

// ── Capability Statement ────────────────────────────────────────────────────

/**
 * Hook for fetching the FHIR CapabilityStatement (server metadata).
 *
 * @returns Query result with CapabilityStatement
 */
export function useFHIRCapability() {
  return useOfflineQuery<FHIRCapabilityStatement>({
    queryKey: ["fhir", "metadata"],
    queryFn: () =>
      apiClient.get<FHIRCapabilityStatement>("/fhir/metadata"),
    refetchInterval: 300_000,
  });
}

// ── Patient ─────────────────────────────────────────────────────────────────

/**
 * Hook for searching FHIR Patient resources.
 *
 * @param params - Search parameters (name, identifier, birthdate)
 * @returns Query result with FHIR Bundle
 */
export function useFHIRPatients(params?: {
  name?: string;
  identifier?: string;
  birthdate?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.name) qs.set("name", params.name);
  if (params?.identifier) qs.set("identifier", params.identifier);
  if (params?.birthdate) qs.set("birthdate", params.birthdate);
  const query = qs.toString();

  return useOfflineQuery<FHIRBundle>({
    queryKey: ["fhir", "Patient", params],
    queryFn: () =>
      apiClient.get<FHIRBundle>(`/fhir/Patient${query ? `?${query}` : ""}`),
    enabled: !!(params?.name || params?.identifier || params?.birthdate),
  });
}

/**
 * Hook for reading a single FHIR Patient resource.
 *
 * @param patientId - Patient UUID
 * @returns Query result with FHIR Patient resource
 */
export function useFHIRPatient(patientId: string | undefined) {
  return useOfflineQuery<Record<string, unknown>>({
    queryKey: ["fhir", "Patient", patientId],
    queryFn: () =>
      apiClient.get<Record<string, unknown>>(`/fhir/Patient/${patientId}`),
    enabled: !!patientId,
  });
}

// ── Encounter ───────────────────────────────────────────────────────────────

/**
 * Hook for searching FHIR Encounter resources.
 *
 * @param params - Search parameters (patient, status)
 * @returns Query result with FHIR Bundle
 */
export function useFHIREncounters(params?: {
  patient?: string;
  status?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.patient) qs.set("patient", params.patient);
  if (params?.status) qs.set("status", params.status);
  const query = qs.toString();

  return useOfflineQuery<FHIRBundle>({
    queryKey: ["fhir", "Encounter", params],
    queryFn: () =>
      apiClient.get<FHIRBundle>(`/fhir/Encounter${query ? `?${query}` : ""}`),
  });
}

// ── Observation ─────────────────────────────────────────────────────────────

/**
 * Hook for searching FHIR Observation resources (vitals + labs).
 *
 * @param params - Search parameters (patient, category, code)
 * @returns Query result with FHIR Bundle
 */
export function useFHIRObservations(params?: {
  patient?: string;
  category?: string;
  code?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.patient) qs.set("patient", params.patient);
  if (params?.category) qs.set("category", params.category);
  if (params?.code) qs.set("code", params.code);
  const query = qs.toString();

  return useOfflineQuery<FHIRBundle>({
    queryKey: ["fhir", "Observation", params],
    queryFn: () =>
      apiClient.get<FHIRBundle>(`/fhir/Observation${query ? `?${query}` : ""}`),
  });
}

// ── MedicationRequest ───────────────────────────────────────────────────────

/**
 * Hook for searching FHIR MedicationRequest resources.
 *
 * @param params - Search parameters (patient, status)
 * @returns Query result with FHIR Bundle
 */
export function useFHIRMedicationRequests(params?: {
  patient?: string;
  status?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.patient) qs.set("patient", params.patient);
  if (params?.status) qs.set("status", params.status);
  const query = qs.toString();

  return useOfflineQuery<FHIRBundle>({
    queryKey: ["fhir", "MedicationRequest", params],
    queryFn: () =>
      apiClient.get<FHIRBundle>(
        `/fhir/MedicationRequest${query ? `?${query}` : ""}`,
      ),
  });
}

// ── Condition ───────────────────────────────────────────────────────────────

/**
 * Hook for searching FHIR Condition resources.
 *
 * @param params - Search parameters (patient, clinical-status)
 * @returns Query result with FHIR Bundle
 */
export function useFHIRConditions(params?: {
  patient?: string;
  clinicalStatus?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.patient) qs.set("patient", params.patient);
  if (params?.clinicalStatus) qs.set("clinical-status", params.clinicalStatus);
  const query = qs.toString();

  return useOfflineQuery<FHIRBundle>({
    queryKey: ["fhir", "Condition", params],
    queryFn: () =>
      apiClient.get<FHIRBundle>(`/fhir/Condition${query ? `?${query}` : ""}`),
  });
}

// ── DiagnosticReport ────────────────────────────────────────────────────────

/**
 * Hook for reading a FHIR DiagnosticReport resource.
 *
 * @param orderId - Lab order UUID
 * @returns Query result with FHIR DiagnosticReport
 */
export function useFHIRDiagnosticReport(orderId: string | undefined) {
  return useOfflineQuery<Record<string, unknown>>({
    queryKey: ["fhir", "DiagnosticReport", orderId],
    queryFn: () =>
      apiClient.get<Record<string, unknown>>(
        `/fhir/DiagnosticReport/${orderId}`,
      ),
    enabled: !!orderId,
  });
}
