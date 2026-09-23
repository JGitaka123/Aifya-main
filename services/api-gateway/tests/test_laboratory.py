"""
Comprehensive tests for the laboratory module endpoints.

Tests cover the lab worklist, order detail, specimen collection,
result entry, result verification, and critical value notification.
Lab orders are created through the encounters flow (POST /encounters/{id}/lab-orders).
"""

import uuid
from collections.abc import Callable

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.license_check import require_module
from app.main import app

# ── Override require_module("laboratory") so tests bypass license tier gating ─


def _noop_module_checker(module: str) -> Callable:
    """
    No-op replacement for require_module in tests.

    @param module: Module name (ignored)
    @returns Async callable that does nothing
    """

    async def _noop() -> None:
        pass

    return _noop


# Patch the require_module factory so the laboratory router dependency is a no-op.
# We store the original and restore it after tests via the autouse fixture below.
_original_require_module = require_module


@pytest.fixture(autouse=True)
def _patch_module_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch require_module so laboratory endpoints are accessible without a license."""
    import app.routers.laboratory as lab_mod

    # The router was already built with Depends(require_module("laboratory")),
    # so we override the dependency at the app level for each concrete checker
    # that was captured at import time. Re-import the router's dependencies list
    # and override each one.
    for dep in lab_mod.router.dependencies:
        if dep.dependency is not None:
            app.dependency_overrides[dep.dependency] = _noop_module_checker("laboratory")


# ── Helper fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def patient_id(client: AsyncClient) -> str:
    """
    Create a test patient and return their ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Amina",
            "last_name": "Hassan",
            "date_of_birth": "1992-03-14",
            "gender": "female",
            "phone_number": "0722111222",
        },
    )
    assert response.status_code == 201, f"Patient creation failed: {response.text}"
    data: dict = response.json()
    return str(data["id"])


@pytest_asyncio.fixture
async def encounter_id(client: AsyncClient, patient_id: str) -> str:
    """
    Create an OPD encounter and return its ID.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Encounter UUID string
    """
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Fever and joint pain for 5 days",
        },
    )
    assert response.status_code == 201, f"Encounter creation failed: {response.text}"
    data: dict = response.json()
    return str(data["id"])


@pytest_asyncio.fixture
async def lab_order(
    client: AsyncClient, patient_id: str, encounter_id: str
) -> dict:
    """
    Create a lab order via the encounters endpoint and return the full response.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @param encounter_id: Encounter UUID string
    @returns Lab order response dict
    """
    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/lab-orders",
        json={
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "priority": "urgent",
            "clinical_info": "Fever x5 days, suspect dengue or malaria",
            "fasting": False,
            "tests": [
                {
                    "test_code": "CBC",
                    "test_name": "Complete Blood Count",
                },
                {
                    "test_code": "MAL-RDT",
                    "test_name": "Malaria Rapid Diagnostic Test",
                },
            ],
        },
    )
    assert response.status_code == 201, f"Lab order creation failed: {response.text}"
    data: dict = response.json()
    return data


# ── 1. Worklist: empty ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_worklist_empty(client: AsyncClient) -> None:
    """Test that the lab worklist returns empty when no orders exist."""
    response = await client.get("/api/v1/laboratory/worklist")

    assert response.status_code == 200
    data: dict = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# ── 2. Order detail: 404 for non-existent ID ────────────────────────────────


