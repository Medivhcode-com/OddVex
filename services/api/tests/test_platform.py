"""Cross-cutting behaviour: error envelope, headers, CORS, rate limiting, config, logging."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oddvex_api.cache import InMemoryTTLCache, cached
from oddvex_api.config import DEV_JWT_SECRET, Settings
from oddvex_api.db.session import normalize_database_url
from oddvex_api.logging_config import JsonFormatter
from oddvex_api.main import create_app
from oddvex_api.ratelimit import SlidingWindowRateLimiter

from .conftest import PASSWORD, AppFactory, SettingsFactory

LOGIN = {"email": "nobody@example.test", "password": PASSWORD}


def assert_envelope(body: dict, code: str) -> None:
    assert set(body) == {"error"}
    assert set(body["error"]) <= {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


# ------------------------------------------------------------- error envelope
def test_every_error_uses_the_envelope(client: TestClient, headers: dict[str, str]) -> None:
    assert_envelope(client.get("/v1/does-not-exist").json(), "not_found")
    assert_envelope(client.get("/v1/events/evt_missing").json(), "not_found")
    assert_envelope(client.get("/v1/bets/missing", headers=headers).json(), "not_found")
    assert_envelope(client.put("/v1/leagues").json(), "method_not_allowed")
    assert client.put("/v1/leagues").status_code == 405
    assert_envelope(client.get("/v1/me").json(), "not_authenticated")
    assert_envelope(
        client.post("/v1/quant/convert", json={"odds": 5}).json(), "invalid_american_odds"
    )

    validation = client.post("/v1/auth/register", json={"email": "x"})
    assert validation.status_code == 422
    assert_envelope(validation.json(), "validation_error")
    details = validation.json()["error"]["details"]
    assert isinstance(details, list) and details
    assert all(set(d) == {"loc", "message", "type"} for d in details)
    assert {"body", "password"} <= {part for d in details for part in d["loc"]}

    malformed = client.post(
        "/v1/quant/convert", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert malformed.status_code == 422
    assert_envelope(malformed.json(), "validation_error")


def test_unhandled_errors_are_enveloped_and_do_not_leak(make_app: AppFactory) -> None:
    app = make_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert response.status_code == 500
    assert_envelope(response.json(), "internal_error")
    assert "secret" not in response.text
    assert response.headers["x-request-id"]


# -------------------------------------------------------------------- headers
def test_request_id_and_security_headers(client: TestClient) -> None:
    response = client.get("/health")
    assert len(response.headers["x-request-id"]) == 32
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "strict-transport-security" not in response.headers  # only in production
    echoed = client.get("/health", headers={"X-Request-ID": "trace-abc-12345"})
    assert echoed.headers["x-request-id"] == "trace-abc-12345"
    replaced = client.get("/health", headers={"X-Request-ID": "bad id with spaces\tand tabs"})
    assert replaced.headers["x-request-id"] != "bad id with spaces\tand tabs"
    assert client.get("/v1/nope").headers["x-content-type-options"] == "nosniff"
    assert client.get("/v1/me").headers["cache-control"] == "no-store"


def test_hsts_and_docs_in_production(make_app: AppFactory) -> None:
    app = make_app(env="production", jwt_secret="p" * 48, db_auto_create=True)
    with TestClient(app) as client:
        assert "max-age" in client.get("/health").headers["strict-transport-security"]
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_docs_are_served_outside_production(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "OddVex API"


# ----------------------------------------------------------------------- CORS
def test_cors_allowlist(make_app: AppFactory) -> None:
    app = make_app(cors_origins="http://localhost:3000, https://app.example.test/")
    with TestClient(app) as client:
        for origin in ("http://localhost:3000", "https://app.example.test"):
            response = client.get("/v1/meta", headers={"Origin": origin})
            assert response.headers["access-control-allow-origin"] == origin
        denied = client.get("/v1/meta", headers={"Origin": "https://evil.example.test"})
        assert "access-control-allow-origin" not in denied.headers
        preflight = client.options(
            "/v1/bets",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"
        blocked = client.options(
            "/v1/bets",
            headers={
                "Origin": "https://evil.example.test",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert blocked.status_code == 400
        # Error responses carry CORS headers too, so browsers can read the envelope.
        error = client.get("/v1/me", headers={"Origin": "http://localhost:3000"})
        assert error.status_code == 401
        assert error.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_default_cors_origin_is_localhost_3000() -> None:
    assert Settings(_env_file=None).cors_origin_list == ["http://localhost:3000"]  # type: ignore[call-arg]


# --------------------------------------------------------------- rate limiting
def test_sliding_window_limiter() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(window_seconds=60, clock=lambda: now[0])
    assert [limiter.check("ip", 3)[0] for _ in range(3)] == [True, True, True]
    allowed, retry_after = limiter.check("ip", 3)
    assert (allowed, retry_after) == (False, 60.0)
    assert limiter.check("other-ip", 3)[0] is True
    now[0] = 30.0
    assert limiter.check("ip", 3) == (False, 30.0)
    now[0] = 60.1  # the first three hits have slid out of the window
    assert limiter.check("ip", 3)[0] is True
    limiter.reset()
    assert limiter.check("ip", 1)[0] is True


def test_auth_routes_are_rate_limited_per_ip(make_app: AppFactory) -> None:
    app = make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=3)
    with TestClient(app) as client:
        statuses = [client.post("/v1/auth/login", json=LOGIN).status_code for _ in range(5)]
        assert statuses == [401, 401, 401, 429, 429]
        limited = client.post("/v1/auth/register", json={})  # register shares the auth bucket
        assert limited.status_code == 429
        assert_envelope(limited.json(), "rate_limited")
        assert int(limited.headers["retry-after"]) >= 1
        assert limited.json()["error"]["details"]["retry_after_seconds"] == int(
            limited.headers["retry-after"]
        )
        # Other routes are unaffected.
        assert client.get("/v1/meta").status_code == 200
        assert client.post("/v1/assistant/query", json={"message": "help"}).status_code == 200
        app.state.rate_limiter.reset()
        assert client.post("/v1/auth/login", json=LOGIN).status_code == 401


def test_assistant_is_rate_limited_separately(make_app: AppFactory) -> None:
    app = make_app(
        rate_limit_enabled=True, rate_limit_assistant_per_minute=2, rate_limit_auth_per_minute=50
    )
    with TestClient(app) as client:
        statuses = [
            client.post("/v1/assistant/query", json={"message": "help"}).status_code
            for _ in range(4)
        ]
        assert statuses == [200, 200, 429, 429]
        assert client.post("/v1/auth/login", json=LOGIN).status_code == 401


def test_rate_limit_can_be_disabled(make_app: AppFactory) -> None:
    app = make_app(rate_limit_enabled=False, rate_limit_auth_per_minute=1)
    with TestClient(app) as client:
        assert {client.post("/v1/auth/login", json=LOGIN).status_code for _ in range(6)} == {401}


def test_forwarded_for_is_ignored_unless_proxy_is_trusted(make_app: AppFactory) -> None:
    def statuses(app: FastAPI) -> list[int]:
        with TestClient(app) as client:
            return [
                client.post(
                    "/v1/auth/login",
                    json=LOGIN,
                    headers={"X-Forwarded-For": f"198.51.100.7, 203.0.113.{i}"},
                ).status_code
                for i in range(4)
            ]

    # Untrusted: spoofing the header does not buy a fresh bucket.
    assert statuses(make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=2)) == [
        401,
        401,
        429,
        429,
    ]
    # Trusted proxy: each forwarded client has its own bucket.
    assert (
        statuses(make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=2, trust_proxy=True))
        == [401] * 4
    )


def test_trusted_proxy_limits_per_forwarded_client(make_app: AppFactory) -> None:
    app = make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=2, trust_proxy=True)
    with TestClient(app) as client:
        # Forged client-supplied entries vary; the entry appended by the proxy does not.
        statuses = [
            client.post(
                "/v1/auth/login",
                json=LOGIN,
                headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"},
            ).status_code
            for i in range(3)
        ]
        assert statuses == [401, 401, 429]


# --------------------------------------------------------------- configuration
def test_production_refuses_the_default_jwt_secret(make_settings: SettingsFactory) -> None:
    with pytest.raises(RuntimeError, match="ODDVEX_JWT_SECRET"):
        create_app(make_settings(env="production"))
    with pytest.raises(RuntimeError, match="ODDVEX_JWT_SECRET"):
        create_app(make_settings(env="production", jwt_secret=DEV_JWT_SECRET))
    with pytest.raises(RuntimeError, match="at least 32"):
        create_app(make_settings(env="production", jwt_secret="too-short"))
    with pytest.raises(RuntimeError, match="CORS"):
        create_app(make_settings(env="production", jwt_secret="s" * 40, cors_origins="*"))
    assert create_app(make_settings(env="production", jwt_secret="s" * 40)) is not None
    assert create_app(make_settings(env="development")) is not None  # default secret is fine in dev


def test_settings_read_the_documented_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/oddvex")
    monkeypatch.setenv("ODDVEX_ENV", "production")
    monkeypatch.setenv("ODDVEX_JWT_SECRET", "x" * 40)
    monkeypatch.setenv("ODDVEX_CORS_ORIGINS", "https://a.example.test,https://b.example.test")
    monkeypatch.setenv("ODDVEX_TRUST_PROXY", "true")
    monkeypatch.setenv("ODDVEX_RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("ODDVEX_RATE_LIMIT_AUTH_PER_MINUTE", "77")
    monkeypatch.setenv("ODDVEX_STALE_LIVE_SECONDS", "45")
    monkeypatch.setenv("ODDVEX_DEMO_PASSWORD", "another-demo-password")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url == "postgresql://u:p@db:5432/oddvex"
    assert settings.is_production and settings.jwt_secret == "x" * 40
    assert settings.cors_origin_list == ["https://a.example.test", "https://b.example.test"]
    assert settings.trust_proxy is True and settings.rate_limit_enabled is False
    assert settings.rate_limit_auth_per_minute == 77
    assert settings.stale_live_seconds == 45
    assert settings.demo_password == "another-demo-password"
    assert settings.should_auto_create_tables is False  # never auto-create in production


def test_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.env == "development"
    assert settings.database_url.startswith("sqlite:///")
    assert (settings.stale_live_seconds, settings.stale_pregame_seconds) == (120, 900)
    assert settings.trust_proxy is False and settings.auto_seed_demo is False
    assert settings.should_auto_create_tables is True


def test_postgres_urls_use_the_psycopg_driver() -> None:
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert (
        normalize_database_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    )
    assert normalize_database_url("sqlite:///x.db") == "sqlite:///x.db"


# ------------------------------------------------------------ logging / cache
def test_json_log_lines() -> None:
    record = logging.LogRecord("oddvex.access", logging.INFO, __file__, 1, "request", (), None)
    record.request_id = "abc"
    record.status = 200
    line = json.loads(JsonFormatter().format(record))
    assert line["message"] == "request" and line["level"] == "INFO"
    assert line["request_id"] == "abc" and line["status"] == 200
    assert line["ts"].endswith("+00:00")


def test_requests_are_logged_as_json_with_the_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    access = logging.getLogger("oddvex.access")
    access.addHandler(caplog.handler)
    access.setLevel(logging.INFO)
    try:
        response = client.get("/v1/meta", headers={"X-Request-ID": "trace-xyz-98765"})
    finally:
        access.removeHandler(caplog.handler)
    records = [r for r in caplog.records if r.getMessage() == "request"]
    assert records
    record = records[-1]
    assert record.request_id == "trace-xyz-98765" == response.headers["x-request-id"]  # type: ignore[attr-defined]
    assert (record.method, record.path, record.status) == ("GET", "/v1/meta", 200)  # type: ignore[attr-defined]
    assert json.loads(JsonFormatter().format(record))["duration_ms"] >= 0


def test_ttl_cache() -> None:
    now = [0.0]
    cache = InMemoryTTLCache(max_entries=2, clock=lambda: now[0])
    calls = []

    def compute() -> list[int]:
        calls.append(1)
        return []

    assert cached(cache, "k", 10, compute) == []
    assert cached(cache, "k", 10, compute) == []
    assert len(calls) == 1  # an empty list is still a cache hit
    now[0] = 11
    cached(cache, "k", 10, compute)
    assert len(calls) == 2
    cache.set("a", 1, 10)
    cache.set("b", 2, 10)
    assert cache.get("k") is None  # evicted: bounded size
    cache.delete("a")
    assert cache.get("a") is None
    cache.set("zero", 1, 0)
    assert cache.get("zero") is None
    cache.clear()
    assert cache.get("b") is None
