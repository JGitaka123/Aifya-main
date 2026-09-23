"""
Celery application for background tasks and scheduled jobs.

Run the worker and beat scheduler alongside the API:

    celery -A app.worker worker --loglevel=info
    celery -A app.worker beat --loglevel=info

Task modules register themselves via the `include` list below; the DHIS2
module additionally imports `celery_app` from here to attach its tasks.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "aifya",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.services.comms.scheduler",
        "app.services.dhis2.scheduler",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Nairobi",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    # Patient communication reminders (see app/services/comms/scheduler.py)
    "appointment-reminders-hourly": {
        "task": "comms.schedule_appointment_reminders",
        "schedule": crontab(minute=0),
    },
    "anc-reminders-daily": {
        "task": "comms.schedule_anc_reminders",
        "schedule": crontab(hour=7, minute=0),
    },
    "immunization-reminders-daily": {
        "task": "comms.schedule_immunization_reminders",
        "schedule": crontab(hour=7, minute=30),
    },
    "retry-unsent-messages": {
        "task": "comms.check_unsent_messages",
        "schedule": crontab(minute="*/30"),
    },
}