@pytest.mark.asyncio
async def test_get_order_not_found(client: AsyncClient) -> None:
    """Test that fetching a non-existent lab order returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/laboratory/orders/{fake_id}")

    assert response.status_code == 404
    data: dict = response.json()
    assert data["detail"] == "Lab order not found"


# ── 3. Specimen collection ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_specimen(client: AsyncClient, lab_order: dict) -> None:
    """Test recording specimen collection for a lab order."""
    order_id: str = lab_order["id"]

    response = await client.post(
        f"/api/v1/laboratory/orders/{order_id}/collect",
        json={"specimen_id": "SPEC-20260412-001"},
    )

    assert response.status_code == 200
    data: dict = response.json()
    assert data["id"] == order_id
    assert data["status"] == "collected"
    assert data["specimen_collected_at"] is not None


@pytest.mark.asyncio
async def test_collect_specimen_without_specimen_id(
    client: AsyncClient, lab_order: dict
) -> None:
    """Test specimen collection works without an explicit specimen ID."""
    order_id: str = lab_order["id"]

    response = await client.post(
        f"/api/v1/laboratory/orders/{order_id}/collect",
        json={},
    )

    assert response.status_code == 200
    data: dict = response.json()
    assert data["id"] == order_id
    assert data["status"] == "collected"


@pytest.mark.asyncio
async def test_collect_specimen_not_found(client: AsyncClient) -> None:
    """Test 404 when collecting specimen for non-existent order."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/laboratory/orders/{fake_id}/collect",
        json={},
    )

    assert response.status_code == 404
    data: dict = response.json()
    assert data["detail"] == "Lab order not found"


# ── 4. Worklist with status filter ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_worklist_with_orders(client: AsyncClient, lab_order: dict) -> None:
    """Test that the worklist includes newly created lab orders."""
    response = await client.get("/api/v1/laboratory/worklist")

    assert response.status_code == 200
    data: dict = response.json()
    assert data["total"] >= 1
    order_ids = [item["id"] for item in data["items"]]
    assert lab_order["id"] in order_ids


@pytest.mark.asyncio
async def test_worklist_filter_by_status(
    client: AsyncClient, lab_order: dict
) -> None:
    """Test filtering the worklist by order status."""
    order_id: str = lab_order["id"]

    # Collect specimen so the order moves to 'collected'
    collect_resp = await client.post(
        f"/api/v1/laboratory/orders/{order_id}/collect",
        json={"specimen_id": "SPEC-FILTER-001"},
    )
    assert collect_resp.status_code == 200

    # Filter for collected orders
    response = await client.get(
        "/api/v1/laboratory/worklist", params={"status": "collected"}
    )

    assert response.status_code == 200
    data: dict = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["status"] == "collected"


@pytest.mark.asyncio
async def test_worklist_filter_no_match(
    client: AsyncClient, lab_order: dict
) -> None:
    """Test that filtering by a status with no matches returns empty."""
    # The order is in 'ordered' status, filter for 'completed'
    response = await client.get(
        "/api/v1/laboratory/worklist", params={"status": "completed"}
    )

    assert response.status_code == 200
    data: dict = response.json()
    assert data["total"] == 0
    assert data["items"] == []


# ── 5. Order detail: existing order ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_order_detail(client: AsyncClient, lab_order: dict) -> None:
    """Test fetching a lab order returns full detail with results."""
    order_id: str = lab_order["id"]

    response = await client.get(f"/api/v1/laboratory/orders/{order_id}")

    assert response.status_code == 200
    data: dict = response.json()
    assert data["order"]["id"] == order_id
    assert data["order"]["priority"] == "urgent"
    assert data["order"]["status"] == "ordered"
    assert isinstance(data["results"], list)
    # Should have one result per test requested (CBC + MAL-RDT)
    assert len(data["results"]) == 2
    test_codes = [r["test_code"] for r in data["results"]]
    assert "CBC" in test_codes
    assert "MAL-RDT" in test_codes
    # Patient info populated
    assert data["patient_name"] is not None
    assert data["patient_mrn"] is not None


