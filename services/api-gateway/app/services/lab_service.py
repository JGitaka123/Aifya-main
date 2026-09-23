import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.lab import LabOrder, LabResult
from app.models.patient import Patient
from app.schemas.lab import (
    LabOrderCreate,
    LabResultEntry,
    LabWorklistItem,
)
from app.services.service_billing import LAB_ORDER, ServiceBillingService

_logger = logging.getLogger(__name__)


# Critical value thresholds for common lab tests
CRITICAL_LAB_VALUES: dict[str, dict[str, float | str]] = {
    "WBC": {"low": 2.0, "high": 30.0, "unit": "x10^9/L"},
    "HGB": {"low": 5.0, "high": 20.0, "unit": "g/dL"},
    "PLT": {"low": 20.0, "high": 1000.0, "unit": "x10^9/L"},
    "K": {"low": 2.5, "high": 6.5, "unit": "mmol/L"},
    "NA": {"low": 120.0, "high": 160.0, "unit": "mmol/L"},
    "GLU": {"low": 2.2, "high": 27.8, "unit": "mmol/L"},
    "CREAT": {"low": 0.0, "high": 10.0, "unit": "mg/dL"},
    "INR": {"low": 0.0, "high": 5.0, "unit": "ratio"},
    "TROP": {"low": 0.0, "high": 0.04, "unit": "ng/mL"},
    "PH": {"low": 7.2, "high": 7.6, "unit": ""},
    "LACTATE": {"low": 0.0, "high": 4.0, "unit": "mmol/L"},
    "CD4": {"low": 0.0, "high": 99999.0, "unit": "cells/uL"},
}


