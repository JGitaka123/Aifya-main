"""
Retrieval service.

The read/write facade over the vector store. Every search is scoped by
facility_id for multi-tenant isolation. Which store backs it is decided by
``VECTOR_BACKEND`` and handled entirely inside ``app.services.vector_store``.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.config import get_settings
from app.services import vector_store
from app.services.embedding_service import backend_name, embed_query

logger = get_logger(__name__)
settings = get_settings()


async def ensure_collection(session: AsyncSession) -> None:
    """
    Prepare the vector index.

    @param session: Async database session
    """
    await vector_store.ensure_collection(session)


async def upsert_vectors(session: AsyncSession, points: list[dict]) -> None:
    """
    Store embeddings for freshly inserted chunks.

    @param session: Async database session
    @param points: Dicts with keys id, vector and payload. The payload must
                   include facility_id, document_id, category, chunk_index,
                   text, page_number, section_title and document_title.
    """
    await vector_store.upsert_points(session, points)


async def delete_document_vectors(
    session: AsyncSession,
    facility_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """
    Drop a document's vectors. Scoped by facility_id for safety.

    @param session: Async database session
    @param facility_id: Facility UUID (multi-tenant guard)
    @param document_id: Document UUID to de-index
    """
    await vector_store.delete_points(session, facility_id, document_id)


async def search_similar(
    session: AsyncSession,
    query_text: str,
    facility_id: uuid.UUID,
    top_k: int | None = None,
    categories: list[str] | None = None,
    department: str | None = None,
    document_ids: list[uuid.UUID] | None = None,
) -> list[dict]:
    """
    Find the document chunks most similar to a query within one facility.

    @param session: Async database session
    @param query_text: Natural language query
    @param facility_id: Facility UUID (mandatory multi-tenant filter)
    @param top_k: Number of results to return
    @param categories: Optional category filter
    @param department: Optional department filter
    @param document_ids: Optional document ID filter
    @returns List of dicts with score and payload fields
    """
    top_k = top_k or settings.retrieval_top_k
    query_vector = embed_query(query_text)

    hits = await vector_store.search_points(
        session=session,
        vector=query_vector,
        facility_id=facility_id,
        top_k=top_k,
        categories=categories,
        department=department,
        document_ids=document_ids,
    )

    logger.info(
        "vector_search_complete",
        facility_id=str(facility_id),
        query_length=len(query_text),
        results=len(hits),
        backend=settings.vector_backend,
        embedding_backend=backend_name(),
    )
    return hits


async def check_health(session: AsyncSession) -> str:
    """
    Check vector search availability.

    @param session: Async database session
    @returns Status string: 'connected' or 'disconnected'
    """
    return await vector_store.health(session)