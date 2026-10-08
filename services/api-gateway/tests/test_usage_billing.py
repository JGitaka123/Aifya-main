"""Facility usage billing: 20 KES per patient-day.

Aifya charges the hospital for every patient-day of use: a patient seen at
reception, a patient who arrived through the emergency department, and every
calendar day an inpatient spends on a ward. A patient who comes through more
than one of those doors on the same day is charged once.

These tests pin the arithmetic, the deduplication and the month boundaries,
because the hospital is asked to pay the answer. They also pin that the Reports
calculator and the HR Aifya Usage ledger are the same figure - two screens
disagreeing about one month is exactly the failure this work removed.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient

from app.models.encounter import Encounter
from app.models.ipd import Admission
from app.models.patient import Patient
from app.services.aifya_usage_service import AifyaUsageService
from app.services.usage_billing_service import UsageBillingService
from tests.conftest import FACILITY_ID, session_factory

#: 20 KES a patient-day, in cents -- the agreed rate card.
RATE = 2_000

#: The billing month every test works in.
MONTH = "2026-09"

#: Reference day for admissions that are still open. Mid-month, so it is the
#: reference day that clips the open stay rather than the month end.
REFERENCE = date(2026, 9, 10)


def _patient(index: int) -> Patient:
    """
    Build a registered patient.

    @param index: Distinguishing suffix for the MRN
    @returns Patient row ready to add to the session
    """
    return Patient(
        id=uuid.uuid4(),
        facility_id=FACILITY_ID,
        mrn=f"MRN-{index:04d}",
        first_name="Test",
        last_name=f"Patient{index}",
        date_of_birth=date(1990, 1, 1),
        gender="female",
        phone_number="0700000000",
    )


def _encounter(
    patient_id: uuid.UUID, encounter_type: str, when: datetime
) -> Encounter:
    """
    Build a clinical encounter at a controlled moment.

    @param patient_id: Patient the encounter belongs to
    @param encounter_type: Encounter type, e.g. ``opd`` or ``emergency``
    @param when: When the encounter happened
    @returns Encounter row ready to add to the session
    """
    return Encounter(
        id=uuid.uuid4(),
        facility_id=FACILITY_ID,
        patient_id=patient_id,
        encounter_type=encounter_type,
        encounter_date=when,
        status="completed",
    )


def _admission(
    patient_id: uuid.UUID,
    admitted: datetime,
    discharged: datetime | None,
    index: int,
) -> Admission:
    """
    Build an inpatient admission with controlled dates.

    @param patient_id: Patient the admission belongs to
    @param admitted: Admission moment
    @param discharged: Discharge moment, or None while still admitted
    @param index: Distinguishing suffix for the admission number
    @returns Admission row ready to add to the session
    """
    return Admission(
        id=uuid.uuid4(),
        facility_id=FACILITY_ID,
        encounter_id=uuid.uuid4(),
        patient_id=patient_id,
        ward_id=uuid.uuid4(),
        bed_id=uuid.uuid4(),
        admission_number=f"ADM-{index:04d}",
        status="admitted" if discharged is None else "discharged",
        admitted_at=admitted,
        discharged_at=discharged,
    )


async def _seed_september() -> list[uuid.UUID]:
    """
    Seed a month whose expected charge is knowable by hand.

    * Patient 1 was seen at reception **and** was in a bed on 5 September, so
      that day must be charged once, as an inpatient.
    * Patient 6's stay is closed inside the month: 1st to 4th, four bed-days.
    * Patient 1's stay is open, so it runs to the reference day.
    * Patient 7's stay is entirely in July, and contributes nothing to
      September; its August encounter is August's alone.

    @returns The seeded patient ids, in order
    """
    async with session_factory() as db:
        patients = [_patient(i) for i in range(1, 8)]
        db.add_all(patients)
        await db.flush()

        db.add_all(
            [
                _encounter(
                    patients[0].id, "opd", datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
                ),
                _encounter(
                    patients[1].id, "opd", datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
                ),
                _encounter(
                    patients[2].id, "opd", datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
                ),
                _encounter(
                    patients[3].id,
                    "emergency",
                    datetime(2026, 9, 6, 14, 0, tzinfo=UTC),
                ),
                _encounter(
                    patients[4].id,
                    "emergency",
                    datetime(2026, 9, 7, 14, 0, tzinfo=UTC),
                ),
                # August's own usage, so the trend has something to separate.
                _encounter(
                    patients[3].id,
                    "emergency",
                    datetime(2026, 8, 21, 14, 0, tzinfo=UTC),
                ),
                _encounter(
                    patients[6].id, "opd", datetime(2026, 8, 20, 9, 0, tzinfo=UTC)
                ),
            ]
        )
        db.add_all(
            [
                _admission(
                    patients[0].id, datetime(2026, 8, 28, 8, 0, tzinfo=UTC), None, 1
                ),
                _admission(
                    patients[5].id,
                    datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
                    datetime(2026, 9, 4, 10, 0, tzinfo=UTC),
                    2,
                ),
                _admission(
                    patients[6].id,
                    datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
                    datetime(2026, 7, 3, 10, 0, tzinfo=UTC),
                    3,
                ),
            ]
        )
        await db.commit()
        return [patient.id for patient in patients]


async def _lines(facility_id: uuid.UUID = FACILITY_ID, **kwargs) -> dict:
    """
    Build one month's report and index its lines by key.

    @param facility_id: Facility UUID
    @param kwargs: Overrides for :meth:`UsageBillingService.build_report`
    @returns Mapping of line key to line
    """
    options = {"rate_cents": RATE, "today": REFERENCE}
    options.update(kwargs)
    async with session_factory() as db:
        report = await UsageBillingService(db).build_report(
            facility_id, MONTH, **options
        )
    return {line.key: line for line in report.lines}


@pytest.mark.asyncio
async def test_a_patient_in_a_bed_is_charged_once_that_day() -> None:
    """Patient 1 was at reception and in a bed on 5 September - one charge."""
    await _seed_september()
    lines = await _lines()

    # Only patients 2 and 3 are charged to registration: patient 1's encounter
    # on the 5th is swallowed by the bed they were lying in that day.
    assert lines["reception_registrations"].quantity == 2
    assert lines["emergency_registrations"].quantity == 2


@pytest.mark.asyncio
async def test_both_ends_of_a_stay_are_charged() -> None:
    """A closed stay from the 1st to the 4th is four bed-days, not three."""
    await _seed_september()
    # Four days for the closed stay, ten for the open one running to the 10th.
    assert (await _lines())["ipd_bed_days"].quantity == 14


@pytest.mark.asyncio
async def test_an_open_stay_stops_at_the_reference_day() -> None:
    """An admission still open is charged up to the day being asked about."""
    await _seed_september()
    # To the end of the month the open stay is thirty days, not ten.
    assert (
        await _lines(today=date(2026, 9, 30))
    )["ipd_bed_days"].quantity == 34


@pytest.mark.asyncio
async def test_report_prices_every_patient_day() -> None:
    """Every channel is metered, multiplied by the rate and totalled."""
    await _seed_september()
    async with session_factory() as db:
        report = await UsageBillingService(db).build_report(
            FACILITY_ID, MONTH, RATE, today=REFERENCE
        )

    assert report.total_quantity == 18
    for line in report.lines:
        assert line.rate_cents == RATE
        assert line.amount_cents == line.quantity * RATE
    assert report.total_cents == 18 * RATE


@pytest.mark.asyncio
async def test_report_honours_a_rate_override() -> None:
    """The calculator can be run at a different rate without changing data."""
    await _seed_september()
    async with session_factory() as db:
        report = await UsageBillingService(db).build_report(
            FACILITY_ID, MONTH, 5_000, today=REFERENCE
        )

    assert report.rate_cents == 5_000
    assert report.total_cents == 18 * 5_000


@pytest.mark.asyncio
async def test_report_defaults_to_the_facility_rate() -> None:
    """With no rate typed in, the calculator uses the billed rate."""
    await _seed_september()
    async with session_factory() as db:
        await AifyaUsageService(db).set_config(FACILITY_ID, 3_500, "KES", None)
        await db.commit()

    async with session_factory() as db:
        report = await UsageBillingService(db).build_report(
            FACILITY_ID, MONTH, today=REFERENCE
        )

    assert report.rate_cents == 3_500
    assert report.currency == "KES"
    assert report.total_cents == 18 * 3_500


@pytest.mark.asyncio
async def test_report_agrees_with_the_usage_ledger() -> None:
    """The calculator and the HR ledger must never quote different days."""
    await _seed_september()
    async with session_factory() as db:
        buckets = await AifyaUsageService(db).day_buckets(
            FACILITY_ID, date(2026, 9, 1), date(2026, 9, 30), today=REFERENCE
        )
        report = await UsageBillingService(db).build_report(
            FACILITY_ID, MONTH, RATE, today=REFERENCE
        )

    assert all(
        registration + emergency + inpatient == total
        for registration, emergency, inpatient, total in buckets.values()
    )
    assert sum(total for *_, total in buckets.values()) == report.total_quantity
    assert report.total_quantity == 18


@pytest.mark.asyncio
async def test_trend_reports_each_month_separately() -> None:
    """August's charge is August's, not September's."""
    await _seed_september()

    async with session_factory() as db:
        trend = await UsageBillingService(db).build_trend(
            FACILITY_ID, 3, RATE, end_month=MONTH, today=REFERENCE
        )

    months = {entry.month: entry for entry in trend.months}
    assert list(months) == ["2026-07", "2026-08", "2026-09"]

    # September: two registration days, two emergency days, fourteen in a bed.
    assert months["2026-09"].reception_registrations == 2
    assert months["2026-09"].emergency_registrations == 2
    assert months["2026-09"].ipd_bed_days == 14

    # August: the 20th at reception, the 21st in emergency, and the four
    # August days (28th-31st) of the stay that was open when the month ended.
    assert months["2026-08"].reception_registrations == 1
    assert months["2026-08"].emergency_registrations == 1
    assert months["2026-08"].ipd_bed_days == 4

    # July: the only stay began and ended inside July, so it is July's charge.
    assert months["2026-07"].reception_registrations == 0
    assert months["2026-07"].emergency_registrations == 0
    assert months["2026-07"].ipd_bed_days == 3

    assert trend.total_cents == sum(entry.total_cents for entry in trend.months)


