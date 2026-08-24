import json
import logging
from typing import Any

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None


def _get_client() -> redis.Redis | None:
    """Lazily build a Redis client; None when unavailable (graceful mode)."""
    global _pool

    try:
        if _pool is None:
            _pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )

        client = redis.Redis(connection_pool=_pool)

        client.ping()

        return client
    except Exception:
        logger.warning("Redis unavailable - cache bypassed")

        return None


def cache_get(key: str) -> Any | None:
    client = _get_client()

    if not client:
        return None

    try:
        raw = client.get(key)

        return json.loads(raw) if raw else None
    except Exception:
        logger.warning("cache_get failed for %s", key)

        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    client = _get_client()

    if not client:
        return

    try:
        client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception:
        logger.warning("cache_set failed for %s", key)


def invalidate_prefix(prefix: str) -> int:
    """Delete keys matching prefix*; returns count (best effort)."""
    client = _get_client()

    if not client:
        return 0

    try:
        keys = list(client.scan_iter(f"{prefix}*"))
        count = len(keys)

        if keys:
            client.delete(*keys)

        return count
    except Exception:
        logger.warning("invalidate_prefix failed for %s", prefix)

        return 0
