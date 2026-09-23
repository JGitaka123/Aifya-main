"""
Vector store abstraction.

Backends:

* ``postgres`` - the default. Chunk embeddings live in
  ``knowledge_chunks.embedding`` (``real[]``) and similarity is a dot product
  computed with ``unnest ... WITH ORDINALITY``, so search needs nothing beyond
  the PostgreSQL Aifya already runs. Nothing else to install, nothing else to
  start, and the index travels with the database backup.
* ``qdrant``   - an external Qdrant server (the docker-compose stack).
* ``local``    - qdrant-client's embedded mode, for a single-process machine
  that would rather keep a vector file on disk than a column in the database.

Embeddings are L2 normalised, so a plain dot product is the cosine similarity.

Every public function is async and takes the caller's session. The session
already carries ``app.current_facility_id``, so row-level security scopes each
statement to the right tenant without any extra plumbing.
"""

import uuid

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import ARRAY, REAL
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import bindparam
from starlette.concurrency import run_in_threadpool
from structlog import get_logger

from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

# Payload fields worth indexing on a real Qdrant server.
_INDEXED_FIELDS: tuple[str, ...] = (
    "facility_id",
    "document_id",
    "category",
    "department",
)

_EMBEDDING_COLUMN_CHECK = text(
    "SELECT 1 FROM information_schema.columns "
    "WHERE table_name = 'knowledge_chunks' AND column_name = 'embedding'"
)

_UPSERT_EMBEDDING_SQL = text(
    "UPDATE knowledge_chunks SET embedding = CAST(:vector AS real[]) "
    "WHERE qdrant_point_id = :point_id AND facility_id = :facility_id"
).bindparams(bindparam("vector", type_=ARRAY(REAL)))

_CLEAR_EMBEDDINGS_SQL = text(
    "UPDATE knowledge_chunks SET embedding = NULL "
    "WHERE facility_id = :facility_id AND document_id = :document_id"
)

_SEARCH_SQL_HEAD = """
SELECT
    c.document_id,
    c.chunk_index,
    c.text,
    c.page_number,
    c.section_title,
    d.title AS document_title,
    d.category,
    d.department,
    scores.score
FROM knowledge_chunks AS c
JOIN knowledge_documents AS d ON d.id = c.document_id
CROSS JOIN LATERAL (
    SELECT sum(
        CAST(a.value AS double precision) * CAST(b.value AS double precision)
    ) AS score
    FROM unnest(c.embedding) WITH ORDINALITY AS a(value, position)
    JOIN unnest(CAST(:vector AS real[])) WITH ORDINALITY AS b(value, position)
      ON a.position = b.position
) AS scores
WHERE c.facility_id = :facility_id
  AND c.embedding IS NOT NULL
  AND d.is_deleted = false
"""

_SEARCH_SQL_TAIL = """
  AND scores.score >= :threshold
ORDER BY scores.score DESC
LIMIT :top_k
"""

_qdrant_client = None


def is_postgres() -> bool:
    """
    Whether chunk embeddings are stored in PostgreSQL.

    @returns True when VECTOR_BACKEND is "postgres"
    """
    return settings.vector_backend == "postgres"


async def _assert_embedding_column(session: AsyncSession) -> None:
    """
    Fail with an actionable message when migration 024 has not been applied.

    @param session: Async database session
    @raises RuntimeError: If knowledge_chunks.embedding is missing
    """
    result = await session.execute(_EMBEDDING_COLUMN_CHECK)
    if result.first() is None:
        raise RuntimeError(
            "knowledge_chunks.embedding is missing. Run "
            "'alembic upgrade head' in services/api-gateway "
            "(migration 024_knowledge_chunk_embeddings)."
        )


# ---------------------------------------------------------------------------
# Qdrant backend (external server or qdrant-client embedded mode)
# ---------------------------------------------------------------------------


