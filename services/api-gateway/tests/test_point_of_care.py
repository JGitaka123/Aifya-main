"""General testing done in the consultation room.

HIV, malaria RDT, urinalysis and pregnancy tests are run at the bedside, not in
the laboratory, so they are recorded against the encounter and an abnormal
result is flagged rather than left in free-text notes. A priced test is also
itemised on the visit's bill, so the receipt the patient is given lists the
tests that were actually run.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def patient_id(client: AsyncClient) -> str:
    """Create a test patient and return their ID."""
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Mary",
            "last_name": "Achieng",
            "date_of_birth": "1996-11-02",
            "gender": "female",
            "phone_number": "0733000222",
        },
    )
    return response.json()["id"]


@pytest.fixture
async def encounter_id(client: AsyncClient, patient_id: str) -> str:
    """Create an OPD encounter to attach tests to."""
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Routine screening",
        },
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_record_reactive_hiv_test_is_flagged(
    client: AsyncClient, encounter_id: str, patient_id: str
) -> None:
    """A reactive result is abnormal and reaches the chart immediately."""
    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/tests",
        json={
            "test_code": "HIV",
            "test_name": "HIV test",
            "category": "rapid_diagnostic",
            "specimen_type": "blood",
            "result_value": "Reactive",
            "interpretation": "reactive",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["encounter_id"] == encounter_id
    assert data["patient_id"] == patient_id
    assert data["test_name"] == "HIV test"
    assert data["interpretation"] == "reactive"
    assert data["is_abnormal"] is True


@pytest.mark.asyncio
async def test_record_normal_result_is_not_flagged(
    client: AsyncClient, encounter_id: str
) -> None:
    """A normal result is recorded without an abnormal flag."""
    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/tests",
        json={
            "test_code": "GLU",
            "test_name": "Blood glucose",
            "result_value": "5.2",
            "result_numeric": 5.2,
            "result_unit": "mmol/L",
            "interpretation": "normal",
        },
    )

    assert response.status_code == 201
    assert response.json()["is_abnormal"] is False


@pytest.mark.asyncio
async def test_list_tests_for_an_encounter(
    client: AsyncClient, encounter_id: str
) -> None:
    """Recorded tests are returned for the encounter, newest first."""
    await client.post(
        f"/api/v1/encounters/{encounter_id}/tests",
        json={"test_code": "HIV", "test_name": "HIV test", "result_value": "Non-reactive"},
    )
    await client.post(
        f"/api/v1/encounters/{encounter_id}/tests",
        json={"test_code": "MRDT", "test_name": "Malaria RDT", "result_value": "Negative"},
    )

    response = await client.get(f"/api/v1/encounters/{encounter_id}/tests")
    assert response.status_code == 200
    tests = response.json()
    assert len(tests) == 2
    assert {test["test_code"] for test in tests} == {"HIV", "MRDT"}


@pytest.mark.asyncio
async def test_test_on_unknown_encounter_is_not_found(client: AsyncClient) -> None:
    """A test cannot be attached to an encounter that does not exist."""
    response = await client.post(
        f"/api/v1/encounters/{uuid.uuid4()}/tests",
        json={"test_code": "HIV", "test_name": "HIV test", "result_value": "Reactive"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_interpretation_is_rejected(
    client: AsyncClient, encounter_id: str
) -> None:
    """Only known interpretations are accepted."""
    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/tests",
        json={
            "test_code": "HIV",
            "test_name": "HIV test",
            "result_value": "Maybe",
            "interpretation": "probably",
        },
    )
    assert response.status_code == 422


def test_built_in_test_prices_apply_when_facility_configures_nothing() -> None:
    """The OPD panel's standard tests are priced out of the box."""
    from app.services.point_of_care_fee import resolve_point_of_care_price_cents

    assert resolve_point_of_care_price_cents(None, test_code="MRDT") == 20_000
    assert resolve_point_of_care_price_cents(None, test_code="URIN") == 20_000
    assert resolve_point_of_care_price_cents(None, test_code="PREG") == 20_000
    assert resolve_point_of_care_price_cents(None, test_code="GLU") == 15_000
    assert resolve_point_of_care_price_cents(None, test_code="HBSAG") == 30_000
    # HIV screening stays free, and an unknown custom test is never charged
    # without a configured price.
    assert resolve_point_of_care_price_cents(None, test_code="HIV") == 0
    assert resolve_point_of_care_price_cents(None, test_code="hiv") == 0
    assert resolve_point_of_care_price_cents(None, test_code="SOMETHING") == 0


