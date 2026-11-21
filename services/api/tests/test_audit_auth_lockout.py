"""Sign-in lockout: failed sign-ins are counted per (email, client network), with a much
higher ceiling per email across all networks.

A stranger's failures must lock out only the stranger. Before, eight wrong passwords from
anywhere refused the owner's correct password from every address for fifteen minutes, and
the stranger could renew that for as long as they liked.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oddvex_api.ratelimit import SlidingWindowRateLimiter, client_ip, client_network

from .conftest import PASSWORD, AppFactory, register

EMAIL = "ada@example.test"
WRONG = "wrong-password"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def lockout_client(make_app: AppFactory, **overrides: Any) -> tuple[TestClient, FakeClock]:
    """Rate limits on, with a per-IP limit high enough to stay out of the way."""
    settings: dict[str, Any] = {
        "rate_limit_enabled": True,
        "rate_limit_auth_per_minute": 100_000,
        "trust_proxy": True,
        **overrides,
    }
    app = make_app(**settings)
    clock = FakeClock()
    app.state.account_limiter = SlidingWindowRateLimiter(
        app.state.settings.account_limit_window_seconds, clock=clock
    )
    return TestClient(app), clock


@pytest.fixture
def throttled(make_app: AppFactory) -> Iterator[tuple[TestClient, FakeClock]]:
    client, clock = lockout_client(make_app)
    with client:
        register(client)
        yield client, clock


def attempt(client: TestClient, email: str, password: str, ip: str = "198.51.100.1") -> Any:
    return client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Forwarded-For": ip},
    )


def lock_out(client: TestClient, email: str, ip: str, failures: int = 8) -> None:
    for number in range(failures):
        assert attempt(client, email, WRONG, ip=ip).status_code == 401, number
    assert attempt(client, email, WRONG, ip=ip).status_code == 429


# ------------------------------------------------------------- the finding itself
def test_a_strangers_failures_do_not_lock_out_the_owner(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, clock = throttled
    assert client.app.state.settings.login_max_failures == 8  # type: ignore[attr-defined]
    lock_out(client, EMAIL, "203.0.113.9")
    # The stranger stays refused, right password or not.
    assert attempt(client, EMAIL, PASSWORD, ip="203.0.113.9").status_code == 429
    # The owner signs in from their own address, as often as they like.
    for _ in range(3):
        signed_in = attempt(client, EMAIL, PASSWORD, ip="198.51.100.20")
        assert signed_in.status_code == 200, signed_in.text

    # The stranger renews the lock every window; the owner is never affected.
    for _ in range(3):
        clock.now += 901
        lock_out(client, EMAIL, "203.0.113.9")
        assert attempt(client, EMAIL, PASSWORD, ip="198.51.100.20").status_code == 200


def test_the_pair_is_refused_with_the_same_429_as_before(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, clock = throttled
    for number in range(8):
        clock.now += 10
        assert attempt(client, EMAIL, WRONG, ip="203.0.113.9").status_code == 401, number
    blocked = attempt(client, EMAIL, PASSWORD, ip="203.0.113.9")
    assert blocked.status_code == 429
    body = blocked.json()["error"]
    assert body["code"] == "rate_limited" and set(body) == {"code", "message", "details"}
    # The first failure was 70 seconds ago in a 900 second window.
    assert body["details"] == {"retry_after_seconds": 830}
    assert blocked.headers["retry-after"] == "830"
    assert "access_token" not in blocked.text
    # Attempts made while refused are not counted, so they do not extend the refusal.
    clock.now += 829
    assert attempt(client, EMAIL, PASSWORD, ip="203.0.113.9").status_code == 429
    clock.now += 2
    assert attempt(client, EMAIL, PASSWORD, ip="203.0.113.9").status_code == 200


def test_a_successful_sign_in_clears_only_the_callers_own_pair(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    for _ in range(7):
        assert attempt(client, EMAIL, WRONG, ip="203.0.113.9").status_code == 401
        assert attempt(client, EMAIL, WRONG, ip="198.51.100.20").status_code == 401
    assert attempt(client, EMAIL, PASSWORD, ip="198.51.100.20").status_code == 200
    # The owner's count starts again from zero...
    for _ in range(7):
        assert attempt(client, EMAIL, WRONG, ip="198.51.100.20").status_code == 401
    assert attempt(client, EMAIL, PASSWORD, ip="198.51.100.20").status_code == 200
    # ...and the other address keeps its seven: one more failure and it is refused.
    assert attempt(client, EMAIL, WRONG, ip="203.0.113.9").status_code == 401
    assert attempt(client, EMAIL, PASSWORD, ip="203.0.113.9").status_code == 429


def test_one_address_is_counted_separately_for_each_email(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    register(client, "grace@example.test")
    lock_out(client, EMAIL, "203.0.113.9")
    assert attempt(client, "grace@example.test", PASSWORD, ip="203.0.113.9").status_code == 200


# -------------------------------------------------------------- the client network
def test_an_ipv6_host_cannot_dodge_the_count_inside_its_64_prefix(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    for number in range(8):
        failed = attempt(client, EMAIL, WRONG, ip=f"2001:db8:1:2:{number + 1:x}::{number + 7:x}")
        assert failed.status_code == 401, number
    # A ninth address of the same /64 is refused, in any spelling of the prefix.
    assert attempt(client, EMAIL, PASSWORD, ip="2001:db8:1:2:ffff::1").status_code == 429
    assert attempt(client, EMAIL, PASSWORD, ip="2001:0DB8:0001:0002::9").status_code == 429
    # The neighbouring /64 is another network.
    assert attempt(client, EMAIL, PASSWORD, ip="2001:db8:1:3::1").status_code == 200


def test_ipv4_addresses_are_separate_networks_even_when_neighbours(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    lock_out(client, EMAIL, "203.0.113.9")
    assert attempt(client, EMAIL, PASSWORD, ip="203.0.113.10").status_code == 200


def test_client_network() -> None:
    assert client_network("203.0.113.9") == "203.0.113.9"
    assert client_network(" 203.0.113.9 ") == "203.0.113.9"
    assert client_network("2001:db8:1:2:3:4:5:6") == "2001:db8:1:2::/64"
    assert client_network("2001:0DB8:0001:0002::1") == "2001:db8:1:2::/64"
    assert client_network("::1") == "::/64"
    # An IPv4 address written as IPv6 is that IPv4 address, not one bucket for all of IPv4.
    assert client_network("::ffff:203.0.113.9") == "203.0.113.9"
    assert client_network("::ffff:203.0.113.10") == "203.0.113.10"
    # A zone index is not part of the network, and neither is a port a proxy added.
    assert client_network("fe80::1%eth0") == "fe80::/64"
    assert client_network("203.0.113.9:51234") == "203.0.113.9"
    assert client_network("[2001:db8:1:2::9]:51234") == "2001:db8:1:2::/64"
    assert client_network("[2001:db8:1:2::9]") == "2001:db8:1:2::/64"
    assert client_network("[::ffff:203.0.113.9]:443") == "203.0.113.9"
    # Not an address (the test client's peer name, or a proxy that sends something else):
    # used as it is, without whitespace, so it can never be read as two parts of a key.
    assert client_network("testclient") == "testclient"
    assert client_network("not an address") == "notanaddress"
    assert client_network("") == "unknown"


def test_a_forwarded_address_with_control_characters_is_not_used() -> None:
    from starlette.datastructures import State
    from starlette.requests import Request

    class App:
        state = State({"settings": type("S", (), {"trust_proxy": True})()})

    def request(forwarded: bytes) -> Request:
        return Request(
            {
                "type": "http",
                "app": App(),
                "headers": [(b"x-forwarded-for", forwarded)],
                "client": ("192.0.2.1", 1234),
            }
        )

    assert client_ip(request(b"198.51.100.7, 203.0.113.9")) == "203.0.113.9"
    assert client_ip(request(b"203.0.113.9\x00")) == "192.0.2.1"
    assert client_ip(request(b"203.0.113.9, 20\x003.0.113.9\x7f")) == "192.0.2.1"
    assert client_ip(request(b"")) == "192.0.2.1"


def test_an_ipv4_mapped_address_shares_the_count_of_its_ipv4_address(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    lock_out(client, EMAIL, "::ffff:203.0.113.9")
    assert attempt(client, EMAIL, PASSWORD, ip="203.0.113.9").status_code == 429
    assert attempt(client, EMAIL, PASSWORD, ip="::ffff:203.0.113.10").status_code == 200


def test_without_a_trusted_proxy_the_peer_address_is_the_network(make_app: AppFactory) -> None:
    client, _ = lockout_client(make_app, trust_proxy=False)
    with client:
        register(client)
        # The header is ignored, so every attempt is from the same peer.
        for number in range(8):
            assert attempt(client, EMAIL, WRONG, ip=f"203.0.113.{number}").status_code == 401
        assert attempt(client, EMAIL, PASSWORD, ip="198.51.100.20").status_code == 429


# ---------------------------------------------------------- the per-email ceiling
def test_guessing_spread_over_many_addresses_is_stopped_by_the_per_email_ceiling(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, clock = throttled
    settings = client.app.state.settings  # type: ignore[attr-defined]
    assert settings.login_max_failures_per_email == 50
    for number in range(50):
        clock.now += 1
        # Seven addresses' worth of guesses would trip no pair; fifty in all trip the email.
        failed = attempt(client, EMAIL, WRONG, ip=f"203.0.113.{number}")
        assert failed.status_code == 401, number
    for ip in ("203.0.113.200", "198.51.100.20"):
        blocked = attempt(client, EMAIL, PASSWORD, ip=ip)
        assert blocked.status_code == 429
        body = blocked.json()["error"]
        assert body["code"] == "rate_limited" and set(body) == {"code", "message", "details"}
        # The first of the fifty was 49 seconds ago in a 900 second window.
        assert body["details"] == {"retry_after_seconds": 851}
        assert blocked.headers["retry-after"] == "851"
    # Other accounts are not affected, and the window moves on.
    register(client, "grace@example.test")
    assert attempt(client, "grace@example.test", PASSWORD, ip="203.0.113.1").status_code == 200
    clock.now += 852
    assert attempt(client, EMAIL, PASSWORD, ip="198.51.100.20").status_code == 200


def test_a_successful_sign_in_does_not_reset_the_per_email_count(
    make_app: AppFactory,
) -> None:
    client, _ = lockout_client(make_app, login_max_failures_per_email=10)
    with client:
        register(client)
        for number in range(9):
            assert attempt(client, EMAIL, WRONG, ip=f"203.0.113.{number}").status_code == 401
        # The owner signs in: their own pair is cleared, the count for the email is not,
        # or a guesser who also holds one valid password could reset it at will.
        assert attempt(client, EMAIL, PASSWORD, ip="198.51.100.20").status_code == 200
        assert attempt(client, EMAIL, WRONG, ip="203.0.113.99").status_code == 401
        assert attempt(client, EMAIL, PASSWORD, ip="198.51.100.20").status_code == 429


def test_the_longer_of_the_two_refusals_is_reported(make_app: AppFactory) -> None:
    client, clock = lockout_client(make_app, login_max_failures=2, login_max_failures_per_email=3)
    with client:
        register(client)
        assert attempt(client, EMAIL, WRONG, ip="203.0.113.1").status_code == 401  # t = 1000
        clock.now += 100
        assert attempt(client, EMAIL, WRONG, ip="203.0.113.2").status_code == 401  # t = 1100
        clock.now += 100
        assert attempt(client, EMAIL, WRONG, ip="203.0.113.2").status_code == 401  # t = 1200
        # 203.0.113.2: its pair frees at 1100 + 900, the email at 1000 + 900. The pair is later.
        blocked = attempt(client, EMAIL, PASSWORD, ip="203.0.113.2")
        assert blocked.json()["error"]["details"] == {"retry_after_seconds": 800}
        # 203.0.113.1 has one failure of its own: only the email ceiling refuses it.
        blocked = attempt(client, EMAIL, PASSWORD, ip="203.0.113.1")
        assert blocked.json()["error"]["details"] == {"retry_after_seconds": 700}


# -------------------------------------------------- nothing is revealed, nothing leaks
def test_the_answers_are_identical_for_an_email_without_an_account(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    seen: dict[str, list[tuple[int, str, dict[str, Any], str | None]]] = {}
    for email in (EMAIL, "nobody@example.test"):
        answers = seen.setdefault(email, [])

        def note(response: Any, answers: list[Any] = answers) -> None:
            error = response.json()["error"]
            answers.append(
                (
                    response.status_code,
                    error["code"],
                    error.get("details") or {},
                    response.headers.get("retry-after"),
                )
            )

        # One address until its pair is refused, then spread until the email is refused.
        for _ in range(10):
            note(attempt(client, email, WRONG, ip="203.0.113.9"))
        for number in range(45):
            note(attempt(client, email, WRONG, ip=f"198.51.100.{number}"))
    assert seen[EMAIL] == seen["nobody@example.test"]
    statuses = [status for status, _, _, _ in seen[EMAIL]]
    # 8 counted, 2 refused for the pair, 42 more counted (50 in all), 3 refused for the email.
    assert statuses == [401] * 8 + [429] * 2 + [401] * 42 + [429] * 3


def test_the_case_of_the_email_does_not_dodge_the_count(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    for _ in range(8):
        assert attempt(client, "ADA@Example.Test", WRONG, ip="203.0.113.9").status_code == 401
    assert attempt(client, EMAIL, PASSWORD, ip="203.0.113.9").status_code == 429


def test_a_completed_password_reset_lifts_every_refusal_for_the_email(
    make_app: AppFactory,
) -> None:
    client, _ = lockout_client(make_app, login_max_failures_per_email=10)
    with client:
        register(client)
        register(client, "grace@example.test")
        lock_out(client, "grace@example.test", "203.0.113.0")
        lock_out(client, EMAIL, "203.0.113.0")
        for _ in range(2):
            assert attempt(client, EMAIL, WRONG, ip="203.0.113.1").status_code == 401
        # Ten failures in all: refused from everywhere.
        assert attempt(client, EMAIL, PASSWORD, ip="198.51.100.20").status_code == 429
        client.post("/v1/auth/password-reset/request", json={"email": EMAIL})
        token = client.get(
            "/v1/dev/email-outbox/latest", params={"to": EMAIL, "template": "password_reset"}
        ).json()["token"]
        done = client.post(
            "/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "the-new-password-1"},
            headers={"X-Forwarded-For": "198.51.100.20"},
        )
        assert done.status_code == 204
        # The old password is gone, so the guesses at it count for nothing any more: the
        # owner can sign in from the address that reset it and from the one that was
        # refused on its own.
        for ip in ("198.51.100.20", "203.0.113.0"):
            signed_in = attempt(client, EMAIL, "the-new-password-1", ip=ip)
            assert signed_in.status_code == 200, ip
        # Another email's refusal on the same network is not lifted by it.
        assert attempt(client, "grace@example.test", PASSWORD, ip="203.0.113.0").status_code == 429


def test_the_lockout_is_off_when_rate_limiting_is_disabled(client: TestClient) -> None:
    assert client.app.state.settings.rate_limit_enabled is False  # type: ignore[attr-defined]
    register(client)
    for _ in range(60):
        assert attempt(client, EMAIL, WRONG).status_code == 401
    assert attempt(client, EMAIL, PASSWORD).status_code == 200


def test_the_per_email_ceiling_is_a_setting(make_settings: Any) -> None:
    assert make_settings().login_max_failures_per_email == 50
    assert make_settings(login_max_failures_per_email=200).login_max_failures_per_email == 200
    with pytest.raises(ValueError):
        make_settings(login_max_failures_per_email=0)
