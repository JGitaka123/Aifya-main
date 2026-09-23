"""Tests for middleware functionality."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.middleware import SecurityHeadersMiddleware, RateLimitMiddleware


def create_test_app(rate_limit: int = 5) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=rate_limit, window_seconds=60)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return app


class TestSecurityHeaders:
    def test_security_headers_present(self):
        app = create_test_app()
        client = TestClient(app)
        response = client.get("/test")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "max-age" in response.headers["Strict-Transport-Security"]
        assert "Referrer-Policy" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert "Permissions-Policy" in response.headers


class TestRateLimiting:
    def test_allows_under_limit(self):
        app = create_test_app(rate_limit=10)
        client = TestClient(app)
        for _ in range(10):
            response = client.get("/test")
            assert response.status_code == 200

    def test_blocks_over_limit(self):
        app = create_test_app(rate_limit=3)
        client = TestClient(app)
        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == 429
        body = response.json()
        assert "Too many requests" in body["error"]