def _get_qdrant_client():
    """
    Get or create the Qdrant client singleton.

    @returns QdrantClient instance
    """
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient

        if settings.vector_backend == "local":
            from pathlib import Path

            path = Path(settings.qdrant_local_path)
            path.mkdir(parents=True, exist_ok=True)
            _qdrant_client = QdrantClient(path=str(path))
            logger.info("qdrant_local_mode", path=str(path))
        else:
            _qdrant_client = QdrantClient(
                url=settings.qdrant_endpoint,
                api_key=settings.qdrant_api_key,
                timeout=30.0,
            )
            logger.info("qdrant_remote_mode", url=settings.qdrant_endpoint)
    return _qdrant_client


def _qdrant_ensure_collection() -> None:
    """
    Create the Qdrant collection if it does not exist.
    """
    from qdrant_client.http import models as qmodels

    client = _get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection in existing:
        logger.info(
            "qdrant_collection_exists", collection=settings.qdrant_collection
        )
        return

    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=qmodels.VectorParams(
            size=settings.embedding_dimension,
            distance=qmodels.Distance.COSINE,
        ),
    )

    if settings.vector_backend == "qdrant":
        for field in _INDEXED_FIELDS:
            client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name=field,
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )

    logger.info(
        "qdrant_collection_created",
        collection=settings.qdrant_collection,
        dimension=settings.embedding_dimension,
    )


def _qdrant_upsert(points: list[dict]) -> None:
    """
    Upsert vectors with their metadata payloads.

    @param points: Dicts with keys id, vector, payload
    """
    from qdrant_client.http import models as qmodels

    client = _get_qdrant_client()
    structs = [
        qmodels.PointStruct(
            id=p["id"], vector=p["vector"], payload=p["payload"]
        )
        for p in points
    ]
    for index in range(0, len(structs), 100):
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=structs[index : index + 100],
            wait=True,
        )


def _qdrant_delete(facility_id: uuid.UUID, document_id: uuid.UUID) -> None:
    """
    Delete every vector belonging to one document.

    @param facility_id: Facility UUID (multi-tenant guard)
    @param document_id: Document UUID whose vectors should go
    """
    from qdrant_client.http import models as qmodels

    client = _get_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="facility_id",
                        match=qmodels.MatchValue(value=str(facility_id)),
                    ),
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=str(document_id)),
                    ),
                ]
            )
        ),
        wait=True,
    )


def _qdrant_search(
    vector: list[float],
    facility_id: uuid.UUID,
    top_k: int,
    categories: list[str] | None,
    department: str | None,
    document_ids: list[uuid.UUID] | None,
) -> list[dict]:
    """
    Similarity search constrained to one facility.

    @param vector: Query embedding
    @param facility_id: Facility UUID (mandatory multi-tenant filter)
    @param top_k: Maximum number of hits
    @param categories: Optional category filter
    @param department: Optional department filter
    @param document_ids: Optional document ID filter
    @returns List of dicts with score and payload fields
    """
    from qdrant_client.http import models as qmodels

    client = _get_qdrant_client()
    must: list[qmodels.Condition] = [
        qmodels.FieldCondition(
            key="facility_id",
            match=qmodels.MatchValue(value=str(facility_id)),
        )
    ]
    if categories:
        must.append(
            qmodels.FieldCondition(
                key="category", match=qmodels.MatchAny(any=list(categories))
            )
        )
    if department:
        must.append(
            qmodels.FieldCondition(
                key="department", match=qmodels.MatchValue(value=department)
            )
        )
    if document_ids:
        must.append(
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchAny(any=[str(d) for d in document_ids]),
            )
        )

    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=vector,
        query_filter=qmodels.Filter(must=must),
        limit=top_k,
        score_threshold=settings.similarity_threshold,
    )
    return [
        {"score": point.score, "point_id": point.id, **(point.payload or {})}
        for point in results
    ]


def _qdrant_health() -> str:
    """
    Check Qdrant connectivity.

    @returns Status string
    """
    try:
        _get_qdrant_client().get_collections()
        return "connected"
    except Exception:
        return "disconnected"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def ensure_collection(session: AsyncSession) -> None:
    """
    Prepare the vector index. A no-op for the Postgres backend beyond
    verifying that migration 024 has been applied.

    @param session: Async database session
    """
    if is_postgres():
        await _assert_embedding_column(session)
        logger.info("vector_store_ready", backend="postgres")
        return
    await run_in_threadpool(_qdrant_ensure_collection)


