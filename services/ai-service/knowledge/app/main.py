"""
Aifya Knowledge RAG — FastAPI application entry point.
Institutional document RAG for hospital policies, SOPs, guidelines.
"""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog import get_logger

from app.config import get_settings
from app.database import async_session_factory
from app.middleware import (
    AuditLoggingMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.models.schemas import HealthResponse
from app.routers import documents, query
from app.services.document_service import check_storage_health, ensure_bucket
from app.services.embedding_service import backend_name
from app.services.retrieval_service import check_health as check_vector_health
from app.services.retrieval_service import ensure_collection

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup/shutdown lifecycle.
    Prepares the vector collection and the storage backend.
    """
    logger.info("app_startup", status="starting", service="knowledge-rag")

    # Neither failure is fatal: the service must still answer /health and the
    # document endpoints so the problem is visible in the UI, rather than
    # refusing to boot and leaving the frontend with an opaque 502.
    try:
        async with async_session_factory() as session:
            await ensure_collection(session)
    except Exception as exc:
        logger.warning(
            "vector_store_init_failed",
            backend=settings.vector_backend,
            error=str(exc),
        )

    try:
        # Sync on purpose: the local backend is a directory check, and the
        # MinIO backend is a single blocking HTTP call.
        ensure_bucket()
    except Exception as exc:
        logger.warning(
            "storage_init_failed",
            backend=settings.storage_backend,
            error=str(exc),
        )

    logger.info(
        "app_startup",
        status="complete",
        service="knowledge-rag",
        vector_backend=settings.vector_backend,
        storage_backend=settings.storage_backend,
        ingest_mode=settings.ingest_mode,
        embedding_backend=backend_name(),
    )
    yield
    logger.info("app_shutdown", status="complete", service="knowledge-rag")


_is_dev: bool = settings.app_env == "development" or settings.debug
_docs_url: str | None = "/docs" if _is_dev else None
_redoc_url: str | None = "/redoc" if _is_dev else None
_openapi_url: str | None = f"{settings.api_v1_str}/openapi.json" if _is_dev else None

app = FastAPI(
    title=settings.project_name,
    description="Institutional knowledge RAG service for Aifya HMIS",
    version="1.0.0",
    openapi_url=_openapi_url,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    lifespan=lifespan,
)

# --- Middleware (order: last added = first executed) ---
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- API router ---
api_router = APIRouter(prefix=settings.api_v1_str)
api_router.include_router(documents.router)
api_router.include_router(query.router)
app.include_router(api_router)


# --- Health check ---
@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Service health check.
    Reports connectivity to Qdrant and MinIO.

    @returns HealthResponse with component statuses
    """
    from app.services.generation_service import check_health as check_vllm_health

    async with async_session_factory() as session:
        vector_status = await check_vector_health(session)
    storage_status = check_storage_health()
    vllm_status = await check_vllm_health()

    overall = "ok"
    if any(s == "disconnected" for s in [vector_status, storage_status]):
        overall = "degraded"

    return HealthResponse(
        status=overall,
        service="aifya-knowledge-rag",
        components={
            "vector_store": vector_status,
            "vector_backend": settings.vector_backend,
            "storage": storage_status,
            "storage_backend": settings.storage_backend,
            "embeddings": backend_name(),
            "ingest_mode": settings.ingest_mode,
            "llm": vllm_status,
        },
    )
