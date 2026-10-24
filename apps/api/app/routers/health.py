"""
Health & Readiness Endpoints
"""

from __future__ import annotations

import time

from fastapi import APIRouter

from packages.schemas.api import HealthResponse, ReadyResponse

router = APIRouter()

_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health():
    """Liveness check."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        uptime_seconds=round(time.time() - _start_time, 2),
    )


@router.get("/ready", response_model=ReadyResponse)
async def readiness():
    """
    Readiness check: verifies core dependencies are reachable.
    In production, each check would actually ping the service.
    """
    checks = {
        "database": True,
        "redis": True,
        "kafka": True,
    }

    # TODO: Implement real connectivity checks
    # try:
    #     async with get_async_session() as session:
    #         await session.execute(text("SELECT 1"))
    # except Exception:
    #     checks["database"] = False
    #
    # try:
    #     r = await get_redis()
    #     await r.ping()
    # except Exception:
    #     checks["redis"] = False

    return ReadyResponse(
        ready=all(checks.values()),
        checks=checks,
    )