async def upsert_points(
    session: AsyncSession, points: list[dict]
) -> None:
    """
    Store the embeddings for freshly inserted chunks.

    The Postgres backend writes to ``knowledge_chunks.embedding`` and therefore
    expects the chunk rows to exist already; the pipeline inserts them before
    calling this.

    @param session: Async database session
    @param points: Dicts with keys id, vector and payload
    """
    if not points:
        return

    if not is_postgres():
        await run_in_threadpool(_qdrant_upsert, points)
        return

    facility_id = points[0].get("payload", {}).get("facility_id")
    await session.execute(
        _UPSERT_EMBEDDING_SQL,
        [
            {
                "vector": list(p["vector"]),
                "point_id": str(p["id"]),
                "facility_id": facility_id,
            }
            for p in points
        ],
    )
    logger.debug("embeddings_stored", count=len(points), backend="postgres")


async def delete_points(
    session: AsyncSession,
    facility_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """
    Drop a document's vectors from the index.

    @param session: Async database session
    @param facility_id: Facility UUID (multi-tenant guard)
    @param document_id: Document UUID to de-index
    """
    if is_postgres():
        await session.execute(
            _CLEAR_EMBEDDINGS_SQL,
            {"facility_id": facility_id, "document_id": document_id},
        )
        await session.commit()
        logger.info(
            "embeddings_cleared",
            facility_id=str(facility_id),
            document_id=str(document_id),
        )
        return

    await run_in_threadpool(_qdrant_delete, facility_id, document_id)
    logger.info(
        "qdrant_vectors_deleted",
        facility_id=str(facility_id),
        document_id=str(document_id),
    )


async def search_points(
    session: AsyncSession,
    vector: list[float],
    facility_id: uuid.UUID,
    top_k: int,
    categories: list[str] | None = None,
    department: str | None = None,
    document_ids: list[uuid.UUID] | None = None,
) -> list[dict]:
    """
    Find the chunks most similar to a query, scoped to one facility.

    @param session: Async database session
    @param vector: Query embedding
    @param facility_id: Facility UUID (mandatory multi-tenant filter)
    @param top_k: Maximum number of hits
    @param categories: Optional category filter
    @param department: Optional department filter
    @param document_ids: Optional document ID filter
    @returns List of dicts with score and payload fields
    """
    if not is_postgres():
        return await run_in_threadpool(
            _qdrant_search,
            vector,
            facility_id,
            top_k,
            categories,
            department,
            document_ids,
        )

    sql = _SEARCH_SQL_HEAD
    params: dict = {
        "vector": list(vector),
        "facility_id": facility_id,
        "threshold": settings.similarity_threshold,
        "top_k": top_k,
    }
    if categories:
        sql += "  AND d.category = ANY(CAST(:categories AS text[]))\n"
        params["categories"] = list(categories)
    if department:
        sql += "  AND d.department = :department\n"
        params["department"] = department
    if document_ids:
        sql += "  AND CAST(c.document_id AS text) = ANY(CAST(:document_ids AS text[]))\n"
        params["document_ids"] = [str(d) for d in document_ids]

    statement = text(sql + _SEARCH_SQL_TAIL).bindparams(
        bindparam("vector", type_=ARRAY(REAL))
    )
    if categories:
        statement = statement.bindparams(
            bindparam("categories", type_=ARRAY(Text))
        )
    if document_ids:
        statement = statement.bindparams(
            bindparam("document_ids", type_=ARRAY(Text))
        )

    result = await session.execute(statement, params)
    return [
        {
            "score": float(row.score),
            "point_id": str(row.document_id),
            "document_id": str(row.document_id),
            "document_title": row.document_title,
            "category": row.category,
            "department": row.department,
            "chunk_index": row.chunk_index,
            "text": row.text,
            "page_number": row.page_number,
            "section_title": row.section_title or "",
        }
        for row in result.all()
    ]


async def health(session: AsyncSession) -> str:
    """
    Check vector search availability.

    @param session: Async database session
    @returns Status string: 'connected' or 'disconnected'
    """
    try:
        if is_postgres():
            await _assert_embedding_column(session)
            return "connected"
        return await run_in_threadpool(_qdrant_health)
    except Exception:
        return "disconnected"