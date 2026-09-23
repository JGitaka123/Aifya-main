"""
FHIR R4 resource models — simplified Pydantic models matching FHIR structure.

These models represent the core FHIR R4 resources used for health data exchange.
See: https://hl7.org/fhir/R4/

All models follow FHIR R4 naming conventions (camelCase fields).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ── FHIR Primitives & Building Blocks ──────────────────────────────────────


class FHIRCoding(BaseModel):
    """
    FHIR R4 Coding — a reference to a code defined by a terminology system.

    @param system: Identity of the terminology system (e.g., http://loinc.org)
    @param code: Symbol in syntax defined by the system
    @param display: Representation defined by the system
    """

    system: str | None = None
    code: str | None = None
    display: str | None = None


class FHIRCodeableConcept(BaseModel):
    """
    FHIR R4 CodeableConcept — a concept that may be defined by one or more coding systems.

    @param coding: Code(s) defined by a terminology system
    @param text: Plain text representation of the concept
    """

    coding: list[FHIRCoding] = Field(default_factory=list)
    text: str | None = None


class FHIRIdentifier(BaseModel):
    """
    FHIR R4 Identifier — a numeric or alphanumeric string associated with a resource.

    @param system: The namespace for the identifier value
    @param value: The value that is unique within the system
    @param type: A coded type for the identifier
    """

    system: str | None = None
    value: str | None = None
    type: FHIRCodeableConcept | None = None


class FHIRHumanName(BaseModel):
    """
    FHIR R4 HumanName — name of a human.

    @param use: usual | official | temp | nickname | anonymous | old | maiden
    @param family: Family name (often called 'Surname')
    @param given: Given names (not always 'first')
    @param text: Full text representation of the name
    """

    use: str | None = None
    family: str | None = None
    given: list[str] = Field(default_factory=list)
    text: str | None = None


class FHIRContactPoint(BaseModel):
    """
    FHIR R4 ContactPoint — details of a technology-mediated contact point.

    @param system: phone | fax | email | pager | url | sms | other
    @param value: The actual contact point details
    @param use: home | work | temp | old | mobile
    """

    system: str | None = None
    value: str | None = None
    use: str | None = None


class FHIRAddress(BaseModel):
    """
    FHIR R4 Address — postal address.

    @param use: home | work | temp | old | billing
    @param type: postal | physical | both
    @param text: Full text representation
    @param line: Street name, number, direction, P.O. Box, etc.
    @param city: City, town, or village
    @param district: Sub-county / district
    @param state: County (Kenya-specific)
    @param postalCode: Postal code
    @param country: Country (ISO 3166)
    """

    use: str | None = None
    type: str | None = None
    text: str | None = None
    line: list[str] = Field(default_factory=list)
    city: str | None = None
    district: str | None = None
    state: str | None = None
    postalCode: str | None = None
    country: str | None = None


class FHIRReference(BaseModel):
    """
    FHIR R4 Reference — a reference from one resource to another.

    @param reference: Relative or absolute URI reference
    @param display: Text alternative for the resource
    """

    reference: str | None = None
    display: str | None = None


class FHIRPeriod(BaseModel):
    """
    FHIR R4 Period — a time period defined by a start and end date/time.

    @param start: Starting time with inclusive boundary
    @param end: End time with inclusive boundary
    """

    start: str | None = None
    end: str | None = None


class FHIRQuantity(BaseModel):
    """
    FHIR R4 Quantity — a measured amount (or an amount that can potentially be measured).

    @param value: Numerical value
    @param unit: Unit representation
    @param system: System that defines coded unit form
    @param code: Coded form of the unit
    """

    value: float | None = None
    unit: str | None = None
    system: str | None = None
    code: str | None = None


class FHIRReferenceRange(BaseModel):
    """
    FHIR R4 Observation reference range.

    @param low: Low Range, if relevant
    @param high: High Range, if relevant
    @param text: Text based reference range
    """

    low: FHIRQuantity | None = None
    high: FHIRQuantity | None = None
    text: str | None = None


class FHIRMeta(BaseModel):
    """
    FHIR R4 Meta — metadata about a resource.

    @param versionId: Version specific identifier
    @param lastUpdated: When the resource version last changed
    """

    versionId: str | None = None
    lastUpdated: str | None = None


class FHIRDosageInstruction(BaseModel):
    """
    FHIR R4 Dosage — how medication is/was taken or should be taken.

    @param text: Free text dosage instructions
    @param route: How drug should enter body
    @param timing: When medication should be administered (text form)
    @param doseAndRate: Amount of medication administered
    """

    text: str | None = None
    route: FHIRCodeableConcept | None = None
    timing: dict | None = None
    doseAndRate: list[dict] | None = None


# ── FHIR Issue (for OperationOutcome) ──────────────────────────────────────


class FHIRIssueSeverity(StrEnum):
    """FHIR OperationOutcome issue severity."""

    FATAL = "fatal"
    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"


class FHIRIssueCode(StrEnum):
    """FHIR OperationOutcome issue code (subset of common codes)."""

    NOT_FOUND = "not-found"
    INVALID = "invalid"
    PROCESSING = "processing"
    SECURITY = "security"
    INFORMATIONAL = "informational"
    EXCEPTION = "exception"
    NOT_SUPPORTED = "not-supported"


class FHIRIssue(BaseModel):
    """
    FHIR R4 OperationOutcome Issue.

    @param severity: fatal | error | warning | information
    @param code: Error or condition code
    @param diagnostics: Additional diagnostic information about the issue
    """

    severity: FHIRIssueSeverity
    code: FHIRIssueCode
    diagnostics: str | None = None


# ── FHIR Resources ─────────────────────────────────────────────────────────


class FHIRResource(BaseModel):
    """
    Base FHIR R4 resource with resourceType, id, and meta.

    @param resourceType: Type of the resource
    @param id: Logical id of the resource
    @param meta: Metadata about the resource
    """

    resourceType: str
    id: str | None = None
    meta: FHIRMeta | None = None


class FHIRPatient(FHIRResource):
    """
    FHIR R4 Patient resource.
    Maps Aifya patient demographics to FHIR-compliant structure.

    @param identifier: MRN, national ID, and other identifiers
    @param name: Patient name(s)
    @param gender: male | female | other | unknown
    @param birthDate: Date of birth (YYYY-MM-DD)
    @param telecom: Contact points (phone, email)
    @param address: Patient address(es)
    """

    resourceType: str = "Patient"
    identifier: list[FHIRIdentifier] = Field(default_factory=list)
    name: list[FHIRHumanName] = Field(default_factory=list)
    gender: str | None = None
    birthDate: str | None = None
    telecom: list[FHIRContactPoint] = Field(default_factory=list)
    address: list[FHIRAddress] = Field(default_factory=list)


class FHIREncounter(FHIRResource):
    """
    FHIR R4 Encounter resource.
    Maps Aifya clinical encounters to FHIR structure.

    @param status: planned | arrived | triaged | in-progress | onleave | finished | cancelled
    @param class_: Classification of patient encounter (AMB, EMER, IMP, etc.)
    @param type: Specific type of encounter
    @param subject: The patient present at the encounter
    @param period: The start and end time of the encounter
    @param reasonCode: Coded reason(s) the encounter takes place
    @param location: Location(s) where the encounter took place
    """

    resourceType: str = "Encounter"
    status: str | None = None
    class_: FHIRCoding | None = Field(None, alias="class")
    type: list[FHIRCodeableConcept] = Field(default_factory=list)
    subject: FHIRReference | None = None
    period: FHIRPeriod | None = None
    reasonCode: list[FHIRCodeableConcept] = Field(default_factory=list)
    location: list[dict] | None = None

    model_config = {"populate_by_name": True}


class FHIRObservation(FHIRResource):
    """
    FHIR R4 Observation resource.
    Used for vitals, lab results, and other clinical measurements.

    @param status: registered | preliminary | final | amended | corrected | cancelled
    @param category: Classification of type of observation
    @param code: Type of observation (LOINC coded)
    @param subject: Who/what the observation is about
    @param effectiveDateTime: Clinically relevant time for observation
    @param valueQuantity: Actual result value
    @param valueString: String result value (for non-numeric)
    @param referenceRange: Reference range(s) for interpretation
    @param interpretation: High, low, normal, etc.
    """

    resourceType: str = "Observation"
    status: str | None = None
    category: list[FHIRCodeableConcept] = Field(default_factory=list)
    code: FHIRCodeableConcept | None = None
    subject: FHIRReference | None = None
    effectiveDateTime: str | None = None
    valueQuantity: FHIRQuantity | None = None
    valueString: str | None = None
    referenceRange: list[FHIRReferenceRange] = Field(default_factory=list)
    interpretation: list[FHIRCodeableConcept] = Field(default_factory=list)


class FHIRMedicationRequest(FHIRResource):
    """
    FHIR R4 MedicationRequest resource.
    Maps Aifya prescriptions to FHIR medication ordering structure.

    @param status: active | on-hold | cancelled | completed | stopped | draft
    @param intent: proposal | plan | order | original-order | reflex-order | filler-order | instance-order | option
    @param medicationCodeableConcept: Medication being requested
    @param subject: Who the medication request is for
    @param authoredOn: When request was initially authored
    @param dosageInstruction: How the medication should be taken
    """

    resourceType: str = "MedicationRequest"
    status: str | None = None
    intent: str = "order"
    medicationCodeableConcept: FHIRCodeableConcept | None = None
    subject: FHIRReference | None = None
    authoredOn: str | None = None
    dosageInstruction: list[FHIRDosageInstruction] = Field(default_factory=list)


class FHIRDiagnosticReport(FHIRResource):
    """
    FHIR R4 DiagnosticReport resource.
    Groups lab results under a single report.

    @param status: registered | partial | preliminary | final | amended | corrected | appended | cancelled
    @param category: Service category
    @param code: Name/code for this diagnostic report
    @param subject: The subject of the report
    @param effectiveDateTime: Clinically relevant time for the report
    @param result: Observations that are part of this diagnostic report
    """

    resourceType: str = "DiagnosticReport"
    status: str | None = None
    category: list[FHIRCodeableConcept] = Field(default_factory=list)
    code: FHIRCodeableConcept | None = None
    subject: FHIRReference | None = None
    effectiveDateTime: str | None = None
    result: list[FHIRReference] = Field(default_factory=list)


class FHIRCondition(FHIRResource):
    """
    FHIR R4 Condition resource.
    Maps Aifya diagnoses to FHIR condition structure.

    @param clinicalStatus: active | recurrence | relapse | inactive | remission | resolved
    @param verificationStatus: unconfirmed | provisional | differential | confirmed | refuted
    @param category: problem-list-item | encounter-diagnosis
    @param code: Identification of the condition (ICD-10)
    @param subject: Who has the condition
    @param onsetDateTime: Estimated or actual date the condition began
    """

    resourceType: str = "Condition"
    clinicalStatus: FHIRCodeableConcept | None = None
    verificationStatus: FHIRCodeableConcept | None = None
    category: list[FHIRCodeableConcept] = Field(default_factory=list)
    code: FHIRCodeableConcept | None = None
    subject: FHIRReference | None = None
    onsetDateTime: str | None = None


# ── FHIR Bundle ────────────────────────────────────────────────────────────


class FHIRBundleEntry(BaseModel):
    """
    FHIR R4 Bundle entry.

    @param fullUrl: URI for resource (e.g., Patient/uuid)
    @param resource: The resource in the entry
    """

    fullUrl: str | None = None
    resource: dict | None = None


class FHIRBundle(FHIRResource):
    """
    FHIR R4 Bundle — a container for a collection of resources.

    @param type: searchset | batch | transaction | batch-response | transaction-response | history | document | message | collection
    @param total: Total number of matches if search
    @param entry: Entry in the bundle
    """

    resourceType: str = "Bundle"
    type: str = "searchset"
    total: int | None = None
    entry: list[FHIRBundleEntry] = Field(default_factory=list)


# ── FHIR OperationOutcome ──────────────────────────────────────────────────


class FHIROperationOutcome(FHIRResource):
    """
    FHIR R4 OperationOutcome — information about the outcome of an operation.
    Used for error responses and warnings.

    @param issue: List of issues (errors, warnings, information)
    """

    resourceType: str = "OperationOutcome"
    issue: list[FHIRIssue] = Field(default_factory=list)


# ── FHIR CapabilityStatement (simplified) ──────────────────────────────────


class FHIRCapabilityRestResource(BaseModel):
    """
    Simplified capability statement resource entry.

    @param type: Resource type name
    @param interaction: Supported interactions
    @param searchParam: Supported search parameters
    """

    type: str
    interaction: list[dict] = Field(default_factory=list)
    searchParam: list[dict] = Field(default_factory=list)


class FHIRCapabilityRest(BaseModel):
    """
    Simplified capability statement REST entry.

    @param mode: server | client
    @param resource: Resources served by the endpoint
    """

    mode: str = "server"
    resource: list[FHIRCapabilityRestResource] = Field(default_factory=list)


class FHIRCapabilityStatement(FHIRResource):
    """
    FHIR R4 CapabilityStatement — server capabilities declaration.

    @param status: draft | active | retired | unknown
    @param kind: instance | capability | requirements
    @param fhirVersion: FHIR version (4.0.1)
    @param format: Supported formats
    @param rest: REST capabilities
    """

    resourceType: str = "CapabilityStatement"
    status: str = "active"
    kind: str = "instance"
    fhirVersion: str = "4.0.1"
    format: list[str] = Field(default_factory=lambda: ["application/fhir+json"])
    rest: list[FHIRCapabilityRest] = Field(default_factory=list)
    name: str | None = None
    title: str | None = None
    date: str | None = None
    publisher: str | None = None
    description: str | None = None
    software: dict | None = None
