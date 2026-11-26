"""Shared set-up for the snapshot archive tests (P0.1).

Everything here is synthetic: the seeded schedule of :class:`ControlledProvider`, its
fictional sportsbooks (northline, cardinal, summit, blueharbor, kestrel, oldmill) and
hand-written quotes, so every expected price in the tests can be worked out by hand.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from oddvex_api.archive.capture import PassReport, StatusRecord, capture_pass
from oddvex_api.archive.guard import install_archive_guard
from oddvex_api.config import Settings
from oddvex_api.db import Base, Bet, BetLeg, User, make_engine, make_session_factory, new_id
from oddvex_api.flags import service as flags

from .conftest import FROZEN_NOW, SettingsFactory
from .fakes import ControlledProvider, moneyline, spread, total

API_ROOT = Path(__file__).resolve().parents[1]
T0 = FROZEN_NOW
#: An NHL game that starts at 21:00 and stays upcoming through every capture below.
PREGAME = "evt_nhl_20260314_3"
#: An MLB game at 20:00, upcoming until then: the second leg of the parlay.
PREGAME_2 = "evt_mlb_20260314_3"
#: Next day's NHL game: in scope (36 h) but no bet is placed on it before the prune.
OTHER_PREGAME = "evt_nhl_20260315_0"
#: An NBA game in progress at T0.
LIVE = "evt_nba_20260314_3"
#: The books "the user" holds in these tests.
USER_BOOKS = ["northline", "summit"]
#: Settings for every archive test: props on the same cadence as odds.
ARCHIVE_SETTINGS: dict[str, Any] = {
    "snapshot_props_interval_seconds": 360,
}


@dataclass
class ArchiveEnv:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    provider: ControlledProvider

    def capture(self, at: datetime, *, force: bool = True) -> PassReport:
        """Move the clock to ``at`` and run one capture pass."""
        self.provider.current = at
        return capture_pass(self.engine, self.provider, self.settings, force=force)


def enable_archive(session_factory: sessionmaker[Session], enabled: bool = True) -> None:
    with session_factory() as db:
        flags.set_flag(db, "snapshot_archive", enabled)
        db.commit()


@pytest.fixture
def archive_env(make_settings: SettingsFactory) -> Iterator[ArchiveEnv]:
    settings = make_settings(**ARCHIVE_SETTINGS)
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    install_archive_guard()
    session_factory = make_session_factory(engine)
    enable_archive(session_factory)
    yield ArchiveEnv(settings, engine, session_factory, ControlledProvider())
    engine.dispose()


def capture_script(
    env: ArchiveEnv, *args: str, extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``scripts/capture_snapshots.py`` on the test database, as the worker does."""
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "DATABASE_URL": env.settings.database_url,
        "ODDVEX_ENV": "test",
        "ODDVEX_LOG_LEVEL": "WARNING",
        **(extra or {}),
    }
    return subprocess.run(
        [sys.executable, str(API_ROOT / "scripts" / "capture_snapshots.py"), *args],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


# ------------------------------------------------------------------ quotes
#: Hand-written quotes per capture offset (seconds after T0). Book, status, age in
#: seconds at capture, outcomes. ``oldmill`` is always older than the 900 s pregame limit
#: (stale) and ``kestrel`` is suspended, and each carries the highest price on purpose.
PREGAME_QUOTES: dict[int, dict[str, list[Any]]] = {
    0: {
        "moneyline": [
            ("northline", "open", 30, moneyline(-120, 100)),
            ("cardinal", "open", 30, moneyline(-110, -105)),
            ("summit", "open", 30, moneyline(-125, 105)),
            ("oldmill", "open", 1000, moneyline(-105, 130)),
            ("kestrel", "suspended", 30, moneyline(-102, 120)),
        ],
        "spread": [
            ("northline", "open", 30, spread(-1.5, 150, -180)),
            ("cardinal", "open", 30, spread(-1.5, 160, -190)),
            ("summit", "open", 30, spread(-1.5, 155, -185)),
            ("blueharbor", "open", 30, spread(-2.5, 210, -260)),
        ],
        "total": [
            ("northline", "open", 30, total(5.5, -110, -110)),
            ("summit", "open", 30, total(5.5, -105, -115)),
            ("cardinal", "open", 30, total(6.0, -120, 100)),
        ],
    },
    360: {
        "moneyline": [
            ("northline", "open", 20, moneyline(-115, -105)),
            ("cardinal", "open", 20, moneyline(-118, 100)),
            ("summit", "open", 20, moneyline(-120, 100)),
            ("oldmill", "open", 1000, moneyline(-105, 130)),
            ("kestrel", "suspended", 20, moneyline(-102, 120)),
        ],
        "spread": [
            ("northline", "open", 20, spread(-1.5, 145, -175)),
            ("cardinal", "open", 20, spread(-1.5, 140, -170)),
            ("summit", "open", 20, spread(-1.5, 150, -180)),
            ("blueharbor", "open", 20, spread(-2.5, 210, -260)),
        ],
        "total": [
            ("northline", "open", 20, total(5.5, -112, -108)),
            ("summit", "open", 20, total(5.5, -108, -112)),
            ("cardinal", "open", 20, total(6.0, -120, 100)),
        ],
    },
    720: {
        "moneyline": [
            ("northline", "open", 10, moneyline(-110, -110)),
            ("cardinal", "open", 10, moneyline(-105, -115)),
            ("summit", "open", 10, moneyline(-112, -108)),
            ("oldmill", "open", 1000, moneyline(-105, 130)),
            ("kestrel", "suspended", 10, moneyline(-102, 120)),
        ],
        "spread": [
            ("northline", "open", 10, spread(-1.5, 140, -170)),
            ("cardinal", "open", 10, spread(-1.5, 135, -165)),
            ("summit", "open", 10, spread(-1.5, 145, -175)),
            ("blueharbor", "open", 10, spread(-2.5, 205, -255)),
        ],
        "total": [
            ("northline", "open", 10, total(5.5, -115, -105)),
            ("summit", "open", 10, total(5.5, 100, -120)),
            ("cardinal", "open", 10, total(6.0, -125, 105)),
        ],
    },
    1800: {
        "moneyline": [
            ("northline", "open", 10, moneyline(100, -120)),
            ("cardinal", "open", 10, moneyline(105, -125)),
            ("summit", "open", 10, moneyline(-102, -118)),
        ],
        "spread": [
            ("northline", "open", 10, spread(-1.5, 130, -160)),
            ("summit", "open", 10, spread(-1.5, 135, -165)),
        ],
        "total": [
            ("northline", "open", 10, total(5.5, -120, 100)),
            ("summit", "open", 10, total(5.5, -110, -110)),
        ],
    },
}
#: The second parlay leg's game: moneyline only.
PREGAME_2_QUOTES: dict[int, list[Any]] = {
    0: [
        ("northline", "open", 30, moneyline(-150, 130)),
        ("summit", "open", 30, moneyline(-145, 125)),
    ],
    360: [
        ("northline", "open", 20, moneyline(-155, 135)),
        ("summit", "open", 20, moneyline(-140, 120)),
    ],
    720: [
        ("northline", "open", 10, moneyline(-160, 140)),
        ("summit", "open", 10, moneyline(-150, 130)),
        ("cardinal", "open", 10, moneyline(-135, 115)),
    ],
    1800: [("northline", "open", 10, moneyline(-170, 150))],
}
#: The live game: fresh quotes (10 s old) at every capture.
LIVE_QUOTES: dict[int, list[Any]] = {
    offset: [
        ("northline", "open", 10, moneyline(-130 - offset // 100, 110)),
        ("summit", "open", 10, moneyline(-135 - offset // 100, 115)),
    ]
    for offset in (0, 360, 720, 1800)
}
#: The other pregame game: the same quotes at every capture.
OTHER_QUOTES = [
    ("northline", "open", 30, moneyline(-140, 120)),
    ("summit", "open", 30, moneyline(-135, 115)),
]


def set_quotes(provider: ControlledProvider, offset: int) -> None:
    """Install the hand-written quotes for the capture ``offset`` seconds after T0."""
    for market, quotes in PREGAME_QUOTES[offset].items():
        provider.set_odds(PREGAME, market, quotes)
    provider.set_odds(PREGAME_2, "moneyline", PREGAME_2_QUOTES[offset])
    provider.set_odds(LIVE, "moneyline", LIVE_QUOTES[offset])
    provider.set_odds(OTHER_PREGAME, "moneyline", OTHER_QUOTES)


SCHEDULE = (0, 360, 720, 1800)


def capture_schedule_on(
    engine: Engine,
    provider: ControlledProvider,
    settings: Settings,
    offsets: tuple[int, ...] = SCHEDULE,
) -> None:
    """Captures at T0 + each offset, with that offset's quotes."""
    for offset in offsets:
        set_quotes(provider, offset)
        provider.current = T0 + timedelta(seconds=offset)
        report = capture_pass(engine, provider, settings, force=True)
        assert report.odds is not None and report.odds.status == "ok", report


def capture_schedule(env: ArchiveEnv, offsets: tuple[int, ...] = SCHEDULE) -> None:
    capture_schedule_on(env.engine, env.provider, env.settings, offsets)


# -------------------------------------------------------------------- bets
def make_user(db: Session, email: str = "ada@example.test") -> User:
    user = User(email=email, password_hash="x", display_name="Ada", age_confirmed_at=T0)
    db.add(user)
    db.flush()
    return user


def make_bet(
    db: Session,
    user: User,
    placed_at: datetime,
    legs: list[dict[str, Any]],
    sportsbook: str = "Northline",
) -> Bet:
    """A bet with structured legs: each leg is ``{event_id, market, outcome_key, line,
    odds_decimal}``; ``selection`` defaults to a label built from them."""
    bet = Bet(
        id=new_id(),
        user_id=user.id,
        bet_type="straight" if len(legs) == 1 else "parlay",
        sportsbook=sportsbook,
        stake=Decimal("10.00"),
        odds_decimal=Decimal("1.909091"),
        placed_at=placed_at,
    )
    for position, leg in enumerate(legs):
        bet.legs.append(
            BetLeg(
                position=position,
                selection=leg.get("selection", f"{leg.get('outcome_key')} {leg.get('line')}"),
                market=leg["market"],
                event_id=leg.get("event_id"),
                outcome_key=leg.get("outcome_key"),
                line=None if leg.get("line") is None else Decimal(str(leg["line"])),
                odds_decimal=Decimal(str(leg.get("odds_decimal", "1.909091"))),
            )
        )
    db.add(bet)
    db.flush()
    return bet


__all__ = [
    "ARCHIVE_SETTINGS",
    "LIVE",
    "OTHER_PREGAME",
    "PREGAME",
    "PREGAME_2",
    "T0",
    "USER_BOOKS",
    "ArchiveEnv",
    "StatusRecord",
    "archive_env",
    "capture_schedule",
    "capture_schedule_on",
    "capture_script",
    "enable_archive",
    "make_bet",
    "make_user",
    "set_quotes",
]
