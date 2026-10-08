"""Every department a patient waits in must be able to call them.

A visit's number only covers the room the patient is already sitting in. When a
clinician orders labs or imaging the patient waits somewhere else, and when the
result comes back they wait again to be reviewed. These tests drive the real
routers and pin the bridges that keep those waits visible to the board and the
speakers: lab and imaging orders, the return-for-review call, and a critical
triage reading.
"""

import pytest
from httpx import AsyncClient

from app.models.staff import Department
from tests.conftest import FACILITY_ID, USER_ID, session_factory


async def _department(code: str, name: str) -> str:
    """Insert a real department, since tests do not seed the HR module."""

    async with session_factory() as db:
        department = Department(
            facility_id=FACILITY_ID,
            code=code,
            name=name,
            department_type="clinical",
            is_active=True,
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(department)
        await db.commit()
        await db.refresh(department)
        return str(department.id)


async def _patient(client: AsyncClient, phone: str = "0700000000") -> str:
    """Register a patient and return their id."""

    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Amina",
            "last_name": "Wanjiku",
            "date_of_birth": "1995-03-10",
            "gender": "female",
            "phone_number": phone,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _visit(client: AsyncClient, patient_id: str, **overrides) -> dict:
    """Open a visit and return the created encounter."""

    payload = {
        "patient_id": patient_id,
        "encounter_type": "opd",
        "chief_complaint": "Fever",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/encounters", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _rows(board: dict, **match) -> list[dict]:
    """The live board rows matching every field given."""

    return [
        row
        for row in board["items"]
        if all(row.get(key) == value for key, value in match.items())
    ]


async def _run_lab_order(
    client: AsyncClient,
    *,
    patient_id: str,
    encounter_id: str,
    priority: str,
    test_code: str,
    test_name: str,
    result_value: str,
    result_numeric: float | None = None,
) -> None:
    """Order, collect, enter and verify one lab result."""

    order = await client.post(
        f"/api/v1/encounters/{encounter_id}/lab-orders",
        json={
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "priority": priority,
            "tests": [{"test_code": test_code, "test_name": test_name}],
        },
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    collect = await client.post(
        f"/api/v1/laboratory/orders/{order_id}/collect",
        json={"specimen_id": f"{test_code}-001"},
    )
    assert collect.status_code == 200, collect.text

    detail = await client.get(f"/api/v1/laboratory/orders/{order_id}")
    assert detail.status_code == 200, detail.text
    result_id = detail.json()["results"][0]["id"]

    enter = await client.post(
        f"/api/v1/laboratory/results/{result_id}/enter",
        json={
            "result_value": result_value,
            "result_numeric": result_numeric,
            "interpretation": "abnormal",
        },
    )
    assert enter.status_code == 200, enter.text

    verify = await client.post(
        f"/api/v1/laboratory/results/{result_id}/verify",
        json={"notes": "Released"},
    )
    assert verify.status_code == 200, verify.text


@pytest.mark.asyncio
async def test_a_lab_order_puts_the_patient_in_the_lab_queue(
    client: AsyncClient,
) -> None:
    """Ordering tests is a wait: the lab board lights up without a second step."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)

    order = await client.post(
        f"/api/v1/encounters/{encounter['id']}/lab-orders",
        json={
            "encounter_id": encounter["id"],
            "patient_id": patient,
            "priority": "urgent",
            "clinical_info": "Fever x5 days",
            "tests": [{"test_code": "CBC", "test_name": "Complete Blood Count"}],
        },
    )
    assert order.status_code == 201, order.text

    board = (await client.get("/api/v1/queue")).json()
    lab = [
        row
        for row in _rows(board, patient_id=patient, status="WAITING")
        if row["ticket_number"].startswith("LAB")
    ]

    assert len(lab) == 1
    assert lab[0]["priority"] == 4
    assert lab[0]["notes"].startswith("Lab order")
    assert lab[0]["encounter_id"] is None


@pytest.mark.asyncio
async def test_a_lab_order_routes_into_a_named_lab_department(
    client: AsyncClient,
) -> None:
    """When the facility has a lab unit, the ticket belongs to it."""

    lab = await _department("LAB", "Laboratory")
    patient = await _patient(client)
    encounter = await _visit(client, patient)

    await client.post(
        f"/api/v1/encounters/{encounter['id']}/lab-orders",
        json={
            "encounter_id": encounter["id"],
            "patient_id": patient,
            "tests": [{"test_code": "CBC", "test_name": "Complete Blood Count"}],
        },
    )

    board = (await client.get("/api/v1/queue")).json()
    mine = _rows(board, patient_id=patient, department_id=lab, status="WAITING")

    assert mine
    assert mine[0]["ticket_number"].startswith("LAB")


@pytest.mark.asyncio
async def test_an_imaging_order_puts_the_patient_in_the_imaging_queue(
    client: AsyncClient,
) -> None:
    """Ordering a study is a wait: the imaging board gets its own number."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)

    order = await client.post(
        "/api/v1/radiology/orders",
        json={
            "patient_id": patient,
            "encounter_id": encounter["id"],
            "modality": "xray",
            "body_part": "chest",
            "study_description": "Chest X-ray PA",
            "priority": "stat",
        },
    )
    assert order.status_code == 201, order.text

    board = (await client.get("/api/v1/queue")).json()
    rad = [
        row
        for row in _rows(board, patient_id=patient, status="WAITING")
        if row["ticket_number"].startswith("RAD")
    ]

    assert len(rad) == 1
    assert rad[0]["priority"] == 5
    assert rad[0]["notes"].startswith("Imaging order")


@pytest.mark.asyncio
async def test_ready_lab_results_call_the_patient_back_for_review(
    client: AsyncClient,
) -> None:
    """The result is a second wait: the patient returns to the doctor's board."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)
    encounter_id = encounter["id"]

    called = await client.post("/api/v1/queue/call-next", json={})
    assert called.status_code == 200, called.text
    assert called.json()["encounter_id"] == encounter_id

    await _run_lab_order(
        client,
        patient_id=patient,
        encounter_id=encounter_id,
        priority="routine",
        test_code="BC",
        test_name="Blood Culture",
        result_value="No growth",
    )

    board = (await client.get("/api/v1/queue")).json()
    review = _rows(
        board, patient_id=patient, encounter_id=encounter_id, status="WAITING"
    )

    assert len(review) == 1
    assert review[0]["priority"] == 4
    assert review[0]["notes"].startswith("Lab results ready")
    assert review[0]["ticket_number"].startswith("OPD")


@pytest.mark.asyncio
async def test_a_critical_lab_result_is_returned_ahead_of_a_routine_review(
    client: AsyncClient,
) -> None:
    """A critical value is called back as an emergency, not a routine review."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)
    encounter_id = encounter["id"]
    await client.post("/api/v1/queue/call-next", json={})

    await _run_lab_order(
        client,
        patient_id=patient,
        encounter_id=encounter_id,
        priority="stat",
        test_code="K",
        test_name="Potassium",
        result_value="7.2",
        result_numeric=7.2,
    )

    board = (await client.get("/api/v1/queue")).json()
    review = [
        row
        for row in _rows(board, patient_id=patient, status="WAITING")
        if row["notes"] and row["notes"].startswith("Lab results ready")
    ]

    assert review
    assert review[0]["priority"] == 5
    assert review[0]["triage_category"] == "emergency"


@pytest.mark.asyncio
async def test_ready_imaging_reports_call_the_patient_back_for_review(
    client: AsyncClient,
) -> None:
    """An imaging report is a second wait, exactly like a lab result."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)
    encounter_id = encounter["id"]
    await client.post("/api/v1/queue/call-next", json={})

    order = (
        await client.post(
            "/api/v1/radiology/orders",
            json={
                "patient_id": patient,
                "encounter_id": encounter_id,
                "modality": "xray",
                "body_part": "chest",
                "study_description": "Chest X-ray PA",
                "priority": "routine",
            },
        )
    ).json()
    order_id = order["id"]

    pay = await client.post(
        f"/api/v1/billing/pos/encounters/{encounter_id}/pay",
        json={
            "payment_method": "cash",
            "reference_type": "imaging_order",
            "reference_id": order_id,
        },
    )
    assert pay.status_code == 201, pay.text

    perform = await client.post(
        f"/api/v1/radiology/orders/{order_id}/perform",
        json={"accession_number": "ACC-001"},
    )
    assert perform.status_code == 200, perform.text

    detail = (await client.get(f"/api/v1/radiology/orders/{order_id}")).json()
    result_id = detail["result"]["id"]

    report = await client.post(
        f"/api/v1/radiology/results/{result_id}/report",
        json={"impression": "No acute abnormality"},
    )
    assert report.status_code == 200, report.text

    verify = await client.post(
        f"/api/v1/radiology/results/{result_id}/verify",
        json={"notes": "Released"},
    )
    assert verify.status_code == 200, verify.text

    board = (await client.get("/api/v1/queue")).json()
    review = [
        row
        for row in _rows(board, patient_id=patient, status="WAITING")
        if row["notes"] and row["notes"].startswith("Imaging report ready")
    ]

    assert review
    assert review[0]["priority"] == 4


@pytest.mark.asyncio
async def test_a_critical_vital_sign_moves_the_patient_up_the_opd_queue(
    client: AsyncClient,
) -> None:
    """Systolic 200 is not a note: it is the patient's turn."""

    earlier = await _patient(client, phone="0700000001")
    await _visit(client, earlier)
    critical = await _patient(client, phone="0700000002")
    encounter = await _visit(client, critical)

    vitals = await client.post(
        f"/api/v1/encounters/{encounter['id']}/vitals",
        json={
            "encounter_id": encounter["id"],
            "patient_id": critical,
            "systolic_bp": 200,
            "diastolic_bp": 110,
            "heart_rate": 120,
            "temperature": 39.6,
        },
    )
    assert vitals.status_code == 201, vitals.text
    assert vitals.json()["is_critical"] is True

    board = (await client.get("/api/v1/queue")).json()
    mine = _rows(board, patient_id=critical, status="WAITING")
    assert mine and mine[0]["priority"] == 4

    called = await client.post("/api/v1/queue/call-next", json={})
    assert called.status_code == 200, called.text
    assert called.json()["patient_id"] == critical


@pytest.mark.asyncio
async def test_a_prescription_puts_the_patient_in_the_pharmacy_queue(
    client: AsyncClient,
) -> None:
    """Collecting medicine is a wait: the dispensary gets its own number."""

    patient = await _patient(client)
    encounter = await _visit(client, patient)

    response = await client.post(
        f"/api/v1/encounters/{encounter['id']}/prescriptions",
        json={
            "encounter_id": encounter["id"],
            "patient_id": patient,
            "drug_name": "Paracetamol",
            "dosage": "500mg",
            "dosage_value": 500,
            "dosage_unit": "mg",
            "route": "oral",
            "frequency": "tds",
            "duration_days": 3,
            "quantity": 9,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["blocked"] is False

    board = (await client.get("/api/v1/queue")).json()
    pharm = [
        row
        for row in _rows(board, patient_id=patient, status="WAITING")
        if row["ticket_number"].startswith("PHARM")
    ]

    assert len(pharm) == 1
    assert pharm[0]["notes"].startswith("Prescription")
