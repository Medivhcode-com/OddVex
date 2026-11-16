"""In-memory sliding-window rate limiters: per IP, and per account.

Process-local: with several workers each worker keeps its own counters. Swap
for a shared store (e.g. Redis) before scaling horizontally.

Two limiters live on the app. ``rate_limiter`` counts requests per client IP
(:func:`rate_limit`). ``account_limiter`` counts things per account whatever the IP:
failed logins per email (:func:`check_login_allowed`, :func:`record_login_failure`) and
verification or reset emails per address (:func:`limit_account_action`). The per-account
keys are the address as typed, whether or not an account exists for it, so the answer
never reveals that.
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

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        cutoff = now - self.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        return hits

    def blocked_for(self, key: str, limit: int) -> float:
        """Seconds until ``key`` is back under ``limit``; 0 when it is. Records nothing."""
        now = self._clock()
        with self._lock:
            hits = self._prune(key, now)
            if len(hits) < limit:
                if not hits:
                    del self._hits[key]
                return 0.0
            return max(0.0, hits[len(hits) - limit] + self.window_seconds - now)

    def hit(self, key: str) -> None:
        """Record one occurrence without checking a limit."""
        now = self._clock()
        with self._lock:
            self._prune(key, now).append(now)
            if len(self._hits) > 10_000:
                cutoff = now - self.window_seconds
                for stale_key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
                    del self._hits[stale_key]

    def forget(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

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


def too_many_requests(retry_after: float) -> ApiError:
    seconds = max(1, int(retry_after + 0.999))
    return ApiError(
        429,
        "rate_limited",
        f"Too many requests. Try again in {seconds} seconds.",
        details={"retry_after_seconds": seconds},
        headers={"Retry-After": str(seconds)},
    )


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
            raise too_many_requests(retry_after)

    return dependency


# ------------------------------------------------------------ per account
def _login_key(email: str) -> str:
    return f"login-failed:{email}"


def check_login_allowed(request: Request, email: str) -> None:
    """429 when this email has had too many failed logins inside the window.

    Checked before the password, for any email, so a locked-out address looks the same
    whether or not an account exists for it and whichever IP the attempt comes from.
    """
    settings = request.app.state.settings
    if not settings.rate_limit_enabled:
        return
    limiter: SlidingWindowRateLimiter = request.app.state.account_limiter
    retry_after = limiter.blocked_for(_login_key(email), settings.login_max_failures)
    if retry_after > 0:
        raise too_many_requests(retry_after)


def record_login_failure(request: Request, email: str) -> None:
    if request.app.state.settings.rate_limit_enabled:
        request.app.state.account_limiter.hit(_login_key(email))


def clear_login_failures(request: Request, email: str) -> None:
    request.app.state.account_limiter.forget(_login_key(email))


def limit_account_action(request: Request, action: str, subject: str, limit: int) -> None:
    """Count one ``action`` for ``subject`` (an email or user id); 429 over ``limit``."""
    settings = request.app.state.settings
    if not settings.rate_limit_enabled:
        return
    limiter: SlidingWindowRateLimiter = request.app.state.account_limiter
    allowed, retry_after = limiter.check(f"{action}:{subject}", limit)
    if not allowed:
        raise too_many_requests(retry_after)
