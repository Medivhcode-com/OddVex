"""Email verification and password reset. No email is ever sent: the outbox is a table."""

from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.auth import router as auth_router
from oddvex_api.db import AuditLog, Base, EmailOutbox, EmailToken, User, utcnow
from oddvex_api.mailer import templates
from oddvex_api.mailer.sender import (
    LINK_WITHHELD,
    OutboxEmailSender,
    ResendEmailSender,
    make_sender,
)
from oddvex_api.mailer.service import TOKEN_BYTES, hash_token, new_token

from .conftest import (
    PASSWORD,
    AppFactory,
    SettingsFactory,
    admin_headers,
    auth_headers,
    register,
    set_flag,
)
from .test_notification_copy import BANNED_PHRASES

Headers = dict[str, str]
EMAIL = "ada@example.test"
NEW_PASSWORD = "a-brand-new-password"
INVALID = {
    "error": {
        "code": "invalid_or_expired_token",
        "message": "This link is not valid or has expired. Request a new one.",
    }
}


def latest(client: TestClient, to: str = EMAIL, template: str | None = None) -> dict[str, Any]:
    params = {"to": to, **({"template": template} if template else {})}
    response = client.get("/v1/dev/email-outbox/latest", params=params)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def rows(client: TestClient, model: type) -> list[Any]:
    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        return list(db.scalars(select(model)))


def actions(client: TestClient) -> list[str]:
    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        return list(db.scalars(select(AuditLog.action).order_by(AuditLog.created_at)))


def login(client: TestClient, password: str, email: str = EMAIL) -> Any:
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def request_reset(client: TestClient, email: str = EMAIL, **kwargs: Any) -> Any:
    return client.post("/v1/auth/password-reset/request", json={"email": email}, **kwargs)


def reset_token(client: TestClient, email: str = EMAIL) -> str:
    assert request_reset(client, email).status_code == 202
    return latest(client, email, "password_reset")["token"]  # type: ignore[no-any-return]


def confirm_reset(client: TestClient, token: str, password: str = NEW_PASSWORD) -> Any:
    return client.post(
        "/v1/auth/password-reset/confirm", json={"token": token, "new_password": password}
    )


# --------------------------------------------------------- email verification
def test_registration_queues_a_verification_email_in_the_outbox(client: TestClient) -> None:
    account = register(client)
    assert account["user"]["email_verified"] is False
    (row,) = rows(client, EmailOutbox)
    assert (row.to_email, row.template, row.user_id) == (
        EMAIL,
        "verify_email",
        account["user"]["id"],
    )
    assert row.subject == "Confirm your email address for OddVex"
    assert row.dev_link and row.dev_link in row.body_text
    assert row.created_at is not None

    email = latest(client)
    assert set(email) == {
        "id",
        "to",
        "template",
        "subject",
        "body_text",
        "dev_link",
        "token",
        "created_at",
    }
    assert email["dev_link"] == f"http://localhost:3000/verify-email?token={email['token']}"
    # 32 random bytes, URL-safe: 43 characters.
    assert TOKEN_BYTES >= 32 and len(email["token"]) >= 43
    assert re.fullmatch(r"[A-Za-z0-9_-]+", email["token"])


def test_only_a_hash_of_the_token_is_stored(client: TestClient) -> None:
    register(client)
    token = latest(client)["token"]
    (stored,) = rows(client, EmailToken)
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest() == hash_token(token)
    assert stored.purpose == "verify_email" and stored.used_at is None
    assert stored.expires_at - stored.created_at == timedelta(hours=24)
    assert token not in repr(vars(stored))
    assert len({new_token() for _ in range(50)}) == 50


