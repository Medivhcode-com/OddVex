"""In-memory sliding-window rate limiters: per IP, and per account.

Process-local: with several workers each worker keeps its own counters. Swap
for a shared store (e.g. Redis) before scaling horizontally.

Two limiters live on the app. ``rate_limiter`` counts requests per client IP
(:func:`rate_limit`). ``account_limiter`` counts things per account whatever the IP:
failed logins per email (:func:`check_login_allowed`, :func:`record_login_failure`) and
verification or reset emails per address (:func:`limit_account_action`). The per-account
keys are the address as typed, whether or not an account exists for it, so the answer
never reveals that.

The community has limiters with their own windows (picks per day; comments, reports and
follows per hour), counted per user: :func:`check_user_quota` and :func:`use_user_quota`.

Routes that write or export a user's own data are limited per user id, whatever the
address: :func:`user_rate_limit` is the dependency and :func:`enforce_user_limit` the
call behind it. Each bucket in :data:`USER_LIMITS` has one or more ceilings (bet and sync
writes: per minute and per day; the export: per hour), each one a setting.

Those count requests over time. Two things are also limited by how many one user has in
progress at the same moment, because each one holds memory for as long as it runs:
streamed responses (:func:`take_user_stream_slot`, :class:`UserStreamResponse`) and
auto-settlement (:func:`user_exclusive`).
"""

from __future__ import annotations

import threading
import time
import weakref
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

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
                # Keys are only pruned when they are used again, so compare the newest
                # hit with the window: a key nobody has used since is dropped here.
                for stale_key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
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


