"""
FHIR R4 service layer — queries Aifya database and returns FHIR resources.
All queries are scoped by facility_id for multi-tenant safety.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.models.diagnosis import Diagnosis
from app.models.encounter import Encounter
from app.models.lab import LabOrder, LabResult
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.vital import VitalSign
from app.services.fhir.mappers import (
    diagnosis_to_fhir,
    encounter_to_fhir,
    lab_result_to_fhir,
    make_searchset_bundle,
    patient_to_fhir,
    prescription_to_fhir,
    vital_to_fhir,
)
from app.services.fhir.models import (
    FHIRBundle,
    FHIRCapabilityRest,
    FHIRCapabilityRestResource,
    FHIRCapabilityStatement,
    FHIRDiagnosticReport,
    FHIREncounter,
    FHIRPatient,
    FHIRReference,
)

logger = get_logger(__name__)


class FHIRService:
    """
    FHIR R4 service — reads Aifya data and returns FHIR-compliant resources.
    All methods enforce facility_id scoping for multi-tenant isolation.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Patient ───────────────────────────────────────────────────────────

    async def get_patient(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> FHIRPatient | None:
        """
        Read a single patient as FHIR Patient resource.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID (multi-tenant scope)
        @returns FHIRPatient or None if not found
        """
        result = await self.db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.facility_id == facility_id,
                Patient.is_deleted == False,  # noqa: E712
            )
        )
        patient = result.scalar_one_or_none()
        if not patient:
            return None
        return patient_to_fhir(patient)

    async def search_patients(
        self,
        facility_id: uuid.UUID,
        *,
        name: str | None = None,
        identifier: str | None = None,
        birthdate: str | None = None,
    ) -> FHIRBundle:
        """
        Search patients and return as FHIR Bundle.

        @param facility_id: Facility UUID
        @param name: Name search string
        @param identifier: MRN or ID number
        @param birthdate: Date of birth (YYYY-MM-DD)
        @returns FHIRBundle with matching patients
        """
        stmt = select(Patient).where(
            Patient.facility_id == facility_id,
            Patient.is_deleted == False,  # noqa: E712
        )

        if name:
            name_filter = f"%{name}%"
            stmt = stmt.where(
                (Patient.first_name.ilike(name_filter))
                | (Patient.last_name.ilike(name_filter))
            )
        if identifier:
            stmt = stmt.where(Patient.mrn == identifier)
        if birthdate:
            stmt = stmt.where(Patient.date_of_birth == birthdate)

        stmt = stmt.limit(50)
        result = await self.db.execute(stmt)
        patients = result.scalars().all()

        resources = [patient_to_fhir(p).model_dump(exclude_none=True) for p in patients]
        return make_searchset_bundle(resources, "Patient")

    # ── Encounter ─────────────────────────────────────────────────────────

    async def get_encounter(
        self,
        encounter_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> FHIREncounter | None:
        """
        Read a single encounter as FHIR Encounter resource.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns FHIREncounter or None
        """
        result = await self.db.execute(
            select(Encounter).where(
                Encounter.id == encounter_id,
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
            )
        )
        encounter = result.scalar_one_or_none()
        if not encounter:
            return None
        return encounter_to_fhir(encounter)

    async def search_encounters(
        self,
        facility_id: uuid.UUID,
        *,
        patient: uuid.UUID | None = None,
        status: str | None = None,
    ) -> FHIRBundle:
        """
        Search encounters and return as FHIR Bundle.

        @param facility_id: Facility UUID
        @param patient: Optional patient UUID filter
        @param status: Optional FHIR status filter
        @returns FHIRBundle with matching encounters
        """
        stmt = select(Encounter).where(
            Encounter.facility_id == facility_id,
            Encounter.is_deleted == False,  # noqa: E712
        )

        if patient:
            stmt = stmt.where(Encounter.patient_id == patient)
        if status:
            # Reverse-map FHIR status to Aifya status
            reverse_map = {v: k for k, v in {
                "waiting": "arrived",
                "in_consultation": "in-progress",
                "completed": "finished",
                "cancelled": "cancelled",
            }.items()}
            aifya_status = reverse_map.get(status)
            if aifya_status:
                stmt = stmt.where(Encounter.status == aifya_status)

        stmt = stmt.order_by(Encounter.created_at.desc()).limit(50)
        result = await self.db.execute(stmt)
        encounters = result.scalars().all()

        resources = [encounter_to_fhir(e).model_dump(exclude_none=True) for e in encounters]
        return make_searchset_bundle(resources, "Encounter")

    # ── Observation (Vitals + Labs) ───────────────────────────────────────

    async def search_observations(
        self,
        facility_id: uuid.UUID,
        *,
        patient: uuid.UUID | None = None,
        category: str | None = None,
        code: str | None = None,
    ) -> FHIRBundle:
        """
        Search observations (vitals and lab results) as FHIR Bundle.

        @param facility_id: Facility UUID
        @param patient: Patient UUID filter
        @param category: vital-signs or laboratory
        @param code: LOINC code filter
        @returns FHIRBundle with observations
        """
        resources: list[dict] = []

        # Vital signs
        if category in (None, "vital-signs"):
            vital_stmt = select(VitalSign).where(
                VitalSign.facility_id == facility_id,
                VitalSign.is_deleted == False,  # noqa: E712
            )
            if patient:
                vital_stmt = vital_stmt.where(VitalSign.patient_id == patient)
            vital_stmt = vital_stmt.order_by(VitalSign.created_at.desc()).limit(20)

            result = await self.db.execute(vital_stmt)
            vitals = result.scalars().all()

            for v in vitals:
                fhir_obs = vital_to_fhir(v)
                for obs in fhir_obs:
                    if code and obs.code:
                        codings = obs.code.coding or []
                        if not any(c.code == code for c in codings):
                            continue
                    resources.append(obs.model_dump(exclude_none=True))

        # Lab results
        if category in (None, "laboratory"):
            lab_stmt = (
                select(LabResult)
                .join(LabOrder)
                .where(
                    LabOrder.facility_id == facility_id,
                    LabResult.is_deleted == False,  # noqa: E712
                    LabResult.status.in_(["preliminary", "final"]),
                )
            )
            if patient:
                lab_stmt = lab_stmt.where(LabOrder.patient_id == patient)
            if code:
                lab_stmt = lab_stmt.where(
                    (LabResult.loinc_code == code) | (LabResult.test_code == code)
                )
            lab_stmt = lab_stmt.order_by(LabResult.created_at.desc()).limit(20)

            lab_rows = await self.db.execute(lab_stmt)
            labs = lab_rows.scalars().all()

            for lr in labs:
                resources.append(
                    lab_result_to_fhir(lr).model_dump(exclude_none=True)
                )

        return make_searchset_bundle(resources, "Observation")

    # ── MedicationRequest ─────────────────────────────────────────────────

    async def search_medication_requests(
        self,
        facility_id: uuid.UUID,
        *,
        patient: uuid.UUID | None = None,
        status: str | None = None,
    ) -> FHIRBundle:
        """
        Search medication requests (prescriptions) as FHIR Bundle.

        @param facility_id: Facility UUID
        @param patient: Patient UUID filter
        @param status: FHIR status filter (active, completed, cancelled)
        @returns FHIRBundle with medication requests
        """
        stmt = select(Prescription).where(
            Prescription.facility_id == facility_id,
            Prescription.is_deleted == False,  # noqa: E712
        )
        if patient:
            stmt = stmt.where(Prescription.patient_id == patient)
        if status:
            status_reverse = {
                "active": ["pending", "partially_dispensed"],
                "completed": ["dispensed"],
                "cancelled": ["cancelled"],
            }
            aifya_statuses = status_reverse.get(status, [])
            if aifya_statuses:
                stmt = stmt.where(Prescription.status.in_(aifya_statuses))

        stmt = stmt.order_by(Prescription.created_at.desc()).limit(50)
        result = await self.db.execute(stmt)
        prescriptions = result.scalars().all()

        resources = [
            prescription_to_fhir(rx).model_dump(exclude_none=True) for rx in prescriptions
        ]
        return make_searchset_bundle(resources, "MedicationRequest")

    # ── Condition ─────────────────────────────────────────────────────────

    async def search_conditions(
        self,
        facility_id: uuid.UUID,
        *,
        patient: uuid.UUID | None = None,
        clinical_status: str | None = None,
    ) -> FHIRBundle:
        """
        Search conditions (diagnoses) as FHIR Bundle.

        @param facility_id: Facility UUID
        @param patient: Patient UUID filter
        @param clinical_status: FHIR clinical status filter
        @returns FHIRBundle with conditions
        """
        stmt = select(Diagnosis).where(
            Diagnosis.facility_id == facility_id,
            Diagnosis.is_deleted == False,  # noqa: E712
        )
        if patient:
            stmt = stmt.where(Diagnosis.patient_id == patient)
        if clinical_status:
            stmt = stmt.where(Diagnosis.clinical_status == clinical_status)

        stmt = stmt.order_by(Diagnosis.created_at.desc()).limit(50)
        result = await self.db.execute(stmt)
        diagnoses = result.scalars().all()

        resources = [
            diagnosis_to_fhir(dx).model_dump(exclude_none=True) for dx in diagnoses
        ]
        return make_searchset_bundle(resources, "Condition")

    # ── DiagnosticReport ──────────────────────────────────────────────────

    async def get_diagnostic_report(
        self,
        order_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> FHIRDiagnosticReport | None:
        """
        Read a lab order as a FHIR DiagnosticReport with result references.

        @param order_id: Lab order UUID
        @param facility_id: Facility UUID
        @returns FHIRDiagnosticReport or None
        """
        order_result = await self.db.execute(
            select(LabOrder).where(
                LabOrder.id == order_id,
                LabOrder.facility_id == facility_id,
                LabOrder.is_deleted == False,  # noqa: E712
            )
        )
        order = order_result.scalar_one_or_none()
        if not order:
            return None

        results_result = await self.db.execute(
            select(LabResult).where(
                LabResult.order_id == order_id,
                LabResult.is_deleted == False,  # noqa: E712
            )
        )
        results = results_result.scalars().all()

        all_final = all(r.status == "final" for r in results)

        return FHIRDiagnosticReport(
            id=str(order.id),
            status="final" if all_final else "partial",
            code=FHIRCodeableConcept(text=f"Lab Order {order.order_number}"),
            subject=FHIRReference(reference=f"Patient/{order.patient_id}"),
            effectiveDateTime=str(order.created_at) if order.created_at else None,
            result=[
                FHIRReference(
                    reference=f"Observation/{r.id}",
                    display=r.test_name,
                )
                for r in results
            ],
        )

    # ── Capability Statement ──────────────────────────────────────────────

    def get_capability_statement(self) -> FHIRCapabilityStatement:
        """
        Generate a FHIR CapabilityStatement describing this server's capabilities.

        @returns FHIRCapabilityStatement
        """
        now = datetime.now(UTC).isoformat()

        resources = [
            FHIRCapabilityRestResource(
                type="Patient",
                interaction=[{"code": "read"}, {"code": "search-type"}],
                searchParam=[
                    {"name": "name", "type": "string"},
                    {"name": "identifier", "type": "token"},
                    {"name": "birthdate", "type": "date"},
                ],
            ),
            FHIRCapabilityRestResource(
                type="Encounter",
                interaction=[{"code": "read"}, {"code": "search-type"}],
                searchParam=[
                    {"name": "patient", "type": "reference"},
                    {"name": "status", "type": "token"},
                ],
            ),
            FHIRCapabilityRestResource(
                type="Observation",
                interaction=[{"code": "search-type"}],
                searchParam=[
                    {"name": "patient", "type": "reference"},
                    {"name": "category", "type": "token"},
                    {"name": "code", "type": "token"},
                ],
            ),
            FHIRCapabilityRestResource(
                type="MedicationRequest",
                interaction=[{"code": "search-type"}],
                searchParam=[
                    {"name": "patient", "type": "reference"},
                    {"name": "status", "type": "token"},
                ],
            ),
            FHIRCapabilityRestResource(
                type="Condition",
                interaction=[{"code": "search-type"}],
                searchParam=[
                    {"name": "patient", "type": "reference"},
                    {"name": "clinical-status", "type": "token"},
                ],
            ),
            FHIRCapabilityRestResource(
                type="DiagnosticReport",
                interaction=[{"code": "read"}],
                searchParam=[],
            ),
        ]

        return FHIRCapabilityStatement(
            id="aifya-fhir",
            name="AifyaFHIRServer",
            title="Aifya FHIR R4 Server",
            date=now,
            publisher="Aifya — Akili kwa Afya",
            description="FHIR R4 read-only gateway for Aifya hospital management system",
            software={"name": "Aifya FHIR Gateway", "version": "1.0.0"},
            rest=[FHIRCapabilityRest(mode="server", resource=resources)],
        )


# Import needed here to avoid circular import issues
from app.services.fhir.models import FHIRCodeableConcept  # noqa: E402