@pytest.mark.asyncio
async def test_usage_billing_endpoint_returns_the_month(
    client: AsyncClient,
) -> None:
    """GET /api/v1/reports/usage-billing explains the month's charge."""
    await _seed_september()

    response = await client.get(
        f"/api/v1/reports/usage-billing?month={MONTH}&rate_cents={RATE}"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["month"] == MONTH
    assert body["currency"] == "KES"
    assert body["rate_cents"] == RATE
    assert len(body["lines"]) == 3
    assert body["due_date"] == "2026-10-15"


@pytest.mark.asyncio
async def test_usage_billing_endpoint_follows_the_configured_rate(
    client: AsyncClient,
) -> None:
    """With no rate given, the endpoint uses the rate the facility is billed at."""
    await _seed_september()
    async with session_factory() as db:
        await AifyaUsageService(db).set_config(FACILITY_ID, 3_500, "KES", None)
        await db.commit()

    response = await client.get(f"/api/v1/reports/usage-billing?month={MONTH}")

    assert response.status_code == 200, response.text
    assert response.json()["rate_cents"] == 3_500


@pytest.mark.asyncio
async def test_usage_billing_endpoint_rejects_a_bad_month(
    client: AsyncClient,
) -> None:
    """A month that is not YYYY-MM is refused before it reaches the database."""
    response = await client.get("/api/v1/reports/usage-billing?month=2026-13")

    assert response.status_code == 422