def test_facility_settings_override_point_of_care_prices() -> None:
    """A facility can re-price a test, or switch point-of-care billing off."""
    from app.services.point_of_care_fee import resolve_point_of_care_price_cents

    by_code = {"point_of_care_prices": {"by_test_code": {"MRDT": 35_000}}}
    assert resolve_point_of_care_price_cents(by_code, test_code="MRDT") == 35_000

    fallback = {"point_of_care_prices": {"default_cents": 10_000}}
    assert resolve_point_of_care_price_cents(fallback, test_code="CUSTOM") == 10_000

    switched_off = {"point_of_care_prices": {"default_cents": 0}}
    assert resolve_point_of_care_price_cents(switched_off, test_code="MRDT") == 0


@pytest.mark.asyncio
async def test_priced_test_is_itemised_on_the_visit_bill(
    client: AsyncClient, encounter_id: str
) -> None:
    """A screening test reaches the bill so the printed receipt lists it."""
    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/tests",
        json={
            "test_code": "MRDT",
            "test_name": "Malaria RDT",
            "result_value": "Negative",
            "interpretation": "negative",
        },
    )
    assert response.status_code == 201

    response = await client.get(
        f"/api/v1/billing/pos/encounters/{encounter_id}/charges",
        params={"include_paid": "true"},
    )
    assert response.status_code == 200
    charges = [
        item
        for item in response.json()["items"]
        if item["reference_type"] == "point_of_care"
    ]
    assert len(charges) == 1
    assert charges[0]["reference_id"] == encounter_id
    assert charges[0]["description"] == "OPD: Malaria RDT"
    assert charges[0]["total_cents"] == 20_000
    assert charges[0]["balance_cents"] == 20_000


@pytest.mark.asyncio
async def test_tests_of_one_visit_share_a_single_collectable_charge(
    client: AsyncClient, encounter_id: str
) -> None:
    """The desk collects once and one receipt carries every test run."""
    for code, name in (("MRDT", "Malaria RDT"), ("URIN", "Urinalysis")):
        response = await client.post(
            f"/api/v1/encounters/{encounter_id}/tests",
            json={"test_code": code, "test_name": name, "result_value": "Negative"},
        )
        assert response.status_code == 201

    response = await client.get(
        f"/api/v1/billing/pos/encounters/{encounter_id}/charges",
        params={"include_paid": "true"},
    )
    charges = [
        item
        for item in response.json()["items"]
        if item["reference_type"] == "point_of_care"
    ]
    assert len(charges) == 1
    assert "Malaria RDT" in charges[0]["description"]
    assert "Urinalysis" in charges[0]["description"]
    assert charges[0]["total_cents"] == 40_000


@pytest.mark.asyncio
async def test_free_test_adds_no_charge(
    client: AsyncClient, encounter_id: str
) -> None:
    """A free screening never creates a line the desk has to collect."""
    response = await client.post(
        f"/api/v1/encounters/{encounter_id}/tests",
        json={"test_code": "HIV", "test_name": "HIV test", "result_value": "Non-reactive"},
    )
    assert response.status_code == 201

    response = await client.get(
        f"/api/v1/billing/pos/encounters/{encounter_id}/charges",
        params={"include_paid": "true"},
    )
    assert [
        item
        for item in response.json()["items"]
        if item["reference_type"] == "point_of_care"
    ] == []
