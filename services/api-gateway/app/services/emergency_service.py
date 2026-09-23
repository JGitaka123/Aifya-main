import uuid
from datetime import UTC, date, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.emergency import EmergencyVisit
from app.models.encounter import Encounter
from app.models.hr import LeaveRequest, Shift, ShiftAssignment
from app.models.ipd import Admission, Bed
from app.models.patient import Patient
from app.models.referral import Referral
from app.models.staff import Department, Staff
from app.schemas.emergency import (
    AssignDoctorRequest,
    DispositionRequest,
    DoctorOnDuty,
    EmergencyListItem,
    EmergencySummary,
    EmergencyVisitCreate,
    TriageRequest,
)
from app.schemas.ipd import AdmissionCreate, TransferToEmergencyRequest
from app.schemas.referral import ReferralCreate
from app.services.ipd_service import IPDService
from app.services.leave_overlap import staff_ids_on_approved_leave
from app.services.referral_service import ReferralService

TRIAGE_COLORS = {
    "emergency": "red",
    "urgent": "orange",
    "standard": "yellow",
    "non_urgent": "green",
    "dead": "blue",
}


class EmergencyService:
    """
    Service for emergency department: registration, SATS triage,
    doctor assignment, treatment tracking, and disposition.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_visit(
        self,
        data: EmergencyVisitCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
        encounter_id: uuid.UUID | None = None,
        referral_type: str = "external",
    ) -> EmergencyVisit:
        """
        Register a new emergency visit.

        Every visit is attached to an encounter so the episode can be
        documented, billed and referred onwards. When the patient arrived on
        referral, an incoming referral is created (or the supplied one is
        linked) so the Referrals tab shows where the patient came from.

        @param data: Visit data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @param encounter_id: Existing encounter to reuse, if the caller already has one
        @param referral_type: "external" for a referral from another facility,
            "internal" for a transfer inside this facility
        @returns Created emergency visit
        @raises ValueError: If the supplied referral_id does not exist
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count_result = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(
                EmergencyVisit.facility_id == facility_id,
                EmergencyVisit.visit_number.like(f"ER-{date_part}-%"),
                EmergencyVisit.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count_result.scalar() or 0) + 1
        visit_number = f"ER-{date_part}-{seq:04d}"

        if encounter_id is None:
            encounter = Encounter(
                facility_id=facility_id,
                patient_id=data.patient_id,
                encounter_type="emergency",
                chief_complaint=data.chief_complaint,
                status="waiting",
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(encounter)
            await self.db.flush()
            await self.db.refresh(encounter)
            encounter_id = encounter.id

        referral_id = data.referral_id
        created_referral: Referral | None = None
        if referral_id is not None:
            existing = await self.db.execute(
                select(Referral).where(
                    Referral.id == referral_id,
                    Referral.is_deleted == False,  # noqa: E712
                )
            )
            if existing.scalar_one_or_none() is None:
                raise ValueError("Referral not found")
        elif data.arrival_mode == "referral":
            created_referral = await self._create_incoming_referral(
                data=data,
                encounter_id=encounter_id,
                facility_id=facility_id,
                created_by=created_by,
                referral_type=referral_type,
            )
            referral_id = created_referral.id

        visit = EmergencyVisit(
            facility_id=facility_id,
            patient_id=data.patient_id,
            encounter_id=encounter_id,
            referral_id=referral_id,
            visit_number=visit_number,
            arrival_time=now,
            arrival_mode=data.arrival_mode,
            brought_by=data.brought_by,
            chief_complaint=data.chief_complaint,
            is_trauma=data.is_trauma,
            is_resuscitation=False,  # Default; updated during triage when category is "emergency"
            allergies_noted=data.allergies_noted,
            notes=data.notes,
            status="arrived",
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(visit)
        await self.db.flush()
        await self.db.refresh(visit)

        if created_referral is not None:
            created_referral.emergency_visit_id = visit.id

        event = EventBase(
            facility_id=facility_id,
            stream_type="emergency",
            stream_id=data.patient_id,
            event_type="EmergencyVisitRegistered",
            event_data={
                "visit_id": str(visit.id),
                "visit_number": visit_number,
                "complaint": data.chief_complaint,
                "arrival_mode": data.arrival_mode,
                "referral_id": str(referral_id) if referral_id else None,
            },
            version=1,
            created_by=created_by,
        )
        self.db.add(event)
        return visit

    async def transfer_inpatient_to_emergency(
        self,
        admission_id: uuid.UUID,
        data: TransferToEmergencyRequest,
        facility_id: uuid.UUID,
        transferred_by: uuid.UUID,
    ) -> EmergencyVisit | None:
        '''Transfer an inpatient whose condition has worsened to the Emergency Department.

        Registers an emergency visit for the patient and closes the current
        IPD admission as transferred, freeing the ward bed so the patient
        appears in the emergency queue for triage.

        @param admission_id: IPD admission UUID
        @param data: Transfer reason and notes
        @param facility_id: Facility UUID
        @param transferred_by: Staff UUID initiating the transfer
        @returns Created emergency visit or None
        '''
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
        if admission.status not in ('admitted', 'on_leave'):
            raise ValueError(
                f'Cannot transfer to emergency with status: {admission.status}'
            )

        visit = await self.register_visit(
            data=EmergencyVisitCreate(
                patient_id=admission.patient_id,
                arrival_mode='referral',
                chief_complaint=data.reason,
                notes=(
                    data.notes
                    or f'Transferred from IPD admission {admission.admission_number}'
                ),
            ),
            facility_id=facility_id,
            created_by=transferred_by,
            encounter_id=admission.encounter_id,
            referral_type="internal",
        )

        now = datetime.now(UTC)
        los = (now - admission.admitted_at).days if admission.admitted_at else 0
        summary = (
            f'Condition worsened; transferred to Emergency Department '
            f'(visit {visit.visit_number}): {data.reason}'
        )

        admission.status = 'transferred'
        admission.discharged_at = now
        admission.discharged_by = transferred_by
        admission.discharge_type = 'transferred'
        admission.discharge_summary = summary
        admission.length_of_stay_days = los
        admission.updated_by = transferred_by

        # Free the bed for cleaning and reallocation.
        bed_result = await self.db.execute(
            select(Bed).where(Bed.id == admission.bed_id)
        )
        bed = bed_result.scalar_one_or_none()
        if bed:
            bed.status = 'cleaning'
            bed.current_patient_id = None
            bed.current_admission_id = None

        # End the inpatient episode on the source encounter. The new
        # emergency visit now tracks the patient's continued care.
        enc_result = await self.db.execute(
            select(Encounter).where(Encounter.id == admission.encounter_id)
        )
        encounter = enc_result.scalar_one_or_none()
        if encounter:
            encounter.status = 'discharged'
            encounter.discharge_date = now
            encounter.discharge_summary = summary
            encounter.disposition = 'referred'

        event = EventBase(
            facility_id=facility_id,
            stream_type='admission',
            stream_id=admission.patient_id,
            event_type='PatientTransferredToEmergency',
            event_data={
                'admission_id': str(admission.id),
                'admission_number': admission.admission_number,
                'visit_id': str(visit.id),
                'visit_number': visit.visit_number,
                'reason': data.reason,
            },
            version=1,
            created_by=transferred_by,
        )
        self.db.add(event)

        await self.db.flush()
        await self.db.refresh(visit)
        return visit

    async def triage(
        self,
        visit_id: uuid.UUID,
        data: TriageRequest,
        facility_id: uuid.UUID,
        triaged_by: uuid.UUID,
    ) -> EmergencyVisit | None:
        """
        Perform SATS triage on an emergency visit.

        @param visit_id: Visit UUID
        @param data: Triage data
        @param facility_id: Facility UUID
        @param triaged_by: Staff UUID
        @returns Updated visit or None
        """
        visit = await self._get_visit(visit_id, facility_id)
        if not visit:
            return None

        now = datetime.now(UTC)
        visit.triage_category = data.triage_category
        visit.triage_color = TRIAGE_COLORS.get(data.triage_category, "yellow")
        visit.triage_score = data.triage_score
        visit.triage_vitals = data.triage_vitals
        visit.triage_time = now
        visit.triaged_by = triaged_by
        visit.status = "triaged"
        if data.treatment_area:
            visit.treatment_area = data.treatment_area
        if data.triage_category == "emergency":
            visit.is_resuscitation = True
            visit.treatment_area = visit.treatment_area or "resus"
        if data.notes:
            visit.notes = (visit.notes or "") + f"\n[Triage] {data.notes}"
        visit.updated_by = triaged_by
        await self.db.flush()
        await self.db.refresh(visit)
        return visit

    async def assign_doctor(
        self,
        visit_id: uuid.UUID,
        data: AssignDoctorRequest,
        facility_id: uuid.UUID,
        assigned_by: uuid.UUID,
    ) -> EmergencyVisit | None:
        """
        Assign a doctor to an emergency visit.

        @param visit_id: Visit UUID
        @param data: Assignment data
        @param facility_id: Facility UUID
        @param assigned_by: Staff UUID
        @returns Updated visit or None
        """
        visit = await self._get_visit(visit_id, facility_id)
        if not visit:
            return None

        visit.assigned_doctor_id = data.doctor_id
        visit.status = "in_treatment"
        visit.treatment_started_at = datetime.now(UTC)
        visit.updated_by = assigned_by
        await self.db.flush()
        await self.db.refresh(visit)
        return visit

    async def record_disposition(
        self,
        visit_id: uuid.UUID,
        data: DispositionRequest,
        facility_id: uuid.UUID,
        disposed_by: uuid.UUID,
    ) -> EmergencyVisit | None:
        """
        Record disposition for an emergency visit.

        A "transfer" disposition also raises an outgoing referral for the
        receiving facility so the Referrals tab shows the patient going out.

        @param visit_id: Visit UUID
        @param data: Disposition data
        @param facility_id: Facility UUID
        @param disposed_by: Staff UUID
        @returns Updated visit or None
        """
        visit = await self._get_visit(visit_id, facility_id)
        if not visit:
            return None

        now = datetime.now(UTC)
        visit.disposition = data.disposition
        visit.disposition_time = now
        visit.disposition_notes = data.disposition_notes

        status_map = {
            "discharge": "discharged",
            "admit": "admitted",
            "transfer": "transferred",
            "deceased": "deceased",
            "left_ama": "left_against_advice",
        }
        visit.status = status_map.get(data.disposition, "discharged")
        admission_ref: uuid.UUID | None = None
        referral_ref: uuid.UUID | None = None
        if data.disposition == "admit":
            ward_id, admission = await self._admit_from_emergency(
                visit=visit,
                data=data,
                facility_id=facility_id,
                disposed_by=disposed_by,
            )
            visit.admitted_to_ward_id = ward_id
            admission_ref = admission.id
        elif data.disposition == "transfer":
            referral = await self._create_outgoing_referral(
                visit=visit,
                data=data,
                facility_id=facility_id,
                disposed_by=disposed_by,
            )
            referral_ref = referral.id
        elif data.admitted_to_ward_id:
            visit.admitted_to_ward_id = data.admitted_to_ward_id
        visit.updated_by = disposed_by
        await self.db.flush()
        await self.db.refresh(visit)

        event = EventBase(
            facility_id=facility_id,
            stream_type="emergency",
            stream_id=visit.patient_id,
            event_type="EmergencyDisposition",
            event_data={
                "visit_id": str(visit.id),
                "disposition": data.disposition,
                "admission_id": str(admission_ref) if admission_ref else None,
                "referral_id": str(referral_ref) if referral_ref else None,
            },
            version=1,
            created_by=disposed_by,
        )
        self.db.add(event)
        return visit

    async def _admit_from_emergency(
        self,
        visit: EmergencyVisit,
        data: DispositionRequest,
        facility_id: uuid.UUID,
        disposed_by: uuid.UUID,
    ):
        """
        Create a real IPD admission when an emergency patient is admitted.

        Ensures an encounter exists for the emergency visit, then reuses the
        IPD admission service so the patient appears on the ward board with
        the bed marked occupied.

        @param visit: Emergency visit being admitted
        @param data: Disposition data
        @param facility_id: Facility UUID
        @param disposed_by: Staff UUID
        @returns Tuple of (ward_id, Admission record)
        """
        if not data.bed_id:
            raise ValueError("Admitting to IPD requires selecting a bed")

        bed_result = await self.db.execute(
            select(Bed).where(
                Bed.id == data.bed_id,
                Bed.facility_id == facility_id,
                Bed.is_deleted == False,  # noqa: E712
            )
        )
        bed = bed_result.scalar_one_or_none()
        if not bed:
            raise ValueError("Selected bed not found")
        if bed.status != "available":
            raise ValueError(f"Selected bed is not available (status: {bed.status})")

        ward_id = data.admitted_to_ward_id or bed.ward_id

        # The IPD admission links to an Encounter. register_visit creates one
        # for every new visit; older rows may still be missing it.
        encounter_id = visit.encounter_id
        if encounter_id is None:
            encounter = Encounter(
                facility_id=facility_id,
                patient_id=visit.patient_id,
                encounter_type="emergency",
                chief_complaint=visit.chief_complaint,
                triage_category=visit.triage_category,
                attending_doctor_id=visit.assigned_doctor_id,
                status="admitted",
                created_by=disposed_by,
                updated_by=disposed_by,
            )
            self.db.add(encounter)
            await self.db.flush()
            await self.db.refresh(encounter)
            encounter_id = encounter.id
            visit.encounter_id = encounter_id

        ipd_service = IPDService(self.db)
        admission = await ipd_service.admit_patient(
            data=AdmissionCreate(
                encounter_id=encounter_id,
                patient_id=visit.patient_id,
                ward_id=ward_id,
                bed_id=data.bed_id,
                attending_doctor_id=visit.assigned_doctor_id,
                admission_reason=data.admission_reason or visit.chief_complaint,
                admission_diagnosis=data.admission_diagnosis,
                admitted_from="emergency",
                accommodation_type=data.accommodation_type,
            ),
            facility_id=facility_id,
            admitted_by=disposed_by,
        )
        return ward_id, admission

    async def _create_incoming_referral(
        self,
        data: EmergencyVisitCreate,
        encounter_id: uuid.UUID | None,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
        referral_type: str = "external",
    ) -> Referral:
        """
        Create the incoming referral that brought a patient to the ED.

        @param data: Visit data including the referring facility and reason
        @param encounter_id: Encounter UUID for the episode
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @param referral_type: "external" or "internal"
        @returns Created referral
        """
        referral_service = ReferralService(self.db)
        return await referral_service.create_referral(
            data=ReferralCreate(
                patient_id=data.patient_id,
                encounter_id=encounter_id,
                referral_type=referral_type,
                direction="incoming",
                referring_facility_name=data.referred_from_facility_name,
                receiving_facility_id=facility_id,
                reason=data.referral_reason or data.chief_complaint,
                clinical_notes=data.notes,
                urgency=data.referral_urgency,
            ),
            facility_id=facility_id,
            created_by=created_by,
            initial_status="received",
        )

    async def _create_outgoing_referral(
        self,
        visit: EmergencyVisit,
        data: DispositionRequest,
        facility_id: uuid.UUID,
        disposed_by: uuid.UUID,
    ) -> Referral:
        """
        Raise an outgoing referral for an ED patient sent on for more care.

        @param visit: Emergency visit being transferred
        @param data: Disposition data with the receiving facility details
        @param facility_id: Facility UUID
        @param disposed_by: Staff UUID
        @returns Created referral
        @raises ValueError: If no receiving facility was supplied
        """
        if not (data.receiving_facility_name or data.receiving_facility_id):
            raise ValueError(
                "Transferring a patient requires the receiving facility"
            )

        referral_service = ReferralService(self.db)
        return await referral_service.create_referral(
            data=ReferralCreate(
                patient_id=visit.patient_id,
                encounter_id=visit.encounter_id,
                emergency_visit_id=visit.id,
                referral_type="external",
                direction="outgoing",
                referring_doctor_id=visit.assigned_doctor_id,
                receiving_facility_id=data.receiving_facility_id,
                receiving_facility_name=data.receiving_facility_name,
                receiving_facility_mfl=data.receiving_facility_mfl,
                reason=data.transfer_reason or visit.chief_complaint,
                clinical_notes=data.disposition_notes,
                diagnosis=data.admission_diagnosis,
                urgency=data.transfer_urgency,
                notes=data.disposition_notes,
            ),
            facility_id=facility_id,
            created_by=disposed_by,
            initial_status="sent",
        )

    async def get_queue(
        self,
        facility_id: uuid.UUID,
        status: str | None = None,
    ) -> list[EmergencyListItem]:
        """
        Get emergency queue with patient and doctor names.

        @param facility_id: Facility UUID
        @param status: Optional status filter
        @returns List of emergency visits
        """
        DoctorStaff = Staff.__table__.alias("doctor_staff")  # noqa: N806 — SQLAlchemy alias naming

        query = (
            select(
                EmergencyVisit,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
                Patient.mrn,
                DoctorStaff.c.first_name.label("d_first"),
                DoctorStaff.c.last_name.label("d_last"),
            )
            .join(Patient, EmergencyVisit.patient_id == Patient.id)
            .outerjoin(DoctorStaff, EmergencyVisit.assigned_doctor_id == DoctorStaff.c.id)
            .where(
                EmergencyVisit.facility_id == facility_id,
                EmergencyVisit.is_deleted == False,  # noqa: E712
            )
        )

        if status:
            query = query.where(EmergencyVisit.status == status)
        else:
            query = query.where(
                EmergencyVisit.status.in_(["arrived", "triaged", "in_treatment", "observation"])
            )

        # Priority order: red first, then by arrival time
        triage_order = case(
            (EmergencyVisit.triage_color == "red", 1),
            (EmergencyVisit.triage_color == "orange", 2),
            (EmergencyVisit.triage_color == "yellow", 3),
            (EmergencyVisit.triage_color == "green", 4),
            (EmergencyVisit.triage_color == "blue", 5),
            else_=6,
        )
        query = query.order_by(triage_order.asc(), EmergencyVisit.arrival_time.asc())

        result = await self.db.execute(query)
        rows = result.all()

        items: list[EmergencyListItem] = []
        for visit, p_first, p_last, mrn, d_first, d_last in rows:
            items.append(
                EmergencyListItem(
                    id=visit.id,
                    visit_number=visit.visit_number,
                    patient_id=visit.patient_id,
                    patient_name=f"{p_first or ''} {p_last or ''}".strip() or None,
                    patient_mrn=mrn,
                    referral_id=visit.referral_id,
                    arrival_time=visit.arrival_time,
                    arrival_mode=visit.arrival_mode,
                    chief_complaint=visit.chief_complaint,
                    triage_category=visit.triage_category,
                    triage_color=visit.triage_color,
                    triage_score=visit.triage_score,
                    treatment_area=visit.treatment_area,
                    assigned_doctor_name=f"{d_first or ''} {d_last or ''}".strip() or None,
                    status=visit.status,
                    is_trauma=visit.is_trauma,
                    is_resuscitation=visit.is_resuscitation,
                )
            )
        return items

    async def get_doctors_on_duty(
        self,
        facility_id: uuid.UUID,
        duty_date: date | None = None,
    ) -> list[DoctorOnDuty]:
        """
        Get doctors rostered on duty for a given day.

        A doctor counts as on duty when they have an assigned/confirmed
        shift assignment for the day, are active staff with role doctor,
        and are not on approved leave.

        @param facility_id: Facility UUID
        @param duty_date: Optional roster date (defaults to today)
        @returns List of on-duty doctors with their shift
        """
        target_date = duty_date or date.today()

        on_leave_ids = await staff_ids_on_approved_leave(
            self.db, facility_id, target_date
        )

        result = await self.db.execute(
            select(
                Staff.id.label("doctor_id"),
                Staff.first_name,
                Staff.last_name,
                Staff.title,
                Staff.specialization,
                Department.name.label("department_name"),
                Shift.id.label("shift_id"),
                Shift.name.label("shift_name"),
                Shift.code.label("shift_code"),
                Shift.start_time.label("shift_start_time"),
                Shift.end_time.label("shift_end_time"),
                Shift.is_night_shift,
            )
            .select_from(Staff)
            .join(
                ShiftAssignment,
                ShiftAssignment.staff_id == Staff.id,
            )
            .outerjoin(Shift, Shift.id == ShiftAssignment.shift_id)
            .outerjoin(
                Department,
                Department.id == Staff.primary_department_id,
            )
            .where(
                Staff.facility_id == facility_id,
                Staff.is_deleted == False,  # noqa: E712
                Staff.is_active == True,  # noqa: E712
                Staff.role == "doctor",
                ShiftAssignment.facility_id == facility_id,
                ShiftAssignment.is_deleted == False,  # noqa: E712
                ShiftAssignment.assignment_date == target_date,
                ShiftAssignment.status.in_(["assigned", "confirmed"]),
            )
            .order_by(Staff.last_name.asc(), Staff.first_name.asc())
        )

        doctors: list[DoctorOnDuty] = []
        seen: set[uuid.UUID] = set()
        for row in result.all():
            if row.doctor_id in seen or row.doctor_id in on_leave_ids:
                continue
            seen.add(row.doctor_id)
            doctors.append(
                DoctorOnDuty(
                    id=row.doctor_id,
                    first_name=row.first_name,
                    last_name=row.last_name,
                    title=row.title,
                    specialization=row.specialization,
                    department_name=row.department_name,
                    shift_id=row.shift_id,
                    shift_name=row.shift_name,
                    shift_code=row.shift_code,
                    shift_start_time=row.shift_start_time,
                    shift_end_time=row.shift_end_time,
                    is_night_shift=row.is_night_shift or False,
                )
            )
        return doctors

    async def get_visit(
        self, visit_id: uuid.UUID, facility_id: uuid.UUID
    ) -> EmergencyVisit | None:
        """
        Get a single emergency visit.

        @param visit_id: Visit UUID
        @param facility_id: Facility UUID
        @returns Emergency visit or None
        """
        return await self._get_visit(visit_id, facility_id)

    async def get_summary(self, facility_id: uuid.UUID) -> EmergencySummary:
        """
        Get emergency department summary.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        today = date.today()
        base = [
            EmergencyVisit.facility_id == facility_id,
            EmergencyVisit.is_deleted == False,  # noqa: E712
            func.date(EmergencyVisit.arrival_time) == today,
        ]

        total = await self.db.execute(select(func.count(EmergencyVisit.id)).where(*base))
        awaiting = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "arrived")
        )
        treating = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "in_treatment")
        )
        observing = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "observation")
        )
        red = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.triage_color == "red")
        )
        orange = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.triage_color == "orange")
        )
        discharged = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "discharged")
        )
        admitted = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "admitted")
        )
        trauma = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(
                *base, EmergencyVisit.is_trauma == True  # noqa: E712
            )
        )

        return EmergencySummary(
            total_today=total.scalar() or 0,
            awaiting_triage=awaiting.scalar() or 0,
            in_treatment=treating.scalar() or 0,
            in_observation=observing.scalar() or 0,
            critical_red=red.scalar() or 0,
            urgent_orange=orange.scalar() or 0,
            discharged_today=discharged.scalar() or 0,
            admitted_today=admitted.scalar() or 0,
            trauma_cases=trauma.scalar() or 0,
        )

    async def _get_visit(
        self, visit_id: uuid.UUID, facility_id: uuid.UUID
    ) -> EmergencyVisit | None:
        """Get a single visit by ID."""
        result = await self.db.execute(
            select(EmergencyVisit).where(
                EmergencyVisit.id == visit_id,
                EmergencyVisit.facility_id == facility_id,
                EmergencyVisit.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()
