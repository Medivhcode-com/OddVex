"""Log hygiene and NUL characters.

A failed database statement must not put bound values (email addresses, password hashes)
in the log, whichever route ran it. A NUL character in any text a client sends is refused
with 422 before anything reaches the database: PostgreSQL cannot store one, so it used to
end in a 500 with the statement and its values in the log.
"""

from __future__ import annotations

import io
import json
import logging
import re
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, StatementError

from oddvex_api.db import User, make_engine
from oddvex_api.logging_config import (
    DatabaseErrorFilter,
    JsonFormatter,
    configure_logging,
    database_safe_traceback,
)

from .conftest import EXTERNAL_DATABASE_URL, PASSWORD, AppFactory, auth_headers, register

Headers = dict[str, str]
EMAIL = "real.person@example.test"
NAME = "Real Person Fullname"
BET = {
    "bet_type": "straight",
    "stake": 10,
    "sportsbook": "Northline",
    "legs": [{"selection": "Tides ML", "market": "moneyline", "odds": -110}],
}


@pytest.fixture
def log_lines() -> Iterator[io.StringIO]:
    """Everything the application's loggers write, formatted as it is in the container."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("oddvex")
    logger.addHandler(handler)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)


def password_hash_of(app: FastAPI, email: str) -> str:
    with app.state.session_factory() as db:
        user = db.query(User).filter(User.email == email).one()
        return str(user.password_hash)


# ------------------------------------------------- a failed statement in the log
def test_a_failed_statement_does_not_log_its_bound_values(
    make_app: AppFactory, log_lines: io.StringIO
) -> None:
    app = make_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        register(client, "first@example.test")
        first_hash = password_hash_of(app, "first@example.test")
        # The table loses a column the INSERT names: the statement fails in the database,
        # after its values were bound.
        with app.state.engine.begin() as connection:
            connection.execute(text("ALTER TABLE users DROP COLUMN search_key"))
        failed = client.post(
            "/v1/auth/register",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "display_name": NAME,
                "age_confirmed": True,
            },
        )
        assert failed.status_code == 500
        assert failed.json() == {
            "error": {"code": "internal_error", "message": "An unexpected error occurred"}
        }
    logged = log_lines.getvalue()
    (line,) = [json.loads(row) for row in logged.splitlines() if "unhandled_error" in row]
    assert line["path"] == "/v1/auth/register" and line["level"] == "ERROR"
    # What is needed to find the fault is there: the kind of error and the statement.
    assert "INSERT INTO users" in line["exc"]
    assert "Traceback (most recent call last)" in line["exc"]
    assert "OperationalError" in line["exc"] or "ProgrammingError" in line["exc"]
    # What was bound to it is not.
    for secret in (EMAIL, "real.person", NAME, "$argon2", first_hash, PASSWORD):
        assert secret not in logged, secret
    assert "[parameters:" not in logged


def test_both_engines_hide_statement_parameters(tmp_path: Any) -> None:
    urls = [f"sqlite:///{tmp_path / 'hide.db'}", "sqlite://"]
    if EXTERNAL_DATABASE_URL:
        urls.append(EXTERNAL_DATABASE_URL)
    for url in urls:
        engine = make_engine(url)
        assert engine.hide_parameters is True, url
        with pytest.raises(sqlalchemy.exc.DBAPIError) as caught, engine.connect() as connection:
            connection.execute(
                text("SELECT * FROM no_such_table_here WHERE email = :email"),
                {"email": EMAIL},
            )
        assert EMAIL not in str(caught.value), url
        engine.dispose()


class FakeDriverError(Exception):
    """Stands in for a driver error: PostgreSQL puts the row or the key in its message."""

    sqlstate = "23514"


FakeDriverError.__module__ = "psycopg.errors"


def _raise_check_violation() -> None:
    detail = (
        'new row for relation "users" violates check constraint "ck_users_role"\n'
        f"DETAIL:  Failing row contains (u1, {EMAIL}, $argon2id$v=19$m=65536$abc$def, {NAME})."
    )
    try:
        raise FakeDriverError(detail)
    except FakeDriverError as driver_error:
        raise IntegrityError(
            "UPDATE users SET password_hash=%(password_hash)s WHERE users.id = %(id)s",
            {"password_hash": "$argon2id$v=19$m=65536$abc$def", "id": "u1"},
            driver_error,
            hide_parameters=True,
        ) from driver_error


def test_the_drivers_message_is_withheld_from_the_logged_traceback() -> None:
    """``hide_parameters`` removes the parameter list, not the driver's own text: a failed
    check or a NOT NULL violation names the whole row there, password hash included."""
    try:
        try:
            _raise_check_violation()
        except IntegrityError as error:
            raise RuntimeError(f"could not save: {error}") from error
    except RuntimeError as wrapped:
        failure = wrapped
    # The standard rendering is the problem being fixed.
    record = logging.LogRecord(
        "oddvex.access", logging.ERROR, __file__, 1, "unhandled_error", (), None
    )
    record.exc_info = (type(failure), failure, failure.__traceback__)
    assert EMAIL in logging.Formatter().formatException(record.exc_info)

    line = json.loads(JsonFormatter().format(record))
    for secret in (EMAIL, "$argon2id", NAME, "Failing row"):
        assert secret not in line["exc"], secret
    # Still enough to debug with: every exception of the chain by name, where it was
    # raised, the SQLSTATE and the statement (which has placeholders, not values).
    for expected in (
        "Traceback (most recent call last)",
        "_raise_check_violation",
        "psycopg.errors.FakeDriverError",
        "sqlalchemy.exc.IntegrityError",
        "RuntimeError",
        "SQLSTATE 23514",
        "UPDATE users SET password_hash=%(password_hash)s",
        "The above exception was the direct cause of the following exception",
    ):
        assert expected in line["exc"], expected


def test_an_error_while_binding_a_value_is_withheld_too() -> None:
    try:
        try:
            raise ValueError(f"cannot bind {EMAIL!r}")
        except ValueError as bind_error:
            raise StatementError(
                "(builtins.ValueError) cannot bind",
                "SELECT 1 WHERE :x",
                {"x": EMAIL},
                bind_error,
                hide_parameters=True,
            ) from bind_error
    except StatementError as failure:
        rendered = database_safe_traceback(failure)
    assert rendered is not None and EMAIL not in rendered
    assert "ValueError" in rendered and "StatementError" in rendered


def test_other_errors_are_logged_in_full() -> None:
    try:
        raise KeyError("which-key")
    except KeyError as failure:
        assert database_safe_traceback(failure) is None
        record = logging.LogRecord("oddvex.app", logging.ERROR, __file__, 1, "boom", (), None)
        record.exc_info = (type(failure), failure, failure.__traceback__)
    line = json.loads(JsonFormatter().format(record))
    assert "KeyError: 'which-key'" in line["exc"]


def test_the_servers_own_error_logger_gets_the_same_treatment(make_app: AppFactory) -> None:
    """An error that escapes the application (a failed batch of a streamed response, a
    background task) is logged by uvicorn, with uvicorn's formatter."""
    make_app()
    configure_logging("WARNING")  # twice: the filter is added once
    server_logger = logging.getLogger("uvicorn.error")
    assert [type(f) for f in server_logger.filters].count(DatabaseErrorFilter) == 1
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    server_logger.addHandler(handler)
    try:
        try:
            _raise_check_violation()
        except IntegrityError:
            server_logger.exception("Exception in ASGI application")
        try:
            raise KeyError("which-key")
        except KeyError:
            server_logger.exception("Exception in ASGI application")
    finally:
        server_logger.removeHandler(handler)
    written = stream.getvalue()
    for secret in (EMAIL, "$argon2id", NAME):
        assert secret not in written, secret
    assert "sqlalchemy.exc.IntegrityError" in written and "SQLSTATE 23514" in written
    assert "KeyError: 'which-key'" in written


