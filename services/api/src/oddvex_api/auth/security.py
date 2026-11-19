"""Password hashing (argon2id) and JWT access tokens."""

from __future__ import annotations

import math
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

_hasher = PasswordHasher()
# Verified against when the account does not exist, to keep login timing uniform.
_DUMMY_HASH = _hasher.hash("oddvex-timing-equaliser")

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "oddvex-api"

#: Limits used until :func:`configure_password_hashing` is called (scripts, tests). They
#: equal the defaults of ``Settings.password_hash_concurrency`` and
#: ``Settings.password_hash_wait_seconds``.
DEFAULT_PASSWORD_HASH_CONCURRENCY = 2
DEFAULT_PASSWORD_HASH_WAIT_SECONDS = 1.0
#: What a shed request is told to wait. A slot is held for the length of one hash.
PASSWORD_HASH_RETRY_AFTER_SECONDS = 1.0


class PasswordHashBusy(Exception):
    """Every hashing slot stayed taken for the whole wait, so the call was not run.

    It says nothing about the password. Callers must not treat it as a failed check:
    the API answers 429 (``errors.py``) without counting or auditing a failed login.
    """

    def __init__(self, retry_after_seconds: float = PASSWORD_HASH_RETRY_AFTER_SECONDS) -> None:
        super().__init__("Password hashing is at capacity")
        self.retry_after_seconds = retry_after_seconds


class _HashLimiter:
    """At most ``slots`` argon2 operations at once in this process.

    One argon2id operation with the library defaults holds about 64 MiB while it runs,
    so without a bound the memory in use grows with the number of parallel logins and
    sign-ups, whatever the request rate limit says.
    """

    def __init__(self, slots: int, wait_seconds: float) -> None:
        if slots < 1:
            raise ValueError("slots must be at least 1")
        if not math.isfinite(wait_seconds) or wait_seconds < 0:
            raise ValueError("wait_seconds must be a finite number, zero or more")
        self.slots = slots
        self.wait_seconds = wait_seconds
        self._semaphore = threading.BoundedSemaphore(slots)

    @contextmanager
    def slot(self) -> Iterator[None]:
        """Hold one slot for the body. Raises :class:`PasswordHashBusy` if none frees up
        within ``wait_seconds`` (0 does not wait at all)."""
        if not self._semaphore.acquire(timeout=self.wait_seconds):
            raise PasswordHashBusy
        try:
            yield
        finally:
            self._semaphore.release()


_limiter = _HashLimiter(DEFAULT_PASSWORD_HASH_CONCURRENCY, DEFAULT_PASSWORD_HASH_WAIT_SECONDS)
_limiter_lock = threading.Lock()


def configure_password_hashing(
    concurrency: int = DEFAULT_PASSWORD_HASH_CONCURRENCY,
    wait_seconds: float = DEFAULT_PASSWORD_HASH_WAIT_SECONDS,
) -> None:
    """Set how many argon2 operations may run at once and how long a caller waits for a slot.

    Called by ``create_app`` with the values from ``Settings``. The limit belongs to the
    process, not to one app: hashing memory is shared by everything in it. Calling this
    again with the same values keeps the limiter and the slots in use. With other values
    a new limiter takes over and operations already running finish on the old one, so the
    bound can be exceeded for as long as those take.
    """
    global _limiter
    with _limiter_lock:
        if (_limiter.slots, _limiter.wait_seconds) != (concurrency, wait_seconds):
            _limiter = _HashLimiter(concurrency, wait_seconds)


def hash_password(password: str) -> str:
    """Hash ``password``. Raises :class:`PasswordHashBusy` when no slot frees up in time."""
    with _limiter.slot():
        return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Whether ``password`` matches. Raises :class:`PasswordHashBusy` when no slot frees up
    in time; that is never reported as ``False``."""
    with _limiter.slot():
        try:
            return (
                _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
            )
        except (Argon2Error, InvalidHashError):
            return False


def create_access_token(
    user_id: str,
    role: str,
    secret: str,
    ttl_minutes: int,
    now: datetime | None = None,
    token_version: int = 0,
) -> tuple[str, int]:
    """Sign an access token. ``token_version`` is the user's current ``token_version``;
    it is only written when non-zero, so a token without the claim means version 0."""
    issued = now or datetime.now(UTC)
    ttl_seconds = ttl_minutes * 60
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iss": JWT_ISSUER,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    if token_version:
        payload["ver"] = token_version
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM), ttl_seconds


def decode_access_token(token: str, secret: str) -> dict[str, Any] | None:
    """Return the claims, or ``None`` if the token is invalid or expired."""
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.PyJWTError:
        return None
    return claims
