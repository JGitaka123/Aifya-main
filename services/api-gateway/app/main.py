import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

# Error tracking â€” active only when SENTRY_DSN is configured. PII is not
# sent (send_default_pii stays False; request bodies are excluded).
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        max_request_body_size="never",
    )
from app.middleware.license_guard import LicenseGuardMiddleware
from app.bootstrap_internal import (
    ensure_all_facility_licenses,
    ensure_internal_super_admin,
    ensure_keycloak_bootstrap,
)
from app.routers import (
    agents,
    analytics,
    appointments,
    auth_session,
    billing,
    cds,
    clinical_trials,
    communications,
    dental,
    dhis2,
    emergency,
    encounters,
    federated,
    fhir,
    finance,
    help_bot,
    hr,
    icd10,
    imaging,
    insurance,
    inventory,
    ipd,
    laboratory,
    licensing,
    mch,
    mpesa,
    onboarding,
    patients,
    payroll,
    performance,
    pharmacy,
    radiology,
    referral,
    reports,
    theatre,
)

# Disable OpenAPI/Swagger docs in production to avoid exposing API surface
_is_dev: bool = settings.debug
_docs_url: str | None = "/api/docs" if _is_dev else None
_redoc_url: str | None = "/api/redoc" if _is_dev else None
_openapi_url: str | None = "/api/openapi.json" if _is_dev else None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    # Startup: pre-fetch Keycloak JWKS
    from app.auth.keycloak import get_keycloak_public_keys

    with suppress(Exception):
        await get_keycloak_public_keys()
    # Internal auth mode: provision the first-run platform super-admin.
    with suppress(Exception):
        await ensure_internal_super_admin()
    # Keycloak mode: create the facility the seeded realm users point at.
    with suppress(Exception):
        await ensure_keycloak_bootstrap()
    # Issue licenses for approved facilities so every module is usable.
    with suppress(Exception):
        await ensure_all_facility_licenses()
    # Widens encrypted employee columns on DBs that predate migrations 011/020.
    with suppress(Exception):
        from app.db_fixes import ensure_employee_db_fixes

        await ensure_employee_db_fixes()
    # Seed the national statutory defaults (PAYE bands, NSSF tiers, SHIF and
    # housing-levy rates, personal relief, default leave types). Global rows and
    # idempotent, so this is safe on every boot. Without them the engine has no
    # bands or tiers to apply and computes PAYE and NSSF as zero for everyone.
    try:
        from app.database import async_session
        from app.services.payroll.seed_data import seed_payroll_defaults

        async with async_session() as session:
            await seed_payroll_defaults(session)
            await session.commit()
    except Exception:
        _logger.exception("payroll_statutory_seed_failed")
    yield


_logger = logging.getLogger(__name__)


class ErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    """
    Convert any unhandled exception into a JSON 500 response.

    Placed INSIDE the CORS middleware so the error response is decorated with
    CORS headers â€” otherwise a server error surfaces in the browser as a bare
    "Failed to fetch" with no status or detail (QA D1). The cause is logged
    (and reported to Sentry when configured); the client gets a safe message.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception:
            _logger.exception(
                "unhandled_error method=%s path=%s",
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error. The team has been notified."
                },
            )


app = FastAPI(
    title="Aifya API",
    description="AI-Native Hospital Management System API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

# Added before CORS so it wraps closer to the routes: CORS then decorates
# the JSON 500 it returns (added middleware are applied inner-first).
app.add_middleware(ErrorEnvelopeMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# License enforcement middleware â€” checks module access on every request
app.add_middleware(LicenseGuardMiddleware)

# Routes
app.include_router(patients.router, prefix="/api/v1/patients", tags=["patients"])
app.include_router(auth_session.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(
    onboarding.router, prefix="/api/v1/onboarding", tags=["onboarding"]
)
app.include_router(cds.router, prefix="/api/v1/cds", tags=["cds"])
app.include_router(encounters.router, prefix="/api/v1/encounters", tags=["encounters"])
app.include_router(icd10.router, prefix="/api/v1/icd10", tags=["icd10"])
app.include_router(pharmacy.router, prefix="/api/v1/pharmacy", tags=["pharmacy"])
app.include_router(laboratory.router, prefix="/api/v1/laboratory", tags=["laboratory"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"])
app.include_router(finance.router, prefix="/api/v1/finance", tags=["finance"])
app.include_router(ipd.router, prefix="/api/v1/ipd", tags=["ipd"])
app.include_router(radiology.router, prefix="/api/v1/radiology", tags=["radiology"])
app.include_router(mch.router, prefix="/api/v1/mch", tags=["mch"])
app.include_router(appointments.router, tags=["appointments"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(hr.router, prefix="/api/v1/hr", tags=["hr"])
app.include_router(payroll.router, prefix="/api/v1/payroll", tags=["payroll"])
app.include_router(emergency.router, prefix="/api/v1/emergency", tags=["emergency"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["inventory"])
app.include_router(theatre.router, prefix="/api/v1/theatre", tags=["theatre"])
app.include_router(referral.router, prefix="/api/v1/referrals", tags=["referrals"])
app.include_router(insurance.router, prefix="/api/v1/insurance", tags=["insurance"])
app.include_router(dental.router, prefix="/api/v1/dental", tags=["dental"])
app.include_router(licensing.router, prefix="/api/v1/licensing", tags=["licensing"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(
    communications.router,
    prefix="/api/v1/communications",
    tags=["communications"],
)
app.include_router(fhir.router, prefix="/api/v1/fhir", tags=["fhir"])
app.include_router(dhis2.router, prefix="/api/v1/dhis2", tags=["dhis2"])
app.include_router(mpesa.router, prefix="/api/v1/mpesa", tags=["mpesa"])
app.include_router(imaging.router, prefix="/api/v1/imaging", tags=["imaging"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(
    clinical_trials.router,
    prefix="/api/v1/trials",
    tags=["clinical-trials"],
)
app.include_router(federated.router, prefix="/api/v1/federated", tags=["federated"])
app.include_router(
    performance.router,
    prefix="/api/v1/performance",
    tags=["performance"],
)
app.include_router(help_bot.router, prefix="/api/v1/help", tags=["help-bot"])


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint (no auth required)."""
    return {"status": "ok", "service": "aifya-api-gateway"}