def test_confirm_marks_the_email_verified_once(client: TestClient, headers: Headers) -> None:
    token = latest(client)["token"]
    # No sign-in needed: the link may be opened in another browser.
    confirmed = client.post("/v1/auth/verify-email/confirm", json={"token": token})
    assert confirmed.status_code == 200 and confirmed.json() == {"email_verified": True}
    assert client.get("/v1/me", headers=headers).json()["email_verified"] is True
    assert client.get("/v1/me/export", headers=headers).json()["user"]["email_verified"] is True

    reused = client.post("/v1/auth/verify-email/confirm", json={"token": token})
    assert reused.status_code == 400 and reused.json() == INVALID
    assert "auth.email_verified" in actions(client)
    (stored,) = rows(client, EmailToken)
    assert stored.used_at is not None


def test_unknown_expired_and_wrong_purpose_tokens_look_the_same(
    client: TestClient, headers: Headers
) -> None:
    unknown = client.post("/v1/auth/verify-email/confirm", json={"token": new_token()})
    assert unknown.status_code == 400 and unknown.json() == INVALID

    # A password-reset token does not verify an email, and the other way round.
    verify = latest(client, template="verify_email")["token"]
    reset = reset_token(client)
    wrong = client.post("/v1/auth/verify-email/confirm", json={"token": reset})
    assert wrong.status_code == 400 and wrong.json() == INVALID
    assert confirm_reset(client, verify).json() == INVALID

    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        row = db.scalar(select(EmailToken).where(EmailToken.token_hash == hash_token(verify)))
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    expired = client.post("/v1/auth/verify-email/confirm", json={"token": verify})
    assert expired.status_code == 400 and expired.json() == INVALID
    assert client.get("/v1/me", headers=headers).json()["email_verified"] is False

    for body in ({}, {"token": "short"}, {"token": "x" * 300}, {"token": None}):
        invalid = client.post("/v1/auth/verify-email/confirm", json=body)
        assert invalid.status_code == 422, body
        assert invalid.json()["error"]["code"] == "validation_error"


def test_requesting_again_replaces_the_earlier_link(client: TestClient, headers: Headers) -> None:
    first = latest(client)["token"]
    assert client.post("/v1/auth/verify-email/request").status_code == 401
    again = client.post("/v1/auth/verify-email/request", headers=headers)
    assert again.status_code == 202
    assert again.json() == {"message": "A confirmation email has been queued for your address."}
    second = latest(client)["token"]
    assert second != first and len(rows(client, EmailOutbox)) == 2
    assert len(rows(client, EmailToken)) == 1  # only the newest link is live
    assert client.post("/v1/auth/verify-email/confirm", json={"token": first}).json() == INVALID
    assert client.post("/v1/auth/verify-email/confirm", json={"token": second}).status_code == 200

    # Already confirmed: nothing more is queued.
    done = client.post("/v1/auth/verify-email/request", headers=headers)
    assert done.status_code == 202
    assert done.json() == {"message": "Your email address is already confirmed."}
    assert len(rows(client, EmailOutbox)) == 2
    assert actions(client).count("auth.email_verification_requested") == 1


def test_an_unverified_user_is_not_blocked_from_anything(
    client: TestClient, headers: Headers
) -> None:
    assert client.get("/v1/me", headers=headers).json()["email_verified"] is False
    bet = {
        "bet_type": "straight",
        "stake": 10,
        "sportsbook": "Northline",
        "legs": [{"selection": "x", "market": "moneyline", "odds": -110}],
    }
    assert client.post("/v1/bets", json=bet, headers=headers).status_code == 201
    for path in (
        "/v1/bets",
        "/v1/bets/analytics",
        "/v1/watchlist",
        "/v1/alerts",
        "/v1/notifications",
        "/v1/me/export",
        "/v1/me/entitlements",
        "/v1/sync/connections",
    ):
        assert client.get(path, headers=headers).status_code == 200, path


