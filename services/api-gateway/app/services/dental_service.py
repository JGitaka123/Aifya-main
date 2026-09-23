import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dental import DentalChart, DentalTreatmentPlan, DentalVisit
from app.models.patient import Patient
from app.models.staff import Staff
from app.schemas.dental import (
    DentalChartUpdate,
    DentalSummary,
    DentalTreatmentPlanCreate,
    DentalTreatmentPlanResponse,
    DentalVisitCreate,
    DentalVisitListItem,
)


class DentalService:
    """Service for dental module: charts, visits, and treatment plans."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Charts ───────────────────────────────────────────────────────────

    async def get_or_create_chart(
        self, patient_id: uuid.UUID, facility_id: uuid.UUID, created_by: uuid.UUID
    ) -> DentalChart:
        """
        Get or create a dental chart for a patient.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Dental chart
        """
        result = await self.db.execute(
            select(DentalChart).where(
                DentalChart.patient_id == patient_id,
                DentalChart.facility_id == facility_id,
                DentalChart.is_deleted == False,  # noqa: E712
            )
        )
        chart = result.scalar_one_or_none()
        if chart:
            return chart

        chart = DentalChart(
            facility_id=facility_id,
            patient_id=patient_id,
            teeth={},
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(chart)
        await self.db.flush()
        await self.db.refresh(chart)
        return chart

    async def update_chart(
        self,
        patient_id: uuid.UUID,
        data: DentalChartUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> DentalChart:
        """
        Update dental chart data.

        @param patient_id: Patient UUID
        @param data: Chart update data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated chart
        """
        chart = await self.get_or_create_chart(patient_id, facility_id, updated_by)
        chart.teeth = data.teeth
        if data.periodontal_status is not None:
            chart.periodontal_status = data.periodontal_status
        if data.occlusion_notes is not None:
            chart.occlusion_notes = data.occlusion_notes
        if data.last_xray_date is not None:
            chart.last_xray_date = data.last_xray_date
        if data.notes is not None:
            chart.notes = data.notes
        chart.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(chart)
        return chart

    # ── Visits ───────────────────────────────────────────────────────────

    async def create_visit(
        self, data: DentalVisitCreate, facility_id: uuid.UUID, created_by: uuid.UUID
    ) -> DentalVisit:
        """
        Create a dental visit.

        @param data: Visit data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created visit
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count = await self.db.execute(
            select(func.count(DentalVisit.id)).where(
                DentalVisit.facility_id == facility_id,
                DentalVisit.visit_number.like(f"DV-{date_part}-%"),
                DentalVisit.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count.scalar() or 0) + 1
        visit_number = f"DV-{date_part}-{seq:04d}"

        visit = DentalVisit(
            facility_id=facility_id,
            visit_number=visit_number,
            patient_id=data.patient_id,
            encounter_id=data.encounter_id,
            dentist_id=data.dentist_id,
            visit_date=data.visit_date or now,
            chief_complaint=data.chief_complaint,
            examination_findings=data.examination_findings,
            procedures=data.procedures,
            diagnosis=data.diagnosis,
            status="scheduled",
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(visit)
        await self.db.flush()
        await self.db.refresh(visit)
        return visit

    async def get_visits(
        self, facility_id: uuid.UUID, patient_id: uuid.UUID | None = None
    ) -> list[DentalVisitListItem]:
        """
        Get dental visits with patient and dentist names.

        @param facility_id: Facility UUID
        @param patient_id: Optional patient filter
        @returns List of visits
        """
        DentistStaff = Staff.__table__.alias("dentist_staff")  # noqa: N806 — SQLAlchemy alias naming

        query = (
            select(
                DentalVisit,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
                DentistStaff.c.first_name.label("d_first"),
                DentistStaff.c.last_name.label("d_last"),
            )
            .join(Patient, DentalVisit.patient_id == Patient.id)
            .outerjoin(DentistStaff, DentalVisit.dentist_id == DentistStaff.c.id)
            .where(
                DentalVisit.facility_id == facility_id,
                DentalVisit.is_deleted == False,  # noqa: E712
            )
        )
        if patient_id:
            query = query.where(DentalVisit.patient_id == patient_id)
        query = query.order_by(DentalVisit.visit_date.desc())

        result = await self.db.execute(query)
        return [
            DentalVisitListItem(
                id=v.id,
                visit_number=v.visit_number,
                patient_id=v.patient_id,
                patient_name=f"{pf or ''} {pl or ''}".strip() or None,
                dentist_name=f"{df or ''} {dl or ''}".strip() or None,
                visit_date=v.visit_date,
                chief_complaint=v.chief_complaint,
                status=v.status,
            )
            for v, pf, pl, df, dl in result.all()
        ]

    async def get_visit(self, visit_id: uuid.UUID, facility_id: uuid.UUID) -> DentalVisit | None:
        """
        Get a single dental visit.

        @param visit_id: Visit UUID
        @param facility_id: Facility UUID
        @returns Dental visit or None
        """
        result = await self.db.execute(
            select(DentalVisit).where(
                DentalVisit.id == visit_id,
                DentalVisit.facility_id == facility_id,
                DentalVisit.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    # ── Treatment Plans ──────────────────────────────────────────────────

    async def create_treatment_plan(
        self, data: DentalTreatmentPlanCreate, facility_id: uuid.UUID, created_by: uuid.UUID
    ) -> DentalTreatmentPlan:
        """
        Create a dental treatment plan.

        @param data: Treatment plan data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created plan
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count = await self.db.execute(
            select(func.count(DentalTreatmentPlan.id)).where(
                DentalTreatmentPlan.facility_id == facility_id,
                DentalTreatmentPlan.plan_number.like(f"DP-{date_part}-%"),
                DentalTreatmentPlan.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count.scalar() or 0) + 1

        plan = DentalTreatmentPlan(
            facility_id=facility_id,
            plan_number=f"DP-{date_part}-{seq:04d}",
            patient_id=data.patient_id,
            dentist_id=data.dentist_id,
            diagnosis=data.diagnosis,
            plan_items=data.plan_items,
            total_estimated_cost=data.total_estimated_cost,
            status="draft",
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(plan)
        await self.db.flush()
        await self.db.refresh(plan)
        return plan

    async def get_treatment_plans(
        self, facility_id: uuid.UUID, patient_id: uuid.UUID | None = None
    ) -> list[DentalTreatmentPlanResponse]:
        """
        Get treatment plans with patient and dentist names.

        @param facility_id: Facility UUID
        @param patient_id: Optional patient filter
        @returns List of treatment plans
        """
        PlanDentist = Staff.__table__.alias("plan_dentist_staff")  # noqa: N806

        query = (
            select(
                DentalTreatmentPlan,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
                Patient.mrn.label("p_mrn"),
                PlanDentist.c.first_name.label("d_first"),
                PlanDentist.c.last_name.label("d_last"),
            )
            .join(Patient, DentalTreatmentPlan.patient_id == Patient.id)
            .outerjoin(
                PlanDentist, DentalTreatmentPlan.dentist_id == PlanDentist.c.id
            )
            .where(
                DentalTreatmentPlan.facility_id == facility_id,
                DentalTreatmentPlan.is_deleted == False,  # noqa: E712
            )
        )
        if patient_id:
            query = query.where(DentalTreatmentPlan.patient_id == patient_id)
        query = query.order_by(DentalTreatmentPlan.created_at.desc())

        result = await self.db.execute(query)
        return [
            DentalTreatmentPlanResponse(
                id=p.id,
                plan_number=p.plan_number,
                patient_id=p.patient_id,
                patient_name=f"{p_first or ''} {p_last or ''}".strip() or None,
                patient_mrn=mrn,
                dentist_id=p.dentist_id,
                dentist_name=f"{d_first or ''} {d_last or ''}".strip() or None,
                diagnosis=p.diagnosis,
                plan_items=p.plan_items or [],
                total_estimated_cost=p.total_estimated_cost,
                status=p.status,
                notes=p.notes,
                created_at=p.created_at,
            )
            for p, p_first, p_last, mrn, d_first, d_last in result.all()
        ]

    async def update_treatment_plan_status(
        self,
        plan_id: uuid.UUID,
        new_status: str,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> DentalTreatmentPlan | None:
        """
        Move a treatment plan to a new lifecycle status.

        @param plan_id: Treatment plan UUID
        @param new_status: Target status value
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated plan, or None when it does not exist
        """
        result = await self.db.execute(
            select(DentalTreatmentPlan).where(
                DentalTreatmentPlan.id == plan_id,
                DentalTreatmentPlan.facility_id == facility_id,
                DentalTreatmentPlan.is_deleted == False,  # noqa: E712
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            return None

        plan.status = new_status
        plan.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(plan)
        return plan

    # ── Summary ──────────────────────────────────────────────────────────

    async def get_summary(self, facility_id: uuid.UUID) -> DentalSummary:
        """
        Get dental summary stats.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        today = date.today()

        patients = await self.db.execute(
            select(func.count(func.distinct(DentalVisit.patient_id))).where(
                DentalVisit.facility_id == facility_id,
                DentalVisit.is_deleted == False,  # noqa: E712
            )
        )
        today_visits = await self.db.execute(
            select(func.count(DentalVisit.id)).where(
                DentalVisit.facility_id == facility_id,
                DentalVisit.is_deleted == False,  # noqa: E712
                func.date(DentalVisit.visit_date) == today,
            )
        )
        pending = await self.db.execute(
            select(func.count(DentalTreatmentPlan.id)).where(
                DentalTreatmentPlan.facility_id == facility_id,
                DentalTreatmentPlan.is_deleted == False,  # noqa: E712
                DentalTreatmentPlan.status.in_(["draft", "approved", "in_progress"]),
            )
        )
        completed = await self.db.execute(
            select(func.count(DentalVisit.id)).where(
                DentalVisit.facility_id == facility_id,
                DentalVisit.is_deleted == False,  # noqa: E712
                func.date(DentalVisit.visit_date) == today,
                DentalVisit.status == "completed",
            )
        )

        return DentalSummary(
            total_patients=patients.scalar() or 0,
            today_visits=today_visits.scalar() or 0,
            pending_treatments=pending.scalar() or 0,
            completed_today=completed.scalar() or 0,
        )