@pytest.mark.skipif(
    not (EXTERNAL_DATABASE_URL or "").startswith("postgresql"), reason="PostgreSQL only"
)
def test_postgresql_failing_row_detail_is_not_logged(
    make_app: AppFactory, log_lines: io.StringIO
) -> None:
    app = make_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        account = register(client, EMAIL, display_name=NAME)
        headers = {"Authorization": f"Bearer {account['access_token']}"}
        old_hash = password_hash_of(app, EMAIL)
        with app.state.engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users ADD CONSTRAINT ck_no_new_hash "
                    "CHECK (password_changed_at IS NULL) NOT VALID"
                )
            )
        failed = client.post(
            "/v1/me/password",
            json={"current_password": PASSWORD, "new_password": "another-password-1"},
            headers=headers,
        )
        assert failed.status_code == 500
    logged = log_lines.getvalue()
    (line,) = [json.loads(row) for row in logged.splitlines() if "unhandled_error" in row]
    assert "CheckViolation" in line["exc"] and "SQLSTATE 23514" in line["exc"]
    assert "ck_no_new_hash" in line["exc"]  # the constraint is named, the row is not shown
    for secret in (EMAIL, NAME, old_hash, "$argon2", "Failing row"):
        assert secret not in logged, secret


# ------------------------------------------------------------------ NUL characters
def assert_nul_refused(response: Any, *loc: str) -> None:
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"] == "Request validation failed"
    assert error["details"] == [
        {
            "loc": list(loc),
            "message": "Text cannot contain the NUL character",
            "type": "nul_character",
        }
    ]


