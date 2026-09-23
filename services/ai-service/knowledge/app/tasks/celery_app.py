"""
Celery application for async document ingestion tasks.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "aifya_knowledge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Africa/Nairobi",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,
    task_time_limit=900,
    task_default_queue="knowledge",
    task_routes={
        "app.tasks.ingest.*": {"queue": "knowledge"},
    },
)