def test_verification_requests_are_limited_per_user(make_app: AppFactory) -> None:
    app = make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=1000, trust_proxy=True)
    with TestClient(app) as client:
        headers = auth_headers(client)
        other = auth_headers(client, "grace@example.test")
        for attempt in range(3):
            ok = client.post(
                "/v1/auth/verify-email/request",
                headers={**headers, "X-Forwarded-For": f"10.0.0.{attempt}"},
            )
            assert ok.status_code == 202, attempt
        limited = client.post(
            "/v1/auth/verify-email/request", headers={**headers, "X-Forwarded-For": "10.9.9.9"}
        )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limited"
        assert int(limited.headers["retry-after"]) > 0
        # Another user is not affected.
        assert client.post("/v1/auth/verify-email/request", headers=other).status_code == 202


def test_links_use_the_configured_web_base_url(make_app: AppFactory) -> None:
    with TestClient(make_app(web_base_url="https://app.example.test/")) as client:
        register(client)
        link = latest(client)["dev_link"]
        assert link.startswith("https://app.example.test/verify-email?token=")
        request_reset(client)
        link = latest(client, template="password_reset")["dev_link"]
        assert link.startswith("https://app.example.test/reset-password?token=")


# ------------------------------------------------------------- password reset
def test_reset_request_is_identical_whether_or_not_the_account_exists(
    client: TestClient,
) -> None:
    register(client)
    before = len(rows(client, EmailOutbox))
    known = request_reset(client)
    unknown = request_reset(client, "nobody@example.test")
    malformed = request_reset(client, "not an email at all")
    for response in (known, unknown, malformed):
        assert response.status_code == 202
        assert response.json() == {
            "message": "If an account exists for that email, a password reset email has "
            "been queued."
        }
    ignored = {"x-request-id", "content-length"}
    assert {k for k in known.headers if k not in ignored} == {
        k for k in unknown.headers if k not in ignored
    }
    assert known.headers["content-length"] == unknown.headers["content-length"]
    assert known.headers["cache-control"] == "no-store"

    # Only the real account got an email, and only it was audited.
    outbox = rows(client, EmailOutbox)
    assert len(outbox) == before + 1
    assert [(r.to_email, r.template) for r in outbox][-1] == (EMAIL, "password_reset")
    assert actions(client).count("auth.password_reset_requested") == 1
    assert (
        client.get("/v1/dev/email-outbox/latest", params={"to": "nobody@example.test"}).status_code
        == 404
    )


