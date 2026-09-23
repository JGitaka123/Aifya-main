import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient


class PatientRepository:
    """Repository for patient database operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, patient: Patient) -> Patient:
        """
        Insert a new patient record.

        @param patient: Patient model instance to persist
        @returns The persisted patient with generated fields
        """
        self.db.add(patient)
        await self.db.flush()
        await self.db.refresh(patient)
        return patient

    async def get_by_id(
        self, patient_id: uuid.UUID, facility_id: uuid.UUID
    ) -> Patient | None:
        """
        Fetch a patient by ID, scoped to facility.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID from JWT
        @returns Patient or None if not found
        """
        result = await self.db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.facility_id == facility_id,
                Patient.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        facility_id: uuid.UUID,
        query: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Patient], int]:
        """
        Search patients by name, national ID, phone, or MRN.

        @param facility_id: Facility UUID from JWT
        @param query: Search string
        @param page: Page number (1-based)
        @param page_size: Results per page
        @returns Tuple of (patients list, total count)
        """
        base = select(Patient).where(
            Patient.facility_id == facility_id,
            Patient.is_deleted == False,  # noqa: E712
        )

        if query:
            search_term = f"%{query}%"
            base = base.where(
                or_(
                    Patient.first_name.ilike(search_term),
                    Patient.last_name.ilike(search_term),
                    Patient.middle_name.ilike(search_term),
                    Patient.national_id.ilike(search_term),
                    Patient.phone_number.ilike(search_term),
                    Patient.mrn.ilike(search_term),
                )
            )

        # Count
        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Paginate
        offset = (page - 1) * page_size
        result = await self.db.execute(
            base.order_by(Patient.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        patients = list(result.scalars().all())

        return patients, total

    async def update(self, patient: Patient) -> Patient:
        """
        Update a patient record.

        @param patient: Patient model with updated fields
        @returns Updated patient
        """
        await self.db.flush()
        await self.db.refresh(patient)
        return patient

    async def generate_mrn(self, facility_id: uuid.UUID) -> str:
        """
        Generate the next MRN for a facility.

        @param facility_id: Facility UUID
        @returns MRN string like "MRN-000001"
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(Patient)
            .where(Patient.facility_id == facility_id)
        )
        count = result.scalar_one()
        return f"MRN-{count + 1:06d}"
