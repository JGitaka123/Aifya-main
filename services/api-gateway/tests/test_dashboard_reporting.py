"""Dashboard reporting: the landing page must answer in one round trip."""

from datetime import datetime

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Every counter the dashboard screen renders. The web client reads all of
# these, so a missing key is a blank card on the landing page.
DASHBOARD_FIELDS = {
    "total_patients",
    "patients_today",
    "patients_this_month",
    "opd_visits_today",
    "opd_visits_month",
    "active_admissions",
    "admissions_today",
    "discharges_today",
    "bed_occupancy_rate",
    "appointments_today",
    "appointments_completed",
    "appointments_no_show",
    "lab_orders_today",
    "lab_pending",
    "lab_critical",
    "prescriptions_today",
    "dispensed_today",
    "stock_alerts",
    "revenue_today",
    "revenue_month",
    "outstanding_balance",
    "imaging_orders_today",
    "imaging_pending_reports",
    "active_anc_profiles",
    "deliveries_month",
    "immunizations_month",
}


def _patient(phone: str) -> dict:
    """Minimal registration payload accepted by POST /patients."""
    return {
        "first_name": "Dash",
        "last_name": "Board",
        "date_of_birth": "1990-01-01",
        "gender": "male",
        "phone_number": phone,
    }


async def test_the_dashboard_endpoint_answers_with_every_counter(
    client: AsyncClient,
) -> None:
    """An empty facility still returns the full, correctly typed payload."""
    response = await client.get("/api/v1/reports/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert DASHBOARD_FIELDS <= set(body)
    for field in DASHBOARD_FIELDS - {"bed_occupancy_rate"}:
        assert isinstance(body[field], int), field
    assert body["bed_occupancy_rate"] == 0.0
    assert body["total_patients"] == 0


async def test_a_registered_patient_lands_in_todays_counters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Registration flows straight through to the dashboard counters."""
    created = await client.post("/api/v1/patients", json=_patient("0712345678"))
    assert created.status_code == 201

    # Pin the registration timestamp to "now" so the day filter is
    # deterministic whatever the database clock reports.
    await db_session.execute(
        text("update patients set created_at = :now"),
        {"now": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
    )
    await db_session.commit()

    body = (await client.get("/api/v1/reports/dashboard")).json()
    assert body["total_patients"] == 1
    assert body["patients_today"] == 1
    assert body["patients_this_month"] == 1


async def test_the_dashboard_trends_endpoint_returns_series(
    client: AsyncClient,
) -> None:
    """The trend charts need five labelled day-series."""
    response = await client.get("/api/v1/reports/dashboard/trends?days=14")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "opd_visits",
        "admissions",
        "revenue",
        "lab_orders",
        "appointments",
    }
    for series in body.values():
        assert isinstance(series, list)


async def test_the_top_diagnoses_endpoint_returns_a_list(
    client: AsyncClient,
) -> None:
    """The top-diagnoses card reads a bare list."""
    response = await client.get("/api/v1/reports/dashboard/top-diagnoses?limit=5")

    assert response.status_code == 200
    assert response.json() == []
