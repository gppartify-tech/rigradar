"""Tiny fixed-window rate limiter on Redis (protects the paid AI chat endpoint)."""
from __future__ import annotations

import logging
import time

import redis
from fastapi import HTTPException

from app.config import settings

log = logging.getLogger(__name__)
_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1)
    return _client


def hit(bucket: str, limit: int, window_seconds: int) -> None:
    """Raise 429 when `bucket` was hit more than `limit` times in the current window.
    If Redis is down the request is allowed (fail open) - availability over strictness."""
    window = int(time.time() // window_seconds)
    key = f"rigradar:rl:{bucket}:{window}"
    try:
        client = _redis()
        count = client.incr(key)
        if count == 1:
            client.expire(key, window_seconds)
    except redis.RedisError as exc:
        log.warning("rate limiter unavailable: %s", exc)
        return
    if count > limit:
        raise HTTPException(429, "Too many messages - please wait a few minutes and try again.")
