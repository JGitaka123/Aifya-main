"""
Celery wrapper around the shared ingestion pipeline.

Only loaded when INGEST_MODE=celery. The pipeline itself lives in
``app.services.ingest_pipeline`` so the very same code also runs inline in the
upload request without Redis or a worker process.
"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from structlog import get_logger

from app.config import get_settings
from app.services.ingest_pipeline import run_ingest
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()


@celery_app.task(
    name="app.tasks.ingest.ingest_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def ingest_document(
    self,
    document_id: str,
    facility_id: str,
    object_key: str,
    mime_type: str,
    document_title: str,
    category: str,
    department: str | None = None,
) -> dict:
    """
    Ingest one document, retrying on failure.

    @param document_id: Document UUID string
    @param facility_id: Facility UUID string
    @param object_key: Storage object key of the uploaded file
    @param mime_type: File MIME type
    @param document_title: Document title for the vector payload
    @param category: Document category
    @param department: Optional department
    @returns Dict with status, chunk_count and page_count
    """

    def report(state: str, percent: int) -> None:
        """
        Publish pipeline progress to the Celery result backend.

        @param state: Pipeline stage name
        @param percent: Completion percentage
        """
        self.update_state(state=state, meta={"progress": percent})

    async def _run() -> dict:
        """
        Drive the async pipeline from this synchronous worker.

        A fresh NullPool engine is built per task because asyncio.run gives
        each invocation its own event loop, and pooled asyncpg connections are
        bound to the loop that opened them.

        @returns Pipeline result dict
        """
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                return await run_ingest(
                    session=session,
                    document_id=document_id,
                    facility_id=facility_id,
                    object_key=object_key,
                    mime_type=mime_type,
                    document_title=document_title,
                    category=category,
                    department=department,
                    progress=report,
                )
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("ingest_task_retrying", doc_id=document_id, error=str(exc))
        raise self.retry(exc=exc)