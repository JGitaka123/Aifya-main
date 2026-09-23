"""Celery tasks for automated patient communication scheduling.

These run under the Celery worker/beat defined in app.worker. Each task
opens its own async DB session (Celery tasks are synchronous, so an
asyncio bridge is used), queries the relevant schedule, and sends
reminders through CommunicationService — which enforces DPA consent and
delivers via the configured SMS/WhatsApp provider.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import UTC, date, datetime, timedelta

import structlog
from celery import shared_task
from sqlalchemy import select

from app.database import async_session_factory
from app.models.appointment import Appointment
from app.models.mch import ANCVisit, ChildRecord
from app.models.patient import Patient
from app.services.comms.models import (
    MessageCategory,
    MessageChannel,
    SendMessageRequest,
)
from app.services.comms.service import CommunicationService

logger = structlog.get_logger(__name__)

# Appointment types that map to a specialised reminder category.
_CATEGORY_BY_APPT_TYPE = {
    "anc": MessageCategory.anc_reminder,
    "vaccination": MessageCategory.immunization_reminder,
}

# Standard Kenya KEPI immunization milestones (weeks from birth). Used only
# to send a non-clinical "immunization may be due" heads-up — never to
# assert which specific vaccine is due.
_KEPI_MILESTONE_WEEKS = (6, 10, 14, 39, 78)  # 6/10/14 wks, ~9 mo, ~18 mo


def _run[T](coro: Awaitable[T]) -> T:
    """Run an async coroutine from a synchronous Celery task."""
    return asyncio.run(coro)  # type: ignore[arg-type]


async def _send_reminder(
    service: CommunicationService,
    facility_id: object,
    patient: Patient,
    category: MessageCategory,
    body: str,
) -> bool:
    """
    Send one reminder, swallowing per-patient consent/validation errors so a
    single opt-out never aborts the batch.

    @param service: Communication service
    @param facility_id: Facility UUID
    @param patient: Recipient patient
    @param category: Message category (drives consent bucket)
    @param body: Message text
    @returns Whether the message was accepted for delivery
    """
    try:
        await service.send_message(
            facility_id=facility_id,  # type: ignore[arg-type]
            request=SendMessageRequest(
                patient_id=patient.id,
                channel=MessageChannel.sms,
                category=category,
                body=body,
            ),
            recipient_phone=patient.phone_number,
        )
        return True
    except ValueError as exc:
        logger.info(
            "reminder_skipped", patient_id=str(patient.id), reason=str(exc)
        )
        return False


@shared_task(name="comms.schedule_appointment_reminders")
def schedule_appointment_reminders() -> dict[str, int]:
    """
    Send reminders for appointments in the next 24 hours that have not yet
    been reminded, then mark them reminder_sent. Runs hourly via beat.

    @returns Dict with count of reminders queued
    """
    return _run(_schedule_appointment_reminders())


async def _schedule_appointment_reminders() -> dict[str, int]:
    now = datetime.now(UTC)
    window_end = (now + timedelta(hours=24)).date()
    today = now.date()
    queued = 0

    async with async_session_factory() as db:
        service = CommunicationService(db)
        result = await db.execute(
            select(Appointment, Patient)
            .join(Patient, Appointment.patient_id == Patient.id)
            .where(
                Appointment.is_deleted == False,  # noqa: E712
                Appointment.reminder_sent == False,  # noqa: E712
                Appointment.status.in_(["scheduled", "confirmed"]),
                Appointment.appointment_date >= today,
                Appointment.appointment_date <= window_end,
            )
        )
        for appt, patient in result.all():
            category = _CATEGORY_BY_APPT_TYPE.get(
                appt.appointment_type, MessageCategory.appointment_reminder
            )
            body = (
                f"Reminder: {patient.first_name}, you have an appointment at "
                f"the facility on {appt.appointment_date.isoformat()} at "
                f"{appt.start_time.strftime('%H:%M')}. Reply to reschedule."
            )
            if await _send_reminder(
                service, appt.facility_id, patient, category, body
            ):
                queued += 1
            appt.reminder_sent = True
            appt.reminder_sent_at = now
        await db.commit()

    logger.info("appointment_reminders_completed", queued=queued)
    return {"reminders_queued": queued}


@shared_task(name="comms.schedule_anc_reminders")
def schedule_anc_reminders() -> dict[str, int]:
    """
    Remind ANC patients whose next scheduled visit is three days out.
    Runs daily via beat (single reminder per visit at the 3-day mark).

    @returns Dict with count of reminders queued
    """
    return _run(_schedule_anc_reminders())


async def _schedule_anc_reminders() -> dict[str, int]:
    target = date.today() + timedelta(days=3)
    queued = 0

    async with async_session_factory() as db:
        service = CommunicationService(db)
        result = await db.execute(
            select(ANCVisit, Patient)
            .join(Patient, ANCVisit.patient_id == Patient.id)
            .where(
                ANCVisit.is_deleted == False,  # noqa: E712
                ANCVisit.next_visit_date == target,
            )
        )
        for _visit, patient in result.all():
            body = (
                f"Reminder: {patient.first_name}, your next antenatal (ANC) "
                f"visit is on {target.isoformat()}. Please attend for you and "
                "your baby's health."
            )
            if await _send_reminder(
                service, patient.facility_id, patient,
                MessageCategory.anc_reminder, body,
            ):
                queued += 1
        await db.commit()

    logger.info("anc_reminders_completed", queued=queued)
    return {"anc_reminders_queued": queued}


@shared_task(name="comms.schedule_immunization_reminders")
def schedule_immunization_reminders() -> dict[str, int]:
    """
    Send a heads-up to caregivers whose child crosses a KEPI immunization
    milestone in the next 7 days. Deliberately generic ("may be due") — it
    is a scheduling nudge, not a clinical determination of which vaccine is
    owed. Runs weekly via beat.

    @returns Dict with count of reminders queued
    """
    return _run(_schedule_immunization_reminders())


async def _schedule_immunization_reminders() -> dict[str, int]:
    # Remind exactly 7 days before each milestone so a daily beat run sends
    # a single heads-up per milestone per child (idempotent by construction).
    target = date.today() + timedelta(days=7)
    queued = 0

    async with async_session_factory() as db:
        service = CommunicationService(db)
        result = await db.execute(
            select(ChildRecord, Patient)
            .join(Patient, ChildRecord.mother_patient_id == Patient.id)
            .where(ChildRecord.is_deleted == False)  # noqa: E712
        )
        for child, guardian in result.all():
            milestone_dates = [
                child.date_of_birth + timedelta(weeks=w)
                for w in _KEPI_MILESTONE_WEEKS
            ]
            if target not in milestone_dates:
                continue
            body = (
                f"Reminder: {guardian.first_name}, your child may be due for a "
                "routine immunization this week. Please visit the clinic to "
                "check their vaccination schedule."
            )
            if await _send_reminder(
                service, guardian.facility_id, guardian,
                MessageCategory.immunization_reminder, body,
            ):
                queued += 1
        await db.commit()

    logger.info("immunization_reminders_completed", queued=queued)
    return {"immunization_reminders_queued": queued}


@shared_task(name="comms.check_unsent_messages")
def check_unsent_messages() -> dict[str, int]:
    """
    Retry failed/queued messages (up to 3 attempts each). Runs every 30
    minutes via beat.

    @returns Dict with count of messages retried
    """
    return _run(_check_unsent_messages())


async def _check_unsent_messages() -> dict[str, int]:
    async with async_session_factory() as db:
        service = CommunicationService(db)
        retried = await service.retry_failed_messages(max_retries=3)
    logger.info("check_unsent_messages_completed", retried=retried)
    return {"messages_retried": retried}


# Beat schedule is registered in app/worker.py: appointment reminders
# hourly, ANC + immunization daily, unsent-message retry every 30 minutes.