# ── 6. Result entry ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enter_result(client: AsyncClient, lab_order: dict) -> None:
    """Test entering a lab result value."""
    order_id: str = lab_order["id"]

    # Get the order detail to find result IDs
    detail_resp = await client.get(f"/api/v1/laboratory/orders/{order_id}")
    assert detail_resp.status_code == 200
    results: list[dict] = detail_resp.json()["results"]
    cbc_result = next(r for r in results if r["test_code"] == "CBC")
    result_id: str = cbc_result["id"]

    # Enter a result
    response = await client.post(
        f"/api/v1/laboratory/results/{result_id}/enter",
        json={
            "result_value": "WBC 11.2, RBC 4.5, Hgb 12.1, Plt 250",
            "result_numeric": 11.2,
            "result_unit": "x10^9/L",
            "reference_range": "4.0-11.0",
            "interpretation": "abnormal",
            "is_abnormal": True,
            "notes": "Slightly elevated WBC, suggest repeat in 48h",
            "method": "Automated hematology analyzer",
        },
    )

    assert response.status_code == 200
    data: dict = response.json()
    assert data["id"] == result_id
    assert data["result_value"] == "WBC 11.2, RBC 4.5, Hgb 12.1, Plt 250"
    assert data["result_numeric"] == 11.2
    assert data["result_unit"] == "x10^9/L"
    assert data["reference_range"] == "4.0-11.0"
    assert data["interpretation"] == "abnormal"
    assert data["is_abnormal"] is True
    assert data["status"] == "preliminary"
    assert data["resulted_at"] is not None


@pytest.mark.asyncio
async def test_enter_result_not_found(client: AsyncClient) -> None:
    """Test 404 when entering result for non-existent result ID."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/laboratory/results/{fake_id}/enter",
        json={
            "result_value": "Negative",
            "interpretation": "normal",
        },
    )

    assert response.status_code == 404
    data: dict = response.json()
    assert data["detail"] == "Lab result not found"


# ── 7. Result verification ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_result(client: AsyncClient, lab_order: dict) -> None:
    """Test verifying (approving) a lab result."""
    order_id: str = lab_order["id"]

    # Get result IDs
    detail_resp = await client.get(f"/api/v1/laboratory/orders/{order_id}")
    assert detail_resp.status_code == 200
    results: list[dict] = detail_resp.json()["results"]
    result_id: str = results[0]["id"]

    # Enter a result first (must have a value before verification)
    enter_resp = await client.post(
        f"/api/v1/laboratory/results/{result_id}/enter",
        json={
            "result_value": "Negative",
            "interpretation": "normal",
        },
    )
    assert enter_resp.status_code == 200

    # Now verify
    response = await client.post(
        f"/api/v1/laboratory/results/{result_id}/verify",
        json={"notes": "Results reviewed and confirmed"},
    )

    assert response.status_code == 200
    data: dict = response.json()
    assert data["id"] == result_id
    assert data["status"] == "final"
    assert data["verified_at"] is not None
    assert data["verified_by"] is not None


@pytest.mark.asyncio
async def test_verify_result_without_notes(
    client: AsyncClient, lab_order: dict
) -> None:
    """Test that verification works without optional notes."""
    order_id: str = lab_order["id"]

    detail_resp = await client.get(f"/api/v1/laboratory/orders/{order_id}")
    assert detail_resp.status_code == 200
    results: list[dict] = detail_resp.json()["results"]
    result_id: str = results[0]["id"]

    # Enter a result first
    enter_resp = await client.post(
        f"/api/v1/laboratory/results/{result_id}/enter",
        json={
            "result_value": "Positive",
            "interpretation": "abnormal",
            "is_abnormal": True,
        },
    )
    assert enter_resp.status_code == 200

    # Verify with empty body
    response = await client.post(
        f"/api/v1/laboratory/results/{result_id}/verify",
        json={},
    )

    assert response.status_code == 200
    data: dict = response.json()
    assert data["status"] == "final"


@pytest.mark.asyncio
async def test_verify_result_not_found(client: AsyncClient) -> None:
    """Test 404 when verifying a non-existent result."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/laboratory/results/{fake_id}/verify",
        json={},
    )

    assert response.status_code == 404
    data: dict = response.json()
    assert data["detail"] == "Lab result not found"


