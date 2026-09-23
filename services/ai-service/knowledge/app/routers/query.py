"""
RAG query API endpoint.
Retrieves relevant document chunks and generates answers with citations.
"""

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth.dependencies import CurrentUser, get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.schemas import (
    CitationSource,
    DocumentCategory,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
)
from app.services.generation_service import generate_answer
from app.services.retrieval_service import search_similar

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/query", tags=["query"])


@router.post(
    "",
    response_model=KnowledgeQueryResponse,
    summary="Query the institutional knowledge base",
)
async def query_knowledge_base(
    request: KnowledgeQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> KnowledgeQueryResponse:
    """
    Execute a RAG query against the institutional knowledge base.
    Retrieves relevant chunks from Qdrant (filtered by facility_id),
    then generates an answer using the vLLM-hosted model.

    @param request: Query request with optional filters
    @param db: Database session
    @param current_user: Authenticated user
    @returns Generated answer with citations and metadata
    """
    retrieval_start = time.time()

    categories_str: list[str] | None = None
    if request.categories:
        categories_str = [c.value for c in request.categories]

    document_ids: list[uuid.UUID] | None = None
    if request.document_ids:
        document_ids = request.document_ids

    hits = await search_similar(
        session=db,
        query_text=request.query,
        facility_id=current_user.facility_id,
        top_k=request.top_k,
        categories=categories_str,
        department=request.department,
        document_ids=document_ids,
    )

    retrieval_ms = (time.time() - retrieval_start) * 1000

    generation_start = time.time()
    result = await generate_answer(
        query=request.query,
        chunks=hits,
        language=request.language,
    )
    generation_ms = (time.time() - generation_start) * 1000

    citations: list[CitationSource] = []
    if request.include_chunks:
        for hit in hits:
            cat_str = hit.get("category", "other")
            try:
                cat = DocumentCategory(cat_str)
            except ValueError:
                cat = DocumentCategory.OTHER

            citations.append(
                CitationSource(
                    document_id=uuid.UUID(hit["document_id"]),
                    document_title=hit.get("document_title", "Unknown"),
                    category=cat,
                    section=hit.get("section_title") or None,
                    page_number=hit.get("page_number"),
                    chunk_text=hit.get("text", ""),
                    relevance_score=round(hit.get("score", 0.0), 4),
                )
            )

    logger.info(
        "knowledge_query_complete",
        user=current_user.email,
        facility_id=str(current_user.facility_id),
        query_length=len(request.query),
        hits=len(hits),
        retrieval_ms=round(retrieval_ms, 1),
        generation_ms=round(generation_ms, 1),
        confidence=result["confidence"],
    )

    return KnowledgeQueryResponse(
        answer=result["answer"],
        citations=citations,
        confidence=result["confidence"],
        query=request.query,
        model_used=result["model_used"],
        retrieval_time_ms=round(retrieval_ms, 1),
        generation_time_ms=round(generation_ms, 1),
    )


@router.post(
    "/context",
    response_model=list[CitationSource],
    summary="Get relevant context without generating an answer",
)
async def get_context(
    request: KnowledgeQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[CitationSource]:
    """
    Retrieve relevant document chunks without LLM generation.
    Useful for the contextual sidebar widget and ScribeAI integration.

    @param request: Query request with optional filters
    @param current_user: Authenticated user
    @returns List of relevant citations
    """
    categories_str: list[str] | None = None
    if request.categories:
        categories_str = [c.value for c in request.categories]

    hits = await search_similar(
        session=db,
        query_text=request.query,
        facility_id=current_user.facility_id,
        top_k=request.top_k,
        categories=categories_str,
        department=request.department,
        document_ids=request.document_ids,
    )

    citations: list[CitationSource] = []
    for hit in hits:
        cat_str = hit.get("category", "other")
        try:
            cat = DocumentCategory(cat_str)
        except ValueError:
            cat = DocumentCategory.OTHER

        citations.append(
            CitationSource(
                document_id=uuid.UUID(hit["document_id"]),
                document_title=hit.get("document_title", "Unknown"),
                category=cat,
                section=hit.get("section_title") or None,
                page_number=hit.get("page_number"),
                chunk_text=hit.get("text", ""),
                relevance_score=round(hit.get("score", 0.0), 4),
            )
        )

    return citations
