"""
SHA (Social Health Authority) member validation.
Validates a SHA membership number against the SHA validation API and
caches results for 24h in Redis. Member validation is free (no payment).

If SHA_API_URL is not configured, returns a clearly-labeled mock response
so dev environments can keep working without real SHA credentials.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

import httpx
import redis.asyncio as redis_async
from pydantic import BaseModel
from structlog import get_logger

from app.config import settings

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours


class ShaDependent(BaseModel):
    """SHA dependent on a primary member's plan."""

    name: str
    relationship: str
    sha_number: str | None = None


class ShaMember(BaseModel):
    """
    SHA member validation result.

    @param sha_number: SHA membership number
    @param id_number: Kenyan national ID number (or passport)
    @param name: Full member name from SHA
    @param status: active | inactive | suspended
    @param scheme: SHA scheme name (e.g. "Primary", "EHCP")
    @param dependents: List of registered dependents
    @param is_mock: True when this came from the mock fallback
    """

    sha_number: str
    id_number: str
    name: str
    status: str
    scheme: str
    dependents: list[ShaDependent] = []
    is_mock: bool = False
    mock_reason: str | None = None


def _cache_key(sha_number: str) -> str:
    """Build the Redis cache key for an SHA number."""
    return f"sha:member:{sha_number}"


async def _get_redis() -> redis_async.Redis | None:
    """
    Open a Redis connection for caching. Returns None if Redis is unreachable
    so the validation flow can continue (degraded — no caching).

    @returns Redis client or None
    """
    try:
        client: redis_async.Redis = redis_async.from_url(
            settings.redis_url, decode_responses=True
        )
        await client.ping()
        return client
    except Exception as exc:
        logger.warning("sha_redis_unavailable", error=str(exc))
        return None


async def validate_member(
    sha_number: str,
    id_number: str,
) -> ShaMember | None:
    """
    Validate an SHA member by SHA number + ID number.

    Steps:
    1. Check 24h Redis cache
    2. If miss, call SHA validation API
    3. If SHA_API_URL not configured, return a clearly-labeled mock
    4. Cache the result

    @param sha_number: SHA membership number
    @param id_number: National ID or passport number
    @returns ShaMember if found and active, None if not found
    """
    cache_key = _cache_key(sha_number)
    redis = await _get_redis()

    # 1) Try cache
    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                # Don't return cached negatives — re-check next time
                if data.get("status") in ("active", "inactive", "suspended"):
                    return ShaMember(**data)
        except Exception as exc:
            logger.warning("sha_cache_read_error", error=str(exc))

    # 2) Mock when not configured (dev mode)
    if not settings.sha_api_url or not settings.sha_api_key:
        member = ShaMember(
            sha_number=sha_number,
            id_number=id_number,
            name="MOCK: SHA Member",
            status="active",
            scheme="Primary",
            dependents=[],
            is_mock=True,
            mock_reason="MOCK: SHA API not configured (set SHA_API_URL and SHA_API_KEY)",
        )
        if redis is not None:
            with contextlib.suppress(Exception):
                await redis.set(
                    cache_key,
                    member.model_dump_json(),
                    ex=300,  # short TTL for mocks
                )
        return member

    # 3) Real API call
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{settings.sha_api_url.rstrip('/')}/members/validate",
                params={"sha_number": sha_number, "id_number": id_number},
                headers={"Authorization": f"Bearer {settings.sha_api_key}"},
            )
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            logger.warning(
                "sha_validation_failed",
                status_code=response.status_code,
                body=response.text[:200],
            )
            return None
        payload: dict[str, Any] = response.json()
        member = _parse_sha_response(sha_number, id_number, payload)
    except httpx.HTTPError as exc:
        logger.error("sha_validation_network_error", error=str(exc))
        return None
    except Exception as exc:
        logger.error("sha_validation_unexpected_error", error=str(exc))
        return None

    # 4) Cache success
    if redis is not None and member is not None:
        with contextlib.suppress(Exception):
            await redis.set(
                cache_key,
                member.model_dump_json(),
                ex=_CACHE_TTL_SECONDS,
            )
    return member


def _parse_sha_response(
    sha_number: str,
    id_number: str,
    payload: dict[str, Any],
) -> ShaMember:
    """
    Parse a raw SHA validation response into our ShaMember model.

    @param sha_number: Echo input SHA number
    @param id_number: Echo input ID number
    @param payload: Raw JSON payload from SHA API
    @returns Normalized ShaMember
    """
    deps_raw = payload.get("dependents") or []
    dependents = [
        ShaDependent(
            name=str(d.get("name", "")),
            relationship=str(d.get("relationship", "")),
            sha_number=d.get("sha_number"),
        )
        for d in deps_raw
        if isinstance(d, dict)
    ]
    return ShaMember(
        sha_number=sha_number,
        id_number=id_number,
        name=str(payload.get("name", "")),
        status=str(payload.get("status", "inactive")),
        scheme=str(payload.get("scheme", "")),
        dependents=dependents,
        is_mock=False,
    )