class LabService:
    """
    Service for lab workflow: orders, specimen collection, result entry,
    verification, and critical value alerting.
    Critical lab values MUST trigger immediate alert (CLAUDE.md: Clinical Safety).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Order Creation ────────────────────────────────────────────────────

    async def create_order(
        self,
        data: LabOrderCreate,
        facility_id: uuid.UUID,
        ordered_by: uuid.UUID,
    ) -> LabOrder:
        """
        Create a lab order with individual test results (pending).

        @param data: Lab order data with tests
        @param facility_id: Facility UUID
        @param ordered_by: Doctor's staff UUID
        @returns Created lab order
        """
        order_number = await self._next_order_number(facility_id)

        order = LabOrder(
            facility_id=facility_id,
            encounter_id=data.encounter_id,
            patient_id=data.patient_id,
            ordered_by=ordered_by,
            order_number=order_number,
            priority=data.priority,
            specimen_type=data.specimen_type,
            clinical_info=data.clinical_info,
            fasting=data.fasting,
            total_cost_cents=data.total_cost_cents,
            created_by=ordered_by,
            updated_by=ordered_by,
        )

        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)

        for test in data.tests:
            result = LabResult(
                facility_id=facility_id,
                order_id=order.id,
                patient_id=data.patient_id,
                test_code=test.test_code,
                test_name=test.test_name,
                loinc_code=test.loinc_code,
                panel_name=test.panel_name,
                status="pending",
                created_by=ordered_by,
                updated_by=ordered_by,
            )
            self.db.add(result)

        event = EventBase(
            facility_id=facility_id,
            stream_type="lab_order",
            stream_id=data.patient_id,
            event_type="LabOrderCreated",
            event_data={
                "order_number": order_number,
                "priority": data.priority,
                "tests": [t.test_name for t in data.tests],
                "test_count": len(data.tests),
            },
            version=1,
            created_by=ordered_by,
        )
        self.db.add(event)

        # D2: bill the ordered tests to the encounter invoice so the charge
        # reaches the patient (revenue no longer leaks). The GL posts when the
        # invoice is finalized, keeping AR == outstanding (D3 invariant).
        await self._bill_lab_order(order, data, facility_id, ordered_by)

        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def _bill_lab_order(
        self,
        order: LabOrder,
        data: LabOrderCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> None:
        """
        Price the ordered tests from the catalog and add them as line items on
        the encounter's open invoice (creating a draft invoice if needed).

        Prices are taken from the managed catalog (D6), not the request, so
        clinicians cannot set arbitrary prices. Uncatalogued tests are billed
        at 0 and flagged, never silently dropped.

        @param order: The created lab order
        @param data: The order request (test list)
        @param facility_id: Facility scope
        @param created_by: Ordering user
        """
        from app.models.billing import Invoice, InvoiceItem
        from app.services.billing_service import BillingService
        from app.services.lab_catalog import get_catalog_by_codes

        codes = [t.test_code for t in data.tests]
        catalog = await get_catalog_by_codes(self.db, facility_id, codes)

        priced: list[tuple[str, int, bool]] = []
        total = 0
        for test in data.tests:
            row = catalog.get(test.test_code)
            price = row.price_cents if row else 0
            name = row.test_name if row else test.test_name
            total += price
            priced.append((name, price, row is None))

        order.total_cost_cents = total
        if total <= 0:
            return  # nothing billable (all uncatalogued / free tests)

        invoice: Invoice | None = None
        if order.encounter_id:
            invoice = (
                await self.db.execute(
                    select(Invoice).where(
                        Invoice.encounter_id == order.encounter_id,
                        Invoice.facility_id == facility_id,
                        Invoice.status == "draft",
                        Invoice.is_deleted == False,  # noqa: E712
                    )
                )
            ).scalars().first()

        if invoice is None:
            inv_num = await BillingService(self.db)._next_invoice_number(facility_id)
            invoice = Invoice(
                facility_id=facility_id,
                encounter_id=order.encounter_id,
                patient_id=order.patient_id,
                invoice_number=inv_num,
                status="draft",
                subtotal_cents=0,
                total_cents=0,
                balance_cents=0,
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(invoice)
            await self.db.flush()

        for name, price, uncatalogued in priced:
            self.db.add(
                InvoiceItem(
                    facility_id=facility_id,
                    invoice_id=invoice.id,
                    item_type="lab",
                    description=f"Lab: {name}" + (" [uncatalogued]" if uncatalogued else ""),
                    quantity=1,
                    unit_price_cents=price,
                    total_cents=price,
                    discount_cents=0,
                    reference_id=order.id,
                    reference_type="lab_order",
                    created_by=created_by,
                    updated_by=created_by,
                )
            )
        await self.db.flush()

        # Recompute invoice totals from all its line items.
        items_total = (
            await self.db.execute(
                select(func.coalesce(func.sum(InvoiceItem.total_cents), 0)).where(
                    InvoiceItem.invoice_id == invoice.id,
                    InvoiceItem.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one()
        invoice.subtotal_cents = int(items_total)
        invoice.total_cents = int(items_total)
        # Draft invoices are unpaid, so balance tracks the total.
        invoice.balance_cents = int(items_total)
        invoice.updated_by = created_by
        await self.db.flush()

    # ── Worklist ──────────────────────────────────────────────────────────

    async def get_worklist(
        self,
        facility_id: uuid.UUID,
        status_filter: str | None = None,
    ) -> tuple[list[LabWorklistItem], int]:
        """
        Get the lab worklist — orders with patient info and result counts.
        Uses a LEFT JOIN subquery for result counts to avoid N+1 queries.
        Ordered by priority (stat > urgent > routine) then creation time.

        @param facility_id: Facility UUID
        @param status_filter: Optional status filter; pass "all" for every status
        @returns Tuple of (worklist items, total)
        """
        # Subquery: result counts per order
        result_counts_sq = (
            select(
                LabResult.order_id,
                func.count(LabResult.id).label("total"),
                func.count(
                    case((LabResult.status == "pending", LabResult.id))
                ).label("pending"),
                func.count(
                    case((LabResult.is_critical == True, LabResult.id))  # noqa: E712
                ).label("critical"),
            )
            .where(LabResult.is_deleted == False)  # noqa: E712
            .group_by(LabResult.order_id)
            .subquery()
        )

        stmt = (
            select(
                LabOrder,
                Patient,
                func.coalesce(result_counts_sq.c.total, 0).label("test_count"),
                func.coalesce(result_counts_sq.c.pending, 0).label("pending_count"),
                func.coalesce(result_counts_sq.c.critical, 0).label("critical_count"),
            )
            .join(Patient, LabOrder.patient_id == Patient.id)
            .outerjoin(result_counts_sq, LabOrder.id == result_counts_sq.c.order_id)
            .where(
                LabOrder.facility_id == facility_id,
                LabOrder.is_deleted == False,  # noqa: E712
            )
        )

        # An explicit status narrows to that status; "all" returns every status so
        # orders that have already been resulted never look like they vanished.
        if status_filter and status_filter != "all":
            stmt = stmt.where(LabOrder.status == status_filter)
        elif not status_filter:
            stmt = stmt.where(
                LabOrder.status.in_(["ordered", "collected", "processing"])
            )

        priority_order = case(
            (LabOrder.priority == "stat", 3),
            (LabOrder.priority == "urgent", 2),
            else_=1,
        )
        stmt = stmt.order_by(priority_order.desc(), LabOrder.created_at.asc())

        result = await self.db.execute(stmt)
        rows = result.all()

        items: list[LabWorklistItem] = []
        for order, patient, test_count, pending_count, critical_count in rows:
            items.append(
                LabWorklistItem(
                    id=order.id,
                    order_number=order.order_number,
                    encounter_id=order.encounter_id,
                    patient_id=order.patient_id,
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    patient_mrn=patient.mrn,
                    ordered_by=order.ordered_by,
                    priority=order.priority,
                    status=order.status,
                    specimen_type=order.specimen_type,
                    clinical_info=order.clinical_info,
                    fasting=order.fasting,
                    test_count=test_count,
                    pending_count=pending_count,
                    critical_count=critical_count,
                    created_at=order.created_at,
                )
            )

        return items, len(items)

    # ── Order Detail ──────────────────────────────────────────────────────

    async def get_order_detail(
        self, order_id: uuid.UUID, facility_id: uuid.UUID
    ) -> tuple[LabOrder | None, list[LabResult], str | None, str | None]:
        """
        Get a lab order with all results and patient info.

        @param order_id: LabOrder UUID
        @param facility_id: Facility UUID
        @returns Tuple of (order, results, patient_name, patient_mrn)
        """
        order_result = await self.db.execute(
            select(LabOrder, Patient)
            .join(Patient, LabOrder.patient_id == Patient.id)
            .where(
                LabOrder.id == order_id,
                LabOrder.facility_id == facility_id,
                LabOrder.is_deleted == False,  # noqa: E712
            )
        )
        row = order_result.first()
        if not row:
            return None, [], None, None

        order, patient = row

        results_result = await self.db.execute(
            select(LabResult)
            .where(
                LabResult.order_id == order_id,
                LabResult.facility_id == facility_id,
                LabResult.is_deleted == False,  # noqa: E712
            )
            .order_by(LabResult.created_at.asc())
        )
        results = list(results_result.scalars().all())

        patient_name = f"{patient.first_name} {patient.last_name}"
        return order, results, patient_name, patient.mrn

    # ── Encounter Orders ──────────────────────────────────────────────────

    async def get_encounter_orders(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[LabOrder]:
        """
        Get all lab orders for an encounter.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns List of lab orders
        """
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(LabOrder)
            .options(selectinload(LabOrder.results))
            .where(
                LabOrder.encounter_id == encounter_id,
                LabOrder.facility_id == facility_id,
                LabOrder.is_deleted == False,  # noqa: E712
            )
            .order_by(LabOrder.created_at.desc())
        )
        return list(result.scalars().all())

    # ── Specimen Collection ───────────────────────────────────────────────

    async def collect_specimen(
        self,
        order_id: uuid.UUID,
        facility_id: uuid.UUID,
        collected_by: uuid.UUID,
        specimen_id: str | None = None,
    ) -> LabOrder | None:
        """
        Record specimen collection for a lab order.

        @param order_id: LabOrder UUID
        @param facility_id: Facility UUID
        @param collected_by: Staff UUID
        @param specimen_id: Optional barcode / accession number
        @returns Updated order or None
        """
        result = await self.db.execute(
            select(LabOrder).where(
                LabOrder.id == order_id,
                LabOrder.facility_id == facility_id,
                LabOrder.is_deleted == False,  # noqa: E712
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            return None

        # The lab releases a request only once the patient has paid for it.
        await ServiceBillingService(self.db).assert_service_paid(
            facility_id, LAB_ORDER, order.id, label="Lab request"
        )

        order.status = "collected"
        order.specimen_collected_at = datetime.now(UTC)
        order.specimen_collected_by = collected_by
        if specimen_id:
            order.specimen_id = specimen_id
        order.updated_by = collected_by

        await self.db.flush()
        await self.db.refresh(order)

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="lab_order",
            stream_id=order.patient_id,
            event_type="SpecimenCollected",
            event_data={
                "order_number": order.order_number,
                "specimen_id": specimen_id,
            },
            version=1,
            created_by=collected_by,
        )
        self.db.add(event)

        return order

    # ── Result Entry ──────────────────────────────────────────────────────

    async def enter_result(
        self,
        result_id: uuid.UUID,
        data: LabResultEntry,
        facility_id: uuid.UUID,
        performed_by: uuid.UUID,
    ) -> LabResult | None:
        """
        Enter a lab result. Auto-detects critical values.
        Critical lab values MUST trigger immediate alert (CLAUDE.md: Clinical Safety).

        @param result_id: LabResult UUID
        @param data: Result entry data
        @param facility_id: Facility UUID
        @param performed_by: Lab tech staff UUID
        @returns Updated result or None
        """
        result = await self.db.execute(
            select(LabResult).where(
                LabResult.id == result_id,
                LabResult.facility_id == facility_id,
                LabResult.is_deleted == False,  # noqa: E712
            )
        )
        lab_result = result.scalar_one_or_none()
        if not lab_result:
            return None

        # Update result fields
        lab_result.result_value = data.result_value
        lab_result.result_numeric = data.result_numeric
        lab_result.result_unit = data.result_unit
        lab_result.reference_range = data.reference_range
        lab_result.notes = data.notes
        lab_result.method = data.method
        lab_result.performed_by = performed_by
        lab_result.resulted_at = datetime.now(UTC)
        lab_result.status = "preliminary"
        lab_result.updated_by = performed_by

        # Auto-detect abnormal and critical
        lab_result.is_abnormal = data.is_abnormal
        if data.interpretation:
            lab_result.interpretation = data.interpretation
            if data.interpretation == "critical":
                lab_result.is_critical = True
                lab_result.is_abnormal = True

        # Auto-check critical thresholds
        if data.result_numeric is not None:
            is_critical = self._check_critical_value(
                lab_result.test_code, data.result_numeric
            )
            if is_critical:
                lab_result.is_critical = True
                lab_result.is_abnormal = True
                lab_result.interpretation = "critical"

        # Update parent order status to processing
        order_result = await self.db.execute(
            select(LabOrder).where(LabOrder.id == lab_result.order_id)
        )
        order = order_result.scalar_one_or_none()
        if order and order.status in ("ordered", "collected"):
            order.status = "processing"

        await self.db.flush()
        await self.db.refresh(lab_result)

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="lab_result",
            stream_id=lab_result.patient_id,
            event_type="LabResultEntered",
            event_data={
                "test_code": lab_result.test_code,
                "test_name": lab_result.test_name,
                "result_value": data.result_value,
                "is_critical": lab_result.is_critical,
                "interpretation": lab_result.interpretation,
            },
            version=1,
            created_by=performed_by,
        )
        self.db.add(event)

        # Critical values MUST trigger an immediate alert (CLAUDE.md).
        if lab_result.is_critical and order is not None:
            await self._alert_critical_result(
                lab_result=lab_result, order=order, entered_by=performed_by
            )

        return lab_result

    async def _alert_critical_result(
        self,
        lab_result: LabResult,
        order: LabOrder,
        entered_by: uuid.UUID,
    ) -> None:
        """
        Push an immediate critical-value alert: append a
        CriticalLabResultDetected event and SMS the ordering clinician.
        Alert failures are logged but never block result entry.

        @param lab_result: The critical result
        @param order: Parent lab order (carries ordered_by)
        @param entered_by: Lab tech who entered the result
        """
        event = EventBase(
            facility_id=lab_result.facility_id,
            stream_type="lab_result",
            stream_id=lab_result.patient_id,
            event_type="CriticalLabResultDetected",
            event_data={
                "result_id": str(lab_result.id),
                "order_id": str(order.id),
                "order_number": order.order_number,
                "test_code": lab_result.test_code,
                "test_name": lab_result.test_name,
                "result_value": lab_result.result_value,
                "ordered_by": str(order.ordered_by),
            },
            version=1,
            created_by=entered_by,
        )
        self.db.add(event)
        # Persist the in-transaction alert before attempting an external
        # notification so every critical result has a durable alert record.
        await self.db.flush()

        try:
            from app.models.staff import Staff
            from app.services.comms.service import normalize_kenyan_phone
            from app.services.comms.sms_provider import get_sms_provider

            # ordered_by carries the clinician's Keycloak user id; the
            # staff profile holds their phone number.
            staff_result = await self.db.execute(
                select(Staff.phone).where(
                    Staff.keycloak_user_id == order.ordered_by,
                    Staff.facility_id == lab_result.facility_id,
                    Staff.is_deleted == False,  # noqa: E712
                )
            )
            phone = staff_result.scalar_one_or_none()
            if not phone:
                _logger.warning(
                    "lab.critical_alert.no_clinician_phone order=%s", order.id
                )
                return

            # No patient identifiers in the SMS — order number only (DPA).
            message = (
                f"CRITICAL LAB RESULT: {lab_result.test_name} for order "
                f"{order.order_number}. Review immediately in Aifya."
            )
            sent = await get_sms_provider().send_sms(
                normalize_kenyan_phone(phone), message
            )
            if not sent:
                _logger.warning(
                    "lab.critical_alert.sms_failed order=%s", order.id
                )
        except Exception as exc:
            _logger.warning(
                "lab.critical_alert.failed order=%s error=%s", order.id, exc
            )

    # ── Verification ──────────────────────────────────────────────────────

    async def verify_result(
        self,
        result_id: uuid.UUID,
        facility_id: uuid.UUID,
        verified_by: uuid.UUID,
        notes: str | None = None,
    ) -> LabResult | None:
        """
        Verify (approve) a lab result. Changes status from preliminary to final.

        @param result_id: LabResult UUID
        @param facility_id: Facility UUID
        @param verified_by: Senior lab tech / pathologist staff UUID
        @param notes: Optional verification notes
        @returns Verified result or None
        """
        result = await self.db.execute(
            select(LabResult).where(
                LabResult.id == result_id,
                LabResult.facility_id == facility_id,
                LabResult.is_deleted == False,  # noqa: E712
            )
        )
        lab_result = result.scalar_one_or_none()
        if not lab_result:
            return None
        if lab_result.status not in ("preliminary",):
            raise ValueError(f"Cannot verify result with status: {lab_result.status}")

        lab_result.status = "final"
        lab_result.verified_by = verified_by
        lab_result.verified_at = datetime.now(UTC)
        lab_result.updated_by = verified_by
        if notes:
            lab_result.notes = (lab_result.notes or "") + f"\nVerification: {notes}"

        # Check if all results in order are final — complete the order
        order_result = await self.db.execute(
            select(LabResult).where(
                LabResult.order_id == lab_result.order_id,
                LabResult.facility_id == facility_id,
                LabResult.is_deleted == False,  # noqa: E712
            )
        )
        all_results = list(order_result.scalars().all())
        all_final = all(r.status == "final" for r in all_results)

        if all_final:
            order_q = await self.db.execute(
                select(LabOrder).where(LabOrder.id == lab_result.order_id)
            )
            order = order_q.scalar_one_or_none()
            if order:
                order.status = "completed"

        await self.db.flush()
        await self.db.refresh(lab_result)

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="lab_result",
            stream_id=lab_result.patient_id,
            event_type="LabResultVerified",
            event_data={
                "test_code": lab_result.test_code,
                "test_name": lab_result.test_name,
                "result_value": lab_result.result_value,
                "is_critical": lab_result.is_critical,
                "all_verified": all_final,
            },
            version=1,
            created_by=verified_by,
        )
        self.db.add(event)

        return lab_result

    # ── Critical Notification ─────────────────────────────────────────────

    async def record_critical_notification(
        self,
        result_id: uuid.UUID,
        facility_id: uuid.UUID,
        notified_by: uuid.UUID,
        notified_to: uuid.UUID,
    ) -> LabResult | None:
        """
        Record that a critical value was communicated to a clinician.

        @param result_id: LabResult UUID
        @param facility_id: Facility UUID
        @param notified_by: Lab tech who made the notification
        @param notified_to: Clinician who was notified
        @returns Updated result or None
        """
        result = await self.db.execute(
            select(LabResult).where(
                LabResult.id == result_id,
                LabResult.facility_id == facility_id,
                LabResult.is_deleted == False,  # noqa: E712
            )
        )
        lab_result = result.scalar_one_or_none()
        if not lab_result:
            return None

        lab_result.critical_notified = True
        lab_result.critical_notified_to = notified_to
        lab_result.critical_notified_at = datetime.now(UTC)
        lab_result.updated_by = notified_by

        await self.db.flush()
        await self.db.refresh(lab_result)
        return lab_result

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _check_critical_value(test_code: str, numeric_value: float) -> bool:
        """
        Check if a numeric result exceeds critical thresholds.

        @param test_code: Test code (uppercase matched against CRITICAL_LAB_VALUES)
        @param numeric_value: The numeric result
        @returns True if critical
        """
        thresholds = CRITICAL_LAB_VALUES.get(test_code.upper())
        if not thresholds:
            return False
        low = float(thresholds["low"])
        high = float(thresholds["high"])
        return numeric_value < low or numeric_value > high

    async def _next_order_number(self, facility_id: uuid.UUID) -> str:
        """Generate the next lab order number (LAB-YYYYMMDD-XXXX)."""
        today = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f"LAB-{today}-"

        result = await self.db.execute(
            select(func.count())
            .select_from(LabOrder)
            .where(
                LabOrder.facility_id == facility_id,
                LabOrder.order_number.like(f"{prefix}%"),
            )
        )
        count = result.scalar_one()
        return f"{prefix}{count + 1:04d}"
