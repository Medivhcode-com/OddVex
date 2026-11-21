"""uvicorn's own access log is switched off by the application (compliance#6).

uvicorn writes one plain-text line per request, path and query string included
(``GET /v1/admin/users?q=jane%40example.com``), unless it is started with
``--no-access-log``. The application writes its own request line, without the query
string. ``configure_logging`` removes the handlers of the ``uvicorn.access`` logger and
stops it propagating, so the line is never written, whatever the start command says:
uvicorn configures its logging before it imports the application, and every connection
asks the logger whether it has handlers.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI
from uvicorn.config import LOGGING_CONFIG

from oddvex_api.config import Settings
from oddvex_api.logging_config import configure_logging
from oddvex_api.main import create_app
from oddvex_api.providers import SyntheticProvider

_LOGGERS = ("uvicorn", "uvicorn.access", "uvicorn.error")
_FACTORY_SETTINGS: dict[str, Settings] = {}


@pytest.fixture(autouse=True)
def _restore_uvicorn_loggers() -> Iterator[None]:
    """uvicorn's logging setup changes process-wide loggers: put them back afterwards."""
    saved = {
        name: (
            list(logging.getLogger(name).handlers),
            logging.getLogger(name).propagate,
            logging.getLogger(name).level,
        )
        for name in _LOGGERS
    }
    yield
    for name, (handlers, propagate, level) in saved.items():
        logger = logging.getLogger(name)
        logger.handlers = handlers
        logger.propagate = propagate
        logger.setLevel(level)


def _uvicorn_logging() -> None:
    """What uvicorn does at start-up with access logging on (its default)."""
    uvicorn.Config(app=FastAPI(), access_log=True, log_config=LOGGING_CONFIG)


def test_configure_logging_removes_the_uvicorn_access_handlers() -> None:
    _uvicorn_logging()
    access = logging.getLogger("uvicorn.access")
    assert access.hasHandlers()  # what a start command without --no-access-log sets up

    configure_logging("WARNING")

    assert access.handlers == []
    assert access.propagate is False
    # uvicorn writes the access line only when this is true (protocols/http/*_impl.py).
    assert access.hasHandlers() is False
    # uvicorn's error logger, which reports failures, is left as it was.
    assert logging.getLogger("uvicorn.error").hasHandlers()
    configure_logging("WARNING")  # twice is the same
    assert access.handlers == [] and access.propagate is False


def factory() -> FastAPI:
    """Imported by uvicorn after it has configured logging, as ``oddvex_api.main:app``
    is in production."""
    return create_app(_FACTORY_SETTINGS["settings"], provider=SyntheticProvider(seed=20260101))


def test_a_server_started_with_access_logging_on_writes_no_query_string(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _FACTORY_SETTINGS["settings"] = Settings(
        _env_file=None,
        env="test",
        database_url=f"sqlite:///{tmp_path / 'access.db'}",
        rate_limit_enabled=False,
        log_level="INFO",
    )
    config = uvicorn.Config(
        f"{__name__}:factory",
        factory=True,
        host="127.0.0.1",
        port=0,
        access_log=True,
        log_config=LOGGING_CONFIG,
        lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started:
            assert time.monotonic() < deadline, "server did not start"
            time.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        url = f"http://127.0.0.1:{port}/health?q=jane%40example.com"
        with urllib.request.urlopen(url, timeout=10) as response:
            assert response.status == 200
    finally:
        server.should_exit = True
        thread.join(timeout=15)
    output = capsys.readouterr()
    written = output.out + output.err
    assert "jane" not in written and "example.com" not in written, written
    # uvicorn's own start-up lines still come through: only the access log is off.
    assert "Uvicorn running on" in written, written
