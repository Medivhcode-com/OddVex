"""The administrator role goes only to an account whose email address is verified, in
every environment and whatever the ``email_flows`` flag says, and the first
administrator in production comes from ``scripts/bootstrap_admin.py``.

Before, with ``email_flows`` off (the production default), a listed address was an
administrator from the list alone: whoever had registered that address first got the
role the moment an operator listed it.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.config import Settings
from oddvex_api.db import AuditLog, Base, Bet, EmailToken, User, make_engine, make_session_factory
from oddvex_api.flags import service as flags

from .conftest import (
    ADMIN_EMAIL,
    PASSWORD,
    AppFactory,
    SettingsFactory,
    admin_headers,
    mark_email_verified,
    register,
    verify_email,
)

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = API_ROOT / "scripts" / "bootstrap_admin.py"
Headers = dict[str, str]
BET = {
    "bet_type": "straight",
    "stake": 10,
    "sportsbook": "Northline",
    "legs": [{"selection": "Tides ML", "market": "moneyline", "odds": -110}],
}


def bearer(token: str) -> Headers:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str = PASSWORD) -> Any:
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def audit(app: FastAPI, action: str) -> list[AuditLog]:
    with app.state.session_factory() as db:
        return list(
            db.scalars(
                select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at)
            )
        )


def user_row(app: FastAPI, email: str) -> User:
    with app.state.session_factory() as db:
        return db.scalars(select(User).where(User.email == email)).one()


def production_app(make_app: AppFactory, **overrides: Any) -> FastAPI:
    app = make_app(env="production", jwt_secret="k" * 48, **overrides)
    Base.metadata.create_all(app.state.engine)  # production never creates tables itself
    return app


def assert_not_an_administrator(client: TestClient, headers: Headers) -> None:
    assert client.get("/v1/me", headers=headers).json()["role"] == "user"
    for method, path, body in (
        ("GET", "/v1/admin/overview", None),
        ("GET", "/v1/admin/users", None),
        ("GET", "/v1/admin/audit", None),
        ("PUT", "/v1/admin/flags/community", {"enabled": True}),
    ):
        refused = client.request(method, path, json=body, headers=headers)
        assert refused.status_code == 403, path
        assert refused.json()["error"]["code"] == "forbidden"
    assert client.get("/v1/flags").json()["flags"]["community"] is False


# --------------------------------------------- the list alone gives nobody the role
def test_in_production_a_listed_address_is_not_an_administrator_from_registration(
    make_app: AppFactory,
) -> None:
    app = production_app(make_app, admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        assert client.get("/v1/flags").json()["flags"]["email_flows"] is False
        account = register(client, ADMIN_EMAIL)
        assert account["user"]["role"] == "user" and account["user"]["email_verified"] is False
        assert_not_an_administrator(client, bearer(account["access_token"]))
        signed_in = login(client, ADMIN_EMAIL)
        assert signed_in.json()["user"]["role"] == "user"
        assert_not_an_administrator(client, bearer(signed_in.json()["access_token"]))
        assert audit(app, "role.granted") == []
        assert user_row(app, ADMIN_EMAIL).role == "user"


def test_whoever_registered_an_address_first_gains_nothing_when_it_is_listed_later(
    make_app: AppFactory,
) -> None:
    """The finding's scenario: a stranger registers the address, the operator lists it."""
    app = production_app(make_app)
    with TestClient(app) as client:
        stranger = bearer(register(client, ADMIN_EMAIL)["access_token"])
        register(client, "ada@example.test")
        app.state.engine.dispose()

    listed = make_app(env="production", jwt_secret="k" * 48, admin_emails=ADMIN_EMAIL)
    with TestClient(listed) as client:
        assert_not_an_administrator(client, stranger)
        again = bearer(login(client, ADMIN_EMAIL).json()["access_token"])
        assert_not_an_administrator(client, again)
        assert audit(listed, "role.granted") == []


