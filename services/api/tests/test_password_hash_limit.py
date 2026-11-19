"""The limit on argon2 operations running at once in the process (``auth/security.py``).

One operation holds about 64 MiB while it runs, so this limit is what keeps a burst of
logins or sign-ups inside the container's memory. A request that finds every slot taken
is turned away with 429 and must leave nothing behind: no failed login counted, no audit
row, no user.

Where calls have to overlap, the argon2 hasher is replaced by a fake that counts the calls
inside it and can keep them there. Nothing here depends on how long a real hash takes.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from oddvex_api.auth import security
from oddvex_api.auth.security import PasswordHashBusy
from oddvex_api.db import AuditLog, EmailOutbox, User

from .conftest import PASSWORD, AppFactory, SettingsFactory, register

EMAIL = "ada@example.test"
NEW_PASSWORD = "a-brand-new-password"
SLOTS = 2
#: Upper bound on any wait in this file, so a broken limiter fails a test instead of
#: hanging it. No passing test waits this long.
TIMEOUT = 5.0
SHED = {
    "error": {
        "code": "rate_limited",
        "message": "Too many requests. Try again in 1 seconds.",
        "details": {"retry_after_seconds": 1},
    }
}


# The limiter belongs to the process. ``conftest.py`` puts the defaults back after every test.


class CountingHasher:
    """Stands in for the argon2 hasher: counts the calls inside it and can keep them there."""

    def __init__(self, meet: threading.Barrier | None = None) -> None:
        self._lock = threading.Lock()
        self._meet = meet
        self.in_flight = 0
        self.peak = 0
        self.calls = 0
        #: Released once by every call as it gets in.
        self.entered = threading.Semaphore(0)
        #: Calls stay inside while this is clear.
        self.go = threading.Event()
        self.go.set()

    def _run(self) -> None:
        with self._lock:
            self.in_flight += 1
            self.calls += 1
            self.peak = max(self.peak, self.in_flight)
        try:
            self.entered.release()
            if self._meet is not None:
                self._meet.wait(timeout=TIMEOUT)
            assert self.go.wait(timeout=TIMEOUT), "the call was never let go"
        finally:
            with self._lock:
                self.in_flight -= 1

    def hash(self, password: str) -> str:
        self._run()
        return f"fake${password}"

    def verify(self, stored: str, password: str) -> bool:
        self._run()
        return True


@contextmanager
def held_slots(count: int) -> Iterator[CountingHasher]:
    """Keep ``count`` slots taken for the body, by parking that many calls inside the hasher."""
    hasher = CountingHasher()
    hasher.go.clear()
    with pytest.MonkeyPatch.context() as patch, ThreadPoolExecutor(max_workers=count) as pool:
        patch.setattr(security, "_hasher", hasher)
        parked = [pool.submit(security.hash_password, "parked") for _ in range(count)]
        try:
            for _ in range(count):
                assert hasher.entered.acquire(timeout=TIMEOUT), "a slot could not be taken"
            yield hasher
        finally:
            hasher.go.set()
            for call in parked:
                call.result(timeout=TIMEOUT)


# ---------------------------------------------------------------- the limiter
def test_hashes_in_flight_never_exceed_the_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    slots, callers = 3, 24
    # A call stays inside the hasher until ``slots`` calls are there together. So the limit
    # is reached in every round, and one call too many inside would show in ``peak``.
    hasher = CountingHasher(meet=threading.Barrier(slots))
    monkeypatch.setattr(security, "_hasher", hasher)
    security.configure_password_hashing(slots, wait_seconds=TIMEOUT)
    start = threading.Barrier(callers)

    def call(number: int) -> object:
        start.wait(timeout=TIMEOUT)
        if number % 2:
            return security.verify_password("pw", "stored")
        return security.hash_password("pw")

    with ThreadPoolExecutor(max_workers=callers) as pool:
        pending = [pool.submit(call, number) for number in range(callers)]
        # ``result`` re-raises: a caller that was shed, or stuck, fails the test here.
        results = [future.result(timeout=TIMEOUT) for future in pending]

    assert results == ["fake$pw", True] * (callers // 2)
    assert hasher.calls == callers
    assert hasher.peak == slots
    assert hasher.in_flight == 0


def test_a_full_limiter_raises_busy_and_works_again_once_a_slot_is_free() -> None:
    security.configure_password_hashing(SLOTS, wait_seconds=0)
    stored = security.hash_password(PASSWORD)
    with held_slots(SLOTS) as hasher:
        with pytest.raises(PasswordHashBusy) as shed:
            security.verify_password(PASSWORD, stored)
        assert shed.value.retry_after_seconds == security.PASSWORD_HASH_RETRY_AFTER_SECONDS == 1
        # The unknown-account path (dummy hash) and hashing are covered too.
        with pytest.raises(PasswordHashBusy):
            security.verify_password(PASSWORD, None)
        with pytest.raises(PasswordHashBusy):
            security.hash_password(PASSWORD)
        assert hasher.calls == SLOTS  # the shed calls never reached the hasher
    assert security.verify_password(PASSWORD, stored) is True
    assert security.verify_password("not-the-password", stored) is False
    assert security.hash_password(PASSWORD).startswith("$argon2id$")


def test_a_caller_waits_for_the_configured_time_before_it_is_shed() -> None:
    wait = 0.05
    security.configure_password_hashing(1, wait_seconds=wait)
    with held_slots(1):
        started = time.monotonic()
        with pytest.raises(PasswordHashBusy):
            security.hash_password(PASSWORD)
        assert time.monotonic() - started >= wait


def test_the_limiter_refuses_values_that_would_disable_it() -> None:
    with pytest.raises(ValueError):
        security.configure_password_hashing(0, 1.0)
    with pytest.raises(ValueError):
        security.configure_password_hashing(1, -1.0)
    # An infinite wait would overflow the semaphore's timeout and answer 500, not 429.
    for not_finite in (float("inf"), float("nan")):
        with pytest.raises(ValueError):
            security.configure_password_hashing(1, not_finite)


def test_a_slot_is_given_back_when_the_hasher_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """argon2 can fail (for example when memory cannot be allocated). A slot lost each time
    would shut sign-in for good, so it must come back whatever the hasher does."""

    class FailingHasher:
        def hash(self, password: str) -> str:
            raise MemoryError("no memory for the hash")

        def verify(self, stored: str, password: str) -> bool:
            raise MemoryError("no memory for the hash")

    security.configure_password_hashing(1, wait_seconds=0)
    stored = security.hash_password(PASSWORD)
    with monkeypatch.context() as patch:
        patch.setattr(security, "_hasher", FailingHasher())
        for _ in range(3):  # more failures than slots
            with pytest.raises(MemoryError):
                security.hash_password(PASSWORD)
            with pytest.raises(MemoryError):
                security.verify_password(PASSWORD, stored)
    # The one slot is free again: with no wait allowed, these would be shed otherwise.
    assert security.verify_password(PASSWORD, stored) is True
    assert security.hash_password(PASSWORD).startswith("$argon2id$")


# ------------------------------------------------------------------- settings
def test_settings_defaults_and_bounds(
    make_settings: SettingsFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = make_settings()
    assert (settings.password_hash_concurrency, settings.password_hash_wait_seconds) == (2, 1.0)
    # The limits in force before create_app runs (scripts) are the same ones.
    assert security.DEFAULT_PASSWORD_HASH_CONCURRENCY == 2
    assert security.DEFAULT_PASSWORD_HASH_WAIT_SECONDS == 1.0
    assert make_settings(password_hash_wait_seconds=0).password_hash_wait_seconds == 0
    for bad in (
        {"password_hash_concurrency": 0},
        {"password_hash_concurrency": 33},
        {"password_hash_wait_seconds": -0.1},
        {"password_hash_wait_seconds": 30.1},
        {"password_hash_wait_seconds": float("inf")},
    ):
        with pytest.raises(ValidationError):
            make_settings(**bad)
    monkeypatch.setenv("ODDVEX_PASSWORD_HASH_CONCURRENCY", "4")
    monkeypatch.setenv("ODDVEX_PASSWORD_HASH_WAIT_SECONDS", "0.5")
    from_env = make_settings()
    assert (from_env.password_hash_concurrency, from_env.password_hash_wait_seconds) == (4, 0.5)


def test_create_app_configures_the_limiter_from_settings(make_app: AppFactory) -> None:
    make_app(password_hash_concurrency=3, password_hash_wait_seconds=0.25)
    assert (security._limiter.slots, security._limiter.wait_seconds) == (3, 0.25)

    make_app(password_hash_concurrency=3, password_hash_wait_seconds=0)
    with held_slots(3), pytest.raises(PasswordHashBusy):  # three get in, a fourth does not
        security.hash_password(PASSWORD)

    make_app(password_hash_concurrency=1, password_hash_wait_seconds=0)
    with held_slots(1), pytest.raises(PasswordHashBusy):
        security.hash_password(PASSWORD)


def test_a_second_app_with_the_same_settings_does_not_free_the_slots(make_app: AppFactory) -> None:
    make_app(password_hash_concurrency=1, password_hash_wait_seconds=0)
    with held_slots(1):
        make_app(password_hash_concurrency=1, password_hash_wait_seconds=0)
        with pytest.raises(PasswordHashBusy):
            security.hash_password(PASSWORD)


# -------------------------------------------------------------------- the API
@pytest.fixture
def api(make_app: AppFactory) -> Iterator[TestClient]:
    """``SLOTS`` slots and no waiting. Rate limits are on with a per-IP limit that stays out
    of the way, and one failed login locks an email, so a failure counted by mistake shows
    up as a 429 on the next attempt."""
    app = make_app(
        password_hash_concurrency=SLOTS,
        password_hash_wait_seconds=0,
        rate_limit_enabled=True,
        rate_limit_auth_per_minute=1000,
        login_max_failures=1,
    )
    with TestClient(app) as client:
        yield client


def login(client: TestClient, password: str, email: str = EMAIL) -> Any:
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def rows(client: TestClient, column: Any) -> list[Any]:
    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        return sorted(db.scalars(select(column)))


def assert_shed(response: Any) -> None:
    """The same 429 a rate-limited request gets: standard envelope and ``Retry-After``."""
    assert response.status_code == 429, response.text
    assert response.json() == SHED
    assert response.headers["retry-after"] == "1"
    assert response.headers["x-request-id"]
    assert "access_token" not in response.text


def test_login_is_shed_with_429_and_no_failed_login_is_recorded(api: TestClient) -> None:
    register(api)
    with held_slots(SLOTS) as hasher:
        assert_shed(login(api, PASSWORD))
        assert_shed(login(api, "not-the-password"))
        assert_shed(login(api, PASSWORD, email="nobody@example.test"))
        assert hasher.calls == SLOTS  # none of the three reached the hasher
    assert rows(api, AuditLog.action) == ["auth.register"]
    # One counted failure would lock these emails (``login_max_failures`` is 1 here) and
    # the next attempts would be 429 instead.
    assert login(api, PASSWORD, email="nobody@example.test").status_code == 401
    assert login(api, PASSWORD).status_code == 200
    assert rows(api, AuditLog.action) == ["auth.login", "auth.login_failed", "auth.register"]
    # And the lock does work in this set-up, so the checks above mean something.
    assert login(api, "not-the-password").status_code == 401
    locked = login(api, PASSWORD)
    assert locked.status_code == 429 and locked.json() != SHED


def test_register_is_shed_with_429_and_creates_no_user(api: TestClient) -> None:
    register(api)
    grace = {
        "email": "grace@example.test",
        "password": PASSWORD,
        "display_name": "Grace",
        "age_confirmed": True,
    }
    with held_slots(SLOTS):
        assert_shed(api.post("/v1/auth/register", json=grace))
    assert rows(api, User.email) == [EMAIL]
    assert rows(api, AuditLog.action) == ["auth.register"]
    assert rows(api, EmailOutbox.to_email) == [EMAIL]
    # The same request goes through once a slot is free.
    assert api.post("/v1/auth/register", json=grace).status_code == 201
    assert rows(api, User.email) == [EMAIL, "grace@example.test"]


def test_password_change_and_reset_are_shed_and_change_nothing(api: TestClient) -> None:
    headers = {"Authorization": f"Bearer {register(api)['access_token']}"}
    assert api.post("/v1/auth/password-reset/request", json={"email": EMAIL}).status_code == 202
    token = api.get(
        "/v1/dev/email-outbox/latest", params={"to": EMAIL, "template": "password_reset"}
    ).json()["token"]
    change = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    reset = {"token": token, "new_password": NEW_PASSWORD}
    before = rows(api, AuditLog.action)

    with held_slots(SLOTS):
        assert_shed(api.post("/v1/me/password", json=change, headers=headers))
        assert_shed(api.post("/v1/auth/password-reset/confirm", json=reset))

    # Nothing was audited, least of all a failed password check; the access token and the
    # password still work; and the reset link was not used up.
    assert rows(api, AuditLog.action) == before
    assert api.get("/v1/me", headers=headers).status_code == 200
    assert login(api, PASSWORD).status_code == 200
    assert api.post("/v1/auth/password-reset/confirm", json=reset).status_code == 204
    assert login(api, NEW_PASSWORD).status_code == 200


def test_changing_the_password_takes_one_slot_at_a_time(make_app: AppFactory) -> None:
    """The route verifies and then hashes. With one slot and no waiting, holding the first
    slot while asking for the second would be shed."""
    app = make_app(password_hash_concurrency=1, password_hash_wait_seconds=0)
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {register(client)['access_token']}"}
        changed = client.post(
            "/v1/me/password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text
        assert login(client, NEW_PASSWORD).status_code == 200
