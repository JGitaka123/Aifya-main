import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.patient import Patient
from app.models.radiology import ImagingOrder, ImagingResult
from app.schemas.radiology import (
    ImagingOrderCreate,
    ImagingOrderDetail,
    ImagingOrderResponse,
    ImagingPerformRequest,
    ImagingResultCreate,
    ImagingResultResponse,
    ImagingResultVerify,
    ImagingScheduleRequest,
    ImagingWorklistItem,
    RadiologySummary,
)
from app.services.service_billing import (
    IMAGING_ORDER,
    ServiceBillingService,
    post_service_charge,
)


class RadiologyService:
    """
    Service for radiology workflow: imaging orders, scheduling, performing,
    reporting, verification, and critical finding notification.
    Critical imaging findings MUST trigger immediate alert (CLAUDE.md: Clinical Safety).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Order Creation ────────────────────────────────────────────────────

    async def create_order(
        self,
        data: ImagingOrderCreate,
        facility_id: uuid.UUID,
        ordered_by: uuid.UUID,
    ) -> ImagingOrder:
        """
        Create a new imaging order with auto-generated order number.

        @param data: Imaging order creation data
        @param facility_id: Facility UUID from JWT
        @param ordered_by: Staff UUID who ordered
        @returns Created imaging order
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")

        # Count today's orders for sequential numbering
        count_result = await self.db.execute(
            select(func.count(ImagingOrder.id)).where(
                ImagingOrder.facility_id == facility_id,
                ImagingOrder.order_number.like(f"IMG-{date_part}-%"),
            )
        )
        seq = (count_result.scalar() or 0) + 1
        order_number = f"IMG-{date_part}-{seq:04d}"

        order = ImagingOrder(
            facility_id=facility_id,
            encounter_id=data.encounter_id,
            patient_id=data.patient_id,
            ordered_by=ordered_by,
            order_number=order_number,
            modality=data.modality,
            body_part=data.body_part,
            laterality=data.laterality,
            views_requested=data.views_requested,
            study_description=data.study_description,
            priority=data.priority,
            clinical_indication=data.clinical_indication,
            clinical_history=data.clinical_history,
            contrast_required=data.contrast_required,
            contrast_type=data.contrast_type,
            pregnancy_status=data.pregnancy_status,
            allergies_noted=data.allergies_noted,
            status="ordered",
            created_by=ordered_by,
            updated_by=ordered_by,
        )
        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)

        # Bill the study so the cashier can collect before the scan happens.
        await self._bill_imaging_order(order, facility_id, ordered_by)

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="imaging",
            stream_id=data.patient_id,
            event_type="ImagingOrderCreated",
            event_data={
                "order_id": str(order.id),
                "order_number": order_number,
                "modality": data.modality,
                "body_part": data.body_part,
                "study_description": data.study_description,
                "priority": data.priority,
            },
            version=1,
            created_by=ordered_by,
        )
        self.db.add(event)

        return order

    # ── Worklist ──────────────────────────────────────────────────────────

    async def get_worklist(
        self,
        facility_id: uuid.UUID,
        status: str | None = None,
        modality: str | None = None,
    ) -> list[ImagingWorklistItem]:
        """
        Get imaging worklist with patient info, priority-ordered.

        @param facility_id: Facility UUID
        @param status: Optional status filter
        @param modality: Optional modality filter
        @returns Priority-ordered worklist items
        """
        # Subquery: get result status/critical flag per order (eliminates N+1)
        result_sq = (
            select(
                ImagingResult.order_id,
                ImagingResult.status.label("result_status"),
                ImagingResult.is_critical,
            )
            .where(ImagingResult.is_deleted == False)  # noqa: E712
            .subquery()
        )

        query = (
            select(
                ImagingOrder,
                Patient.first_name,
                Patient.last_name,
                Patient.mrn,
                result_sq.c.result_status,
                result_sq.c.is_critical,
            )
            .join(Patient, ImagingOrder.patient_id == Patient.id)
            .outerjoin(
                result_sq,
                ImagingOrder.id == result_sq.c.order_id,
            )
            .where(
                ImagingOrder.facility_id == facility_id,
                ImagingOrder.is_deleted == False,  # noqa: E712
            )
        )

        if status:
            query = query.where(ImagingOrder.status == status)
        else:
            # Default: exclude cancelled
            query = query.where(ImagingOrder.status != "cancelled")

        if modality:
            query = query.where(ImagingOrder.modality == modality)

        # Priority ordering: stat > urgent > routine, then by created_at
        priority_order = case(
            (ImagingOrder.priority == "stat", 1),
            (ImagingOrder.priority == "urgent", 2),
            else_=3,
        )
        query = query.order_by(priority_order.asc(), ImagingOrder.created_at.asc())

        result = await self.db.execute(query)
        rows = result.all()

        items: list[ImagingWorklistItem] = []
        for order, first_name, last_name, mrn, result_status, is_critical in rows:
            patient_name = f"{first_name or ''} {last_name or ''}".strip() or None
            items.append(
                ImagingWorklistItem(
                    id=order.id,
                    order_number=order.order_number,
                    accession_number=order.accession_number,
                    encounter_id=order.encounter_id,
                    patient_id=order.patient_id,
                    patient_name=patient_name,
                    patient_mrn=mrn,
                    ordered_by=order.ordered_by,
                    modality=order.modality,
                    body_part=order.body_part,
                    laterality=order.laterality,
                    study_description=order.study_description,
                    priority=order.priority,
                    status=order.status,
                    contrast_required=order.contrast_required,
                    has_result=result_status is not None,
                    result_status=result_status,
                    is_critical=is_critical if is_critical is not None else False,
                    scheduled_at=order.scheduled_at,
                    room=order.room,
                    created_at=order.created_at,
                )
            )

        return items

    # ── Order Detail ──────────────────────────────────────────────────────

    async def get_order_detail(
        self,
        order_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> ImagingOrderDetail | None:
        """
        Get full imaging order with result and patient info.

        @param order_id: Imaging order UUID
        @param facility_id: Facility UUID
        @returns Order detail with result, or None
        """
        result = await self.db.execute(
            select(ImagingOrder, Patient.first_name, Patient.last_name, Patient.mrn)
            .join(Patient, ImagingOrder.patient_id == Patient.id)
            .where(
                ImagingOrder.id == order_id,
                ImagingOrder.facility_id == facility_id,
                ImagingOrder.is_deleted == False,  # noqa: E712
            )
        )
        row = result.first()
        if not row:
            return None

        order, first_name, last_name, mrn = row
        patient_name = f"{first_name or ''} {last_name or ''}".strip() or None

        # Get result if exists
        res_result = await self.db.execute(
            select(ImagingResult).where(
                ImagingResult.order_id == order_id,
                ImagingResult.is_deleted == False,  # noqa: E712
            )
        )
        imaging_result = res_result.scalar_one_or_none()

        return ImagingOrderDetail(
            order=ImagingOrderResponse.model_validate(order),
            result=ImagingResultResponse.model_validate(imaging_result) if imaging_result else None,
            patient_name=patient_name,
            patient_mrn=mrn,
        )

    # ── Schedule ──────────────────────────────────────────────────────────

    async def _bill_imaging_order(
        self,
        order: ImagingOrder,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> None:
        """
        Price the study and add it to the encounter's open invoice.

        The price comes from facility settings (see imaging_fee), never from
        the ordering clinician. A study priced at 0 is not billed.

        @param order: The created imaging order
        @param facility_id: Facility scope
        @param created_by: Ordering user
        """
        from app.services.imaging_fee import load_imaging_price_cents

        # One study, one charge: a retried create cannot bill the patient twice.
        existing = await ServiceBillingService(self.db).charge_for(
            facility_id, IMAGING_ORDER, order.id
        )
        if existing is not None:
            order.total_cost_cents = existing.total_cents
            return

        price = await load_imaging_price_cents(
            self.db,
            facility_id,
            modality=order.modality,
            study_description=order.study_description,
        )
        order.total_cost_cents = price
        await post_service_charge(
            self.db,
            facility_id=facility_id,
            encounter_id=order.encounter_id,
            patient_id=order.patient_id,
            item_type="procedure",
            description="Imaging: " + order.study_description,
            unit_price_cents=price,
            reference_type=IMAGING_ORDER,
            reference_id=order.id,
            created_by=created_by,
        )

    async def schedule_order(
        self,
        order_id: uuid.UUID,
        data: ImagingScheduleRequest,
        facility_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> ImagingOrder | None:
        """
        Schedule an imaging study for a specific date/time and room.

        @param order_id: Imaging order UUID
        @param data: Scheduling data
        @param facility_id: Facility UUID
        @param staff_id: Staff UUID performing action
        @returns Updated order, or None if not found
        """
        result = await self.db.execute(
            select(ImagingOrder).where(
                ImagingOrder.id == order_id,
                ImagingOrder.facility_id == facility_id,
                ImagingOrder.is_deleted == False,  # noqa: E712
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            return None

        order.scheduled_at = data.scheduled_at
        order.room = data.room
        order.status = "scheduled"
        order.updated_by = staff_id
        await self.db.flush()
        await self.db.refresh(order)
        return order

    # ── Perform Study ─────────────────────────────────────────────────────

    async def perform_study(
        self,
        order_id: uuid.UUID,
        data: ImagingPerformRequest,
        facility_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> ImagingOrder | None:
        """
        Mark an imaging study as performed by the tech.

        @param order_id: Imaging order UUID
        @param data: Performance data (accession number, notes)
        @param facility_id: Facility UUID
        @param staff_id: Staff UUID of performing tech
        @returns Updated order, or None if not found
        """
        result = await self.db.execute(
            select(ImagingOrder).where(
                ImagingOrder.id == order_id,
                ImagingOrder.facility_id == facility_id,
                ImagingOrder.is_deleted == False,  # noqa: E712
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            return None

        # The study is released only once the patient has paid for it.
        await ServiceBillingService(self.db).assert_service_paid(
            facility_id, IMAGING_ORDER, order.id, label="Imaging request"
        )

        order.status = "in_progress"
        order.performed_by = staff_id
        order.performed_at = datetime.now(UTC)
        if data.accession_number:
            order.accession_number = data.accession_number
        order.updated_by = staff_id
        await self.db.flush()
        await self.db.refresh(order)

        # Create blank result for radiologist to fill in
        imaging_result = ImagingResult(
            facility_id=facility_id,
            order_id=order.id,
            patient_id=order.patient_id,
            status="draft",
            created_by=staff_id,
            updated_by=staff_id,
        )
        self.db.add(imaging_result)

        event = EventBase(
            facility_id=facility_id,
            stream_type="imaging",
            stream_id=order.patient_id,
            event_type="ImagingStudyPerformed",
            event_data={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "modality": order.modality,
                "performed_by": str(staff_id),
            },
            version=1,
            created_by=staff_id,
        )
        self.db.add(event)

        return order

    # ── Report Entry ──────────────────────────────────────────────────────

    async def enter_report(
        self,
        result_id: uuid.UUID,
        data: ImagingResultCreate,
        facility_id: uuid.UUID,
        reported_by: uuid.UUID,
    ) -> ImagingResult | None:
        """
        Enter or update a radiology report (draft or preliminary).

        @param result_id: Imaging result UUID
        @param data: Report data (findings, impression, etc.)
        @param facility_id: Facility UUID
        @param reported_by: Radiologist UUID
        @returns Updated result, or None if not found
        """
        result = await self.db.execute(
            select(ImagingResult).where(
                ImagingResult.id == result_id,
                ImagingResult.facility_id == facility_id,
                ImagingResult.is_deleted == False,  # noqa: E712
            )
        )
        imaging_result = result.scalar_one_or_none()
        if not imaging_result:
            return None

        imaging_result.findings = data.findings
        imaging_result.impression = data.impression
        imaging_result.recommendations = data.recommendations
        imaging_result.technique = data.technique
        imaging_result.comparison = data.comparison
        imaging_result.urgency = data.urgency
        imaging_result.is_critical = data.is_critical
        imaging_result.notes = data.notes
        imaging_result.reported_by = reported_by
        imaging_result.reported_at = datetime.now(UTC)
        imaging_result.status = "preliminary"
        imaging_result.updated_by = reported_by

        await self.db.flush()
        await self.db.refresh(imaging_result)

        event = EventBase(
            facility_id=facility_id,
            stream_type="imaging",
            stream_id=imaging_result.patient_id,
            event_type="ImagingReportEntered",
            event_data={
                "result_id": str(imaging_result.id),
                "order_id": str(imaging_result.order_id),
                "urgency": data.urgency,
                "is_critical": data.is_critical,
            },
            version=1,
            created_by=reported_by,
        )
        self.db.add(event)

        return imaging_result

    # ── Verify Report ─────────────────────────────────────────────────────

    async def verify_report(
        self,
        result_id: uuid.UUID,
        data: ImagingResultVerify,
        facility_id: uuid.UUID,
        verified_by: uuid.UUID,
    ) -> ImagingResult | None:
        """
        Verify (finalise) a radiology report. Completes the order.

        @param result_id: Imaging result UUID
        @param data: Verification notes
        @param facility_id: Facility UUID
        @param verified_by: Verifying radiologist UUID
        @returns Verified result, or None if not found
        """
        result = await self.db.execute(
            select(ImagingResult).where(
                ImagingResult.id == result_id,
                ImagingResult.facility_id == facility_id,
                ImagingResult.is_deleted == False,  # noqa: E712
            )
        )
        imaging_result = result.scalar_one_or_none()
        if not imaging_result:
            return None

        imaging_result.status = "final"
        imaging_result.verified_by = verified_by
        imaging_result.verified_at = datetime.now(UTC)
        if data.notes:
            existing_notes = imaging_result.notes or ""
            imaging_result.notes = f"{existing_notes}\n[Verification] {data.notes}".strip()
        imaging_result.updated_by = verified_by

        # Mark order as completed
        order_result = await self.db.execute(
            select(ImagingOrder).where(ImagingOrder.id == imaging_result.order_id)
        )
        order = order_result.scalar_one_or_none()
        if order:
            order.status = "completed"
            order.updated_by = verified_by

        await self.db.flush()
        await self.db.refresh(imaging_result)

        event = EventBase(
            facility_id=facility_id,
            stream_type="imaging",
            stream_id=imaging_result.patient_id,
            event_type="ImagingReportVerified",
            event_data={
                "result_id": str(imaging_result.id),
                "order_id": str(imaging_result.order_id),
                "urgency": imaging_result.urgency,
                "is_critical": imaging_result.is_critical,
            },
            version=1,
            created_by=verified_by,
        )
        self.db.add(event)

        return imaging_result

    # ── Critical Finding Notification ─────────────────────────────────────

    async def record_critical_notification(
        self,
        result_id: uuid.UUID,
        notified_to: uuid.UUID,
        facility_id: uuid.UUID,
        notified_by: uuid.UUID,
    ) -> ImagingResult | None:
        """
        Record that a critical imaging finding was communicated to a clinician.

        @param result_id: Imaging result UUID
        @param notified_to: Clinician UUID who was notified
        @param facility_id: Facility UUID
        @param notified_by: Staff UUID who notified
        @returns Updated result, or None if not found
        """
        result = await self.db.execute(
            select(ImagingResult).where(
                ImagingResult.id == result_id,
                ImagingResult.facility_id == facility_id,
                ImagingResult.is_deleted == False,  # noqa: E712
            )
        )
        imaging_result = result.scalar_one_or_none()
        if not imaging_result:
            return None

        imaging_result.critical_notified = True
        imaging_result.critical_notified_to = notified_to
        imaging_result.critical_notified_at = datetime.now(UTC)
        imaging_result.updated_by = notified_by

        await self.db.flush()
        await self.db.refresh(imaging_result)

        event = EventBase(
            facility_id=facility_id,
            stream_type="imaging",
            stream_id=imaging_result.patient_id,
            event_type="CriticalImagingFindingNotified",
            event_data={
                "result_id": str(imaging_result.id),
                "order_id": str(imaging_result.order_id),
                "notified_to": str(notified_to),
            },
            version=1,
            created_by=notified_by,
        )
        self.db.add(event)

        return imaging_result

    # ── Summary ───────────────────────────────────────────────────────────

    async def get_summary(
        self, facility_id: uuid.UUID
    ) -> RadiologySummary:
        """
        Get radiology department dashboard summary.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        today = datetime.now(UTC).date()

        # Total orders today
        total_today = await self.db.execute(
            select(func.count(ImagingOrder.id)).where(
                ImagingOrder.facility_id == facility_id,
                ImagingOrder.is_deleted == False,  # noqa: E712
                func.date(ImagingOrder.created_at) == today,
            )
        )

        # Pending (ordered + scheduled)
        pending = await self.db.execute(
            select(func.count(ImagingOrder.id)).where(
                ImagingOrder.facility_id == facility_id,
                ImagingOrder.is_deleted == False,  # noqa: E712
                ImagingOrder.status.in_(["ordered", "scheduled"]),
            )
        )

        # In progress
        in_prog = await self.db.execute(
            select(func.count(ImagingOrder.id)).where(
                ImagingOrder.facility_id == facility_id,
                ImagingOrder.is_deleted == False,  # noqa: E712
                ImagingOrder.status == "in_progress",
            )
        )

        # Completed today
        completed = await self.db.execute(
            select(func.count(ImagingOrder.id)).where(
                ImagingOrder.facility_id == facility_id,
                ImagingOrder.is_deleted == False,  # noqa: E712
                ImagingOrder.status == "completed",
                func.date(ImagingOrder.updated_at) == today,
            )
        )

        # Pending reports (result exists but not final)
        pending_reports = await self.db.execute(
            select(func.count(ImagingResult.id)).where(
                ImagingResult.facility_id == facility_id,
                ImagingResult.is_deleted == False,  # noqa: E712
                ImagingResult.status.in_(["draft", "preliminary"]),
            )
        )

        # Critical findings not yet notified
        critical = await self.db.execute(
            select(func.count(ImagingResult.id)).where(
                ImagingResult.facility_id == facility_id,
                ImagingResult.is_deleted == False,  # noqa: E712
                ImagingResult.is_critical == True,  # noqa: E712
                ImagingResult.critical_notified == False,  # noqa: E712
            )
        )

        return RadiologySummary(
            total_orders_today=total_today.scalar() or 0,
            pending_orders=pending.scalar() or 0,
            in_progress=in_prog.scalar() or 0,
            completed_today=completed.scalar() or 0,
            pending_reports=pending_reports.scalar() or 0,
            critical_findings=critical.scalar() or 0,
        )
