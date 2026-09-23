"""Tests for the Celery reminder task bodies (comms scheduler).

The synchronous @shared_task wrappers use asyncio.run, so these exercise
the async implementations directly and point them at the test DB session.
"""

import uuid
from datetime import date, time, timedelta

import pytest

from app.models.appointment import Appointment
from app.models.mch import ANCVisit, ChildRecord
from app.models.patient import Patient
from app.services.comms import scheduler
from tests.conftest import FACILITY_ID
from tests.conftest import session_factory as _session_factory


@pytest.fixture(autouse=True)
def _point_scheduler_at_test_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the scheduler open sessions on the test engine."""
    monkeypatch.setattr(scheduler, "async_session_factory", _session_factory)


async def _make_patient(first_name: str = "Amina") -> uuid.UUID:
    """Insert a patient and return its id."""
    async with _session_factory() as session:
        patient = Patient(
            facility_id=FACILITY_ID,
            mrn=f"MRN-{uuid.uuid4().hex[:8]}",
            first_name=first_name,
            last_name="Test",
            date_of_birth=date(1995, 1, 1),
            gender="female",
            phone_number="0712345678",
        )
        session.add(patient)
        await session.commit()
        return patient.id


@pytest.mark.asyncio
async def test_appointment_reminder_sent_and_flagged(client) -> None:
    """An appointment in the next 24h is reminded and marked reminder_sent."""
    patient_id = await _make_patient()
    async with _session_factory() as session:
        appt = Appointment(
            facility_id=FACILITY_ID,
            patient_id=patient_id,
            doctor_id=uuid.uuid4(),
            booked_by=uuid.uuid4(),
            appointment_number=f"APT-{uuid.uuid4().hex[:6]}",
            appointment_date=date.today() + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(9, 15),
            appointment_type="consultation",
            status="scheduled",
        )
        session.add(appt)
        await session.commit()
        appt_id = appt.id

    result = await scheduler._schedule_appointment_reminders()
    assert result["reminders_queued"] == 1

    async with _session_factory() as session:
        refreshed = await session.get(Appointment, appt_id)
        assert refreshed is not None
        assert refreshed.reminder_sent is True
        assert refreshed.reminder_sent_at is not None


@pytest.mark.asyncio
async def test_appointment_reminder_not_resent(client) -> None:
    """Already-reminded appointments are skipped on the next run."""
    patient_id = await _make_patient()
    async with _session_factory() as session:
        session.add(
            Appointment(
                facility_id=FACILITY_ID,
                patient_id=patient_id,
                doctor_id=uuid.uuid4(),
                booked_by=uuid.uuid4(),
                appointment_number=f"APT-{uuid.uuid4().hex[:6]}",
                appointment_date=date.today() + timedelta(days=1),
                start_time=time(9, 0),
                end_time=time(9, 15),
                appointment_type="consultation",
                status="scheduled",
                reminder_sent=True,
            )
        )
        await session.commit()

    result = await scheduler._schedule_appointment_reminders()
    assert result["reminders_queued"] == 0


@pytest.mark.asyncio
async def test_anc_reminder_targets_three_days_out(client) -> None:
    """ANC patients with a visit exactly 3 days out are reminded."""
    patient_id = await _make_patient("Wanjiru")
    async with _session_factory() as session:
        session.add(
            ANCVisit(
                facility_id=FACILITY_ID,
                anc_profile_id=uuid.uuid4(),
                patient_id=patient_id,
                provider_id=uuid.uuid4(),
                visit_number=1,
                visit_date=date.today(),
                next_visit_date=date.today() + timedelta(days=3),
            )
        )
        await session.commit()

    result = await scheduler._schedule_anc_reminders()
    assert result["anc_reminders_queued"] == 1

    # A visit 5 days out is not yet reminded.
    async with _session_factory() as session:
        session.add(
            ANCVisit(
                facility_id=FACILITY_ID,
                anc_profile_id=uuid.uuid4(),
                patient_id=patient_id,
                provider_id=uuid.uuid4(),
                visit_number=2,
                visit_date=date.today(),
                next_visit_date=date.today() + timedelta(days=5),
            )
        )
        await session.commit()
    result2 = await scheduler._schedule_anc_reminders()
    assert result2["anc_reminders_queued"] == 1  # still just the 3-day one


@pytest.mark.asyncio
async def test_immunization_reminder_on_milestone(client) -> None:
    """A child whose KEPI milestone falls 7 days out triggers a heads-up."""
    guardian_id = await _make_patient("Njeri")
    # 6-week milestone lands 7 days from now → born 5 weeks + (7 days ago).
    dob = date.today() + timedelta(days=7) - timedelta(weeks=6)
    child_patient_id = await _make_patient("Baby")
    async with _session_factory() as session:
        session.add(
            ChildRecord(
                facility_id=FACILITY_ID,
                patient_id=child_patient_id,
                mother_patient_id=guardian_id,
                child_number=f"CH-{uuid.uuid4().hex[:6]}",
                date_of_birth=dob,
                sex="female",
            )
        )
        await session.commit()

    result = await scheduler._schedule_immunization_reminders()
    assert result["immunization_reminders_queued"] == 1


@pytest.mark.asyncio
async def test_immunization_no_reminder_off_milestone(client) -> None:
    """A child not near any milestone is not reminded."""
    guardian_id = await _make_patient("Akinyi")
    dob = date.today() - timedelta(weeks=3)  # next milestone (6w) is 3 wks out
    child_patient_id = await _make_patient("Baby2")
    async with _session_factory() as session:
        session.add(
            ChildRecord(
                facility_id=FACILITY_ID,
                patient_id=child_patient_id,
                mother_patient_id=guardian_id,
                child_number=f"CH-{uuid.uuid4().hex[:6]}",
                date_of_birth=dob,
                sex="male",
            )
        )
        await session.commit()

    result = await scheduler._schedule_immunization_reminders()
    assert result["immunization_reminders_queued"] == 0
