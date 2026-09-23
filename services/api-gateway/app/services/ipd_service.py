import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.encounter import Encounter
from app.models.ipd import Admission, Bed, NursingNote, Ward
from app.models.patient import Patient
from app.schemas.ipd import (
    AdmissionCreate,
    AdmissionListItem,
    BedCreate,
    BedResponse,
    DischargeRequest,
    NursingNoteCreate,
    WardBoardSummary,
    WardCreate,
    WardResponse,
)


class IPDService:
    """
    Service for inpatient department: ward/bed management, admissions,
    nursing notes, and discharge workflow.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Ward Management ──────────────────────────────────────────────────

    async def create_ward(
        self, data: WardCreate, facility_id: uuid.UUID, created_by: uuid.UUID
    ) -> Ward:
        """
        Create a new ward.

        @param data: Ward creation data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created ward
        """
        ward = Ward(
            facility_id=facility_id,
            name=data.name,
            code=data.code,
            ward_type=data.ward_type,
            department_id=data.department_id,
            floor=data.floor,
            total_beds=data.total_beds,
            gender_restriction=data.gender_restriction,
            charge_per_day_cents=data.charge_per_day_cents,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(ward)
        await self.db.flush()
        await self.db.refresh(ward)
        return ward

    async def get_wards(
        self, facility_id: uuid.UUID
    ) -> list[WardResponse]:
        """
        Get all wards with bed occupancy counts via a single query
        using a LEFT JOIN on an aggregated bed-counts subquery.

        @param facility_id: Facility UUID
        @returns List of wards with occupancy stats
        """
        bed_counts_sq = (
            select(
                Bed.ward_id,
                func.count(Bed.id).label("total"),
                func.count(
                    case((Bed.status == "available", Bed.id))
                ).label("available"),
                func.count(
                    case((Bed.status == "occupied", Bed.id))
                ).label("occupied"),
            )
            .where(Bed.is_deleted == False)  # noqa: E712
            .group_by(Bed.ward_id)
            .subquery()
        )

        stmt = (
            select(
                Ward,
                func.coalesce(bed_counts_sq.c.available, 0).label("available"),
                func.coalesce(bed_counts_sq.c.occupied, 0).label("occupied"),
            )
            .outerjoin(bed_counts_sq, Ward.id == bed_counts_sq.c.ward_id)
            .where(
                Ward.facility_id == facility_id,
                Ward.is_deleted == False,  # noqa: E712
                Ward.is_active == True,  # noqa: E712
            )
            .order_by(Ward.name.asc())
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        ward_responses: list[WardResponse] = []
        for ward, available, occupied in rows:
            wr = WardResponse.model_validate(ward)
            wr.available_beds = available
            wr.occupied_beds = occupied
            ward_responses.append(wr)

        return ward_responses

    # ── Bed Management ───────────────────────────────────────────────────

    async def create_bed(
        self, data: BedCreate, facility_id: uuid.UUID, created_by: uuid.UUID
    ) -> Bed:
        """
        Create a new bed in a ward.

        @param data: Bed creation data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created bed
        """
        bed = Bed(
            facility_id=facility_id,
            ward_id=data.ward_id,
            bed_number=data.bed_number,
            bed_type=data.bed_type,
            status="available",
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(bed)
        await self.db.flush()
        await self.db.refresh(bed)

        # Update ward total_beds
        ward_result = await self.db.execute(
            select(Ward).where(
                Ward.id == data.ward_id,
                Ward.facility_id == facility_id,
            )
        )
        ward = ward_result.scalar_one_or_none()
        if ward:
            ward.total_beds += 1

        return bed

    async def get_beds(
        self,
        facility_id: uuid.UUID,
        ward_id: uuid.UUID | None = None,
        status_filter: str | None = None,
    ) -> list[BedResponse]:
        """
        Get beds with optional ward and status filters.

        @param facility_id: Facility UUID
        @param ward_id: Optional ward filter
        @param status_filter: Optional status filter
        @returns List of beds
        """
        stmt = select(Bed, Ward).join(Ward, Bed.ward_id == Ward.id).where(
            Bed.facility_id == facility_id,
            Bed.is_deleted == False,  # noqa: E712
        )
        if ward_id:
            stmt = stmt.where(Bed.ward_id == ward_id)
        if status_filter:
            stmt = stmt.where(Bed.status == status_filter)

        stmt = stmt.order_by(Ward.name.asc(), Bed.bed_number.asc())
        result = await self.db.execute(stmt)
        rows = result.all()

        beds: list[BedResponse] = []
        for bed, ward in rows:
            br = BedResponse.model_validate(bed)
            br.ward_name = ward.name

            # Get patient name if occupied
            if bed.current_patient_id:
                pat_result = await self.db.execute(
                    select(Patient).where(Patient.id == bed.current_patient_id)
                )
                patient = pat_result.scalar_one_or_none()
                if patient:
                    br.patient_name = f"{patient.first_name} {patient.last_name}"

            beds.append(br)

        return beds

    # ── Admission ────────────────────────────────────────────────────────

    async def admit_patient(
        self,
        data: AdmissionCreate,
        facility_id: uuid.UUID,
        admitted_by: uuid.UUID,
    ) -> Admission:
        """
        Admit a patient — assigns bed, creates admission record,
        updates encounter status.

        @param data: Admission data
        @param facility_id: Facility UUID
        @param admitted_by: Staff UUID
        @returns Created admission
        """
        # Validate bed is available
        bed_result = await self.db.execute(
            select(Bed).where(
                Bed.id == data.bed_id,
                Bed.facility_id == facility_id,
                Bed.is_deleted == False,  # noqa: E712
            )
        )
        bed = bed_result.scalar_one_or_none()
        if not bed:
            raise ValueError("Bed not found")
        if bed.status != "available":
            raise ValueError(f"Bed is not available (status: {bed.status})")

        admission_number = await self._next_admission_number(facility_id)

        admission = Admission(
            facility_id=facility_id,
            encounter_id=data.encounter_id,
            patient_id=data.patient_id,
            ward_id=data.ward_id,
            bed_id=data.bed_id,
            admission_number=admission_number,
            attending_doctor_id=data.attending_doctor_id,
            primary_nurse_id=data.primary_nurse_id,
            status="admitted",
            admission_reason=data.admission_reason,
            admission_diagnosis=data.admission_diagnosis,
            admitted_from=data.admitted_from,
            accommodation_type=data.accommodation_type,
            created_by=admitted_by,
            updated_by=admitted_by,
        )
        self.db.add(admission)
        await self.db.flush()
        await self.db.refresh(admission)

        # Mark bed as occupied
        bed.status = "occupied"
        bed.current_patient_id = data.patient_id
        bed.current_admission_id = admission.id

        # Update encounter
        enc_result = await self.db.execute(
            select(Encounter).where(Encounter.id == data.encounter_id)
        )
        encounter = enc_result.scalar_one_or_none()
        if encounter:
            encounter.status = "admitted"
            encounter.bed_id = data.bed_id
            encounter.admission_date = datetime.now(UTC)
            encounter.disposition = "admitted"

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="admission",
            stream_id=data.patient_id,
            event_type="PatientAdmitted",
            event_data={
                "admission_number": admission_number,
                "ward_id": str(data.ward_id),
                "bed_id": str(data.bed_id),
                "admitted_from": data.admitted_from,
                "diagnosis": data.admission_diagnosis,
            },
            version=1,
            created_by=admitted_by,
        )
        self.db.add(event)

        return admission

    async def get_admissions(
        self,
        facility_id: uuid.UUID,
        status_filter: str | None = None,
        ward_id: uuid.UUID | None = None,
    ) -> tuple[list[AdmissionListItem], int]:
        """
        Get active admissions with patient and ward info.

        @param facility_id: Facility UUID
        @param status_filter: Optional status filter
        @param ward_id: Optional ward filter
        @returns Tuple of (admission items, total)
        """
        stmt = (
            select(Admission, Patient, Ward, Bed)
            .join(Patient, Admission.patient_id == Patient.id)
            .join(Ward, Admission.ward_id == Ward.id)
            .join(Bed, Admission.bed_id == Bed.id)
            .where(
                Admission.facility_id == facility_id,
                Admission.is_deleted == False,  # noqa: E712
            )
        )

        if status_filter:
            stmt = stmt.where(Admission.status == status_filter)
        else:
            stmt = stmt.where(Admission.status.in_(["admitted", "on_leave"]))

        if ward_id:
            stmt = stmt.where(Admission.ward_id == ward_id)

        stmt = stmt.order_by(Admission.admitted_at.desc())
        result = await self.db.execute(stmt)
        rows = result.all()

        now = datetime.now(UTC)
        items: list[AdmissionListItem] = []
        for admission, patient, ward, bed in rows:
            los = (now - admission.admitted_at).days if admission.admitted_at else None
            items.append(
                AdmissionListItem(
                    id=admission.id,
                    admission_number=admission.admission_number,
                    encounter_id=admission.encounter_id,
                    patient_id=admission.patient_id,
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    patient_mrn=patient.mrn,
                    ward_name=ward.name,
                    bed_number=bed.bed_number,
                    status=admission.status,
                    admission_diagnosis=admission.admission_diagnosis,
                    admitted_from=admission.admitted_from,
                    admitted_at=admission.admitted_at,
                    length_of_stay_days=los,
                )
            )

        return items, len(items)

    async def get_admission_detail(
        self, admission_id: uuid.UUID, facility_id: uuid.UUID
    ) -> Admission | None:
        """
        Get a single admission by ID.

        @param admission_id: Admission UUID
        @param facility_id: Facility UUID
        @returns Admission or None
        """
        result = await self.db.execute(
            select(Admission).where(
                Admission.id == admission_id,
                Admission.facility_id == facility_id,
                Admission.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    # ── Discharge ────────────────────────────────────────────────────────

    async def discharge_patient(
        self,
        admission_id: uuid.UUID,
        data: DischargeRequest,
        facility_id: uuid.UUID,
        discharged_by: uuid.UUID,
    ) -> Admission | None:
        """
        Discharge an inpatient — frees bed, updates encounter.

        @param admission_id: Admission UUID
        @param data: Discharge data
        @param facility_id: Facility UUID
        @param discharged_by: Staff UUID
        @returns Updated admission or None
        """
        result = await self.db.execute(
            select(Admission).where(
                Admission.id == admission_id,
                Admission.facility_id == facility_id,
                Admission.is_deleted == False,  # noqa: E712
            )
        )
        admission = result.scalar_one_or_none()
        if not admission:
            return None
        if admission.status not in ("admitted", "on_leave"):
            raise ValueError(f"Cannot discharge with status: {admission.status}")

        now = datetime.now(UTC)
        los = (now - admission.admitted_at).days if admission.admitted_at else 0

        admission.status = "discharged"
        admission.discharged_at = now
        admission.discharged_by = discharged_by
        admission.discharge_type = data.discharge_type
        admission.discharge_diagnosis = data.discharge_diagnosis
        admission.discharge_summary = data.discharge_summary
        admission.follow_up_plan = data.follow_up_plan
        admission.discharge_medications = data.discharge_medications
        admission.length_of_stay_days = los
        admission.updated_by = discharged_by

        # Free the bed
        bed_result = await self.db.execute(
            select(Bed).where(Bed.id == admission.bed_id)
        )
        bed = bed_result.scalar_one_or_none()
        if bed:
            bed.status = "cleaning"
            bed.current_patient_id = None
            bed.current_admission_id = None

        # Update encounter
        enc_result = await self.db.execute(
            select(Encounter).where(Encounter.id == admission.encounter_id)
        )
        encounter = enc_result.scalar_one_or_none()
        if encounter:
            encounter.status = "discharged"
            encounter.discharge_date = now
            encounter.discharge_summary = data.discharge_summary
            encounter.disposition = "discharged"

        await self.db.flush()
        await self.db.refresh(admission)

        event = EventBase(
            facility_id=facility_id,
            stream_type="admission",
            stream_id=admission.patient_id,
            event_type="PatientDischarged",
            event_data={
                "admission_number": admission.admission_number,
                "discharge_type": data.discharge_type,
                "length_of_stay_days": los,
            },
            version=1,
            created_by=discharged_by,
        )
        self.db.add(event)

        return admission

    # ── Nursing Notes ────────────────────────────────────────────────────

    async def add_nursing_note(
        self,
        admission_id: uuid.UUID,
        data: NursingNoteCreate,
        facility_id: uuid.UUID,
        author_id: uuid.UUID,
    ) -> NursingNote:
        """
        Add a nursing note to an admission.

        @param admission_id: Admission UUID
        @param data: Nursing note data
        @param facility_id: Facility UUID
        @param author_id: Nurse staff UUID
        @returns Created nursing note
        """
        # Get admission for patient_id
        adm_result = await self.db.execute(
            select(Admission).where(
                Admission.id == admission_id,
                Admission.facility_id == facility_id,
                Admission.is_deleted == False,  # noqa: E712
            )
        )
        admission = adm_result.scalar_one_or_none()
        if not admission:
            raise ValueError("Admission not found")

        note = NursingNote(
            facility_id=facility_id,
            admission_id=admission_id,
            patient_id=admission.patient_id,
            author_id=author_id,
            note_type=data.note_type,
            content=data.content,
            shift=data.shift,
            severity=data.severity,
            created_by=author_id,
            updated_by=author_id,
        )
        self.db.add(note)
        await self.db.flush()
        await self.db.refresh(note)

        event = EventBase(
            facility_id=facility_id,
            stream_type="nursing",
            stream_id=admission.patient_id,
            event_type="NursingNoteRecorded",
            event_data={
                "note_type": data.note_type,
                "shift": data.shift,
                "severity": data.severity,
            },
            version=1,
            created_by=author_id,
        )
        self.db.add(event)

        return note

    async def get_nursing_notes(
        self, admission_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[NursingNote]:
        """
        Get all nursing notes for an admission.

        @param admission_id: Admission UUID
        @param facility_id: Facility UUID
        @returns List of nursing notes (newest first)
        """
        result = await self.db.execute(
            select(NursingNote)
            .where(
                NursingNote.admission_id == admission_id,
                NursingNote.facility_id == facility_id,
                NursingNote.is_deleted == False,  # noqa: E712
            )
            .order_by(NursingNote.created_at.desc())
        )
        return list(result.scalars().all())

    # ── Dashboard ────────────────────────────────────────────────────────

    async def get_ward_board_summary(
        self, facility_id: uuid.UUID
    ) -> WardBoardSummary:
        """
        Get ward board summary for IPD dashboard.

        @param facility_id: Facility UUID
        @returns Ward board summary stats
        """
        wards_result = await self.db.execute(
            select(Ward).where(
                Ward.facility_id == facility_id,
                Ward.is_deleted == False,  # noqa: E712
                Ward.is_active == True,  # noqa: E712
            )
        )
        wards = list(wards_result.scalars().all())

        beds_result = await self.db.execute(
            select(Bed).where(
                Bed.facility_id == facility_id,
                Bed.is_deleted == False,  # noqa: E712
            )
        )
        beds = list(beds_result.scalars().all())

        total_beds = len(beds)
        occupied = sum(1 for b in beds if b.status == "occupied")
        available = sum(1 for b in beds if b.status == "available")

        adm_result = await self.db.execute(
            select(func.count())
            .select_from(Admission)
            .where(
                Admission.facility_id == facility_id,
                Admission.status.in_(["admitted", "on_leave"]),
                Admission.is_deleted == False,  # noqa: E712
            )
        )
        active_admissions = adm_result.scalar_one()

        occupancy_rate = (occupied / total_beds * 100) if total_beds > 0 else 0.0

        return WardBoardSummary(
            total_wards=len(wards),
            total_beds=total_beds,
            occupied_beds=occupied,
            available_beds=available,
            active_admissions=active_admissions,
            occupancy_rate=round(occupancy_rate, 1),
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _next_admission_number(self, facility_id: uuid.UUID) -> str:
        """Generate the next admission number (IP-YYYYMMDD-XXXX)."""
        today = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f"IP-{today}-"

        result = await self.db.execute(
            select(func.count())
            .select_from(Admission)
            .where(
                Admission.facility_id == facility_id,
                Admission.admission_number.like(f"{prefix}%"),
            )
        )
        count = result.scalar_one()
        return f"{prefix}{count + 1:04d}"
