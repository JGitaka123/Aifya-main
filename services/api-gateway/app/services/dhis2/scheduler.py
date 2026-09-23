"""
Celery tasks for scheduled DHIS2 report generation and submission.
Runs monthly auto-sync of all MOH forms for facilities with DHIS2 configured.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from structlog import get_logger

logger = get_logger(__name__)


def get_dhis2_config_from_env() -> dict | None:
    """
    Load DHIS2 configuration from environment variables.
    In production, credentials come from HashiCorp Vault.

    @returns DHIS2 config dict or None if not configured
    """
    base_url = os.getenv("DHIS2_BASE_URL")
    username = os.getenv("DHIS2_USERNAME")
    password = os.getenv("DHIS2_PASSWORD")

    if not all([base_url, username, password]):
        return None

    return {
        "base_url": base_url,
        "username": username,
        "password": password,
    }


# ── Celery Task Registration ────────────────────────────────────────────────
# These tasks are registered with the Celery app in the worker configuration.
# Schedule: monthly on the 5th day, giving facilities time to complete data entry.

try:
    from app.worker import celery_app

    @celery_app.task(name="dhis2.monthly_sync", bind=True, max_retries=3)
    def monthly_dhis2_sync(self, facility_id: str, org_unit_id: str) -> dict:
        """
        Monthly DHIS2 sync task — generates all MOH forms for previous month
        and submits to DHIS2. Runs as Celery task for non-blocking execution.

        @param facility_id: Facility UUID string
        @param org_unit_id: DHIS2 organization unit ID
        @returns Sync result summary
        """
        import asyncio
        from uuid import UUID

        from app.database import async_session_factory
        from app.services.dhis2.client import DHIS2Config
        from app.services.dhis2.sync import DHIS2SyncService

        config_env = get_dhis2_config_from_env()
        if not config_env:
            logger.warning("dhis2_not_configured", facility_id=facility_id)
            return {"status": "skipped", "reason": "DHIS2 not configured"}

        dhis2_config = DHIS2Config(
            **config_env,
            org_unit_id=org_unit_id,
        )

        # Calculate previous month range
        today = date.today()
        first_of_month = today.replace(day=1)
        last_of_prev_month = first_of_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)

        async def _run() -> dict:
            async with async_session_factory() as db:
                service = DHIS2SyncService(db)
                forms = ["MOH_705A", "MOH_705B", "MOH_710", "MOH_711", "MOH_713", "MOH_718"]
                results = {}

                for form_code in forms:
                    try:
                        result = await service.generate_and_submit(
                            form_code=form_code,
                            facility_id=UUID(facility_id),
                            date_from=first_of_prev_month,
                            date_to=last_of_prev_month,
                            dhis2_config=dhis2_config,
                        )
                        results[form_code] = result.get("status", "unknown")
                    except Exception as exc:
                        logger.error(
                            "dhis2_form_sync_error",
                            form=form_code,
                            error=str(exc),
                        )
                        results[form_code] = f"error: {exc}"

                return results

        return asyncio.run(_run())

    @celery_app.task(name="dhis2.generate_report", bind=True)
    def generate_moh_report(
        self,
        facility_id: str,
        form_code: str,
        date_from: str,
        date_to: str,
    ) -> dict:
        """
        On-demand MOH report generation (no DHIS2 submission).

        @param facility_id: Facility UUID string
        @param form_code: MOH form code
        @param date_from: Start date (YYYY-MM-DD)
        @param date_to: End date (YYYY-MM-DD)
        @returns Generated report data
        """
        import asyncio
        from datetime import date as date_type
        from uuid import UUID

        from app.database import async_session_factory
        from app.services.dhis2.sync import DHIS2SyncService

        async def _run() -> dict:
            async with async_session_factory() as db:
                service = DHIS2SyncService(db)
                report = await service._generate_report(
                    form_code=form_code,
                    facility_id=UUID(facility_id),
                    date_from=date_type.fromisoformat(date_from),
                    date_to=date_type.fromisoformat(date_to),
                )
                return report or {"error": f"Unknown form: {form_code}"}

        return asyncio.run(_run())

except ImportError:
    # Worker not available (e.g., during tests or migrations)
    logger.debug("celery_not_available", message="DHIS2 tasks not registered")
