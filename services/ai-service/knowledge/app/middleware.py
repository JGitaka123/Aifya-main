"""
HTTP middleware for the Knowledge RAG service.
Reuses the same patterns as ScribeAI: audit logging, security headers, rate limiting.
"""

import json
import time
import uuid
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from structlog import get_logger

from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with structured fields for audit trail."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        @param request: Incoming HTTP request
        @param call_next: Next middleware/handler
        @returns HTTP response with X-Request-ID header
        """
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start_time = time.time()

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id

            log_fn = logger.warning if response.status_code >= 400 else logger.info
            log_fn(
                "http_request",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return response

        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "http_request_exception",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=duration_ms,
                exc_info=True,
            )
            return Response(
                content=json.dumps({
                    "error": "Internal Server Error",
                    "code": "500",
                    "details": {
                        "message": "An unexpected error occurred.",
                        "trace_id": request_id,
                    },
                }),
                status_code=500,
                media_type="application/json",
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        @param request: Incoming request
        @param call_next: Next handler
        @returns Response with security headers
        """
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per IP address."""

    def __init__(
        self, app, max_requests: int | None = None, window_seconds: int = 60
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests or settings.rate_limit_per_minute
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        @param request: Incoming request
        @param call_next: Next handler
        @returns Response or 429 if rate limited
        """
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if now - t < self.window_seconds
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            logger.warning("rate_limit_exceeded", client_ip=client_ip)
            return Response(
                content=json.dumps({
                    "error": "Too many requests",
                    "retry_after": self.window_seconds,
                }),
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.window_seconds)},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)
