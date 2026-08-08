from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from backend.app.core.config import get_settings


@dataclass
class RateLimitBucket:
    window_started_at: float
    count: int


class InMemoryRateLimiter:
    """Small fixed-window limiter for the single-process deployment phase."""

    def __init__(self) -> None:
        self._buckets: dict[str, RateLimitBucket] = {}
        self._lock = threading.Lock()

    def check(self, *, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(now, window_seconds)
            bucket = self._buckets.get(key)
            if bucket is None or now - bucket.window_started_at >= window_seconds:
                self._buckets[key] = RateLimitBucket(window_started_at=now, count=1)
                return

            if bucket.count >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket.window_started_at)))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "code": "RATE_LIMIT_EXCEEDED",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            bucket.count += 1

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()

    def _prune(self, now: float, window_seconds: int) -> None:
        expired = [
            key
            for key, bucket in self._buckets.items()
            if now - bucket.window_started_at >= window_seconds
        ]
        for key in expired:
            self._buckets.pop(key, None)


rate_limiter = InMemoryRateLimiter()


def enforce_rate_limit(request: Request, token: str | None = None) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    client_host = request.client.host if request.client else "unknown"
    identity = token or "anonymous"
    path = request.url.path
    key = f"{client_host}:{identity}:{path}"
    rate_limiter.check(
        key=key,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
