"""
FHIR R4 mappers — convert between Aifya internal models and FHIR R4 resources.

Maps Patient, Encounter, VitalSign, Prescription, Diagnosis, and LabResult
to their FHIR R4 counterparts with standard terminology system references.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.fhir.models import (
    FHIRAddress,
    FHIRBundle,
    FHIRBundleEntry,
    FHIRCodeableConcept,
    FHIRCoding,
    FHIRCondition,
    FHIRContactPoint,
    FHIRDosageInstruction,
    FHIREncounter,
    FHIRHumanName,
    FHIRIdentifier,
    FHIRMedicationRequest,
    FHIRMeta,
    FHIRObservation,
    FHIRPatient,
    FHIRPeriod,
    FHIRQuantity,
    FHIRReference,
    FHIRReferenceRange,
)

if TYPE_CHECKING:
    from app.models.diagnosis import Diagnosis
    from app.models.encounter import Encounter
    from app.models.lab import LabResult
    from app.models.patient import Patient
    from app.models.prescription import Prescription
    from app.models.vital import VitalSign


# ── LOINC Code Mappings ───────────────────────────────────────────────────────

VITAL_LOINC: dict[str, tuple[str, str, str]] = {
    # key: (loinc_code, display_name, unit)
    "systolic_bp": ("8480-6", "Systolic blood pressure", "mmHg"),
    "diastolic_bp": ("8462-4", "Diastolic blood pressure", "mmHg"),
    "heart_rate": ("8867-4", "Heart rate", "beats/min"),
    "temperature": ("8310-5", "Body temperature", "Cel"),
    "respiratory_rate": ("9279-1", "Respiratory rate", "breaths/min"),
    "oxygen_saturation": ("2708-6", "Oxygen saturation", "%"),
    "weight_kg": ("29463-7", "Body weight", "kg"),
    "height_cm": ("8302-2", "Body height", "cm"),
    "bmi": ("39156-5", "Body mass index", "kg/m2"),
    "blood_glucose": ("2345-7", "Glucose [Mass/volume] in Blood", "mmol/L"),
}

# ── Encounter Status Mapping ─────────────────────────────────────────────────

ENCOUNTER_STATUS_MAP: dict[str, str] = {
    "waiting": "arrived",
    "in_consultation": "in-progress",
    "completed": "finished",
    "admitted": "in-progress",
    "discharged": "finished",
    "cancelled": "cancelled",
}

ENCOUNTER_CLASS_MAP: dict[str, tuple[str, str]] = {
    "opd": ("AMB", "ambulatory"),
    "ipd": ("IMP", "inpatient encounter"),
    "emergency": ("EMER", "emergency"),
    "mch": ("AMB", "ambulatory"),
    "dental": ("AMB", "ambulatory"),
    "surgical": ("IMP", "inpatient encounter"),
    "follow_up": ("AMB", "ambulatory"),
}


# ── Patient Mapper ────────────────────────────────────────────────────────────


def patient_to_fhir(patient: Patient) -> FHIRPatient:
    """
    Convert an Aifya Patient to a FHIR R4 Patient resource.

    @param patient: Aifya patient model
    @returns FHIRPatient resource
    """
    identifiers: list[FHIRIdentifier] = []
    if patient.mrn:
        identifiers.append(
            FHIRIdentifier(
                system="urn:aifya:mrn",
                value=patient.mrn,
                type=FHIRCodeableConcept(text="Medical Record Number"),
            )
        )
    if hasattr(patient, "national_id") and patient.national_id:
        identifiers.append(
            FHIRIdentifier(
                system="urn:ke:national-id",
                value=patient.national_id,
                type=FHIRCodeableConcept(text="National ID"),
            )
        )

    telecom: list[FHIRContactPoint] = []
    if patient.phone_number:
        telecom.append(
            FHIRContactPoint(system="phone", value=patient.phone_number, use="mobile")
        )
    if hasattr(patient, "email") and patient.email:
        telecom.append(
            FHIRContactPoint(system="email", value=patient.email, use="home")
        )

    address: list[FHIRAddress] = []
    if hasattr(patient, "county") and patient.county:
        address.append(
            FHIRAddress(
                use="home",
                state=patient.county,
                district=getattr(patient, "sub_county", None),
                country="KE",
            )
        )

    updated = str(patient.updated_at) if patient.updated_at else None

    return FHIRPatient(
        id=str(patient.id),
        meta=FHIRMeta(versionId="1", lastUpdated=updated),
        identifier=identifiers,
        name=[
            FHIRHumanName(
                use="official",
                family=patient.last_name,
                given=[patient.first_name]
                + ([patient.middle_name] if getattr(patient, "middle_name", None) else []),
                text=f"{patient.first_name} {patient.last_name}",
            )
        ],
        gender=patient.gender or "unknown",
        birthDate=str(patient.date_of_birth) if patient.date_of_birth else None,
        telecom=telecom,
        address=address,
    )


# ── Encounter Mapper ─────────────────────────────────────────────────────────


def encounter_to_fhir(encounter: Encounter) -> FHIREncounter:
    """
    Convert an Aifya Encounter to a FHIR R4 Encounter resource.

    @param encounter: Aifya encounter model
    @returns FHIREncounter resource
    """
    enc_type = encounter.encounter_type or "opd"
    class_code, class_display = ENCOUNTER_CLASS_MAP.get(enc_type, ("AMB", "ambulatory"))
    fhir_status = ENCOUNTER_STATUS_MAP.get(encounter.status or "waiting", "unknown")

    reason_codes: list[FHIRCodeableConcept] = []
    if encounter.chief_complaint:
        reason_codes.append(FHIRCodeableConcept(text=encounter.chief_complaint))

    period_start = str(encounter.encounter_date) if encounter.encounter_date else None

    return FHIREncounter(
        id=str(encounter.id),
        meta=FHIRMeta(versionId="1", lastUpdated=str(encounter.updated_at) if encounter.updated_at else None),
        status=fhir_status,
        **{"class": FHIRCoding(
            system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
            code=class_code,
            display=class_display,
        )},
        subject=FHIRReference(reference=f"Patient/{encounter.patient_id}"),
        period=FHIRPeriod(start=period_start),
        reasonCode=reason_codes,
    )


# ── Vital Signs Mapper ───────────────────────────────────────────────────────


def vital_to_fhir(vital: VitalSign) -> list[FHIRObservation]:
    """
    Convert an Aifya VitalSign record to individual FHIR R4 Observations.
    Each vital parameter becomes its own Observation with LOINC coding.

    @param vital: Aifya vital signs model
    @returns List of FHIRObservation resources (one per measured vital)
    """
    observations: list[FHIRObservation] = []
    recorded = str(vital.recorded_at) if hasattr(vital, "recorded_at") and vital.recorded_at else str(vital.created_at)

    vital_category = FHIRCodeableConcept(
        coding=[
            FHIRCoding(
                system="http://terminology.hl7.org/CodeSystem/observation-category",
                code="vital-signs",
                display="Vital Signs",
            )
        ]
    )

    for attr, (loinc, display, unit) in VITAL_LOINC.items():
        value = getattr(vital, attr, None)
        if value is None:
            continue

        obs = FHIRObservation(
            id=f"{vital.id}-{attr}",
            status="final",
            category=[vital_category],
            code=FHIRCodeableConcept(
                coding=[FHIRCoding(system="http://loinc.org", code=loinc, display=display)],
                text=display,
            ),
            subject=FHIRReference(reference=f"Patient/{vital.patient_id}"),
            effectiveDateTime=recorded,
            valueQuantity=FHIRQuantity(
                value=float(value),
                unit=unit,
                system="http://unitsofmeasure.org",
                code=unit,
            ),
        )
        observations.append(obs)

    return observations


# ── Prescription Mapper ───────────────────────────────────────────────────────


def prescription_to_fhir(rx: Prescription) -> FHIRMedicationRequest:
    """
    Convert an Aifya Prescription to a FHIR R4 MedicationRequest resource.

    @param rx: Aifya prescription model
    @returns FHIRMedicationRequest resource
    """
    status_map: dict[str, str] = {
        "pending": "active",
        "dispensed": "completed",
        "partially_dispensed": "active",
        "cancelled": "cancelled",
    }

    return FHIRMedicationRequest(
        id=str(rx.id),
        meta=FHIRMeta(versionId="1", lastUpdated=str(rx.updated_at) if rx.updated_at else None),
        status=status_map.get(rx.status or "pending", "active"),
        intent="order",
        medicationCodeableConcept=FHIRCodeableConcept(
            text=rx.drug_name,
            coding=[
                FHIRCoding(
                    system="urn:aifya:drug-code",
                    code=rx.drug_code,
                    display=rx.drug_name,
                )
            ]
            if rx.drug_code
            else [],
        ),
        subject=FHIRReference(reference=f"Patient/{rx.patient_id}"),
        authoredOn=str(rx.created_at) if rx.created_at else None,
        dosageInstruction=[
            FHIRDosageInstruction(
                text=f"{rx.dosage} {rx.route} {rx.frequency}",
                route=FHIRCodeableConcept(text=rx.route),
            )
        ],
    )


# ── Diagnosis Mapper ─────────────────────────────────────────────────────────


def diagnosis_to_fhir(dx: Diagnosis) -> FHIRCondition:
    """
    Convert an Aifya Diagnosis to a FHIR R4 Condition resource.

    @param dx: Aifya diagnosis model
    @returns FHIRCondition resource
    """
    clinical_status_map: dict[str, str] = {
        "active": "active",
        "recurrence": "recurrence",
        "relapse": "relapse",
        "inactive": "inactive",
        "remission": "remission",
        "resolved": "resolved",
    }

    verification_map: dict[str, str] = {
        "primary": "confirmed",
        "secondary": "confirmed",
        "differential": "differential",
        "ruled_out": "refuted",
    }

    cs = clinical_status_map.get(dx.clinical_status or "active", "active")
    vs = verification_map.get(dx.diagnosis_type or "primary", "confirmed")

    return FHIRCondition(
        id=str(dx.id),
        meta=FHIRMeta(versionId="1", lastUpdated=str(dx.updated_at) if dx.updated_at else None),
        clinicalStatus=FHIRCodeableConcept(
            coding=[
                FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                    code=cs,
                )
            ]
        ),
        verificationStatus=FHIRCodeableConcept(
            coding=[
                FHIRCoding(
                    system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    code=vs,
                )
            ]
        ),
        category=[
            FHIRCodeableConcept(
                coding=[
                    FHIRCoding(
                        system="http://terminology.hl7.org/CodeSystem/condition-category",
                        code="encounter-diagnosis",
                    )
                ]
            )
        ],
        code=FHIRCodeableConcept(
            coding=[
                FHIRCoding(
                    system="http://hl7.org/fhir/sid/icd-10",
                    code=dx.icd10_code,
                    display=dx.icd10_description,
                )
            ],
            text=dx.icd10_description,
        ),
        subject=FHIRReference(reference=f"Patient/{dx.patient_id}"),
        onsetDateTime=str(dx.onset_date) if dx.onset_date else None,
    )


# ── Lab Result Mapper ─────────────────────────────────────────────────────────


def lab_result_to_fhir(result: LabResult) -> FHIRObservation:
    """
    Convert an Aifya LabResult to a FHIR R4 Observation resource.

    @param result: Aifya lab result model
    @returns FHIRObservation resource
    """
    lab_category = FHIRCodeableConcept(
        coding=[
            FHIRCoding(
                system="http://terminology.hl7.org/CodeSystem/observation-category",
                code="laboratory",
                display="Laboratory",
            )
        ]
    )

    value_quantity = None
    value_string = None
    if result.result_numeric is not None:
        value_quantity = FHIRQuantity(
            value=result.result_numeric,
            unit=result.result_unit or "",
        )
    elif result.result_value:
        value_string = result.result_value

    ref_range: list[FHIRReferenceRange] = []
    if result.reference_range:
        ref_range.append(FHIRReferenceRange(text=result.reference_range))

    interp: list[FHIRCodeableConcept] = []
    if result.interpretation:
        interp.append(FHIRCodeableConcept(text=result.interpretation))

    return FHIRObservation(
        id=str(result.id),
        meta=FHIRMeta(versionId="1", lastUpdated=str(result.updated_at) if result.updated_at else None),
        status="final" if result.status == "final" else "preliminary",
        category=[lab_category],
        code=FHIRCodeableConcept(
            coding=[
                FHIRCoding(
                    system="http://loinc.org" if result.loinc_code else "urn:aifya:test-code",
                    code=result.loinc_code or result.test_code,
                    display=result.test_name,
                )
            ],
            text=result.test_name,
        ),
        subject=FHIRReference(reference=f"Patient/{result.patient_id}"),
        effectiveDateTime=str(result.resulted_at) if result.resulted_at else None,
        valueQuantity=value_quantity,
        valueString=value_string,
        referenceRange=ref_range,
        interpretation=interp,
    )


# ── Bundle Helper ─────────────────────────────────────────────────────────────


def make_searchset_bundle(
    resources: list[dict],
    resource_type: str,
) -> FHIRBundle:
    """
    Wrap a list of FHIR resources in a searchset Bundle.

    @param resources: List of FHIR resource dicts
    @param resource_type: Type of resources (e.g., "Patient")
    @returns FHIRBundle with searchset type
    """
    entries: list[FHIRBundleEntry] = []
    for r in resources:
        rid = r.get("id", "unknown")
        entries.append(
            FHIRBundleEntry(
                fullUrl=f"{resource_type}/{rid}",
                resource=r,
            )
        )

    return FHIRBundle(
        type="searchset",
        total=len(entries),
        entry=entries,
    )
