import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.diagnosis import Diagnosis
from app.schemas.diagnosis import DiagnosisCreate


class DiagnosisService:
    """Service for managing ICD-10 diagnoses on encounters."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add_diagnosis(
        self,
        data: DiagnosisCreate,
        facility_id: uuid.UUID,
        diagnosed_by: uuid.UUID,
    ) -> Diagnosis:
        """
        Add a diagnosis to an encounter.

        @param data: Diagnosis data with ICD-10 code
        @param facility_id: Facility UUID
        @param diagnosed_by: Doctor's staff UUID
        @returns Created diagnosis
        """
        diagnosis = Diagnosis(
            facility_id=facility_id,
            encounter_id=data.encounter_id,
            patient_id=data.patient_id,
            diagnosed_by=diagnosed_by,
            created_by=diagnosed_by,
            updated_by=diagnosed_by,
            **data.model_dump(exclude={"encounter_id", "patient_id"}),
        )

        self.db.add(diagnosis)
        await self.db.flush()
        await self.db.refresh(diagnosis)

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="diagnosis",
            stream_id=data.patient_id,
            event_type="DiagnosisRecorded",
            event_data={
                "icd10_code": data.icd10_code,
                "icd10_description": data.icd10_description,
                "diagnosis_type": data.diagnosis_type,
                "certainty": data.certainty,
                "is_chronic": data.is_chronic,
            },
            version=1,
            created_by=diagnosed_by,
        )
        self.db.add(event)

        return diagnosis

    async def get_encounter_diagnoses(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[Diagnosis]:
        """
        Get all diagnoses for an encounter.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns List of diagnoses
        """
        result = await self.db.execute(
            select(Diagnosis)
            .where(
                Diagnosis.encounter_id == encounter_id,
                Diagnosis.facility_id == facility_id,
                Diagnosis.is_deleted == False,  # noqa: E712
            )
            .order_by(Diagnosis.created_at.desc())
        )
        return list(result.scalars().all())
