"""
DHIS2 API v2 client — handles authentication, data value set submission,
and organization unit lookups for Kenya's national DHIS2 instance.

Credentials stored in Vault / env vars (NEVER in DB or code).
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel
from structlog import get_logger

logger = get_logger(__name__)


class DHIS2Config(BaseModel):
    """
    DHIS2 connection configuration.

    @param base_url: DHIS2 instance URL (e.g. https://hiskenya.org)
    @param username: DHIS2 API username
    @param password: DHIS2 API password
    @param org_unit_id: DHIS2 organization unit ID for this facility
    """
    base_url: str
    username: str
    password: str
    org_unit_id: str


class DHIS2DataValue(BaseModel):
    """
    Single DHIS2 data value for submission.

    @param dataElement: DHIS2 data element UID
    @param categoryOptionCombo: Category option combo UID (for disaggregation)
    @param value: The value to submit
    """
    dataElement: str
    categoryOptionCombo: str = ""
    value: str


class DHIS2DataValueSet(BaseModel):
    """
    DHIS2 data value set payload per the DHIS2 Web API spec.

    @param dataSet: DHIS2 dataset UID (e.g. MOH 705A dataset)
    @param period: DHIS2 period string (e.g. "202601" for Jan 2026)
    @param orgUnit: Organization unit UID
    @param dataValues: List of data values
    """
    dataSet: str
    period: str
    orgUnit: str
    dataValues: list[DHIS2DataValue]


class DHIS2SubmissionResult(BaseModel):
    """
    Result of a DHIS2 data value set submission.

    @param success: Whether submission succeeded
    @param status: DHIS2 response status
    @param import_count: Counts of imported/updated/ignored values
    @param description: Descriptive message
    """
    success: bool
    status: str
    import_count: dict[str, int] = {}
    description: str = ""


class DHIS2Client:
    """
    HTTP client for the DHIS2 Web API.
    Uses httpx for async HTTP calls with basic auth.
    """

    def __init__(self, config: DHIS2Config) -> None:
        """
        Initialize DHIS2 client.

        @param config: DHIS2 connection configuration
        """
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self._auth = (config.username, config.password)

    async def submit_data_value_set(
        self,
        dataset: DHIS2DataValueSet,
    ) -> DHIS2SubmissionResult:
        """
        Submit a data value set to DHIS2 via POST /api/dataValueSets.

        @param dataset: Data value set payload
        @returns Submission result with import counts
        """
        url = f"{self.base_url}/api/dataValueSets"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=dataset.model_dump(),
                    auth=self._auth,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code in (200, 201):
                    body = response.json()
                    import_summary = body.get("importCount", {})
                    return DHIS2SubmissionResult(
                        success=True,
                        status=body.get("status", "SUCCESS"),
                        import_count={
                            "imported": import_summary.get("imported", 0),
                            "updated": import_summary.get("updated", 0),
                            "ignored": import_summary.get("ignored", 0),
                            "deleted": import_summary.get("deleted", 0),
                        },
                        description=body.get("description", "Data submitted successfully"),
                    )
                else:
                    logger.error(
                        "dhis2_submission_failed",
                        status_code=response.status_code,
                        body=response.text[:500],
                    )
                    return DHIS2SubmissionResult(
                        success=False,
                        status=f"HTTP {response.status_code}",
                        description=response.text[:500],
                    )

        except httpx.TimeoutException:
            logger.error("dhis2_timeout", url=url)
            return DHIS2SubmissionResult(
                success=False,
                status="TIMEOUT",
                description="DHIS2 request timed out after 30s",
            )
        except Exception as exc:
            logger.error("dhis2_error", error=str(exc))
            return DHIS2SubmissionResult(
                success=False,
                status="ERROR",
                description=str(exc),
            )

    async def get_org_units(self) -> list[dict]:
        """
        Fetch organization units from DHIS2.

        @returns List of org unit dicts with id, name, level
        """
        url = f"{self.base_url}/api/organisationUnits"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    url,
                    auth=self._auth,
                    params={"paging": "false", "fields": "id,name,level,parent[id,name]"},
                )
                if response.status_code == 200:
                    return response.json().get("organisationUnits", [])
                return []
        except Exception as exc:
            logger.error("dhis2_org_units_error", error=str(exc))
            return []

    async def get_data_sets(self) -> list[dict]:
        """
        Fetch available data sets from DHIS2.

        @returns List of dataset dicts with id, name, periodType
        """
        url = f"{self.base_url}/api/dataSets"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    url,
                    auth=self._auth,
                    params={"paging": "false", "fields": "id,name,periodType"},
                )
                if response.status_code == 200:
                    return response.json().get("dataSets", [])
                return []
        except Exception as exc:
            logger.error("dhis2_datasets_error", error=str(exc))
            return []

    async def check_connection(self) -> bool:
        """
        Test DHIS2 connectivity by hitting /api/system/info.

        @returns True if connection is successful
        """
        url = f"{self.base_url}/api/system/info"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, auth=self._auth)
                return response.status_code == 200
        except Exception:
            return False
