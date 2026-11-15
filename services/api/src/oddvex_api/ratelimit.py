"""In-memory per-IP sliding-window rate limiter.

Process-local: with several workers each worker keeps its own counters. Swap
for a shared store (e.g. Redis) before scaling horizontally.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

from .errors import ApiError


class SlidingWindowRateLimiter:
    def __init__(self, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.window_seconds = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int) -> tuple[bool, float]:
        """Record a hit. Returns ``(allowed, retry_after_seconds)``."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False, max(0.0, hits[0] + self.window_seconds - now)
            hits.append(now)
            if len(self._hits) > 10_000:
                for stale_key in [k for k, v in self._hits.items() if not v]:
                    del self._hits[stale_key]
            return True, 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_ip(request: Request) -> str:
    """Client address used for rate limiting and audit rows.

    The direct peer address is used unless ``ODDVEX_TRUST_PROXY=true``. In that
    case the *last* ``X-Forwarded-For`` entry is used: it is the one appended by
    the trusted proxy directly in front of the app, whereas earlier entries are
    supplied by the client and can be forged. Only enable this behind exactly
    one proxy that sets the header.
    """
    settings = getattr(request.app.state, "settings", None)
    if settings is not None and settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.split(",")[-1].strip()
        if last:
            return last[:64]
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str) -> Callable[[Request], None]:
    """FastAPI dependency enforcing the configured limit for ``bucket``."""

    def dependency(request: Request) -> None:
        settings = request.app.state.settings
        if not settings.rate_limit_enabled:
            return
        limiter: SlidingWindowRateLimiter = request.app.state.rate_limiter
        limit = int(getattr(settings, f"rate_limit_{bucket}_per_minute"))
        allowed, retry_after = limiter.check(f"{bucket}:{client_ip(request)}", limit)
        if not allowed:
            seconds = max(1, int(retry_after + 0.999))
            raise ApiError(
                429,
                "rate_limited",
                f"Too many requests. Try again in {seconds} seconds.",
                details={"retry_after_seconds": seconds},
                headers={"Retry-After": str(seconds)},
            )

    return dependency