class CoarseWindowCounter:
    """A sliding window counted in fixed buckets, for long windows with high ceilings.

    :class:`SlidingWindowRateLimiter` keeps one timestamp per hit, which is fine for ten
    hits a minute and wasteful for thousands a day. This keeps one integer per bucket
    (24 hourly buckets for a day), so a key costs the same however many hits it has. The
    price is precision: a hit leaves the window when its bucket does, up to one bucket
    length early. Same ``check`` contract as the sliding limiter.
    """

    def __init__(
        self,
        window_seconds: float,
        buckets: int = 24,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window_seconds = window_seconds
        self._buckets = max(1, buckets)
        self._bucket_seconds = window_seconds / self._buckets
        self._clock = clock
        self._lock = threading.Lock()
        #: key -> {bucket number: hits in it}
        self._hits: dict[str, dict[int, int]] = {}

    def _live(self, key: str, current: int) -> dict[int, int]:
        """The key's buckets still inside the window ending in bucket ``current``."""
        counts = self._hits.get(key)
        if counts is None:
            return {}
        oldest = current - self._buckets + 1
        for bucket in [b for b in counts if b < oldest]:
            del counts[bucket]
        return counts

    def check(self, key: str, limit: int) -> tuple[bool, float]:
        """Record a hit. Returns ``(allowed, retry_after_seconds)``. A refused hit is not
        recorded."""
        now = self._clock()
        current = int(now // self._bucket_seconds)
        with self._lock:
            counts = self._live(key, current)
            total = sum(counts.values())
            if total >= limit:
                # Wait until enough of the oldest buckets have left the window.
                excess = total - limit + 1
                leaves = current
                for bucket in sorted(counts):
                    excess -= counts[bucket]
                    leaves = bucket
                    if excess <= 0:
                        break
                gone_at = (leaves + self._buckets) * self._bucket_seconds
                return False, max(0.0, gone_at - now)
            if not counts:
                counts = self._hits.setdefault(key, {})
            counts[current] = counts.get(current, 0) + 1
            if len(self._hits) > 10_000:
                oldest = current - self._buckets + 1
                for stale in [k for k, v in self._hits.items() if not v or max(v) < oldest]:
                    del self._hits[stale]
            return True, 0.0

    def size(self) -> int:
        """Keys with at least one hit inside the window."""
        current = int(self._clock() // self._bucket_seconds)
        with self._lock:
            for key in list(self._hits):
                if not self._live(key, current):
                    del self._hits[key]
            return len(self._hits)

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


# ------------------------------------------------------- per user, own window
def check_user_quota(request: Request, limiter_name: str, user_id: str, limit: int) -> None:
    """429 when ``user_id`` already used ``limit`` slots of ``app.state.<limiter_name>``.

    Records nothing: call :func:`use_user_quota` once the action has succeeded, so a
    request that fails validation does not use up a slot.
    """
    if not request.app.state.settings.rate_limit_enabled:
        return
    limiter: SlidingWindowRateLimiter = getattr(request.app.state, limiter_name)
    retry_after = limiter.blocked_for(user_id, limit)
    if retry_after > 0:
        raise too_many_requests(retry_after)


def use_user_quota(request: Request, limiter_name: str, user_id: str) -> None:
    if request.app.state.settings.rate_limit_enabled:
        getattr(request.app.state, limiter_name).hit(user_id)


# ------------------------------------------------- per user, writes and export
@dataclass(frozen=True, slots=True)
class UserCeiling:
    """One ceiling of a per-user bucket: ``setting`` requests per ``window_seconds``."""

    #: Name of the ``Settings`` field that holds the ceiling.
    setting: str
    window_seconds: float
    #: Count in buckets (:class:`CoarseWindowCounter`) instead of one timestamp per hit.
    coarse: bool = False


#: The per-user buckets. ``writes`` is shared by the bet write routes and the sync write
#: routes; ``export`` belongs to ``GET /v1/me/export``.
USER_LIMITS: dict[str, tuple[UserCeiling, ...]] = {
    "writes": (
        UserCeiling("rate_limit_user_writes_per_minute", 60),
        UserCeiling("rate_limit_user_writes_per_day", 86_400, coarse=True),
    ),
    "export": (UserCeiling("rate_limit_export_per_hour", 3_600),),
}

_user_limiters_lock = threading.Lock()


def _user_limiter(
    app: FastAPI, bucket: str, ceiling: UserCeiling
) -> SlidingWindowRateLimiter | CoarseWindowCounter:
    """The app's counter for one ceiling, created the first time it is needed.

    Kept on ``app.state`` like the other limiters, so each app (each test) has its own.
    """
    limiters: dict[str, Any] | None = getattr(app.state, "user_limiters", None)
    name = f"{bucket}:{ceiling.setting}"
    if limiters is None or name not in limiters:
        with _user_limiters_lock:
            limiters = getattr(app.state, "user_limiters", None)
            if limiters is None:
                limiters = {}
                app.state.user_limiters = limiters
            if name not in limiters:
                limiters[name] = (
                    CoarseWindowCounter(ceiling.window_seconds)
                    if ceiling.coarse
                    else SlidingWindowRateLimiter(ceiling.window_seconds)
                )
    limiter: SlidingWindowRateLimiter | CoarseWindowCounter = limiters[name]
    return limiter


def enforce_user_limit(request: Request, bucket: str, user_id: str) -> None:
    """Count one request of ``user_id`` in ``bucket``; 429 with ``Retry-After`` over a ceiling.

    Keyed on the user id, so it holds from any address and does not affect other users
    behind the same address. Every request counts, whether or not it goes on to succeed.
    A request refused by one ceiling is not counted by the ceilings after it.
    """
    settings = request.app.state.settings
    if not settings.rate_limit_enabled:
        return
    for ceiling in USER_LIMITS[bucket]:
        limiter = _user_limiter(request.app, bucket, ceiling)
        allowed, retry_after = limiter.check(user_id, int(getattr(settings, ceiling.setting)))
        if not allowed:
            raise too_many_requests(retry_after)


def user_rate_limit(
    bucket: str, user_dependency: Callable[..., Any] | None = None
) -> Callable[..., None]:
    """FastAPI dependency enforcing the per-user ceilings of ``bucket`` (:data:`USER_LIMITS`).

    The user comes from ``user_dependency``, by default the signed-in user every other
    route uses; FastAPI resolves it once per request, so adding this to a route that
    already depends on the user costs no second lookup. Use as
    ``dependencies=[Depends(user_rate_limit("writes"))]``.
    """
    if bucket not in USER_LIMITS:
        raise ValueError(f"unknown per-user rate limit bucket {bucket!r}")
    if user_dependency is None:
        from .deps import get_current_user  # imported here: deps.py imports this module

        user_dependency = get_current_user

    # The user is declared as a default value, not in the annotation: annotations in this
    # module are strings, and FastAPI could not resolve a name that only exists here.
    def dependency(request: Request, user: Any = Depends(user_dependency)) -> None:
        enforce_user_limit(request, bucket, user.id)

    return dependency


# ------------------------------------------------ per user, in progress at once
class InProgressCounter:
    """How many of something each key has in progress right now.

    :meth:`leave` never waits for the lock. It can be called by a finaliser (a streamed
    response that was dropped without being sent), and a finaliser can run in the middle
    of any code, including code of this class that holds the lock in the same thread:
    waiting there would never end. A slot that is given back is noted first and taken off
    the count by whichever call holds the lock next; ``enter`` and ``active`` do that
    before they look at the count.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: dict[str, int] = {}
        #: Keys whose slot was given back and is not yet taken off ``_active``.
        self._given_back: deque[str] = deque()

    def _settle(self) -> None:
        """Take every slot given back off the count. Called with the lock held."""
        while True:
            try:
                key = self._given_back.popleft()
            except IndexError:
                return
            active = self._active.get(key, 0)
            if active <= 1:
                self._active.pop(key, None)
            else:
                self._active[key] = active - 1

    def enter(self, key: str, limit: int) -> bool:
        """Take a slot of ``key`` unless ``limit`` are already taken."""
        with self._lock:
            self._settle()
            active = self._active.get(key, 0)
            if active >= limit:
                return False
            self._active[key] = active + 1
            return True

    def leave(self, key: str) -> None:
        """Give a slot of ``key`` back. Returns at once, whoever holds the lock."""
        self._given_back.append(key)
        if self._lock.acquire(blocking=False):
            try:
                self._settle()
            finally:
                self._lock.release()

    def active(self, key: str) -> int:
        with self._lock:
            self._settle()
            return self._active.get(key, 0)


def _in_progress(app: FastAPI, name: str) -> InProgressCounter:
    """The app's counter ``name``, created the first time it is needed (see
    :func:`_user_limiter`)."""
    counters: dict[str, InProgressCounter] | None = getattr(app.state, "user_in_progress", None)
    if counters is None or name not in counters:
        with _user_limiters_lock:
            counters = getattr(app.state, "user_in_progress", None)
            if counters is None:
                counters = {}
                app.state.user_in_progress = counters
            counters.setdefault(name, InProgressCounter())
    return counters[name]


def _take_slot(request: Request, name: str, user_id: str, limit: int) -> Callable[[], None]:
    """Take one of the user's ``limit`` slots of ``name``; 429 when all are in use.

    Returns the call that gives the slot back. Calling it more than once gives the slot
    back once. With rate limiting off nothing is counted.
    """
    if not request.app.state.settings.rate_limit_enabled:
        return lambda: None
    counter = _in_progress(request.app, name)
    if not counter.enter(user_id, limit):
        raise too_many_requests(1)
    once = threading.Lock()

    def release() -> None:
        if once.acquire(blocking=False):
            counter.leave(user_id)

    return release


def take_user_stream_slot(request: Request, user_id: str) -> Callable[[], None]:
    """Count one more streamed response in progress for ``user_id``.

    A streamed response holds one batch of rows for as long as the client takes to read
    it, so a client that opens many and reads none would otherwise hold many batches.
    Over ``rate_limit_user_streams_at_once`` the answer is the standard 429. Returns the
    call that gives the slot back: pass it to :class:`UserStreamResponse`, or call it
    when no response is going to be sent after all.
    """
    limit = int(request.app.state.settings.rate_limit_user_streams_at_once)
    return _take_slot(request, "streams", user_id, limit)


@contextmanager
def user_exclusive(request: Request, name: str, user_id: str) -> Iterator[None]:
    """Run the block for ``user_id`` only if no other request of that user is inside a
    block of the same ``name``; otherwise 429 with ``Retry-After``."""
    release = _take_slot(request, name, user_id, 1)
    try:
        yield
    finally:
        release()


class UserStreamResponse(StreamingResponse):
    """A streamed response that gives its slot back when it ends, however it ends:
    sent in full, cut short by the client, failed part-way, or never sent at all."""

    def __init__(
        self, content: Iterator[bytes], release: Callable[[], None], media_type: str
    ) -> None:
        super().__init__(content, media_type=media_type)
        # Runs ``release`` once: when the response has ended, or, for a response that is
        # dropped without ever being sent, when it is discarded.
        self._give_back = weakref.finalize(self, release)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._give_back()
