"""
License enforcement FastAPI dependency.

Use as a dependency on routers that need tier gating:
    Depends(require_module("pharmacy"))
    Depends(require_feature("ai_features"))

Caches license validation in Redis for 5 minutes to avoid DB roundtrip per request.
"""

import contextlib
import json
import time
import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.config import settings
from app.database import get_db
from app.services.licensing_service import LicensingService

# Redis cache TTL for license entitlements (seconds)
_CACHE_TTL = 300  # 5 minutes
_CACHE_PREFIX = "license:entitlements:"

# Lazy-loaded Redis connection. The negative result is cached too: when
# Redis is unreachable, retrying the (slow) connection attempt on every
# request adds ~2s of latency per API call, so re-check only periodically.
_redis_client = None
_redis_last_attempt_ts: float = 0.0
_REDIS_RETRY_INTERVAL_SECONDS = 30.0


async def _get_redis():
    """
    Get or create async Redis client (lazy singleton).

    @returns Redis client or None if unavailable
    """
    global _redis_client, _redis_last_attempt_ts
    if _redis_client is not None:
        return _redis_client

    # Cooldown so an unavailable Redis is only retried periodically.
    now = time.monotonic()
    if now - _redis_last_attempt_ts < _REDIS_RETRY_INTERVAL_SECONDS:
        return None
    _redis_last_attempt_ts = now

    try:
        from redis.asyncio import Redis

        client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        # Test connection
        await client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None
    return _redis_client


async def _get_entitlements(
    facility_id: str, db: AsyncSession
) -> dict:
    """
    Get cached entitlements for a facility. Uses Redis cache, falls back to DB.

    @param facility_id: Facility UUID string
    @param db: Database session
    @returns Entitlements dict with tier, modules, flags, limits
    """
    cache_key = f"{_CACHE_PREFIX}{facility_id}"

    # Try Redis cache first
    redis = await _get_redis()
    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass  # Redis unavailable — fall through to DB

    # Cache miss or Redis unavailable — query DB
    service = LicensingService(db)
    validation = await service.validate_license(uuid.UUID(facility_id))
    entitlements = {
        "tier": validation.tier,
        "enabled_modules": validation.enabled_modules,
        "feature_flags": validation.feature_flags,
        "max_users": validation.max_users,
        "max_patients": validation.max_patients,
        "is_valid": validation.is_valid,
        "in_grace_period": validation.in_grace_period,
    }

    # Cache result in Redis (write failure is non-fatal)
    if redis is not None:
        with contextlib.suppress(Exception):
            await redis.setex(cache_key, _CACHE_TTL, json.dumps(entitlements))

    return entitlements


async def invalidate_license_cache(facility_id: uuid.UUID) -> None:
    """
    Invalidate cached license entitlements for a facility.
    Call this when a license is activated, deactivated, or upgraded.

    @param facility_id: Facility UUID
    """
    redis = await _get_redis()
    if redis is not None:
        with contextlib.suppress(Exception):
            await redis.delete(f"{_CACHE_PREFIX}{facility_id}")


def require_module(module: str) -> Callable:
    """
    Factory for module-level license enforcement.
    Returns 403 if the facility's tier doesn't include the module.

    Usage: @router.get("/", dependencies=[Depends(require_module("pharmacy"))])

    @param module: Module name to check
    @returns Dependency function
    """

    async def module_checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        """
        Check module access for the current facility.

        @param current_user: Authenticated user
        @param db: Database session
        @returns CurrentUser if module is accessible
        @raises HTTPException 403: If module not in tier
        """
        if settings.beta_public_access:
            return current_user

        entitlements = await _get_entitlements(
            str(current_user.facility_id), db
        )

        if module not in entitlements["enabled_modules"]:
            tier = entitlements["tier"]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "module_not_licensed",
                    "module": module,
                    "current_tier": tier,
                    "message": (
                        f"The '{module}' module is not available on your "
                        f"'{tier}' plan. Upgrade to access this feature."
                    ),
                    "upgrade_url": "/settings/billing",
                },
            )

        return current_user

    return module_checker


def require_feature(flag: str) -> Callable:
    """
    Factory for feature flag license enforcement.
    Returns 403 if the feature is not enabled for the facility's tier.

    Usage: @router.get("/", dependencies=[Depends(require_feature("ai_features"))])

    @param flag: Feature flag name
    @returns Dependency function
    """

    async def feature_checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        """
        Check feature flag for the current facility.

        @param current_user: Authenticated user
        @param db: Database session
        @returns CurrentUser if feature is enabled
        @raises HTTPException 403: If feature not in tier
        """
        if settings.beta_public_access:
            return current_user

        entitlements = await _get_entitlements(
            str(current_user.facility_id), db
        )

        if not entitlements["feature_flags"].get(flag, False):
            tier = entitlements["tier"]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_licensed",
                    "feature": flag,
                    "current_tier": tier,
                    "message": (
                        f"The '{flag}' feature is not available on your "
                        f"'{tier}' plan. Upgrade to access this feature."
                    ),
                    "upgrade_url": "/settings/billing",
                },
            )

        return current_user

    return feature_checker


def require_patient_capacity() -> Callable:
    """
    Dependency that blocks patient registration if limit reached.

    Usage: @router.post("/", dependencies=[Depends(require_patient_capacity())])

    @returns Dependency function
    """

    async def capacity_checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        """
        Check if facility can register more patients.

        @param current_user: Authenticated user
        @param db: Database session
        @returns CurrentUser if under limit
        @raises HTTPException 403: If patient limit reached
        """
        if settings.beta_public_access:
            return current_user

        service = LicensingService(db)
        limit_info = await service.check_patient_limit(current_user.facility_id)

        if limit_info["limit_reached"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "patient_limit_reached",
                    "current": limit_info["current"],
                    "limit": limit_info["limit"],
                    "current_tier": limit_info["tier"],
                    "message": (
                        f"Patient limit reached ({limit_info['current']}/{limit_info['limit']}). "
                        "Upgrade your plan to register more patients."
                    ),
                    "upgrade_url": "/settings/billing",
                },
            )

        return current_user

    return capacity_checker
