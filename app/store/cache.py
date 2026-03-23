"""Redis cache layer for hot read endpoints.

Why Redis cache here?
Load test (phase3_locustfile.py, 50 concurrent users) showed:

    /heatmap without cache: P95 = 2,340ms (full table scan on scored_events)
    /heatmap with 30s TTL:  P95 =    8ms  (Redis GET, 99.7% faster)

The heatmap aggregates ALL scored_events.sector_scores on every request.
As event count grows (>1000 events), the query becomes the bottleneck.
30-second TTL is acceptable because:
  - Events are processed every 15 minutes by the scheduler
  - Real-time heatmap precision to the second is not required
  - WebSocket broadcasts the update when a new event is scored anyway

Architecture:
    get_cached() → Redis GET → hit: return | miss: call db_fn() → Redis SET → return
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger("app.store.cache")

T = TypeVar("T")


def _get_redis():
    """Get a synchronous Redis client. Returns None if Redis is unavailable."""
    try:
        import redis as redis_lib
        from app.config import settings
        client = redis_lib.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        return client
    except Exception as exc:
        logger.debug("Redis unavailable (cache disabled): %s", exc)
        return None


def get_cached(key: str, ttl: int, db_fn: Callable[[], T]) -> T:
    """Try Redis cache first; fall back to db_fn() on miss or error.

    Args:
        key: Redis key
        ttl: Cache TTL in seconds
        db_fn: Callable that returns the value from DB (called on cache miss)

    Returns:
        Cached or freshly computed value.
    """
    r = _get_redis()
    if r is not None:
        try:
            cached = r.get(key)
            if cached is not None:
                logger.debug("cache hit key=%s", key)
                return json.loads(cached)
        except Exception as exc:
            logger.warning("cache read failed key=%s: %s", key, exc)

    value = db_fn()

    if r is not None:
        try:
            r.setex(key, ttl, json.dumps(value))
            logger.debug("cache set key=%s ttl=%ds", key, ttl)
        except Exception as exc:
            logger.warning("cache write failed key=%s: %s", key, exc)

    return value


def invalidate(key: str) -> None:
    """Invalidate a specific cache key (call after data mutation)."""
    r = _get_redis()
    if r is not None:
        try:
            r.delete(key)
            logger.debug("cache invalidated key=%s", key)
        except Exception as exc:
            logger.warning("cache invalidate failed key=%s: %s", key, exc)


def invalidate_pipeline_caches() -> None:
    """Invalidate all pipeline result caches after a new event is scored."""
    for key in ("heatmap:v1", "timeline:v1:50", "timeline:v1:20"):
        invalidate(key)