# ── 8. Critical value notification ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_critical(client: AsyncClient, lab_order: dict) -> None:
    """Test recording critical value notification to a clinician."""
    order_id: str = lab_order["id"]

    # Get result IDs
    detail_resp = await client.get(f"/api/v1/laboratory/orders/{order_id}")
    assert detail_resp.status_code == 200
    results: list[dict] = detail_resp.json()["results"]
    result_id: str = results[0]["id"]

    # Enter a critical result first
    enter_resp = await client.post(
        f"/api/v1/laboratory/results/{result_id}/enter",
        json={
            "result_value": "2.1",
            "result_numeric": 2.1,
            "result_unit": "mmol/L",
            "reference_range": "3.5-5.0",
            "interpretation": "critical",
            "is_abnormal": True,
            "notes": "Critical hypokalemia",
        },
    )
    assert enter_resp.status_code == 200

    # Notify clinician about the critical value
    clinician_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/laboratory/results/{result_id}/notify-critical",
        json={"notified_to": clinician_id},
    )

    assert response.status_code == 200
    data: dict = response.json()
    assert data["id"] == result_id
    assert data["critical_notified"] is True
    assert data["critical_notified_to"] == clinician_id
    assert data["critical_notified_at"] is not None


@pytest.mark.asyncio
async def test_notify_critical_not_found(client: AsyncClient) -> None:
    """Test 404 when notifying critical for non-existent result."""
    fake_id = str(uuid.uuid4())
    clinician_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/laboratory/results/{fake_id}/notify-critical",
        json={"notified_to": clinician_id},
    )

    assert response.status_code == 404
    data: dict = response.json()
    assert data["detail"] == "Lab result not found"


