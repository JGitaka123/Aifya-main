import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.patient import Patient
from app.models.staff import Staff
from app.models.theatre import OperatingTheatre, SurgicalCase
from app.schemas.theatre import (
    OperativeNotesRequest,
    SurgicalCaseCreate,
    SurgicalCaseListItem,
    TheatreCreate,
    TheatreSummary,
)


class TheatreService:
    """
    Service for operating theatre management: theatres, surgical cases,
    scheduling, operative notes, and WHO safety checklists.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Theatres ─────────────────────────────────────────────────────────

    async def create_theatre(
        self,
        data: TheatreCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> OperatingTheatre:
        """
        Create an operating theatre.

        @param data: Theatre data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created theatre
        """
        count_result = await self.db.execute(
            select(func.count(OperatingTheatre.id)).where(
                OperatingTheatre.facility_id == facility_id,
                OperatingTheatre.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count_result.scalar() or 0) + 1
        code = f"OT-{seq:03d}"

        theatre = OperatingTheatre(
            facility_id=facility_id,
            name=data.name,
            code=code,
            theatre_type=data.theatre_type,
            status="available",
            floor=data.floor,
            equipment=data.equipment,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(theatre)
        await self.db.flush()
        await self.db.refresh(theatre)
        return theatre

    async def get_theatres(self, facility_id: uuid.UUID) -> list[OperatingTheatre]:
        """
        Get all active theatres.

        @param facility_id: Facility UUID
        @returns List of theatres
        """
        result = await self.db.execute(
            select(OperatingTheatre).where(
                OperatingTheatre.facility_id == facility_id,
                OperatingTheatre.is_deleted == False,  # noqa: E712
                OperatingTheatre.is_active == True,  # noqa: E712
            ).order_by(OperatingTheatre.code.asc())
        )
        return list(result.scalars().all())

    # ── Surgical Cases ───────────────────────────────────────────────────

    async def schedule_case(
        self,
        data: SurgicalCaseCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> SurgicalCase:
        """
        Schedule a surgical case.

        @param data: Case data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created surgical case
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count_result = await self.db.execute(
            select(func.count(SurgicalCase.id)).where(
                SurgicalCase.facility_id == facility_id,
                SurgicalCase.case_number.like(f"SC-{date_part}-%"),
                SurgicalCase.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count_result.scalar() or 0) + 1
        case_number = f"SC-{date_part}-{seq:04d}"

        case = SurgicalCase(
            facility_id=facility_id,
            case_number=case_number,
            patient_id=data.patient_id,
            encounter_id=data.encounter_id,
            theatre_id=data.theatre_id,
            scheduled_date=data.scheduled_date,
            estimated_duration_min=data.estimated_duration_min,
            priority=data.priority,
            procedure_name=data.procedure_name,
            procedure_code=data.procedure_code,
            laterality=data.laterality,
            diagnosis=data.diagnosis,
            anaesthesia_type=data.anaesthesia_type,
            anaesthetist_id=data.anaesthetist_id,
            lead_surgeon_id=data.lead_surgeon_id,
            assistant_surgeon_id=data.assistant_surgeon_id,
            scrub_nurse_id=data.scrub_nurse_id,
            circulating_nurse_id=data.circulating_nurse_id,
            status="scheduled",
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(case)
        await self.db.flush()
        await self.db.refresh(case)
        return case

    async def get_case_list(
        self,
        facility_id: uuid.UUID,
        target_date: date | None = None,
        status: str | None = None,
    ) -> list[SurgicalCaseListItem]:
        """
        Get surgical case list with patient and surgeon names.

        @param facility_id: Facility UUID
        @param target_date: Optional date filter
        @param status: Optional status filter
        @returns List of surgical cases
        """
        SurgeonStaff = Staff.__table__.alias("surgeon_staff")  # noqa: N806 — SQLAlchemy alias naming

        query = (
            select(
                SurgicalCase,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
                OperatingTheatre.name.label("theatre_name"),
                SurgeonStaff.c.first_name.label("s_first"),
                SurgeonStaff.c.last_name.label("s_last"),
            )
            .join(Patient, SurgicalCase.patient_id == Patient.id)
            .outerjoin(OperatingTheatre, SurgicalCase.theatre_id == OperatingTheatre.id)
            .outerjoin(SurgeonStaff, SurgicalCase.lead_surgeon_id == SurgeonStaff.c.id)
            .where(
                SurgicalCase.facility_id == facility_id,
                SurgicalCase.is_deleted == False,  # noqa: E712
            )
        )

        if target_date:
            query = query.where(func.date(SurgicalCase.scheduled_date) == target_date)
        if status:
            query = query.where(SurgicalCase.status == status)

        query = query.order_by(SurgicalCase.scheduled_date.asc())
        result = await self.db.execute(query)
        rows = result.all()

        return [
            SurgicalCaseListItem(
                id=c.id,
                case_number=c.case_number,
                patient_id=c.patient_id,
                patient_name=f"{pf or ''} {pl or ''}".strip() or None,
                theatre_name=tn,
                scheduled_date=c.scheduled_date,
                procedure_name=c.procedure_name,
                priority=c.priority,
                lead_surgeon_name=f"{sf or ''} {sl or ''}".strip() or None,
                status=c.status,
            )
            for c, pf, pl, tn, sf, sl in rows
        ]

    async def get_case(
        self, case_id: uuid.UUID, facility_id: uuid.UUID
    ) -> SurgicalCase | None:
        """
        Get a single surgical case.

        @param case_id: Case UUID
        @param facility_id: Facility UUID
        @returns Surgical case or None
        """
        result = await self.db.execute(
            select(SurgicalCase).where(
                SurgicalCase.id == case_id,
                SurgicalCase.facility_id == facility_id,
                SurgicalCase.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        case_id: uuid.UUID,
        new_status: str,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> SurgicalCase | None:
        """
        Update surgical case status with automatic timestamp recording.

        @param case_id: Case UUID
        @param new_status: New status
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated case or None
        """
        case = await self.get_case(case_id, facility_id)
        if not case:
            return None

        now = datetime.now(UTC)
        case.status = new_status

        timestamp_map = {
            "preop": "preop_start",
            "in_progress": "surgery_start",
            "in_recovery": "recovery_start",
        }
        if new_status in timestamp_map:
            setattr(case, timestamp_map[new_status], now)
        if new_status == "in_recovery" and case.surgery_start:
            case.surgery_end = now
        if new_status == "completed" and case.recovery_start:
            case.recovery_end = now

        # Update theatre status
        if case.theatre_id:
            theatre_result = await self.db.execute(
                select(OperatingTheatre).where(OperatingTheatre.id == case.theatre_id)
            )
            theatre = theatre_result.scalar_one_or_none()
            if theatre:
                if new_status == "in_progress":
                    theatre.status = "in_use"
                elif new_status in ("completed", "cancelled"):
                    theatre.status = "cleaning"

        case.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(case)

        event = EventBase(
            facility_id=facility_id,
            stream_type="surgery",
            stream_id=case.patient_id,
            event_type="SurgicalCaseStatusChanged",
            event_data={"case_id": str(case.id), "status": new_status},
            version=1,
            created_by=updated_by,
        )
        self.db.add(event)
        return case

    async def record_operative_notes(
        self,
        case_id: uuid.UUID,
        data: OperativeNotesRequest,
        facility_id: uuid.UUID,
        recorded_by: uuid.UUID,
    ) -> SurgicalCase | None:
        """
        Record operative findings and notes post-surgery.

        @param case_id: Case UUID
        @param data: Operative notes
        @param facility_id: Facility UUID
        @param recorded_by: Staff UUID
        @returns Updated case or None
        """
        case = await self.get_case(case_id, facility_id)
        if not case:
            return None

        case.operative_findings = data.operative_findings
        case.operative_notes = data.operative_notes
        case.specimens = data.specimens
        case.implants = data.implants
        case.complications = data.complications
        case.blood_loss_ml = data.blood_loss_ml
        case.postop_instructions = data.postop_instructions
        case.updated_by = recorded_by
        await self.db.flush()
        await self.db.refresh(case)
        return case

    async def get_summary(self, facility_id: uuid.UUID) -> TheatreSummary:
        """
        Get theatre summary stats.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        today = date.today()

        theatres_total = await self.db.execute(
            select(func.count(OperatingTheatre.id)).where(
                OperatingTheatre.facility_id == facility_id,
                OperatingTheatre.is_deleted == False,  # noqa: E712
                OperatingTheatre.is_active == True,  # noqa: E712
            )
        )
        available = await self.db.execute(
            select(func.count(OperatingTheatre.id)).where(
                OperatingTheatre.facility_id == facility_id,
                OperatingTheatre.is_deleted == False,  # noqa: E712
                OperatingTheatre.status == "available",
            )
        )
        in_use = await self.db.execute(
            select(func.count(OperatingTheatre.id)).where(
                OperatingTheatre.facility_id == facility_id,
                OperatingTheatre.is_deleted == False,  # noqa: E712
                OperatingTheatre.status == "in_use",
            )
        )

        case_base = [
            SurgicalCase.facility_id == facility_id,
            SurgicalCase.is_deleted == False,  # noqa: E712
            func.date(SurgicalCase.scheduled_date) == today,
        ]
        scheduled = await self.db.execute(
            select(func.count(SurgicalCase.id)).where(*case_base)
        )
        completed = await self.db.execute(
            select(func.count(SurgicalCase.id)).where(*case_base, SurgicalCase.status == "completed")
        )
        emergency = await self.db.execute(
            select(func.count(SurgicalCase.id)).where(*case_base, SurgicalCase.priority == "emergency")
        )
        cancelled = await self.db.execute(
            select(func.count(SurgicalCase.id)).where(*case_base, SurgicalCase.status == "cancelled")
        )

        return TheatreSummary(
            total_theatres=theatres_total.scalar() or 0,
            available_theatres=available.scalar() or 0,
            in_use_theatres=in_use.scalar() or 0,
            scheduled_today=scheduled.scalar() or 0,
            completed_today=completed.scalar() or 0,
            emergency_cases=emergency.scalar() or 0,
            cancelled_today=cancelled.scalar() or 0,
        )