def test_nul_in_a_sign_in_email_is_422_and_reveals_nothing(client: TestClient) -> None:
    register(client)
    answers = []
    for email in ("ada@example.test\x00", "ad\x00a@example.test", "nobody\x00@example.test"):
        response = client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert_nul_refused(response, "body", "email")
        answers.append(response.json())
    assert answers[0] == answers[1] == answers[2]
    refused = client.post(
        "/v1/auth/login", json={"email": "ada@example.test", "password": "wrong\x00password"}
    )
    assert_nul_refused(refused, "body", "password")
    # The same text without the character is an ordinary sign-in.
    assert (
        client.post(
            "/v1/auth/login", json={"email": "ada@example.test", "password": PASSWORD}
        ).status_code
        == 200
    )


def test_nul_in_account_fields_is_422_and_nothing_is_stored(
    client: TestClient, app: FastAPI
) -> None:
    for field, value in (
        ("email", "eve\x00@example.test"),
        ("display_name", "Eve\x00"),
        ("password", "long-enough\x00-password"),
    ):
        body = {
            "email": "eve@example.test",
            "password": PASSWORD,
            "display_name": "Eve",
            "age_confirmed": True,
            field: value,
        }
        assert_nul_refused(client.post("/v1/auth/register", json=body), "body", field)
    with app.state.session_factory() as db:
        assert db.query(User).count() == 0
    reset = client.post("/v1/auth/password-reset/request", json={"email": "a\x00@example.test"})
    assert_nul_refused(reset, "body", "email")
    confirm = client.post("/v1/auth/verify-email/confirm", json={"token": "t" * 20 + "\x00"})
    assert_nul_refused(confirm, "body", "token")


def test_nul_anywhere_in_a_body_is_422(client: TestClient, headers: Headers) -> None:
    for path, value in (
        (("notes",), "note\x00"),
        (("sportsbook",), "\x00"),
        (("legs", 0, "selection"), "Tides\x00 ML"),
        (("legs", 0, "event_label"), "\x00\x00"),
    ):
        body: Any = json.loads(json.dumps(BET))
        target = body
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        refused = client.post("/v1/bets", json=body, headers=headers)
        assert_nul_refused(refused, "body", *(str(part) for part in path))
    # A key counts as text too, also one the route would ignore.
    extra = client.post("/v1/bets", json={**BET, "x\x00y": 1}, headers=headers)
    assert_nul_refused(extra, "body", "x\x00y".replace("\x00", "\\u0000"))
    assert client.get("/v1/bets", headers=headers).json() == []
    # Other routes with free text.
    assistant = client.post("/v1/assistant/query", json={"query": "best price\x00"})
    assert_nul_refused(assistant, "body", "query")
    watch = client.post(
        "/v1/watchlist", json={"kind": "team", "ref_id": "nba-tides\x00"}, headers=headers
    )
    assert_nul_refused(watch, "body", "ref_id")


def test_nul_in_a_query_or_path_value_is_422(client: TestClient, headers: Headers) -> None:
    assert_nul_refused(client.get("/v1/players?q=%00"), "query", "q")
    assert_nul_refused(client.get("/v1/players", params={"q": "ab\x00cd"}), "query", "q")
    assert_nul_refused(
        client.get("/v1/bets?sportsbook=North%00line", headers=headers), "query", "sportsbook"
    )
    assert_nul_refused(client.get("/v1/bets/abc%00def", headers=headers), "path", "bet_id")
    assert_nul_refused(client.delete("/v1/bets/%00", headers=headers), "path", "bet_id")
    assert_nul_refused(
        client.get("/v1/dev/email-outbox/latest?to=a%00@example.test"), "query", "to"
    )
    # A parameter the route does not declare is refused as well: nothing with the
    # character in it is passed on.
    assert_nul_refused(client.get("/v1/me?anything=%00", headers=headers), "query", "anything")
    # The percent sign followed by two zeros as text ("%2500") is not the character.
    assert client.get("/v1/players?q=%2500").status_code == 200


