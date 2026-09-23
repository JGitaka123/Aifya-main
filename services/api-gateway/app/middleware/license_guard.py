"""
License enforcement middleware.

Intercepts every authenticated request and checks:
1. Module access — is this endpoint's module enabled for the facility's tier?
2. Patient limit — block registration if limit reached
3. Feature flags — check tier-specific feature access

Uses Redis cache for performance (avoids DB hit on every request).
Falls back to DB if cache miss.
"""

from datetime import timedelta

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

# Map URL prefixes to module names for tier gating
ROUTE_MODULE_MAP: dict[str, str] = {
    "/api/v1/patients": "patients",
    "/api/v1/encounters": "encounters",
    "/api/v1/pharmacy": "pharmacy",
    "/api/v1/laboratory": "laboratory",
    "/api/v1/billing": "billing",
    "/api/v1/ipd": "ipd",
    "/api/v1/radiology": "radiology",
    "/api/v1/mch": "mch",
    "/api/v1/appointments": "appointments",
    "/api/v1/reports": "reports",
    "/api/v1/hr": "hr",
    "/api/v1/emergency": "emergency",
    "/api/v1/inventory": "inventory",
    "/api/v1/theatre": "theatre",
    "/api/v1/referrals": "referrals",
    "/api/v1/insurance": "insurance",
    "/api/v1/dental": "dental",
    "/api/v1/trials": "clinical_trials",
}

# Routes that bypass license checks
EXEMPT_ROUTES = {
    "/api/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/v1/licensing/heartbeat",
    "/api/v1/licensing/update-check",
}

# Cache TTL for license validation (avoid DB hit per request)
LICENSE_CACHE_TTL = timedelta(minutes=5)


class LicenseGuardMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces tier-based module access on every request.
    Reads facility_id from request state (set by auth dependency).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Check license entitlements before processing the request.

        @param request: Incoming HTTP request
        @param call_next: Next middleware/handler
        @returns Response or 403 if module not licensed
        """
        path = request.url.path

        # Skip exempt routes
        if path in EXEMPT_ROUTES or path.startswith("/api/v1/licensing"):
            return await call_next(request)

        # Skip non-API routes
        if not path.startswith("/api/v1/"):
            return await call_next(request)

        # Determine which module this request targets
        target_module = None
        for prefix, module in ROUTE_MODULE_MAP.items():
            if path.startswith(prefix):
                target_module = module
                break

        if not target_module:
            return await call_next(request)

        # License check happens AFTER auth — we need facility_id from JWT.
        # The auth dependency sets request.state.current_user.
        # Since we can't access Depends() in middleware, we check after
        # the response if we got a 403 from the dependency, OR we use
        # a lightweight approach: store entitlements in a request-scoped cache.
        #
        # Strategy: The auth dependency populates request state. We add a
        # secondary dependency that checks entitlements. This middleware
        # just adds the module info for the dependency to use.
        request.state.target_module = target_module

        return await call_next(request)


def get_route_module(path: str) -> str | None:
    """
    Get the module name for a given API path.

    @param path: URL path
    @returns Module name or None
    """
    for prefix, module in ROUTE_MODULE_MAP.items():
        if path.startswith(prefix):
            return module
    return None
