import uuid
from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.patient import Patient
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate


class PatientService:
    """Service layer for patient registration business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = PatientRepository(db)

    async def find_potential_duplicates(
        self,
        facility_id: uuid.UUID,
        first_name: str,
        last_name: str,
        date_of_birth: date,
        phone_number: str | None = None,
        national_id: str | None = None,
        passport_number: str | None = None,
    ) -> list[tuple[Patient, list[str]]]:
        """
        Find likely-duplicate patients before registration (D7).

        A match is raised on any of: identical National ID, identical passport
        number, identical phone number, or identical (normalized name + DOB).
        Each returned patient carries the list of reasons it matched so the UI
        can explain "possible duplicate" before creating a second record.

        @param facility_id: Facility UUID from JWT (tenant scope)
        @param first_name: First name to match (case-insensitive)
        @param last_name: Last name to match (case-insensitive)
        @param date_of_birth: Date of birth to match with the name
        @param phone_number: Optional phone to match
        @param national_id: Optional National ID to match
        @param passport_number: Optional passport number to match
        @returns List of (patient, reasons) tuples, most-specific match first
        """
        conditions = []
        if national_id:
            conditions.append(Patient.national_id == national_id.strip())
        if passport_number:
            conditions.append(Patient.passport_number == passport_number.strip())
        if phone_number:
            conditions.append(Patient.phone_number == phone_number.strip())
        name_dob = and_(
            func.lower(Patient.first_name) == first_name.strip().lower(),
            func.lower(Patient.last_name) == last_name.strip().lower(),
            Patient.date_of_birth == date_of_birth,
        )
        conditions.append(name_dob)

        stmt = (
            select(Patient)
            .where(
                Patient.facility_id == facility_id,
                Patient.is_deleted == False,  # noqa: E712
                or_(*conditions),
            )
            .limit(25)
        )
        result = await self.db.execute(stmt)
        patients = list(result.scalars().all())

        matches: list[tuple[Patient, list[str]]] = []
        for patient in patients:
            reasons: list[str] = []
            if national_id and patient.national_id == national_id.strip():
                reasons.append("national_id")
            if (
                passport_number
                and patient.passport_number == passport_number.strip()
            ):
                reasons.append("passport_number")
            if phone_number and patient.phone_number == phone_number.strip():
                reasons.append("phone_number")
            if (
                (patient.first_name or "").strip().lower()
                == first_name.strip().lower()
                and (patient.last_name or "").strip().lower()
                == last_name.strip().lower()
                and patient.date_of_birth == date_of_birth
            ):
                reasons.append("name_dob")
            if reasons:
                matches.append((patient, reasons))

        # Rank strongest identifiers first (ID > passport > name+DOB > phone).
        _priority = {
            "national_id": 0,
            "passport_number": 1,
            "name_dob": 2,
            "phone_number": 3,
        }
        matches.sort(key=lambda m: min(_priority[r] for r in m[1]))
        return matches

    async def register_patient(
        self,
        data: PatientCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> Patient:
        """
        Register a new patient and emit PatientRegistered event.

        @param data: Validated patient registration data
        @param facility_id: Facility UUID from JWT
        @param created_by: Staff UUID who registered the patient
        @param idempotency_key: Optional idempotency key for safe retries
        @returns Created patient record
        """
        mrn = await self.repo.generate_mrn(facility_id)

        patient = Patient(
            facility_id=facility_id,
            mrn=mrn,
            created_by=created_by,
            updated_by=created_by,
            **data.model_dump(exclude_unset=False),
        )

        patient = await self.repo.create(patient)

        # Emit event to immutable event store
        event = EventBase(
            facility_id=facility_id,
            stream_type="patient",
            stream_id=patient.id,
            event_type="PatientRegistered",
            event_data=data.model_dump(mode="json"),
            version=1,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)

        return patient

    async def get_patient(
        self, patient_id: uuid.UUID, facility_id: uuid.UUID
    ) -> Patient | None:
        """
        Get a patient by ID.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID from JWT
        @returns Patient or None
        """
        return await self.repo.get_by_id(patient_id, facility_id)

    async def search_patients(
        self,
        facility_id: uuid.UUID,
        query: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Patient], int]:
        """
        Search patients within a facility.

        @param facility_id: Facility UUID from JWT
        @param query: Search string (name, ID, phone, MRN)
        @param page: Page number
        @param page_size: Results per page
        @returns Tuple of (patients, total count)
        """
        return await self.repo.search(facility_id, query, page, page_size)

    async def update_patient(
        self,
        patient_id: uuid.UUID,
        data: PatientUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> Patient | None:
        """
        Update patient demographics and emit PatientUpdated event.

        @param patient_id: Patient UUID
        @param data: Fields to update
        @param facility_id: Facility UUID from JWT
        @param updated_by: Staff UUID who updated the record
        @param idempotency_key: Optional idempotency key
        @returns Updated patient or None if not found
        """
        patient = await self.repo.get_by_id(patient_id, facility_id)
        if not patient:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(patient, field, value)
        patient.updated_by = updated_by

        patient = await self.repo.update(patient)

        # Get latest event version for this stream
        latest_version_result = await self.db.execute(
            select(func.coalesce(func.max(EventBase.version), 0)).where(
                EventBase.stream_type == "patient",
                EventBase.stream_id == patient.id,
            )
        )
        next_version = latest_version_result.scalar_one() + 1

        event = EventBase(
            facility_id=facility_id,
            stream_type="patient",
            stream_id=patient.id,
            event_type="PatientUpdated",
            event_data=update_data,
            version=next_version,
            created_by=updated_by,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)

        return patient
