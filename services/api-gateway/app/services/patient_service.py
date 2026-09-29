import uuid
from datetime import date, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.diagnosis import Diagnosis
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.staff import Department, Staff
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import (
    PatientCreate,
    PatientHistoryDiagnosis,
    PatientHistoryPrescription,
    PatientHistoryResponse,
    PatientHistoryVisit,
    PatientUpdate,
)

# How far a returning patient's recorded date of birth may drift and still be
# treated as the same person. Date of birth is frequently estimated here
# ("about 40"), so requiring an exact match let already-registered patients
# through as brand-new records whenever the estimate was written down
# differently the second time.
_DOB_TOLERANCE_DAYS = 366
_DOB_TOLERANCE = timedelta(days=_DOB_TOLERANCE_DAYS)


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
        number, identical phone number, or (normalized name + DOB within
        ``_DOB_TOLERANCE_DAYS``). The DOB allowance keeps an already-registered
        patient findable when their estimated date of birth was recorded
        differently on a later visit. Each returned patient carries the list of
        reasons it matched so the UI can explain "possible duplicate" before
        creating a second record.

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
            Patient.date_of_birth.between(
                date_of_birth - _DOB_TOLERANCE,
                date_of_birth + _DOB_TOLERANCE,
            ),
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
                and patient.date_of_birth is not None
            ):
                drift_days = abs((patient.date_of_birth - date_of_birth).days)
                if drift_days == 0:
                    reasons.append("name_dob")
                elif drift_days <= _DOB_TOLERANCE_DAYS:
                    reasons.append("name_dob_approximate")
            if reasons:
                matches.append((patient, reasons))

        # Rank strongest identifiers first
        # (ID > passport > name+exact DOB > name+near DOB > phone).
        _priority = {
            "national_id": 0,
            "passport_number": 1,
            "name_dob": 2,
            "name_dob_approximate": 3,
            "phone_number": 4,
        }
        matches.sort(key=lambda m: min(_priority[r] for r in m[1]))
        return matches

    async def get_clinical_history(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        exclude_encounter_id: uuid.UUID | None = None,
        limit: int = 10,
    ) -> PatientHistoryResponse | None:
        """
        Build a patient's clinical history for display at the point of care.

        Returns the safety-critical patient-level fields (allergies, chronic
        conditions, blood group) together with recent previous visits, each
        carrying its own diagnoses and prescriptions, so a clinician who has
        just been handed a redirected patient can see what has already been
        done without leaving the consultation screen.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID from JWT (tenant scope)
        @param exclude_encounter_id: Encounter to omit (the one being worked on)
        @param limit: Maximum number of previous visits to return
        @returns Clinical history, or None when the patient is not in this facility
        """
        patient_result = await self.db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.facility_id == facility_id,
                Patient.is_deleted == False,  # noqa: E712
            )
        )
        patient = patient_result.scalar_one_or_none()
        if patient is None:
            return None

        visit_filters = [
            Encounter.facility_id == facility_id,
            Encounter.patient_id == patient_id,
            Encounter.is_deleted == False,  # noqa: E712
        ]
        if exclude_encounter_id is not None:
            visit_filters.append(Encounter.id != exclude_encounter_id)

        count_result = await self.db.execute(
            select(func.count(Encounter.id)).where(*visit_filters)
        )
        visit_count = count_result.scalar_one() or 0

        visits_result = await self.db.execute(
            select(Encounter)
            .where(*visit_filters)
            .order_by(Encounter.encounter_date.desc())
            .limit(limit)
        )
        encounters = list(visits_result.scalars().all())
        encounter_ids = [encounter.id for encounter in encounters]

        diagnoses_by_encounter: dict[uuid.UUID, list[PatientHistoryDiagnosis]] = {}
        prescriptions_by_encounter: dict[
            uuid.UUID, list[PatientHistoryPrescription]
        ] = {}

        if encounter_ids:
            diagnosis_rows = await self.db.execute(
                select(Diagnosis)
                .where(
                    Diagnosis.facility_id == facility_id,
                    Diagnosis.encounter_id.in_(encounter_ids),
                    Diagnosis.is_deleted == False,  # noqa: E712
                )
                .order_by(Diagnosis.created_at.asc())
            )
            for diagnosis in diagnosis_rows.scalars().all():
                diagnoses_by_encounter.setdefault(diagnosis.encounter_id, []).append(
                    PatientHistoryDiagnosis(
                        icd10_code=diagnosis.icd10_code,
                        icd10_description=diagnosis.icd10_description,
                        diagnosis_type=diagnosis.diagnosis_type,
                        clinical_status=diagnosis.clinical_status,
                        is_chronic=diagnosis.is_chronic,
                    )
                )

            prescription_rows = await self.db.execute(
                select(Prescription)
                .where(
                    Prescription.facility_id == facility_id,
                    Prescription.encounter_id.in_(encounter_ids),
                    Prescription.is_deleted == False,  # noqa: E712
                )
                .order_by(Prescription.created_at.asc())
            )
            for prescription in prescription_rows.scalars().all():
                prescriptions_by_encounter.setdefault(
                    prescription.encounter_id, []
                ).append(
                    PatientHistoryPrescription(
                        drug_name=prescription.drug_name,
                        dosage=prescription.dosage,
                        frequency=prescription.frequency,
                        status=prescription.status,
                    )
                )

        doctor_ids = {
            encounter.attending_doctor_id
            for encounter in encounters
            if encounter.attending_doctor_id is not None
        }
        doctors: dict[uuid.UUID, str] = {}
        if doctor_ids:
            doctor_rows = await self.db.execute(
                select(Staff.id, Staff.first_name, Staff.last_name).where(
                    Staff.id.in_(doctor_ids)
                )
            )
            doctors = {
                row[0]: f"{row[1] or ''} {row[2] or ''}".strip()
                for row in doctor_rows.all()
            }

        department_ids = {
            encounter.department_id
            for encounter in encounters
            if encounter.department_id is not None
        }
        departments: dict[uuid.UUID, str] = {}
        if department_ids:
            department_rows = await self.db.execute(
                select(Department.id, Department.name).where(
                    Department.id.in_(department_ids)
                )
            )
            departments = {row[0]: row[1] for row in department_rows.all()}

        def _doctor_name(doctor_id: uuid.UUID | None) -> str | None:
            """Resolve a staff display name, tolerating an unassigned encounter."""
            return doctors.get(doctor_id) if doctor_id is not None else None

        def _department_name(department_id: uuid.UUID | None) -> str | None:
            """Resolve a department name, tolerating an unrouted encounter."""
            return (
                departments.get(department_id)
                if department_id is not None
                else None
            )

        visits = [
            PatientHistoryVisit(
                encounter_id=encounter.id,
                encounter_date=encounter.encounter_date,
                encounter_type=encounter.encounter_type,
                status=encounter.status,
                department_name=_department_name(encounter.department_id),
                attending_doctor_name=_doctor_name(encounter.attending_doctor_id),
                chief_complaint=encounter.chief_complaint,
                disposition=encounter.disposition,
                diagnoses=diagnoses_by_encounter.get(encounter.id, []),
                prescriptions=prescriptions_by_encounter.get(encounter.id, []),
            )
            for encounter in encounters
        ]

        today = date.today()
        age_years = (
            today.year
            - patient.date_of_birth.year
            - (
                (today.month, today.day)
                < (patient.date_of_birth.month, patient.date_of_birth.day)
            )
        )

        return PatientHistoryResponse(
            patient_id=patient.id,
            mrn=patient.mrn,
            full_name=f"{patient.first_name} {patient.last_name}".strip(),
            date_of_birth=patient.date_of_birth,
            gender=patient.gender,
            age_years=age_years,
            blood_group=patient.blood_group,
            allergies=list(patient.allergies or []),
            chronic_conditions=list(patient.chronic_conditions or []),
            visit_count=visit_count,
            last_visit_date=encounters[0].encounter_date if encounters else None,
            visits=visits,
        )

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
