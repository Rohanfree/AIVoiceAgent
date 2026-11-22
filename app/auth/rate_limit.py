"""
rate_limit.py — Minimal in-memory fixed-window rate limiter for auth endpoints.

LIMITATION: state lives in this process's memory. It is only a valid security
boundary for a single-process deployment (one uvicorn worker). With multiple
workers or instances each keeps its own counters, so the effective limit is
multiplied by the process count and resets on restart; use shared storage
(e.g. Redis) before scaling out.

Requests are keyed by the TCP peer address. Behind a reverse proxy that is the
proxy's address, so all clients would share one bucket; forwarded headers are
deliberately NOT trusted here because clients can spoof them.
"""

import math
import time
from typing import Callable

from fastapi import HTTPException, Request, status

from app.config import settings


class FixedWindowRateLimiter:
    """Counts hits per key in fixed windows. `clock` is injectable for tests."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        # key -> (window_start, hits)
        self._buckets: dict[str, tuple[float, int]] = {}

    def hit(self, key: str, limit: int, window: float) -> int:
        """Record a request. Returns 0 if allowed, else seconds until retry."""
        now = self._clock()
        if len(self._buckets) > 10_000:
            self._buckets = {k: v for k, v in self._buckets.items() if now - v[0] < window}
        start, hits = self._buckets.get(key, (now, 0))
        if now - start >= window:
            start, hits = now, 0
        if hits >= limit:
            return max(1, math.ceil(start + window - now))
        self._buckets[key] = (start, hits + 1)
        return 0

    def reset(self) -> None:
        self._buckets.clear()


limiter = FixedWindowRateLimiter()


def rate_limit(scope: str):
    """Dependency factory: limit each client address separately per `scope`."""

    async def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        retry_after = limiter.hit(
            f"{scope}:{client}",
            settings.auth_rate_limit_max_requests,
            settings.auth_rate_limit_window_seconds,
        )
        if retry_after:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