@pytest.mark.asyncio
async def test_notify_critical_missing_clinician(client: AsyncClient) -> None:
    """Test that notify-critical requires the notified_to field."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/laboratory/results/{fake_id}/notify-critical",
        json={},
    )

    # Pydantic validation error: notified_to is required
    assert response.status_code == 422


# ── 9. Full workflow: order → collect → enter → verify ───────────────────────


@pytest.mark.asyncio
async def test_full_lab_workflow(
    client: AsyncClient, patient_id: str, encounter_id: str
) -> None:
    """
    Test the complete lab workflow from order creation through verification.

    Steps: create order → collect specimen → enter result → verify result.
    """
    # Step 1: Create a lab order
    order_resp = await client.post(
        f"/api/v1/encounters/{encounter_id}/lab-orders",
        json={
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "priority": "stat",
            "clinical_info": "Suspected sepsis, urgent",
            "fasting": False,
            "tests": [
                {
                    "test_code": "BC",
                    "test_name": "Blood Culture",
                },
            ],
        },
    )
    assert order_resp.status_code == 201
    order_data: dict = order_resp.json()
    order_id: str = order_data["id"]
    assert order_data["status"] == "ordered"
    assert order_data["priority"] == "stat"

    # Step 2: Collect specimen
    collect_resp = await client.post(
        f"/api/v1/laboratory/orders/{order_id}/collect",
        json={"specimen_id": "BC-STAT-001"},
    )
    assert collect_resp.status_code == 200
    assert collect_resp.json()["status"] == "collected"

    # Step 3: Get order detail to find result ID
    detail_resp = await client.get(f"/api/v1/laboratory/orders/{order_id}")
    assert detail_resp.status_code == 200
    detail_data: dict = detail_resp.json()
    assert len(detail_data["results"]) == 1
    result_id: str = detail_data["results"][0]["id"]

    # Step 4: Enter result
    enter_resp = await client.post(
        f"/api/v1/laboratory/results/{result_id}/enter",
        json={
            "result_value": "Staphylococcus aureus isolated",
            "interpretation": "abnormal",
            "is_abnormal": True,
            "method": "Automated blood culture system",
            "notes": "Gram-positive cocci in clusters",
        },
    )
    assert enter_resp.status_code == 200
    assert enter_resp.json()["status"] == "preliminary"

    # Step 5: Verify result
    verify_resp = await client.post(
        f"/api/v1/laboratory/results/{result_id}/verify",
        json={"notes": "Confirmed S. aureus. Sensitivity pending."},
    )
    assert verify_resp.status_code == 200
    verified_data: dict = verify_resp.json()
    assert verified_data["status"] == "final"
    assert verified_data["verified_at"] is not None


# ── Critical value alerting ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_critical_result_emits_alert_event(
    client: AsyncClient, lab_order: dict
) -> None:
    """Entering a critical result appends a CriticalLabResultDetected event."""
    from sqlalchemy import select

    from app.models.base import EventBase
    from tests.conftest import session_factory as session_factory

    order_id: str = lab_order["id"]
    detail_resp = await client.get(f"/api/v1/laboratory/orders/{order_id}")
    results: list[dict] = detail_resp.json()["results"]
    result_id: str = results[0]["id"]

    response = await client.post(
        f"/api/v1/laboratory/results/{result_id}/enter",
        json={
            "result_value": "K+ 7.2 mmol/L",
            "result_numeric": 7.2,
            "result_unit": "mmol/L",
            "interpretation": "critical",
            "is_abnormal": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["is_critical"] is True

    async with session_factory() as session:
        events = await session.execute(
            select(EventBase).where(
                EventBase.event_type == "CriticalLabResultDetected"
            )
        )
        rows = list(events.scalars().all())
    assert len(rows) == 1
    assert rows[0].event_data["result_id"] == result_id
    assert rows[0].event_data["order_id"] == order_id


@pytest.mark.asyncio
async def test_threshold_critical_result_alerts_when_sms_fails(
    client: AsyncClient, lab_order: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A threshold-detected critical value keeps its alert if SMS fails."""
    from sqlalchemy import select

    from app.models.base import EventBase
    from app.models.lab import LabResult
    from app.models.staff import Staff
    from tests.conftest import FACILITY_ID, USER_ID
    from tests.conftest import session_factory as session_factory

    class FailingSMSProvider:
        """Test provider that simulates a notification transport outage."""

        async def send_sms(self, _phone_number: str, _message: str) -> bool:
            """Raise the simulated transport error."""
            raise RuntimeError("SMS unavailable")

    monkeypatch.setattr(
        "app.services.comms.sms_provider.get_sms_provider",
        lambda: FailingSMSProvider(),
    )

    async with session_factory() as session:
        session.add(
            Staff(
                facility_id=FACILITY_ID,
                keycloak_user_id=USER_ID,
                employee_number="LAB-ALERT-001",
                first_name="Alert",
                last_name="Clinician",
                role="doctor",
                phone="0712345678",
                email="alert-clinician@example.test",
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await session.commit()

    order_id: str = lab_order["id"]
    detail_resp = await client.get(f"/api/v1/laboratory/orders/{order_id}")
    result_id: str = detail_resp.json()["results"][0]["id"]

    async with session_factory() as session:
        result_row = await session.execute(
            select(LabResult).where(LabResult.id == uuid.UUID(result_id))
        )
        result_row.scalar_one().test_code = "K"
        await session.commit()

    response = await client.post(
        f"/api/v1/laboratory/results/{result_id}/enter",
        json={
            "result_value": "7.2",
            "result_numeric": 7.2,
            "result_unit": "mmol/L",
            "interpretation": "normal",
        },
    )

    assert response.status_code == 200
    assert response.json()["is_critical"] is True
    assert response.json()["interpretation"] == "critical"

    async with session_factory() as session:
        events = await session.execute(
            select(EventBase).where(
                EventBase.event_type == "CriticalLabResultDetected",
                EventBase.stream_id == uuid.UUID(lab_order["patient_id"]),
            )
        )
        alerts = list(events.scalars().all())
    assert len(alerts) == 1
    assert alerts[0].event_data["result_id"] == result_id
