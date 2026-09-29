"""
Aifya Knowledge RAG — FastAPI application entry point.
Institutional document RAG for hospital policies, SOPs, guidelines.
"""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from structlog import get_logger

from app.knowledge.config import get_settings
from app.knowledge.database import async_session_factory
from app.knowledge.middleware import (
    AuditLoggingMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.knowledge.models.schemas import HealthResponse
from app.knowledge.routers import documents, query
from app.knowledge.services.document_service import check_storage_health, ensure_bucket
from app.knowledge.services.embedding_service import backend_name
from app.knowledge.services.retrieval_service import check_health as check_vector_health
from app.knowledge.services.retrieval_service import ensure_collection

logger = get_logger(__name__)
settings = get_settings()


async def startup() -> None:
    """
    Prepare the vector collection and the storage backend.

    Exposed separately because the api-gateway mounts this app as a
    sub-application and Starlette does not run the lifespan of a mounted
    app, so the gateway calls this from its own lifespan instead.
    """
    logger.info("app_startup", status="starting", service="knowledge-rag")

    # Neither failure is fatal: the app must still answer /health and the
    # document endpoints so the problem is visible in the UI, rather than
    # refusing to boot and leaving the frontend with an opaque error.
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


async def shutdown() -> None:
    """
    Release anything the knowledge app holds on the way down.
    """
    logger.info("app_shutdown", status="complete", service="knowledge-rag")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan for running this app on its own (tests, one-off scripts).

    The api-gateway mount calls startup()/shutdown() directly instead.
    """
    await startup()
    try:
        yield
    finally:
        await shutdown()


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
# CORS is deliberately not added here: this app is mounted inside the
# api-gateway, which owns CORS for every route. Adding it twice would emit
# two Access-Control-Allow-Origin headers and break browser requests.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

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
    from app.knowledge.services.generation_service import check_health as check_vllm_health

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
