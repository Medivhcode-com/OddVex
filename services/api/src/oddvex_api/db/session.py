"""Engine and session factory."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def normalize_database_url(url: str) -> str:
    """Use the psycopg 3 driver for plain ``postgres://`` / ``postgresql://`` URLs."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def make_engine(database_url: str) -> Engine:
    """The engine for ``database_url``.

    ``hide_parameters`` on both kinds: the error of a failed statement then names the
    statement but not the values bound to it (an email address, a password hash), so
    they are in no log line and no traceback, whoever catches or prints the error. The
    driver's own message is handled where errors are logged (``logging_config.py``).
    """
    url = normalize_database_url(database_url)
    if url.startswith("sqlite"):
        kwargs: dict[str, object] = {
            "connect_args": {"check_same_thread": False},
            "hide_parameters": True,
        }
        if ":memory:" in url or url in ("sqlite://", "sqlite:///"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True, hide_parameters=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