def test_reset_response_does_not_depend_on_the_account_lookup(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Structural timing independence: the lookup, the token and the email are handed to
    a task that runs after the response. With that task replaced by a recorder the
    answers are still the same, and the route handler itself has no database access."""
    register(client)
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(auth_router, "_queue_password_reset", lambda *args: calls.append(args))
    before = len(rows(client, EmailOutbox))
    known = request_reset(client)
    unknown = request_reset(client, "nobody@example.test")
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json())
    assert known.status_code == 202
    assert [call[1] for call in calls] == [EMAIL, "nobody@example.test"]
    assert [len(call) for call in calls] == [4, 4]
    assert len(rows(client, EmailOutbox)) == before  # nothing happened in the request itself

    import inspect

    parameters = inspect.signature(auth_router.request_password_reset).parameters
    assert "db" not in parameters and "user" not in parameters
    source = inspect.getsource(auth_router.request_password_reset)
    assert "select(" not in source and "session_factory" not in source


def test_reset_changes_the_password_and_invalidates_every_token(
    client: TestClient, headers: Headers
) -> None:
    second_session = {"Authorization": f"Bearer {login(client, PASSWORD).json()['access_token']}"}
    token = reset_token(client)
    email = latest(client, template="password_reset")
    assert email["dev_link"] == f"http://localhost:3000/reset-password?token={token}"
    (stored,) = [r for r in rows(client, EmailToken) if r.purpose == "password_reset"]
    assert stored.token_hash == hash_token(token)
    assert stored.expires_at - stored.created_at == timedelta(minutes=60)

    done = confirm_reset(client, token)
    assert done.status_code == 204 and done.content == b""

    # Every token issued before the reset is rejected.
    for old in (headers, second_session):
        rejected = client.get("/v1/me", headers=old)
        assert rejected.status_code == 401
        assert rejected.json()["error"]["code"] == "invalid_token"
    assert login(client, PASSWORD).status_code == 401
    fresh = login(client, NEW_PASSWORD)
    assert fresh.status_code == 200
    user = fresh.json()["user"]
    assert user["email_verified"] is True  # following the emailed link proves the address
    new_headers = {"Authorization": f"Bearer {fresh.json()['access_token']}"}
    assert client.get("/v1/me", headers=new_headers).status_code == 200

    # Single use.
    again = confirm_reset(client, token, "yet-another-password")
    assert again.status_code == 400 and again.json() == INVALID
    assert login(client, NEW_PASSWORD).status_code == 200
    log = actions(client)
    assert log.count("auth.password_reset_requested") == 1
    assert log.count("auth.password_reset_completed") == 1
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        stored_user = db.scalar(select(User).where(User.email == EMAIL))
        assert stored_user.token_version == 1 and stored_user.password_changed_at is not None
        assert NEW_PASSWORD not in stored_user.password_hash


def test_reset_token_expires_after_sixty_minutes(client: TestClient, headers: Headers) -> None:
    token = reset_token(client)
    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        row = db.scalar(select(EmailToken).where(EmailToken.token_hash == hash_token(token)))
        # As if it had been requested 60 minutes and one second ago.
        row.created_at -= timedelta(minutes=60, seconds=1)
        row.expires_at -= timedelta(minutes=60, seconds=1)
        db.commit()
    expired = confirm_reset(client, token)
    assert expired.status_code == 400 and expired.json() == INVALID
    assert login(client, PASSWORD).status_code == 200  # the password did not change
    assert client.get("/v1/me", headers=headers).status_code == 200


def test_a_new_reset_request_replaces_the_earlier_link(client: TestClient) -> None:
    register(client)
    first = reset_token(client)
    second = reset_token(client)
    assert first != second
    assert confirm_reset(client, first).json() == INVALID
    assert confirm_reset(client, second).status_code == 204


def test_reset_confirm_validation(client: TestClient) -> None:
    register(client)
    token = reset_token(client)
    for body in (
        {"token": token},
        {"new_password": NEW_PASSWORD},
        {"token": token, "new_password": "short"},
        {"token": token, "new_password": "x" * 129},
        {"token": "tiny", "new_password": NEW_PASSWORD},
    ):
        invalid = client.post("/v1/auth/password-reset/confirm", json=body)
        assert invalid.status_code == 422, body
        assert invalid.json()["error"]["code"] == "validation_error"
    assert confirm_reset(client, new_token()).json() == INVALID
    assert confirm_reset(client, token).status_code == 204  # still usable after the failures
    for body in ({}, {"email": ""}, {"email": "x" * 400}):
        assert client.post("/v1/auth/password-reset/request", json=body).status_code == 422


def test_reset_requests_are_limited_per_email_and_per_ip(make_app: AppFactory) -> None:
    app = make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=6, trust_proxy=True)
    with TestClient(app) as client:
        register(client)
        # Per email, whatever the IP, and the same for an address without an account.
        for email in (EMAIL, "nobody@example.test"):
            for attempt in range(3):
                ok = request_reset(client, email, headers={"X-Forwarded-For": f"10.1.0.{attempt}"})
                assert ok.status_code == 202, (email, attempt)
            limited = request_reset(client, email, headers={"X-Forwarded-For": "10.1.9.9"})
            assert limited.status_code == 429, email
            assert limited.json()["error"]["code"] == "rate_limited"
            assert limited.json()["error"]["details"]["retry_after_seconds"] > 0
            assert int(limited.headers["retry-after"]) > 0
        assert len([r for r in rows(client, EmailOutbox) if r.template == "password_reset"]) == 3

        # Per IP: the shared auth limit (6 a minute here), across different emails.
        for attempt in range(6):
            ok = request_reset(
                client, f"user{attempt}@example.test", headers={"X-Forwarded-For": "10.2.0.1"}
            )
            assert ok.status_code == 202, attempt
        limited = request_reset(
            client, "another@example.test", headers={"X-Forwarded-For": "10.2.0.1"}
        )
        assert limited.status_code == 429
        elsewhere = request_reset(
            client, "another@example.test", headers={"X-Forwarded-For": "10.2.0.2"}
        )
        assert elsewhere.status_code == 202


# ------------------------------------------------------------- dev visibility
def test_dev_outbox_route(client: TestClient) -> None:
    missing = client.get("/v1/dev/email-outbox/latest", params={"to": EMAIL})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
    assert client.get("/v1/dev/email-outbox/latest").status_code == 422
    register(client)
    request_reset(client)
    assert latest(client)["template"] == "password_reset"  # the newest
    assert latest(client, template="verify_email")["template"] == "verify_email"
    assert latest(client, to="  ADA@example.test ")["to"] == EMAIL
    response = client.get("/v1/dev/email-outbox/latest", params={"to": EMAIL})
    assert response.headers["cache-control"] == "no-store"


def test_dev_outbox_route_is_404_in_production_and_no_link_is_stored(
    make_app: AppFactory,
) -> None:
    app = make_app(env="production", jwt_secret="k" * 48, admin_emails="boss@example.test")
    Base.metadata.create_all(app.state.engine)  # production never creates tables itself
    with TestClient(app) as client:
        register(client)
        assert request_reset(client).status_code == 202
        gone = client.get("/v1/dev/email-outbox/latest", params={"to": EMAIL})
        assert gone.status_code == 404
        assert gone.json() == {"error": {"code": "not_found", "message": "Not Found"}}
        assert "token" not in gone.text

        outbox = rows(client, EmailOutbox)
        assert [r.template for r in outbox] == ["verify_email", "password_reset"]
        for row in outbox:
            assert row.dev_link is None
            assert LINK_WITHHELD in row.body_text and "token=" not in row.body_text
        # The token hashes are there; nothing in the database can be turned back into a link.
        assert len(rows(client, EmailToken)) == 2
        admin = admin_headers(client)
        listed = client.get("/v1/admin/email-outbox", headers=admin)
        assert listed.status_code == 200 and "token=" not in listed.text


# ----------------------------------------------------------------- the sender
def test_the_outbox_is_the_default_sender_and_resend_is_a_stub(
    make_settings: SettingsFactory, make_app: AppFactory, app: FastAPI
) -> None:
    assert isinstance(app.state.email_sender, OutboxEmailSender)
    assert make_settings().email_provider == "outbox"
    assert isinstance(make_sender(make_settings()), OutboxEmailSender)
    assert make_sender(make_settings()).keep_links is True  # type: ignore[attr-defined]
    production = make_settings(env="production", jwt_secret="k" * 48)
    assert make_sender(production).keep_links is False  # type: ignore[attr-defined]

    with pytest.raises(NotImplementedError) as error:
        ResendEmailSender()
    assert str(error.value) == "Requires Founder approval and a Resend account"
    with pytest.raises(NotImplementedError, match="Requires Founder approval"):
        make_sender(make_settings(email_provider="resend"))
    # Selecting it refuses to start the app instead of failing on the first email.
    with pytest.raises(NotImplementedError, match="Requires Founder approval"):
        make_app(email_provider="resend")
    with pytest.raises(ValueError):
        make_settings(email_provider="smtp")


def test_no_email_sdk_or_network_client_in_the_mailer() -> None:
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / "src" / "oddvex_api" / "mailer").glob("*.py"))
    )
    for module in ("resend", "httpx", "requests", "smtplib", "urllib.request", "socket", "aiohttp"):
        assert not re.search(rf"^\s*(import|from)\s+{re.escape(module)}\b", source, re.M), module
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "resend" not in pyproject.lower() and "sendgrid" not in pyproject.lower()


def test_email_flows_flag_off_queues_nothing(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    before = len(rows(admin_client, EmailOutbox))
    set_flag(admin_client, admin, "email_flows", False)
    account = register(admin_client)
    assert account["user"]["email_verified"] is False
    assert len(rows(admin_client, EmailOutbox)) == before
    assert request_reset(admin_client).status_code == 404


# ------------------------------------------------------------ account removal
def test_deleting_the_account_removes_its_outbox_rows_and_tokens(
    client: TestClient, headers: Headers, other_headers: Headers
) -> None:
    request_reset(client)
    request_reset(client, "grace@example.test")
    assert len(rows(client, EmailOutbox)) == 4 and len(rows(client, EmailToken)) == 4
    token = latest(client, template="password_reset")["token"]

    assert client.delete("/v1/me", headers=headers).status_code == 204
    assert {r.to_email for r in rows(client, EmailOutbox)} == {"grace@example.test"}
    assert len(rows(client, EmailOutbox)) == 2 and len(rows(client, EmailToken)) == 2
    assert client.get("/v1/dev/email-outbox/latest", params={"to": EMAIL}).status_code == 404
    assert confirm_reset(client, token).json() == INVALID
    assert client.get("/v1/me", headers=other_headers).status_code == 200


# ------------------------------------------------------------------- the copy
LINK = "http://localhost:3000/reset-password?token=abc"
EMAILS = [
    templates.verify_email("http://localhost:3000/verify-email?token=abc", 24 * 60),
    templates.password_reset(LINK, 60),
    templates.password_reset(LINK, 45),
    templates.password_reset(LINK, 1),
]


@pytest.mark.parametrize("email", EMAILS, ids=lambda e: e.template)
def test_email_copy_is_plain_and_complete(email: templates.RenderedEmail) -> None:
    body = email.body_text
    paragraphs = body.split("\n\n")
    assert len(paragraphs) == 5
    assert paragraphs[0].startswith("This email is to ")  # what it is for
    assert "token=abc" in paragraphs[1]  # the link, on its own line
    assert paragraphs[1].splitlines()[1].startswith("http://localhost:3000/")
    assert re.fullmatch(  # the expiry
        r"This link expires in (24 hours|1 hour|45 minutes|1 minute) and works once\.",
        paragraphs[2],
    )
    assert paragraphs[3].startswith("If you didn't ask for this, you can ignore this email.")
    assert paragraphs[4] == (
        "OddVex is for information only and does not accept or place wagers. 21+. "
        "Gambling problem? Call 1-800-GAMBLER."
    )
    # Sentence case, no shouting, no hype.
    assert email.subject[0].isupper() and email.subject == email.subject.strip()
    words = email.subject.replace("OddVex", "").split()
    assert all(word == word.lower() for word in words[1:]), email.subject
    for text in (email.subject, body):
        lowered = text.lower()
        for phrase in (*BANNED_PHRASES, "urgent", "immediately", "act now", "winner"):
            assert phrase not in lowered, phrase
        assert "!" not in text and "Oddvex" not in text and "ODDVEX" not in text
        assert not re.search(r"\b[A-Z]{4,}\b", text.replace("GAMBLER", ""))


def test_expiry_wording() -> None:
    assert "expires in 24 hours" in EMAILS[0].body_text
    assert "expires in 1 hour " in EMAILS[1].body_text
    assert "expires in 45 minutes" in EMAILS[2].body_text
    assert "expires in 1 minute " in EMAILS[3].body_text


def test_the_queued_emails_are_the_templates(client: TestClient) -> None:
    register(client)
    request_reset(client)
    for template, path, expiry in (
        ("verify_email", "/verify-email", "24 hours"),
        ("password_reset", "/reset-password", "1 hour"),
    ):
        email = latest(client, template=template)
        assert email["dev_link"].startswith(f"http://localhost:3000{path}?token=")
        assert email["dev_link"] in email["body_text"]
        assert f"This link expires in {expiry} and works once." in email["body_text"]
        assert templates.IGNORE_LINE in email["body_text"]
        assert email["body_text"].endswith(templates.FOOTER)
