"""
SignalStream — Redis Client
=============================
Async Redis connection pool with tenant-aware key utilities.
"""

from __future__ import annotations

import os
from typing import Any

import redis.asyncio as aioredis

_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create the global async Redis connection pool."""
    global _pool
    if _pool is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        max_connections = int(os.environ.get("REDIS_MAX_CONNECTIONS", "100"))
        _pool = aioredis.from_url(
            redis_url,
            max_connections=max_connections,
            decode_responses=True,
        )
    return _pool


async def close_redis() -> None:
    """Shutdown hook: close the Redis connection pool."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


# ─── Tenant-Aware Key Helpers ────────────────────────────────


def tenant_key(company_id: str, *parts: str) -> str:
    """Build a tenant-scoped Redis key."""
    return f"tenant:{company_id}:{':'.join(parts)}"


def session_key(session_id: str) -> str:
    return f"session:{session_id}"


def rate_limit_key(company_id: str, endpoint: str) -> str:
    return f"ratelimit:{company_id}:{endpoint}"


def idempotency_key(company_id: str, key: str) -> str:
    return f"idempotency:{company_id}:{key}"


def cache_key(company_id: str, cache_type: str, content_hash: str) -> str:
    return f"cache:{cache_type}:{company_id}:{content_hash}"


def dedup_key(company_id: str, content_hash: str) -> str:
    return f"dedup:{company_id}:{content_hash}"


def analytics_key(company_id: str, view: str) -> str:
    return f"analytics:{company_id}:{view}"


# ─── Common Operations ──────────────────────────────────────


async def check_idempotency(company_id: str, key: str) -> str | None:
    """Check if an idempotency key exists. Returns event_id if duplicate."""
    r = await get_redis()
    return await r.get(idempotency_key(company_id, key))


async def set_idempotency(company_id: str, key: str, event_id: str, ttl: int = 86400) -> None:
    """Set an idempotency key with TTL (default 24h)."""
    r = await get_redis()
    await r.set(idempotency_key(company_id, key), event_id, ex=ttl)


async def check_rate_limit(company_id: str, endpoint: str, limit: int = 1000, window: int = 60) -> bool:
    """Simple sliding window rate limiter. Returns True if within limits."""
    r = await get_redis()
    key = rate_limit_key(company_id, endpoint)
    current = await r.incr(key)
    if current == 1:
        await r.expire(key, window)
    return current <= limit


async def get_cached(company_id: str, cache_type: str, content_hash: str) -> str | None:
    """Get a cached value."""
    r = await get_redis()
    return await r.get(cache_key(company_id, cache_type, content_hash))


async def set_cached(
    company_id: str, cache_type: str, content_hash: str, value: str, ttl: int = 3600
) -> None:
    """Set a cached value with TTL."""
    r = await get_redis()
    await r.set(cache_key(company_id, cache_type, content_hash), value, ex=ttl)