@pytest.mark.parametrize("env", ["test", "development"])
def test_with_email_flows_switched_off_elsewhere_the_rule_is_the_same(
    make_app: AppFactory, env: str
) -> None:
    app = make_app(env=env, admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        with app.state.session_factory() as db:
            flags.set_flag(db, "email_flows", False, app.state.settings)
            db.commit()
        account = register(client, ADMIN_EMAIL)
        assert account["user"]["role"] == "user"
        assert_not_an_administrator(client, bearer(account["access_token"]))
        assert audit(app, "role.granted") == []


@pytest.mark.parametrize("production", [True, False])
def test_a_verified_listed_address_gets_the_role_whatever_the_flag_says(
    make_app: AppFactory, production: bool
) -> None:
    app = (
        production_app(make_app, admin_emails=ADMIN_EMAIL)
        if production
        else make_app(admin_emails=ADMIN_EMAIL)
    )
    with TestClient(app) as client:
        with app.state.session_factory() as db:
            flags.set_flag(db, "email_flows", False, app.state.settings)
            db.commit()
        account = register(client, ADMIN_EMAIL)
        headers = bearer(account["access_token"])
        assert_not_an_administrator(client, headers)
        mark_email_verified(client, ADMIN_EMAIL)
        # On the next use of the token, without signing in again.
        assert client.get("/v1/admin/overview", headers=headers).status_code == 200
        assert client.get("/v1/me", headers=headers).json()["role"] == "admin"
        (granted,) = audit(app, "role.granted")
        assert granted.details == {"role": "admin", "source": "admin_emails"}
        assert (granted.user_id, granted.entity_id) == (
            account["user"]["id"],
            account["user"]["id"],
        )
        # A verified address that is not listed stays an ordinary user.
        other = register(client, "ada@example.test")
        mark_email_verified(client, "ada@example.test")
        assert_not_an_administrator(client, bearer(other["access_token"]))


def test_confirming_the_address_grants_the_role_where_email_flows_is_on(
    admin_client: TestClient,
) -> None:
    account = register(admin_client, ADMIN_EMAIL)
    headers = bearer(account["access_token"])
    assert_not_an_administrator(admin_client, headers)
    verify_email(admin_client, ADMIN_EMAIL)
    assert admin_client.get("/v1/admin/overview", headers=headers).status_code == 200


def test_an_unverified_account_that_holds_the_role_loses_it_at_its_next_request(
    make_app: AppFactory,
) -> None:
    """An account the earlier rule made an administrator from the list alone."""
    app = production_app(make_app, admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        account = register(client, ADMIN_EMAIL)
        headers = bearer(account["access_token"])
        with app.state.session_factory() as db:
            db.get(User, account["user"]["id"]).role = "admin"
            db.commit()
        assert client.get("/v1/admin/users", headers=headers).status_code == 403
        assert user_row(app, ADMIN_EMAIL).role == "user"
        (removed,) = audit(app, "role.removed")
        assert removed.details == {"role": "admin", "reason": "email_not_verified"}
        assert (removed.user_id, removed.entity_id) == (
            account["user"]["id"],
            account["user"]["id"],
        )
        # Once, not on every request; and signing in does not bring it back.
        assert_not_an_administrator(client, headers)
        assert login(client, ADMIN_EMAIL).json()["user"]["role"] == "user"
        assert len(audit(app, "role.removed")) == 1


def test_the_test_helper_makes_an_administrator_in_every_environment(
    make_app: AppFactory,
) -> None:
    app = production_app(make_app, admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        headers = admin_headers(client)
        assert client.get("/v1/admin/overview", headers=headers).status_code == 200
        assert user_row(app, ADMIN_EMAIL).email_verified is True


# ------------------------------------------------------------ the operator command
@pytest.fixture
def bootstrap() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bootstrap_admin_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_bootstrap(
    bootstrap: ModuleType, app: FastAPI, capsys: pytest.CaptureFixture[str], *argv: str
) -> tuple[int, str, str]:
    capsys.readouterr()
    code = bootstrap.main(list(argv), settings=app.state.settings)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def printed_password(out: str) -> str:
    (password,) = re.findall(r"^New password: (\S+)$", out, flags=re.MULTILINE)
    return str(password)


def test_bootstrap_creates_the_first_administrator(
    make_app: AppFactory, bootstrap: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    app = production_app(make_app, admin_emails=f"other@example.test, {ADMIN_EMAIL}")
    with TestClient(app) as client:
        code, out, err = run_bootstrap(bootstrap, app, capsys, "--email", "Boss@Example.TEST ")
        assert code == 0, err
        password = printed_password(out)
        assert len(password) >= 24
        assert out.count(password) == 1 and password not in err
        assert f"created the account {ADMIN_EMAIL}" in out
        (advice,) = [line for line in out.splitlines() if "Sign in" in line]
        assert "change" in advice and "at once" in advice

        row = user_row(app, ADMIN_EMAIL)
        assert (row.role, row.status, row.is_active) == ("admin", "active", True)
        assert row.email_verified is True and row.password_hash.startswith("$argon2")
        assert password not in row.password_hash

        signed_in = login(client, ADMIN_EMAIL, password)
        assert signed_in.status_code == 200, signed_in.text
        assert signed_in.json()["user"]["role"] == "admin"
        headers = bearer(signed_in.json()["access_token"])
        assert client.get("/v1/admin/users", headers=headers).status_code == 200
        # The printed password can be changed in the ordinary way.
        changed = client.post(
            "/v1/me/password",
            json={"current_password": password, "new_password": "my-own-new-password"},
            headers=headers,
        )
        assert changed.status_code == 200

        (entry,) = audit(app, "admin.bootstrap")
        assert (entry.user_id, entry.entity_type, entry.entity_id) == (row.id, "user", row.id)
        assert entry.details == {"account": "created", "source": "scripts/bootstrap_admin.py"}
        (granted,) = audit(app, "role.granted")
        assert granted.details == {"role": "admin", "source": "bootstrap_admin"}
        for line in (entry, granted):
            assert ADMIN_EMAIL not in str(line.details) and password not in str(line.details)
            assert line.ip is None and line.request_id is None


def test_bootstrap_takes_over_an_account_someone_else_registered(
    make_app: AppFactory, bootstrap: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    app = production_app(make_app, admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        squatter = register(client, ADMIN_EMAIL, display_name="Not The Owner")
        old = bearer(squatter["access_token"])
        assert client.post("/v1/bets", json=BET, headers=old).status_code == 201
        with app.state.session_factory() as db:
            # A reset link requested before the takeover must not work after it.
            flags.set_flag(db, "email_flows", True, app.state.settings)
            db.commit()
        assert (
            client.post("/v1/auth/password-reset/request", json={"email": ADMIN_EMAIL}).status_code
            == 202
        )
        with app.state.session_factory() as db:
            assert db.scalar(select(EmailToken.id)) is not None

        code, out, err = run_bootstrap(bootstrap, app, capsys, "--email", ADMIN_EMAIL)
        assert code == 0, err
        password = printed_password(out)
        assert len(password) >= 24
        assert f"took over the existing account {ADMIN_EMAIL}" in out

        # Whoever held the address can no longer use it: not the token, not the password.
        refused = client.get("/v1/me", headers=old)
        assert refused.status_code == 401 and refused.json()["error"]["code"] == "invalid_token"
        assert client.get("/v1/admin/users", headers=old).status_code == 401
        assert login(client, ADMIN_EMAIL, PASSWORD).status_code == 401
        with app.state.session_factory() as db:
            assert list(db.scalars(select(EmailToken))) == []

        signed_in = login(client, ADMIN_EMAIL, password)
        assert signed_in.status_code == 200
        user = signed_in.json()["user"]
        assert (user["id"], user["role"], user["email_verified"]) == (
            squatter["user"]["id"],
            "admin",
            True,
        )
        assert (
            client.get(
                "/v1/admin/overview", headers=bearer(signed_in.json()["access_token"])
            ).status_code
            == 200
        )
        (entry,) = audit(app, "admin.bootstrap")
        assert entry.details == {"account": "taken_over", "source": "scripts/bootstrap_admin.py"}
        assert entry.entity_id == squatter["user"]["id"]
        # The account is the same row: its data is still there for the new holder to see.
        with app.state.session_factory() as db:
            assert db.scalar(select(Bet.id).where(Bet.user_id == user["id"])) is not None


def test_bootstrap_twice_sets_another_password_and_ends_the_first(
    make_app: AppFactory, bootstrap: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    app = production_app(make_app, admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        first = printed_password(run_bootstrap(bootstrap, app, capsys, "--email", ADMIN_EMAIL)[1])
        token = bearer(login(client, ADMIN_EMAIL, first).json()["access_token"])
        code, out, _ = run_bootstrap(bootstrap, app, capsys, "--email", ADMIN_EMAIL)
        second = printed_password(out)
        assert code == 0 and second != first
        assert "took over the existing account" in out
        assert login(client, ADMIN_EMAIL, first).status_code == 401
        assert client.get("/v1/me", headers=token).status_code == 401
        assert login(client, ADMIN_EMAIL, second).status_code == 200
        assert len(audit(app, "admin.bootstrap")) == 2
        assert len(audit(app, "role.granted")) == 1  # the role was already there


def test_bootstrap_reopens_a_suspended_or_deactivated_account(
    make_app: AppFactory, bootstrap: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    app = production_app(make_app, admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        account = register(client, ADMIN_EMAIL)
        with app.state.session_factory() as db:
            row = db.get(User, account["user"]["id"])
            row.status, row.is_active = "suspended", False
            db.commit()
        code, out, _ = run_bootstrap(bootstrap, app, capsys, "--email", ADMIN_EMAIL)
        assert code == 0
        signed_in = login(client, ADMIN_EMAIL, printed_password(out))
        assert signed_in.status_code == 200 and signed_in.json()["user"]["role"] == "admin"


def test_bootstrap_refuses_an_address_that_is_not_listed(
    make_app: AppFactory, bootstrap: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    app = production_app(make_app, admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        victim = register(client, "ada@example.test")
        before = user_row(app, "ada@example.test")
        for address in ("ada@example.test", "nobody@example.test"):
            code, out, err = run_bootstrap(bootstrap, app, capsys, "--email", address)
            assert code != 0
            assert f"{address} is not in ODDVEX_ADMIN_EMAILS" in err
            assert "New password" not in out and out == ""
        after = user_row(app, "ada@example.test")
        assert (after.password_hash, after.token_version, after.role, after.email_verified) == (
            before.password_hash,
            before.token_version,
            "user",
            False,
        )
        assert client.get("/v1/me", headers=bearer(victim["access_token"])).status_code == 200
        with app.state.session_factory() as db:
            assert db.scalar(select(User.id).where(User.email == "nobody@example.test")) is None
        assert audit(app, "admin.bootstrap") == []


def test_bootstrap_refuses_when_no_address_is_listed_at_all(
    make_app: AppFactory, bootstrap: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    app = production_app(make_app)
    with TestClient(app):
        code, out, err = run_bootstrap(bootstrap, app, capsys, "--email", ADMIN_EMAIL)
        assert code != 0 and out == ""
        assert "is not in ODDVEX_ADMIN_EMAILS" in err
        with app.state.session_factory() as db:
            assert list(db.scalars(select(User))) == []


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--email"],
        ["--email", ""],
        ["--email", "not-an-address"],
        ["--email", "two@example.test", "--email", "three@example.test", "extra"],
        ["boss@example.test"],
        ["--email", "a b@example.test"],
    ],
)
def test_bootstrap_refuses_bad_arguments(
    make_app: AppFactory,
    bootstrap: ModuleType,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    app = production_app(make_app, admin_emails="boss@example.test, two@example.test")
    with TestClient(app):
        code, out, err = run_bootstrap(bootstrap, app, capsys, *argv)
        assert code != 0 and out == "" and err.strip()
        with app.state.session_factory() as db:
            assert list(db.scalars(select(User))) == []


def test_bootstrap_fails_clearly_when_the_database_is_not_ready(
    tmp_path: Path,
    bootstrap: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A database without tables: migrations have not been applied. Always a file of its
    # own, so that this never touches the database the other tests run on.
    settings = Settings(
        _env_file=None,
        env="production",
        jwt_secret="k" * 48,
        database_url=f"sqlite:///{tmp_path / 'empty.db'}",
        admin_emails=ADMIN_EMAIL,
    )
    capsys.readouterr()
    code = bootstrap.main(["--email", ADMIN_EMAIL], settings=settings)
    captured = capsys.readouterr()
    assert code != 0 and captured.out == ""
    assert "database" in captured.err.lower() and "Nothing was changed" in captured.err
    assert "Traceback" not in captured.err and ADMIN_EMAIL not in captured.err


@pytest.fixture
def script_database(tmp_path: Path) -> Iterator[str]:
    url = f"sqlite:///{tmp_path / 'script.db'}"
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    yield url


def test_the_script_runs_the_way_the_container_runs_it(
    tmp_path: Path, script_database: str, make_settings: SettingsFactory
) -> None:
    """``python scripts/bootstrap_admin.py --email ...`` with settings from the
    environment, from another directory, as ``docker compose exec`` does."""
    env = {
        "DATABASE_URL": script_database,
        "ODDVEX_ENV": "production",
        "ODDVEX_JWT_SECRET": "k" * 48,
        "ODDVEX_ADMIN_EMAILS": "Owner@Example.test",
        "PATH": "/usr/bin:/bin",
    }

    def run(*argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *argv],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    refused = run("--email", "stranger@example.test")
    assert refused.returncode != 0 and refused.stdout == ""
    assert "stranger@example.test is not in ODDVEX_ADMIN_EMAILS" in refused.stderr
    assert "Traceback" not in refused.stderr

    done = run("--email", "owner@example.test")
    assert done.returncode == 0, done.stderr
    password = printed_password(done.stdout)
    assert len(password) >= 24 and done.stdout.count(password) == 1
    assert password not in done.stderr
    assert "Sign in" in done.stdout and "change" in done.stdout

    with make_session_factory(make_engine(script_database))() as db:
        (user,) = db.scalars(select(User))
        assert (user.email, user.role, user.email_verified) == ("owner@example.test", "admin", True)

    # The API on the same database accepts the printed password as an administrator.
    from oddvex_api.main import create_app

    app = create_app(
        make_settings(
            database_url=script_database,
            env="production",
            jwt_secret="k" * 48,
            admin_emails="owner@example.test",
        )
    )
    with TestClient(app) as client:
        signed_in = login(client, "owner@example.test", password)
        assert signed_in.status_code == 200 and signed_in.json()["user"]["role"] == "admin"