def test_text_that_only_looks_like_nul_is_still_accepted(
    client: TestClient, headers: Headers
) -> None:
    for harmless in ("\\u0000", "\\x00", "%00", "\\\\u0000"):
        created = client.post("/v1/bets", json={**BET, "notes": harmless}, headers=headers)
        assert created.status_code == 201, harmless
        assert created.json()["notes"] == harmless
    # Written out as JSON by hand: an escaped backslash followed by "u0000" is six
    # ordinary characters, and the same six after an odd backslash is the character.
    raw_headers = {**headers, "Content-Type": "application/json"}
    template = json.dumps({**BET, "notes": "MARK"})
    harmless_body = template.replace("MARK", "a\\\\u0000b")
    created = client.post("/v1/bets", content=harmless_body, headers=raw_headers)
    assert created.status_code == 201 and created.json()["notes"] == "a\\u0000b"
    for hostile in ("a\\u0000b", "a\\\\\\u0000b"):
        refused = client.post(
            "/v1/bets", content=template.replace("MARK", hostile), headers=raw_headers
        )
        assert_nul_refused(refused, "body", "notes")


def test_nul_cannot_be_hidden_in_another_encoding_of_the_body(
    client: TestClient, headers: Headers
) -> None:
    hostile = json.dumps({**BET, "notes": "note\x00"})
    assert "\\u0000" in hostile
    for encoding in ("utf-16", "utf-16-le", "utf-32", "utf-8-sig"):
        refused = client.post(
            "/v1/bets",
            content=hostile.encode(encoding),
            headers={**headers, "Content-Type": "application/json"},
        )
        assert_nul_refused(refused, "body", "notes")
    # The same encodings without the character work as they did before.
    fine = json.dumps({**BET, "notes": "plain"}).encode("utf-16")
    created = client.post(
        "/v1/bets", content=fine, headers={**headers, "Content-Type": "application/json"}
    )
    assert created.status_code == 201 and created.json()["notes"] == "plain"
    # A raw NUL byte is not JSON at all.
    raw = json.dumps({**BET, "notes": "MARK"}).replace("MARK", "a\x00b").encode()
    broken = client.post(
        "/v1/bets", content=raw, headers={**headers, "Content-Type": "application/json"}
    )
    assert broken.status_code == 422


def test_a_body_that_is_not_json_is_left_to_the_route(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/login",
        content=b"\\u0000 not json at all \x00",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    # A route without a body ignores one, as before.
    assert client.get("/v1/players", params={"q": "a"}).status_code == 200


def test_every_route_of_the_api_has_the_check(client: TestClient, app: FastAPI) -> None:
    """Walks the published schema: every operation refuses a NUL character, signed in or
    not, and whatever else is wrong with the request."""
    schema = app.openapi()
    operations = [
        (method.upper(), path)
        for path, item in schema["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operations) > 100
    for method, path in operations:
        url = re.sub(r"\{[^}]+\}", "x", path)
        refused = client.request(method, f"{url}?probe=%00")
        assert_nul_refused(refused, "query", "probe")
        if method != "GET":
            in_body = client.request(method, url, json={"probe": "\x00"})
            assert_nul_refused(in_body, "body", "probe")
    # Path values, on every operation that has one.
    with_path_value = [(m, p) for m, p in operations if "{" in p]
    assert len(with_path_value) > 30
    for method, path in with_path_value:
        refused = client.request(method, re.sub(r"\{[^}]+\}", "a%00b", path))
        assert refused.status_code == 422, (method, path)
        assert refused.json()["error"]["details"][0]["type"] == "nul_character", (method, path)
    # The check adds nothing to the published schema: no parameter, no new response.
    published = json.dumps(schema).lower()
    assert "nul_character" not in published and "reject_nul" not in published


def test_nul_is_refused_before_the_account_limits_count_it(make_app: AppFactory) -> None:
    app = make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=1000)
    with TestClient(app) as client:
        register(client)
        for _ in range(20):
            refused = client.post(
                "/v1/auth/login", json={"email": "ada@example.test\x00", "password": "x"}
            )
            assert refused.status_code == 422
        signed_in = client.post(
            "/v1/auth/login", json={"email": "ada@example.test", "password": PASSWORD}
        )
        assert signed_in.status_code == 200


def test_an_admin_route_refuses_nul_too(make_app: AppFactory) -> None:
    from .conftest import ADMIN_EMAIL, admin_headers

    with TestClient(make_app(admin_emails=ADMIN_EMAIL)) as client:
        admin = admin_headers(client)
        user_id = client.get("/v1/me", headers=auth_headers(client)).json()["id"]
        refused = client.post(
            f"/v1/admin/users/{user_id}/suspend", json={"reason": "why\x00"}, headers=admin
        )
        assert_nul_refused(refused, "body", "reason")
        assert_nul_refused(client.get("/v1/admin/users?q=%00", headers=admin), "query", "q")
        assert_nul_refused(
            client.get("/v1/admin/audit?user_id=%00", headers=admin), "query", "user_id"
        )
