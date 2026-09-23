"""
Document ingestion pipeline.

Fetch, parse, chunk, embed, index. Exactly the same code runs whether
ingestion happens inline inside the upload request (``INGEST_MODE=inline``) or
in the Celery worker (``INGEST_MODE=celery``); ``app.tasks.ingest`` is a thin
wrapper that drives :func:`run_ingest` from a synchronous worker process.

Everything that touches the database is awaited on the caller's session, so the
facility context that powers row-level security is already in place. The
CPU-bound and blocking steps - file IO, parsing, embedding - are pushed to a
worker thread so a large upload cannot stall the event loop.
"""

import os
import tempfile
import uuid
from typing import Callable

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from structlog import get_logger

from app.chunking.semantic_chunker import TextChunk, chunk_document
from app.config import get_settings
from app.database import set_facility_context
from app.models.document import DocumentChunk, KnowledgeDocument
from app.models.schemas import DocumentStatus
from app.parsers.base import ParsedDocument
from app.parsers.docx_parser import parse_docx
from app.parsers.pdf_parser import parse_pdf
from app.parsers.text_parser import parse_text
from app.services import storage
from app.services.embedding_service import embed_texts
from app.services.retrieval_service import upsert_vectors

logger = get_logger(__name__)
settings = get_settings()

_MIME_PARSERS: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    "text/plain": "text",
    "text/markdown": "text",
    "text/rtf": "text",
}

ProgressCallback = Callable[[str, int], None]


async def _update_status(
    session: AsyncSession,
    document_id: uuid.UUID,
    status: DocumentStatus,
    error_message: str | None = None,
    chunk_count: int | None = None,
    page_count: int | None = None,
) -> None:
    """
    Update the document's ingest status.

    @param session: Async database session
    @param document_id: Document UUID
    @param status: New status
    @param error_message: Error message if failed
    @param chunk_count: Chunk count
    @param page_count: Page count
    """
    values: dict = {"status": status.value, "updated_at": func.now()}
    if error_message is not None:
        values["error_message"] = error_message
    if chunk_count is not None:
        values["chunk_count"] = chunk_count
    if page_count is not None:
        values["page_count"] = page_count

    await session.execute(
        update(KnowledgeDocument)
        .where(KnowledgeDocument.id == document_id)
        .values(**values)
    )
    await session.commit()


def _report(progress: ProgressCallback | None, state: str, percent: int) -> None:
    """
    Emit a progress update when a callback was supplied.

    @param progress: Callback receiving (state, percent), or None
    @param state: Pipeline stage name
    @param percent: Completion percentage
    """
    if progress is not None:
        progress(state, percent)


async def run_ingest(
    session: AsyncSession,
    document_id: str,
    facility_id: str,
    object_key: str,
    mime_type: str,
    document_title: str,
    category: str,
    department: str | None = None,
    progress: ProgressCallback | None = None,
) -> dict:
    """
    Run the full ingestion pipeline for one document.

    Any failure marks the document FAILED and re-raises, so the caller can
    surface the reason on the document instead of a bare 500.

    @param session: Async database session
    @param document_id: Document UUID string
    @param facility_id: Facility UUID string
    @param object_key: Storage object key of the uploaded file
    @param mime_type: File MIME type
    @param document_title: Document title, stored in the vector payload
    @param category: Document category, stored in the vector payload
    @param department: Optional department, stored in the vector payload
    @param progress: Optional callback receiving (state, percent)
    @returns Dict with status, chunk_count and page_count
    """
    doc_uuid = uuid.UUID(document_id)
    fac_uuid = uuid.UUID(facility_id)
    tmp_path: str | None = None

    await set_facility_context(session, facility_id)

    try:
        parser_type = _MIME_PARSERS.get(mime_type, "text")
        suffix_map = {"pdf": ".pdf", "docx": ".docx", "text": ".txt"}
        suffix = suffix_map.get(parser_type, ".txt")

        await _update_status(session, doc_uuid, DocumentStatus.PROCESSING)
        _report(progress, "PROCESSING", 10)

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        await run_in_threadpool(storage.get_file, object_key, tmp_path)
        logger.info("file_fetched", doc_id=document_id, path=tmp_path)

        _report(progress, "PARSING", 25)
        parsed: ParsedDocument
        if parser_type == "pdf":
            parsed = await run_in_threadpool(parse_pdf, tmp_path)
        elif parser_type == "docx":
            parsed = await run_in_threadpool(parse_docx, tmp_path)
        else:
            parsed = await run_in_threadpool(parse_text, tmp_path)

        await _update_status(
            session,
            doc_uuid,
            DocumentStatus.CHUNKING,
            page_count=parsed.total_pages,
        )
        _report(progress, "CHUNKING", 40)

        chunks: list[TextChunk] = await run_in_threadpool(
            chunk_document, parsed
        )
        logger.info("chunking_complete", doc_id=document_id, chunks=len(chunks))

        if not chunks:
            await _update_status(
                session,
                doc_uuid,
                DocumentStatus.FAILED,
                error_message=(
                    "No text content could be extracted from the document."
                ),
            )
            return {"status": "failed", "error": "No extractable text"}

        await _update_status(session, doc_uuid, DocumentStatus.EMBEDDING)
        _report(progress, "EMBEDDING", 55)

        embeddings = await run_in_threadpool(
            embed_texts, [c.text for c in chunks]
        )
        logger.info(
            "embedding_complete", doc_id=document_id, vectors=len(embeddings)
        )

        _report(progress, "STORING", 75)

        # One id per chunk, shared by the stored row and its vector, so a
        # re-index can always find the row an embedding belongs to.
        point_ids = [str(uuid.uuid4()) for _ in chunks]

        session.add_all(
            [
                DocumentChunk(
                    document_id=doc_uuid,
                    facility_id=fac_uuid,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    token_count=chunk.token_count,
                    qdrant_point_id=point_id,
                )
                for chunk, point_id in zip(chunks, point_ids)
            ]
        )
        await session.commit()

        points = [
            {
                "id": point_id,
                "vector": embedding,
                "payload": {
                    "facility_id": facility_id,
                    "document_id": document_id,
                    "document_title": document_title,
                    "category": category,
                    "department": department or "",
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "page_number": chunk.page_number,
                    "section_title": chunk.section_title or "",
                },
            }
            for chunk, embedding, point_id in zip(
                chunks, embeddings, point_ids
            )
        ]

        await upsert_vectors(session, points)
        await session.commit()

        _report(progress, "SAVING_CHUNKS", 90)
        await _update_status(
            session,
            doc_uuid,
            DocumentStatus.READY,
            chunk_count=len(chunks),
        )
        _report(progress, "COMPLETED", 100)

        logger.info(
            "ingest_complete",
            doc_id=document_id,
            chunks=len(chunks),
            pages=parsed.total_pages,
        )
        return {
            "status": "completed",
            "chunk_count": len(chunks),
            "page_count": parsed.total_pages,
        }

    except Exception as exc:
        logger.error(
            "ingest_failed", doc_id=document_id, error=str(exc), exc_info=True
        )
        try:
            await session.rollback()
            await _update_status(
                session,
                doc_uuid,
                DocumentStatus.FAILED,
                error_message=str(exc)[:500],
            )
        except Exception:
            logger.error(
                "ingest_failure_status_write_failed", doc_id=document_id
            )
        raise

    finally:
        if tmp_path is not None and os.path.exists(tmp_path):
            os.unlink(tmp_path)