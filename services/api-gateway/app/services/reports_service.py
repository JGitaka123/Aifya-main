import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.billing import Invoice, Payment
from app.models.diagnosis import Diagnosis
from app.models.encounter import Encounter
from app.models.ipd import Admission, Bed
from app.models.lab import LabOrder, LabResult
from app.models.mch import ANCProfile, DeliveryRecord, Immunization
from app.models.patient import Patient
from app.models.pharmacy import Dispensing, PharmacyItem
from app.models.radiology import ImagingOrder
from app.models.report import GeneratedReport, ReportTemplate
from app.schemas.report import (
    DashboardTrends,
    DepartmentStat,
    FacilityDashboard,
    GeneratedReportListItem,
    ReportGenerateRequest,
    ReportsSummary,
    ReportTemplateCreate,
    ReportTemplateListItem,
    TopDiagnosis,
)


class ReportsService:
    """
    Service for reports & analytics: facility dashboard, MOH reports,
    department analytics, trend data, and report generation.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Report Templates ─────────────────────────────────────────────────

    async def create_template(
        self,
        data: ReportTemplateCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> ReportTemplate:
        """
        Create a report template.

        @param data: Template creation data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created template
        """
        template = ReportTemplate(
            facility_id=facility_id,
            name=data.name,
            code=data.code,
            description=data.description,
            category=data.category,
            department=data.department,
            report_type=data.report_type,
            parameters_schema=data.parameters_schema,
            query_config=data.query_config,
            columns_config=data.columns_config,
            is_scheduled=data.is_scheduled,
            schedule_cron=data.schedule_cron,
            moh_form_number=data.moh_form_number,
            reporting_period=data.reporting_period,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def get_templates(
        self,
        facility_id: uuid.UUID,
        category: str | None = None,
        department: str | None = None,
    ) -> list[ReportTemplateListItem]:
        """
        Get report templates with optional filters.

        @param facility_id: Facility UUID
        @param category: Optional category filter
        @param department: Optional department filter
        @returns List of templates
        """
        query = select(ReportTemplate).where(
            ReportTemplate.facility_id == facility_id,
            ReportTemplate.is_deleted == False,  # noqa: E712
            ReportTemplate.is_active == True,  # noqa: E712
        )
        if category:
            query = query.where(ReportTemplate.category == category)
        if department:
            query = query.where(ReportTemplate.department == department)

        query = query.order_by(ReportTemplate.category.asc(), ReportTemplate.name.asc())
        result = await self.db.execute(query)
        templates = result.scalars().all()

        return [ReportTemplateListItem.model_validate(t) for t in templates]

    async def get_template(
        self,
        template_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> ReportTemplate | None:
        """
        Get a single report template.

        @param template_id: Template UUID
        @param facility_id: Facility UUID
        @returns Template or None
        """
        result = await self.db.execute(
            select(ReportTemplate).where(
                ReportTemplate.id == template_id,
                ReportTemplate.facility_id == facility_id,
                ReportTemplate.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    # ── Report Generation ────────────────────────────────────────────────

    async def generate_report(
        self,
        data: ReportGenerateRequest,
        facility_id: uuid.UUID,
        generated_by: uuid.UUID,
    ) -> GeneratedReport:
        """
        Generate a report from a template.

        @param data: Generation request
        @param facility_id: Facility UUID
        @param generated_by: Staff UUID
        @returns Generated report
        """
        template = await self.get_template(data.template_id, facility_id)
        if not template:
            raise ValueError("Report template not found")

        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")

        count_result = await self.db.execute(
            select(func.count(GeneratedReport.id)).where(
                GeneratedReport.facility_id == facility_id,
                GeneratedReport.report_number.like(f"RPT-{date_part}-%"),
            )
        )
        seq = (count_result.scalar() or 0) + 1
        report_number = f"RPT-{date_part}-{seq:04d}"

        # Generate report data based on template code
        result_data, summary_data, row_count = await self._execute_report(
            template=template,
            facility_id=facility_id,
            date_from=data.date_from,
            date_to=data.date_to,
            parameters=data.parameters,
        )

        report = GeneratedReport(
            facility_id=facility_id,
            template_id=data.template_id,
            title=f"{template.name} ({data.date_from} to {data.date_to})",
            report_number=report_number,
            parameters=data.parameters,
            date_from=data.date_from,
            date_to=data.date_to,
            result_data=result_data,
            summary_data=summary_data,
            row_count=row_count,
            status="completed",
            format=data.format,
            generated_by=generated_by,
            created_by=generated_by,
            updated_by=generated_by,
        )
        self.db.add(report)
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def _execute_report(
        self,
        template: ReportTemplate,
        facility_id: uuid.UUID,
        date_from: date,
        date_to: date,
        parameters: dict | None = None,
    ) -> tuple[dict, dict, int]:
        """
        Execute the report query based on template code.

        @param template: Report template
        @param facility_id: Facility UUID
        @param date_from: Start date
        @param date_to: End date
        @param parameters: Optional parameters
        @returns Tuple of (result_data, summary_data, row_count)
        """
        code = template.code.upper()

        if code == "OPD_DAILY":
            return await self._report_opd_daily(facility_id, date_from, date_to)
        elif code == "IPD_CENSUS":
            return await self._report_ipd_census(facility_id, date_from, date_to)
        elif code == "LAB_WORKLOAD":
            return await self._report_lab_workload(facility_id, date_from, date_to)
        elif code == "PHARMACY_STOCK":
            return await self._report_pharmacy_stock(facility_id)
        elif code == "REVENUE_SUMMARY":
            return await self._report_revenue(facility_id, date_from, date_to)
        elif code == "MOH_705A":
            return await self._report_moh_705a(facility_id, date_from, date_to)
        elif code in ("MOH_705B", "MOH_710", "MOH_711", "MOH_713", "MOH_718"):
            from app.services.dhis2.sync import DHIS2SyncService
            sync = DHIS2SyncService(self.db)
            report = await sync._generate_report(code, facility_id, date_from, date_to)
            if report:
                return (report, report.get("summary", {}), len(report.get("rows", report.get("indicators", {}))))
            return {"rows": []}, {"message": f"Failed to generate {code}"}, 0
        elif code == "TOP_DIAGNOSES":
            return await self._report_top_diagnoses(facility_id, date_from, date_to)
        else:
            return {"rows": []}, {"message": "Custom report — no built-in query"}, 0

    async def _report_opd_daily(
        self, facility_id: uuid.UUID, date_from: date, date_to: date
    ) -> tuple[dict, dict, int]:
        """
        OPD daily attendance report.

        @param facility_id: Facility UUID
        @param date_from: Start date
        @param date_to: End date
        @returns Report data tuple
        """
        result = await self.db.execute(
            select(
                func.date(Encounter.encounter_date).label("visit_date"),
                func.count(Encounter.id).label("total_visits"),
                func.count(func.nullif(Encounter.triage_category, "")).label("triaged"),
            )
            .where(
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
                Encounter.encounter_type == "opd",
                func.date(Encounter.encounter_date) >= date_from,
                func.date(Encounter.encounter_date) <= date_to,
            )
            .group_by(func.date(Encounter.encounter_date))
            .order_by(func.date(Encounter.encounter_date).asc())
        )
        rows = result.all()
        data = [
            {"date": str(r.visit_date), "total_visits": r.total_visits, "triaged": r.triaged}
            for r in rows
        ]

        total_visits = sum(r.total_visits for r in rows)
        return (
            {"rows": data},
            {"total_visits": total_visits, "days": len(data)},
            len(data),
        )

    async def _report_ipd_census(
        self, facility_id: uuid.UUID, date_from: date, date_to: date
    ) -> tuple[dict, dict, int]:
        """
        IPD census report — admissions, discharges, current census.

        @param facility_id: Facility UUID
        @param date_from: Start date
        @param date_to: End date
        @returns Report data tuple
        """
        admissions = await self.db.execute(
            select(func.count(Admission.id)).where(
                Admission.facility_id == facility_id,
                Admission.is_deleted == False,  # noqa: E712
                func.date(Admission.admitted_at) >= date_from,
                func.date(Admission.admitted_at) <= date_to,
            )
        )
        discharges = await self.db.execute(
            select(func.count(Admission.id)).where(
                Admission.facility_id == facility_id,
                Admission.is_deleted == False,  # noqa: E712
                Admission.status == "discharged",
                func.date(Admission.discharged_at) >= date_from,
                func.date(Admission.discharged_at) <= date_to,
            )
        )
        active = await self.db.execute(
            select(func.count(Admission.id)).where(
                Admission.facility_id == facility_id,
                Admission.is_deleted == False,  # noqa: E712
                Admission.status == "admitted",
            )
        )
        total_beds = await self.db.execute(
            select(func.count(Bed.id)).where(
                Bed.facility_id == facility_id,
                Bed.is_deleted == False,  # noqa: E712
            )
        )

        adm_count = admissions.scalar() or 0
        dis_count = discharges.scalar() or 0
        active_count = active.scalar() or 0
        beds = total_beds.scalar() or 1

        return (
            {
                "admissions": adm_count,
                "discharges": dis_count,
                "active_census": active_count,
                "total_beds": beds,
            },
            {
                "occupancy_rate": round((active_count / beds) * 100, 1),
                "average_daily_census": active_count,
            },
            1,
        )

    async def _report_lab_workload(
        self, facility_id: uuid.UUID, date_from: date, date_to: date
    ) -> tuple[dict, dict, int]:
        """
        Lab workload report.

        @param facility_id: Facility UUID
        @param date_from: Start date
        @param date_to: End date
        @returns Report data tuple
        """
        total = await self.db.execute(
            select(func.count(LabOrder.id)).where(
                LabOrder.facility_id == facility_id,
                LabOrder.is_deleted == False,  # noqa: E712
                func.date(LabOrder.created_at) >= date_from,
                func.date(LabOrder.created_at) <= date_to,
            )
        )
        completed = await self.db.execute(
            select(func.count(LabOrder.id)).where(
                LabOrder.facility_id == facility_id,
                LabOrder.is_deleted == False,  # noqa: E712
                LabOrder.status == "completed",
                func.date(LabOrder.created_at) >= date_from,
                func.date(LabOrder.created_at) <= date_to,
            )
        )
        critical = await self.db.execute(
            select(func.count(LabResult.id)).where(
                LabResult.facility_id == facility_id,
                LabResult.is_deleted == False,  # noqa: E712
                LabResult.is_critical == True,  # noqa: E712
                func.date(LabResult.created_at) >= date_from,
                func.date(LabResult.created_at) <= date_to,
            )
        )

        total_count = total.scalar() or 0
        completed_count = completed.scalar() or 0
        critical_count = critical.scalar() or 0

        return (
            {
                "total_orders": total_count,
                "completed": completed_count,
                "pending": total_count - completed_count,
                "critical_results": critical_count,
            },
            {
                "completion_rate": round(
                    (completed_count / total_count * 100) if total_count else 0, 1
                ),
            },
            1,
        )

    async def _report_pharmacy_stock(
        self, facility_id: uuid.UUID
    ) -> tuple[dict, dict, int]:
        """
        Pharmacy stock status report.

        @param facility_id: Facility UUID
        @returns Report data tuple
        """
        result = await self.db.execute(
            select(PharmacyItem).where(
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
                PharmacyItem.is_active == True,  # noqa: E712
            )
        )
        items = result.scalars().all()

        rows = []
        low_stock = 0
        out_of_stock = 0
        for item in items:
            row = {
                "name": item.generic_name,
                "brand": item.drug_name,
                "stock": item.current_quantity,
                "reorder_level": item.reorder_level,
                "unit_price_cents": item.selling_price_cents,
            }
            if item.current_quantity == 0:
                out_of_stock += 1
                row["alert"] = "out_of_stock"
            elif item.reorder_level and item.current_quantity <= item.reorder_level:
                low_stock += 1
                row["alert"] = "low_stock"
            rows.append(row)

        return (
            {"rows": rows},
            {
                "total_items": len(rows),
                "low_stock": low_stock,
                "out_of_stock": out_of_stock,
            },
            len(rows),
        )

    async def _report_revenue(
        self, facility_id: uuid.UUID, date_from: date, date_to: date
    ) -> tuple[dict, dict, int]:
        """
        Revenue summary report (KES cents).

        @param facility_id: Facility UUID
        @param date_from: Start date
        @param date_to: End date
        @returns Report data tuple
        """
        billed = await self.db.execute(
            select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
                func.date(Invoice.created_at) >= date_from,
                func.date(Invoice.created_at) <= date_to,
            )
        )
        paid = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
                Payment.facility_id == facility_id,
                Payment.is_deleted == False,  # noqa: E712
                func.date(Payment.created_at) >= date_from,
                func.date(Payment.created_at) <= date_to,
            )
        )

        billed_total = billed.scalar() or 0
        paid_total = paid.scalar() or 0

        return (
            {
                "total_billed_cents": billed_total,
                "total_paid_cents": paid_total,
                "outstanding_cents": billed_total - paid_total,
            },
            {
                "collection_rate": round(
                    (paid_total / billed_total * 100) if billed_total else 0, 1
                ),
            },
            1,
        )

    async def _report_moh_705a(
        self, facility_id: uuid.UUID, date_from: date, date_to: date
    ) -> tuple[dict, dict, int]:
        """
        MOH 705A — Outpatient Summary (daily disease returns).
        Groups OPD diagnoses by ICD-10 code.

        @param facility_id: Facility UUID
        @param date_from: Start date
        @param date_to: End date
        @returns Report data tuple
        """
        result = await self.db.execute(
            select(
                Diagnosis.icd10_code,
                Diagnosis.icd10_description,
                func.count(Diagnosis.id).label("case_count"),
            )
            .join(Encounter, Diagnosis.encounter_id == Encounter.id)
            .where(
                Diagnosis.facility_id == facility_id,
                Diagnosis.is_deleted == False,  # noqa: E712
                Encounter.encounter_type == "opd",
                func.date(Diagnosis.created_at) >= date_from,
                func.date(Diagnosis.created_at) <= date_to,
            )
            .group_by(Diagnosis.icd10_code, Diagnosis.icd10_description)
            .order_by(func.count(Diagnosis.id).desc())
        )
        rows = result.all()
        data = [
            {"icd_code": r.icd_code, "description": r.description, "cases": r.case_count}
            for r in rows
        ]

        return (
            {"rows": data},
            {"total_diagnoses": sum(r.case_count for r in rows), "unique_codes": len(data)},
            len(data),
        )

    async def _report_top_diagnoses(
        self, facility_id: uuid.UUID, date_from: date, date_to: date
    ) -> tuple[dict, dict, int]:
        """
        Top diagnoses report for analytics.

        @param facility_id: Facility UUID
        @param date_from: Start date
        @param date_to: End date
        @returns Report data tuple
        """
        result = await self.db.execute(
            select(
                Diagnosis.icd10_code,
                Diagnosis.icd10_description,
                func.count(Diagnosis.id).label("case_count"),
            )
            .where(
                Diagnosis.facility_id == facility_id,
                Diagnosis.is_deleted == False,  # noqa: E712
                func.date(Diagnosis.created_at) >= date_from,
                func.date(Diagnosis.created_at) <= date_to,
            )
            .group_by(Diagnosis.icd10_code, Diagnosis.icd10_description)
            .order_by(func.count(Diagnosis.id).desc())
            .limit(20)
        )
        rows = result.all()
        data = [
            {"icd_code": r.icd_code, "description": r.description, "count": r.case_count}
            for r in rows
        ]

        return ({"rows": data}, {"top_count": len(data)}, len(data))

    # ── Generated Reports List ───────────────────────────────────────────

    async def get_generated_reports(
        self,
        facility_id: uuid.UUID,
        template_id: uuid.UUID | None = None,
    ) -> list[GeneratedReportListItem]:
        """
        Get list of generated reports.

        @param facility_id: Facility UUID
        @param template_id: Optional template filter
        @returns List of generated reports
        """
        query = select(GeneratedReport).where(
            GeneratedReport.facility_id == facility_id,
            GeneratedReport.is_deleted == False,  # noqa: E712
        )
        if template_id:
            query = query.where(GeneratedReport.template_id == template_id)

        query = query.order_by(GeneratedReport.generated_at.desc()).limit(100)
        result = await self.db.execute(query)
        reports = result.scalars().all()

        return [GeneratedReportListItem.model_validate(r) for r in reports]

    async def get_generated_report(
        self,
        report_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> GeneratedReport | None:
        """
        Get a single generated report.

        @param report_id: Report UUID
        @param facility_id: Facility UUID
        @returns Generated report or None
        """
        result = await self.db.execute(
            select(GeneratedReport).where(
                GeneratedReport.id == report_id,
                GeneratedReport.facility_id == facility_id,
                GeneratedReport.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    # ── Facility Dashboard ───────────────────────────────────────────────

    async def get_facility_dashboard(
        self, facility_id: uuid.UUID
    ) -> FacilityDashboard:
        """
        Get facility-wide dashboard analytics for today.

        @param facility_id: Facility UUID
        @returns Dashboard analytics
        """
        today = date.today()
        month_start = today.replace(day=1)

        def count_of(model: Any, *criteria: Any) -> Any:
            """Scalar subquery counting the facility's non-deleted rows."""
            return (
                select(func.count(model.id))
                .where(
                    model.facility_id == facility_id,
                    model.is_deleted == False,  # noqa: E712
                    *criteria,
                )
                .scalar_subquery()
            )

        def count_created_between(
            model: Any, column: Any, d_from: date, d_to: date
        ) -> Any:
            """Scalar subquery counting rows created within a date range."""
            return count_of(
                model,
                func.date(column) >= d_from,
                func.date(column) <= d_to,
            )

        def sum_of(model: Any, column: Any, *criteria: Any) -> Any:
            """Scalar subquery totalling a money column for the facility."""
            return (
                select(func.coalesce(func.sum(column), 0))
                .where(
                    model.facility_id == facility_id,
                    model.is_deleted == False,  # noqa: E712
                    *criteria,
                )
                .scalar_subquery()
            )

        counters: dict[str, Any] = {
            # Patients
            "total_patients": count_of(Patient),
            "patients_today": count_created_between(
                Patient, Patient.created_at, today, today
            ),
            "patients_month": count_created_between(
                Patient, Patient.created_at, month_start, today
            ),
            # OPD
            "opd_today": count_of(
                Encounter,
                Encounter.encounter_type == "opd",
                func.date(Encounter.encounter_date) >= today,
                func.date(Encounter.encounter_date) <= today,
            ),
            "opd_month": count_of(
                Encounter,
                Encounter.encounter_type == "opd",
                func.date(Encounter.encounter_date) >= month_start,
                func.date(Encounter.encounter_date) <= today,
            ),
            # IPD
            "active_admissions": count_of(
                Admission, Admission.status == "admitted"
            ),
            "admissions_today": count_created_between(
                Admission, Admission.created_at, today, today
            ),
            "discharges_today": count_of(
                Admission,
                Admission.status == "discharged",
                func.date(Admission.discharged_at) == today,
            ),
            "total_beds": count_of(Bed),
            # Appointments - "today" reflects expected visits, so cancelled
            # and no-show bookings do not inflate the count.
            "appointments_today": count_of(
                Appointment,
                Appointment.appointment_date == today,
                Appointment.status.notin_(["cancelled", "no_show"]),
            ),
            "appointments_completed": count_of(
                Appointment,
                Appointment.appointment_date == today,
                Appointment.status == "completed",
            ),
            "appointments_no_show": count_of(
                Appointment,
                Appointment.appointment_date == today,
                Appointment.status == "no_show",
            ),
            # Lab
            "lab_orders_today": count_created_between(
                LabOrder, LabOrder.created_at, today, today
            ),
            "lab_pending": count_of(
                LabOrder,
                LabOrder.status.in_(["ordered", "specimen_collected"]),
            ),
            "lab_critical": count_of(
                LabResult,
                LabResult.is_critical == True,  # noqa: E712
                func.date(LabResult.created_at) == today,
            ),
            # Pharmacy
            "prescriptions_today": count_created_between(
                Dispensing, Dispensing.created_at, today, today
            ),
            "dispensed_today": count_of(
                Dispensing,
                Dispensing.status == "dispensed",
                func.date(Dispensing.created_at) == today,
            ),
            "stock_alerts": count_of(
                PharmacyItem,
                PharmacyItem.is_active == True,  # noqa: E712
                PharmacyItem.current_quantity <= PharmacyItem.reorder_level,
            ),
            # Billing
            "revenue_today": sum_of(
                Payment,
                Payment.amount_cents,
                func.date(Payment.created_at) == today,
            ),
            "revenue_month": sum_of(
                Payment,
                Payment.amount_cents,
                func.date(Payment.created_at) >= month_start,
                func.date(Payment.created_at) <= today,
            ),
            "outstanding_balance": sum_of(
                Invoice,
                Invoice.balance_cents,
                Invoice.status.in_(["finalized", "partially_paid"]),
            ),
            # Radiology
            "imaging_orders_today": count_created_between(
                ImagingOrder, ImagingOrder.created_at, today, today
            ),
            "imaging_pending_reports": count_of(
                ImagingOrder,
                ImagingOrder.status.in_(["ordered", "scheduled", "in_progress"]),
            ),
            # MCH
            "active_anc_profiles": count_of(
                ANCProfile, ANCProfile.status == "active"
            ),
            "deliveries_month": count_created_between(
                DeliveryRecord, DeliveryRecord.created_at, month_start, today
            ),
            "immunizations_month": count_created_between(
                Immunization, Immunization.created_at, month_start, today
            ),
        }

        # One round trip for the whole dashboard. Issuing these counters as
        # separate statements made the landing page the slowest screen in
        # the app, because every counter paid its own network round trip.
        row = (
            await self.db.execute(
                select(*(
                    subquery.label(name) for name, subquery in counters.items()
                ))
            )
        ).one()

        active_adm = row.active_admissions or 0
        beds_count = row.total_beds or 1
        occupancy = round((active_adm / beds_count) * 100, 1)

        return FacilityDashboard(
            total_patients=row.total_patients or 0,
            patients_today=row.patients_today or 0,
            patients_this_month=row.patients_month or 0,
            opd_visits_today=row.opd_today or 0,
            opd_visits_month=row.opd_month or 0,
            active_admissions=active_adm,
            admissions_today=row.admissions_today or 0,
            discharges_today=row.discharges_today or 0,
            bed_occupancy_rate=occupancy,
            appointments_today=row.appointments_today or 0,
            appointments_completed=row.appointments_completed or 0,
            appointments_no_show=row.appointments_no_show or 0,
            lab_orders_today=row.lab_orders_today or 0,
            lab_pending=row.lab_pending or 0,
            lab_critical=row.lab_critical or 0,
            prescriptions_today=row.prescriptions_today or 0,
            dispensed_today=row.dispensed_today or 0,
            stock_alerts=row.stock_alerts or 0,
            revenue_today=row.revenue_today or 0,
            revenue_month=row.revenue_month or 0,
            outstanding_balance=row.outstanding_balance or 0,
            imaging_orders_today=row.imaging_orders_today or 0,
            imaging_pending_reports=row.imaging_pending_reports or 0,
            active_anc_profiles=row.active_anc_profiles or 0,
            deliveries_month=row.deliveries_month or 0,
            immunizations_month=row.immunizations_month or 0,
        )

    # ── Dashboard Trends ─────────────────────────────────────────────────

    async def get_dashboard_trends(
        self, facility_id: uuid.UUID, days: int = 14
    ) -> DashboardTrends:
        """
        Get time-series trend data for the last N days.

        @param facility_id: Facility UUID
        @param days: Number of days to look back
        @returns Trend data for charts
        """
        today = date.today()
        start = today - timedelta(days=days - 1)

        opd = await self._daily_counts_encounter(facility_id, "opd", start, today)
        admissions = await self._daily_counts(Admission, facility_id, start, today)
        revenue = await self._daily_revenue(facility_id, start, today)
        lab = await self._daily_counts(LabOrder, facility_id, start, today)
        appts = await self._daily_counts_appointments(facility_id, start, today)

        return DashboardTrends(
            opd_visits=opd,
            admissions=admissions,
            revenue=revenue,
            lab_orders=lab,
            appointments=appts,
        )

    # ── Top Diagnoses ────────────────────────────────────────────────────

    async def get_top_diagnoses(
        self,
        facility_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 10,
    ) -> list[TopDiagnosis]:
        """
        Get top diagnoses by frequency.

        @param facility_id: Facility UUID
        @param date_from: Optional start date
        @param date_to: Optional end date
        @param limit: Max results
        @returns List of top diagnoses
        """
        today = date.today()
        d_from = date_from or today.replace(day=1)
        d_to = date_to or today

        result = await self.db.execute(
            select(
                Diagnosis.icd10_code,
                Diagnosis.icd10_description,
                func.count(Diagnosis.id).label("case_count"),
            )
            .where(
                Diagnosis.facility_id == facility_id,
                Diagnosis.is_deleted == False,  # noqa: E712
                func.date(Diagnosis.created_at) >= d_from,
                func.date(Diagnosis.created_at) <= d_to,
            )
            .group_by(Diagnosis.icd10_code, Diagnosis.icd10_description)
            .order_by(func.count(Diagnosis.id).desc())
            .limit(limit)
        )
        rows = result.all()
        return [
            TopDiagnosis(
                icd_code=r.icd10_code,
                description=r.icd10_description or "",
                count=r.case_count,
            )
            for r in rows
        ]

    # ── Summary ──────────────────────────────────────────────────────────

    async def get_summary(self, facility_id: uuid.UUID) -> ReportsSummary:
        """
        Get reports module summary.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        today = date.today()
        month_start = today.replace(day=1)

        total = await self.db.execute(
            select(func.count(ReportTemplate.id)).where(
                ReportTemplate.facility_id == facility_id,
                ReportTemplate.is_deleted == False,  # noqa: E712
            )
        )
        moh = await self.db.execute(
            select(func.count(ReportTemplate.id)).where(
                ReportTemplate.facility_id == facility_id,
                ReportTemplate.is_deleted == False,  # noqa: E712
                ReportTemplate.category == "moh",
            )
        )
        gen_today = await self.db.execute(
            select(func.count(GeneratedReport.id)).where(
                GeneratedReport.facility_id == facility_id,
                GeneratedReport.is_deleted == False,  # noqa: E712
                func.date(GeneratedReport.generated_at) == today,
            )
        )
        gen_month = await self.db.execute(
            select(func.count(GeneratedReport.id)).where(
                GeneratedReport.facility_id == facility_id,
                GeneratedReport.is_deleted == False,  # noqa: E712
                func.date(GeneratedReport.generated_at) >= month_start,
            )
        )

        return ReportsSummary(
            total_templates=total.scalar() or 0,
            moh_templates=moh.scalar() or 0,
            generated_today=gen_today.scalar() or 0,
            generated_month=gen_month.scalar() or 0,
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _count(self, model: Any, facility_id: uuid.UUID) -> int:
        """Count non-deleted records for a facility."""
        result = await self.db.execute(
            select(func.count(model.id)).where(
                model.facility_id == facility_id,
                model.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar() or 0

    async def _count_date(
        self, model: Any, facility_id: uuid.UUID, d_from: date, d_to: date
    ) -> int:
        """Count records created within a date range."""
        result = await self.db.execute(
            select(func.count(model.id)).where(
                model.facility_id == facility_id,
                model.is_deleted == False,  # noqa: E712
                func.date(model.created_at) >= d_from,
                func.date(model.created_at) <= d_to,
            )
        )
        return result.scalar() or 0

    async def _count_encounters(
        self,
        facility_id: uuid.UUID,
        enc_type: str,
        d_from: date,
        d_to: date,
    ) -> int:
        """Count encounters by type within a date range."""
        result = await self.db.execute(
            select(func.count(Encounter.id)).where(
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
                Encounter.encounter_type == enc_type,
                func.date(Encounter.encounter_date) >= d_from,
                func.date(Encounter.encounter_date) <= d_to,
            )
        )
        return result.scalar() or 0

    async def _daily_counts(
        self, model: Any, facility_id: uuid.UUID, d_from: date, d_to: date
    ) -> list[DepartmentStat]:
        """Get daily counts for a model."""
        result = await self.db.execute(
            select(
                func.date(model.created_at).label("d"),
                func.count(model.id).label("c"),
            )
            .where(
                model.facility_id == facility_id,
                model.is_deleted == False,  # noqa: E712
                func.date(model.created_at) >= d_from,
                func.date(model.created_at) <= d_to,
            )
            .group_by(func.date(model.created_at))
            .order_by(func.date(model.created_at).asc())
        )
        return [DepartmentStat(date=r.d, count=r.c) for r in result.all()]

    async def _daily_counts_encounter(
        self,
        facility_id: uuid.UUID,
        enc_type: str,
        d_from: date,
        d_to: date,
    ) -> list[DepartmentStat]:
        """Get daily encounter counts by type."""
        result = await self.db.execute(
            select(
                func.date(Encounter.encounter_date).label("d"),
                func.count(Encounter.id).label("c"),
            )
            .where(
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
                Encounter.encounter_type == enc_type,
                func.date(Encounter.encounter_date) >= d_from,
                func.date(Encounter.encounter_date) <= d_to,
            )
            .group_by(func.date(Encounter.encounter_date))
            .order_by(func.date(Encounter.encounter_date).asc())
        )
        return [DepartmentStat(date=r.d, count=r.c) for r in result.all()]

    async def _daily_counts_appointments(
        self,
        facility_id: uuid.UUID,
        d_from: date,
        d_to: date,
    ) -> list[DepartmentStat]:
        """Get daily expected appointment counts (excludes cancelled/no-show)."""
        result = await self.db.execute(
            select(
                Appointment.appointment_date.label("d"),
                func.count(Appointment.id).label("c"),
            )
            .where(
                Appointment.facility_id == facility_id,
                Appointment.is_deleted == False,  # noqa: E712
                Appointment.appointment_date >= d_from,
                Appointment.appointment_date <= d_to,
                Appointment.status.notin_(["cancelled", "no_show"]),
            )
            .group_by(Appointment.appointment_date)
            .order_by(Appointment.appointment_date.asc())
        )
        return [DepartmentStat(date=r.d, count=r.c) for r in result.all()]

    async def _daily_revenue(
        self,
        facility_id: uuid.UUID,
        d_from: date,
        d_to: date,
    ) -> list[DepartmentStat]:
        """Get daily revenue (KES cents)."""
        result = await self.db.execute(
            select(
                func.date(Payment.created_at).label("d"),
                func.coalesce(func.sum(Payment.amount_cents), 0).label("c"),
            )
            .where(
                Payment.facility_id == facility_id,
                Payment.is_deleted == False,  # noqa: E712
                func.date(Payment.created_at) >= d_from,
                func.date(Payment.created_at) <= d_to,
            )
            .group_by(func.date(Payment.created_at))
            .order_by(func.date(Payment.created_at).asc())
        )
        return [DepartmentStat(date=r.d, count=r.c) for r in result.all()]
