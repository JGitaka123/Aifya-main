/**
 * FHIR R4 resource types for the interoperability gateway.
 * Simplified TypeScript representations of core FHIR resources.
 */

/** FHIR coding element. */
export interface FHIRCoding {
  system?: string | null;
  code?: string | null;
  display?: string | null;
}

/** FHIR codeable concept. */
export interface FHIRCodeableConcept {
  coding?: FHIRCoding[];
  text?: string | null;
}

/** FHIR reference to another resource. */
export interface FHIRReference {
  reference?: string | null;
  display?: string | null;
}

/** FHIR bundle entry. */
export interface FHIRBundleEntry {
  fullUrl?: string | null;
  resource?: Record<string, unknown> | null;
}

/** FHIR Bundle — collection of resources. */
export interface FHIRBundle {
  resourceType: "Bundle";
  type: string;
  total?: number | null;
  entry: FHIRBundleEntry[];
}

/** FHIR capability statement resource entry. */
export interface FHIRCapabilityResource {
  type: string;
  interaction: Array<{ code: string }>;
  searchParam: Array<{ name: string; type: string }>;
}

/** FHIR CapabilityStatement. */
export interface FHIRCapabilityStatement {
  resourceType: "CapabilityStatement";
  name?: string | null;
  title?: string | null;
  description?: string | null;
  status: string;
  fhirVersion: string;
  format: string[];
  rest: Array<{
    mode: string;
    resource: FHIRCapabilityResource[];
  }>;
}

/** Supported FHIR resource types for the explorer. */
export type FHIRResourceType =
  | "Patient"
  | "Encounter"
  | "Observation"
  | "MedicationRequest"
  | "Condition"
  | "DiagnosticReport";
