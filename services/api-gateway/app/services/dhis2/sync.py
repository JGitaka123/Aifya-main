"""
DHIS2 sync service — maps MOH report data to DHIS2 data elements
and submits via the DHIS2 API client.

Data element UIDs are configurable per facility to support different
DHIS2 instance configurations across Kenya's health system.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.services.dhis2.client import (
    DHIS2Client,
    DHIS2Config,
    DHIS2DataValue,
    DHIS2DataValueSet,
)
from app.services.dhis2.moh_forms import (
    generate_moh_705a,
    generate_moh_705b,
    generate_moh_710,
    generate_moh_711,
    generate_moh_713,
    generate_moh_718,
)

logger = get_logger(__name__)

# Default Kenya DHIS2 data element mappings.
# These map MOH form fields to DHIS2 data element UIDs.
# Override per facility via dhis2_config table.
DEFAULT_DATASET_IDS: dict[str, str] = {
    "MOH_705A": "",  # Set per DHIS2 instance
    "MOH_705B": "",
    "MOH_710": "",
    "MOH_711": "",
    "MOH_713": "",
    "MOH_718": "",
}


def _date_to_dhis2_period(date_from: date, date_to: date) -> str:
    """
    Convert a date range to a DHIS2 period string.
    Monthly: "YYYYMM", Quarterly: "YYYYQ1-Q4".

    @param date_from: Start date
    @param date_to: End date
    @returns DHIS2 period string
    """
    # If range spans a single month, use monthly period
    if date_from.month == date_to.month and date_from.year == date_to.year:
        return f"{date_from.year}{date_from.month:02d}"

    # If range spans a quarter
    quarter = (date_from.month - 1) // 3 + 1
    return f"{date_from.year}Q{quarter}"


class DHIS2SyncService:
    """
    Orchestrates MOH report generation and DHIS2 submission.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the sync service.

        @param db: Async database session
        """
        self.db = db

    async def generate_and_submit(
        self,
        form_code: str,
        facility_id: uuid.UUID,
        date_from: date,
        date_to: date,
        dhis2_config: DHIS2Config,
        dataset_id: str | None = None,
    ) -> dict:
        """
        Generate a MOH report and submit to DHIS2.

        @param form_code: MOH form code (e.g. "MOH_705A")
        @param facility_id: Facility UUID
        @param date_from: Report period start
        @param date_to: Report period end
        @param dhis2_config: DHIS2 connection configuration
        @param dataset_id: Override DHIS2 dataset UID
        @returns Dict with report data and submission result
        """
        # Step 1: Generate the report
        report = await self._generate_report(form_code, facility_id, date_from, date_to)
        if not report:
            return {
                "form": form_code,
                "status": "error",
                "message": f"Unknown form code: {form_code}",
            }

        # Step 2: Map to DHIS2 data values
        ds_id = dataset_id or DEFAULT_DATASET_IDS.get(form_code, "")
        period = _date_to_dhis2_period(date_from, date_to)

        data_values = self._map_to_data_values(form_code, report)

        if not ds_id:
            logger.warning(
                "dhis2_no_dataset_id",
                form=form_code,
                message="No DHIS2 dataset ID configured — report generated but not submitted",
            )
            return {
                "form": form_code,
                "status": "generated",
                "report": report,
                "dhis2_submitted": False,
                "message": "No DHIS2 dataset ID configured. Report generated locally only.",
            }

        # Step 3: Submit to DHIS2
        value_set = DHIS2DataValueSet(
            dataSet=ds_id,
            period=period,
            orgUnit=dhis2_config.org_unit_id,
            dataValues=data_values,
        )

        client = DHIS2Client(dhis2_config)
        result = await client.submit_data_value_set(value_set)

        logger.info(
            "dhis2_sync_complete",
            form=form_code,
            success=result.success,
            status=result.status,
        )

        return {
            "form": form_code,
            "status": "submitted" if result.success else "failed",
            "report": report,
            "dhis2_submitted": result.success,
            "dhis2_result": result.model_dump(),
        }

    async def _generate_report(
        self,
        form_code: str,
        facility_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> dict | None:
        """
        Route to the appropriate MOH form generator.

        @param form_code: MOH form code
        @param facility_id: Facility UUID
        @param date_from: Start date
        @param date_to: End date
        @returns Generated report dict or None
        """
        generators = {
            "MOH_705A": generate_moh_705a,
            "MOH_705B": generate_moh_705b,
            "MOH_710": generate_moh_710,
            "MOH_711": generate_moh_711,
            "MOH_713": generate_moh_713,
            "MOH_718": generate_moh_718,
        }
        gen = generators.get(form_code.upper())
        if not gen:
            return None
        return await gen(self.db, facility_id, date_from, date_to)

    def _map_to_data_values(self, form_code: str, report: dict) -> list[DHIS2DataValue]:
        """
        Map generated report data to DHIS2DataValue objects.
        In production, this would use facility-specific data element mappings.
        For now, creates generic mappings from report summary fields.

        @param form_code: MOH form code
        @param report: Generated report dict
        @returns List of DHIS2DataValue objects
        """
        values: list[DHIS2DataValue] = []

        # Map summary/indicator fields to data values
        # The data element UIDs must be configured per DHIS2 instance
        source = report.get("indicators") or report.get("summary", {})

        for key, val in source.items():
            if isinstance(val, (int, float)):
                values.append(
                    DHIS2DataValue(
                        dataElement=f"{form_code}_{key}",  # Placeholder UID
                        value=str(val),
                    )
                )

        # For row-based reports (705A, 705B, 710, 713), aggregate totals
        rows = report.get("rows", [])
        if rows and isinstance(rows, list):
            for i, row in enumerate(rows[:100]):  # Cap at 100 rows
                total = row.get("total") or row.get("doses_given", 0)
                if total:
                    label = row.get("icd10_code") or row.get("vaccine") or row.get("test_name") or f"row_{i}"
                    values.append(
                        DHIS2DataValue(
                            dataElement=f"{form_code}_{label}",  # Placeholder UID
                            value=str(total),
                        )
                    )

        return values

    async def generate_all_reports(
        self,
        facility_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> dict[str, dict]:
        """
        Generate all MOH forms for a facility without submitting to DHIS2.
        Used for local preview and validation.

        @param facility_id: Facility UUID
        @param date_from: Start date
        @param date_to: End date
        @returns Dict mapping form code to report data
        """
        forms = ["MOH_705A", "MOH_705B", "MOH_710", "MOH_711", "MOH_713", "MOH_718"]
        results: dict[str, dict] = {}

        for form_code in forms:
            report = await self._generate_report(form_code, facility_id, date_from, date_to)
            if report:
                results[form_code] = report

        return results
