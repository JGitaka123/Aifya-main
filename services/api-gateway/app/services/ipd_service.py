import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.base import EventBase
from app.models.encounter import Encounter
from app.models.ipd import Admission, AdmissionOrder, Bed, NursingNote, Ward
from app.models.patient import Patient
from app.models.staff import Department, Staff
from app.schemas.ipd import (
    AdmissionCreate,
    AdmissionListItem,
    AdmissionOrderAccept,
    AdmissionOrderAdmit,
    AdmissionOrderCreate,
    AdmissionOrderDecision,
    AdmissionOrderListItem,
    BedCreate,
    BedResponse,
    DischargeRequest,
    NursingNoteCreate,
    WardBoardSummary,
    WardCreate,
    WardResponse,
)
from app.services.queue.queue_service import QueueService


#: Statuses that still need the admission desk's attention.
OPEN_ADMISSION_ORDER_STATUSES = ("pending", "bed_pending", "accepted")


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
            # The patient is no longer waiting in a unit; take their ticket
            # off the call board so a bed does not sit in the waiting count.
            await QueueService(self.db).close_for_encounter(
                facility_id=facility_id,
                encounter_id=encounter.id,
                actor_id=admitted_by,
                reason="admitted to ward",
            )

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

    # ── Admission Orders ─────────────────────────────────────────────────
    #
    # An order is the bridge between consultation and IPD. The clinician
    # raises it; the admission desk works it. Nothing here creates an
    # inpatient — that only happens in admit_from_order, once a ward and bed
    # have actually been assigned.

    async def create_admission_order(
        self,
        data: AdmissionOrderCreate,
        facility_id: uuid.UUID,
        ordered_by: uuid.UUID,
    ) -> AdmissionOrder:
        """
        Raise an admission order for an open encounter.

        Deliberately does not admit anyone: the patient stays an outpatient
        until the admission desk accepts the order and a bed is assigned.

        @param data: Admission order details
        @param facility_id: Facility UUID
        @param ordered_by: Staff UUID of the requesting clinician
        @returns Created admission order
        @raises ValueError: Unknown/closed encounter or an order already open
        """
        enc_result = await self.db.execute(
            select(Encounter).where(
                Encounter.id == data.encounter_id,
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
            )
        )
        encounter = enc_result.scalar_one_or_none()
        if not encounter:
            raise ValueError("Encounter not found")
        if encounter.status in ("completed", "admitted", "cancelled"):
            raise ValueError(
                "This visit is already closed — open a new encounter to request admission"
            )

        # One open request per encounter, otherwise the desk cannot tell which
        # one it is working and the ward ends up with duplicate admissions.
        open_result = await self.db.execute(
            select(AdmissionOrder.id).where(
                AdmissionOrder.facility_id == facility_id,
                AdmissionOrder.encounter_id == data.encounter_id,
                AdmissionOrder.is_deleted == False,  # noqa: E712
                AdmissionOrder.status.in_(OPEN_ADMISSION_ORDER_STATUSES),
            )
        )
        if open_result.scalar_one_or_none():
            raise ValueError("This visit already has an open admission request")

        order = AdmissionOrder(
            facility_id=facility_id,
            order_number=await self._next_admission_order_number(facility_id),
            encounter_id=data.encounter_id,
            patient_id=data.patient_id,
            ordered_by=ordered_by,
            attending_doctor_id=data.attending_doctor_id,
            reason=data.reason,
            primary_diagnosis=data.primary_diagnosis,
            admission_type=data.admission_type,
            priority=data.priority,
            department_id=data.department_id,
            requested_ward_id=data.requested_ward_id,
            clinical_notes=data.clinical_notes,
            requested_at=data.requested_at,
            status="pending",
            created_by=ordered_by,
            updated_by=ordered_by,
        )
        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="admission_order",
                stream_id=data.patient_id,
                event_type="AdmissionOrderCreated",
                event_data={
                    "order_number": order.order_number,
                    "encounter_id": str(data.encounter_id),
                    "admission_type": data.admission_type,
                    "priority": data.priority,
                    "reason": data.reason,
                },
                version=1,
                created_by=ordered_by,
            )
        )

        return order

    async def get_admission_orders(
        self,
        facility_id: uuid.UUID,
        status_filter: str | None = None,
        patient_id: uuid.UUID | None = None,
        encounter_id: uuid.UUID | None = None,
    ) -> tuple[list[AdmissionOrderListItem], int]:
        """
        List admission orders for the queue, newest and most urgent first.

        @param facility_id: Facility UUID
        @param status_filter: Exact status, or "open" for everything still workable
        @param patient_id: Optional patient filter
        @param encounter_id: Optional encounter filter
        @returns Tuple of (order items, total)
        """
        attending = aliased(Staff)
        admitted_ward = aliased(Ward)
        admitted_bed = aliased(Bed)

        stmt = (
            select(
                AdmissionOrder,
                Patient,
                Department,
                Ward,
                attending,
                admitted_ward,
                admitted_bed,
            )
            .join(Patient, AdmissionOrder.patient_id == Patient.id)
            .outerjoin(Department, AdmissionOrder.department_id == Department.id)
            .outerjoin(Ward, AdmissionOrder.requested_ward_id == Ward.id)
            .outerjoin(attending, AdmissionOrder.attending_doctor_id == attending.id)
            .outerjoin(Admission, AdmissionOrder.admission_id == Admission.id)
            .outerjoin(admitted_ward, Admission.ward_id == admitted_ward.id)
            .outerjoin(admitted_bed, Admission.bed_id == admitted_bed.id)
            .where(
                AdmissionOrder.facility_id == facility_id,
                AdmissionOrder.is_deleted == False,  # noqa: E712
            )
        )

        if status_filter == "open":
            stmt = stmt.where(AdmissionOrder.status.in_(OPEN_ADMISSION_ORDER_STATUSES))
        elif status_filter:
            stmt = stmt.where(AdmissionOrder.status == status_filter)

        if patient_id:
            stmt = stmt.where(AdmissionOrder.patient_id == patient_id)
        if encounter_id:
            stmt = stmt.where(AdmissionOrder.encounter_id == encounter_id)

        # Emergency before urgent before routine, then oldest first so nobody
        # starves at the back of the queue.
        priority_rank = case(
            (AdmissionOrder.priority == "emergency", 0),
            (AdmissionOrder.priority == "urgent", 1),
            else_=2,
        )
        stmt = stmt.order_by(priority_rank.asc(), AdmissionOrder.created_at.asc())

        result = await self.db.execute(stmt)
        rows = result.all()
        items = [self._admission_order_item(row) for row in rows]
        return items, len(items)

    async def get_admission_order(
        self, order_id: uuid.UUID, facility_id: uuid.UUID
    ) -> AdmissionOrder | None:
        """
        Get a single admission order.

        @param order_id: Admission order UUID
        @param facility_id: Facility UUID
        @returns Admission order or None
        """
        result = await self.db.execute(
            select(AdmissionOrder).where(
                AdmissionOrder.id == order_id,
                AdmissionOrder.facility_id == facility_id,
                AdmissionOrder.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def accept_admission_order(
        self,
        order_id: uuid.UUID,
        decision: AdmissionOrderAccept,
        facility_id: uuid.UUID,
        decided_by: uuid.UUID,
    ) -> AdmissionOrder:
        """
        Accept an order at the admission desk.

        @param order_id: Admission order UUID
        @param decision: Decision notes and whether a bed is still pending
        @param facility_id: Facility UUID
        @param decided_by: Staff UUID making the decision
        @returns Updated admission order
        @raises ValueError: Unknown order or an order that is already closed
        """
        order = await self._open_order_or_raise(order_id, facility_id)
        order.status = "bed_pending" if decision.bed_pending else "accepted"
        self._record_decision(order, decision.decision_notes, decided_by)
        await self.db.flush()
        await self.db.refresh(order)

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="admission_order",
                stream_id=order.patient_id,
                event_type="AdmissionOrderAccepted",
                event_data={
                    "order_number": order.order_number,
                    "status": order.status,
                },
                version=1,
                created_by=decided_by,
            )
        )
        return order

    async def decline_admission_order(
        self,
        order_id: uuid.UUID,
        decision: AdmissionOrderDecision,
        facility_id: uuid.UUID,
        decided_by: uuid.UUID,
    ) -> AdmissionOrder:
        """
        Decline an order at the admission desk.

        @param order_id: Admission order UUID
        @param decision: Reason for the refusal, shown to the requesting clinician
        @param facility_id: Facility UUID
        @param decided_by: Staff UUID making the decision
        @returns Updated admission order
        @raises ValueError: Unknown order or an order that is already closed
        """
        order = await self._open_order_or_raise(order_id, facility_id)
        order.status = "declined"
        self._record_decision(order, decision.decision_notes, decided_by)
        await self.db.flush()
        await self.db.refresh(order)

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="admission_order",
                stream_id=order.patient_id,
                event_type="AdmissionOrderDeclined",
                event_data={
                    "order_number": order.order_number,
                    "reason": decision.decision_notes,
                },
                version=1,
                created_by=decided_by,
            )
        )
        return order

    async def cancel_admission_order(
        self,
        order_id: uuid.UUID,
        decision: AdmissionOrderDecision,
        facility_id: uuid.UUID,
        cancelled_by: uuid.UUID,
    ) -> AdmissionOrder:
        """
        Cancel an order — the clinician changed their mind or the patient left.

        @param order_id: Admission order UUID
        @param decision: Optional note explaining the cancellation
        @param facility_id: Facility UUID
        @param cancelled_by: Staff UUID cancelling the order
        @returns Updated admission order
        @raises ValueError: Unknown order or an order that is already closed
        """
        order = await self._open_order_or_raise(order_id, facility_id)
        order.status = "cancelled"
        self._record_decision(order, decision.decision_notes, cancelled_by)
        await self.db.flush()
        await self.db.refresh(order)

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="admission_order",
                stream_id=order.patient_id,
                event_type="AdmissionOrderCancelled",
                event_data={
                    "order_number": order.order_number,
                    "reason": decision.decision_notes,
                },
                version=1,
                created_by=cancelled_by,
            )
        )
        return order

    async def admit_from_order(
        self,
        order_id: uuid.UUID,
        data: AdmissionOrderAdmit,
        facility_id: uuid.UUID,
        admitted_by: uuid.UUID,
    ) -> Admission:
        """
        Assign a ward and bed, then create the real IPD admission.

        This is the only path that turns an admission *order* into an
        inpatient: the order must exist and still be open, the bed must be
        free, and the resulting admission is linked back to the order.

        @param order_id: Admission order UUID
        @param data: Ward, bed and optional attending doctor
        @param facility_id: Facility UUID
        @param admitted_by: Staff UUID performing the admission
        @returns Created admission
        @raises ValueError: Unknown/closed order, or the bed is unavailable
        """
        order = await self._open_order_or_raise(order_id, facility_id)

        admission = await self.admit_patient(
            data=AdmissionCreate(
                encounter_id=order.encounter_id,
                patient_id=order.patient_id,
                ward_id=data.ward_id,
                bed_id=data.bed_id,
                attending_doctor_id=(
                    data.attending_doctor_id or order.attending_doctor_id
                ),
                admission_reason=order.reason,
                admission_diagnosis=order.primary_diagnosis,
                admitted_from="opd",
            ),
            facility_id=facility_id,
            admitted_by=admitted_by,
        )

        order.status = "admitted"
        order.admission_id = admission.id
        if data.attending_doctor_id:
            order.attending_doctor_id = data.attending_doctor_id
        self._record_decision(
            order,
            data.decision_notes or order.decision_notes,
            admitted_by,
        )
        await self.db.flush()

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="admission_order",
                stream_id=order.patient_id,
                event_type="AdmissionOrderFulfilled",
                event_data={
                    "order_number": order.order_number,
                    "admission_number": admission.admission_number,
                    "admission_id": str(admission.id),
                    "ward_id": str(data.ward_id),
                    "bed_id": str(data.bed_id),
                },
                version=1,
                created_by=admitted_by,
            )
        )
        return admission

    # ── Admission Order helpers ──────────────────────────────────────────

    async def _open_order_or_raise(
        self, order_id: uuid.UUID, facility_id: uuid.UUID
    ) -> AdmissionOrder:
        """
        Load an order that is still workable.

        @param order_id: Admission order UUID
        @param facility_id: Facility UUID
        @returns The open order
        @raises ValueError: Unknown order, or one already admitted/declined/cancelled
        """
        order = await self.get_admission_order(order_id, facility_id)
        if not order:
            raise ValueError("Admission request not found")
        if order.status not in OPEN_ADMISSION_ORDER_STATUSES:
            raise ValueError(
                f"This admission request is already {order.status} and cannot be changed"
            )
        return order

    def _record_decision(
        self, order: AdmissionOrder, notes: str | None, actor: uuid.UUID
    ) -> None:
        """
        Stamp the order with who decided and when.

        @param order: Order being updated
        @param notes: Decision notes (kept if not supplied)
        @param actor: Staff UUID making the change
        @returns None
        """
        if notes:
            order.decision_notes = notes
        order.decided_by = actor
        order.decided_at = datetime.now(UTC)
        order.updated_by = actor

    def _admission_order_item(self, row) -> AdmissionOrderListItem:
        """
        Flatten a queue row into the list item the UI renders.

        @param row: Row of (order, patient, department, ward, attending, admitted_ward, admitted_bed)
        @returns Admission order list item
        """
        (
            order,
            patient,
            department,
            requested_ward,
            attending,
            admitted_ward,
            admitted_bed,
        ) = row

        item = AdmissionOrderListItem.model_validate(order)
        item.patient_name = f"{patient.first_name} {patient.last_name}"
        item.patient_mrn = patient.mrn
        item.department_name = department.name if department else None
        item.requested_ward_name = requested_ward.name if requested_ward else None
        item.attending_doctor_name = (
            f"{attending.first_name} {attending.last_name}" if attending else None
        )
        item.admitted_ward_name = admitted_ward.name if admitted_ward else None
        item.admitted_bed_number = admitted_bed.bed_number if admitted_bed else None
        return item

    async def _next_admission_order_number(self, facility_id: uuid.UUID) -> str:
        """Generate the next admission-order number (AO-YYYYMMDD-XXXX)."""
        today = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f"AO-{today}-"

        result = await self.db.execute(
            select(func.count())
            .select_from(AdmissionOrder)
            .where(
                AdmissionOrder.facility_id == facility_id,
                AdmissionOrder.order_number.like(f"{prefix}%"),
            )
        )
        count = result.scalar_one()
        return f"{prefix}{count + 1:04d}"

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
