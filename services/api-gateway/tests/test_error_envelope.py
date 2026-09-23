"""D1: unhandled server errors return JSON 500 with CORS headers (not a
bare browser "Failed to fetch")."""

import pytest
from httpx import AsyncClient

from app.main import app


@app.get("/api/_test_boom")
async def _boom() -> dict[str, str]:
    """Test-only route that raises, to exercise the error envelope."""
    raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_unhandled_error_returns_json_500_with_cors(
    client: AsyncClient,
) -> None:
    resp = await client.get(
        "/api/_test_boom", headers={"Origin": "http://localhost:3000"}
    )
    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body  # a readable message, not an opaque failure
    # CORS header present so the browser exposes the error instead of
    # reporting a bare "Failed to fetch".
    assert (
        resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    )
