"""P0.1 "Done when": a query for T returns only rows captured at or before T.

Captures run at T0, T1 = T0+360 s and T2 = T0+720 s, each with different prices, prop
offers and status records. Odds, props, status and the as-of ``EventOddsOut`` are read
before T0, exactly at T1, 1 microsecond before T1, between T1 and T2, and after T2. Every
row returned must have ``captured_at`` at or before T and the values of the latest capture
at or before T. A property test repeats this over random T across the four read paths, and
the same assertion runs through the three ``/v1/archive`` routes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from oddvex_api.archive.capture import StatusRecord, capture_status
from oddvex_api.archive.service import archived_odds, archived_props, archived_status
from oddvex_api.providers import PropOffer

from .archive_support import PREGAME, PREGAME_QUOTES, T0, ArchiveEnv, archive_env, set_quotes
from .conftest import AppFactory, auth_headers

__all__ = ["archive_env"]

T1 = T0 + timedelta(seconds=360)
T2 = T0 + timedelta(seconds=720)
CAPTURES = (T0, T1, T2)
US = timedelta(microseconds=1)
#: Best home moneyline per capture (hand-worked from PREGAME_QUOTES; oldmill is stale and
#: kestrel suspended at every capture).
BEST_HOME = {T0: ("cardinal", -110), T1: ("northline", -115), T2: ("cardinal", -105)}
#: A lineup and an injury record per capture, each different.
STATUSES = {
    T0: ("expected", "questionable"),
    T1: ("confirmed", "doubtful"),
    T2: ("confirmed", "out"),
}


def status_records(provider: Any, at: datetime, player_id: str) -> list[StatusRecord]:
    lineup, injury = STATUSES[at]
    common = {"provider": provider.name, "fetched_at": at, "event_id": PREGAME}
    return [
        StatusRecord(
            **common,
            provider_id=f"lineup:{player_id}",
            player_id=player_id,
            kind="lineup",
            status=lineup,
            source="Fictional Lineup Desk",
            reported_at=at - timedelta(seconds=45),
        ),
        StatusRecord(
            **common,
            provider_id=f"injury:{player_id}",
            player_id=player_id,
            kind="injury",
            status=injury,
            source="Fictional Injury Wire",
            reported_at=at - timedelta(seconds=90),
        ),
    ]


def build_archive(env: ArchiveEnv) -> tuple[str, dict[datetime, set[tuple[Any, ...]]]]:
    """Three captures; returns the player whose props are read and, per capture, the prop
    offers the provider gave for that player at that moment."""
    event = env.provider.get_event(PREGAME)
    assert event is not None and event.status == "upcoming"
    player = env.provider.list_players(team_id=event.home_team_id)[0]
    props: dict[datetime, set[tuple[Any, ...]]] = {}
    for offset, at in zip((0, 360, 720), CAPTURES, strict=True):
        set_quotes(env.provider, offset)
        report = env.capture(at)
        assert report.odds is not None and report.odds.status == "ok"
        assert report.props is not None and report.props.status == "ok"
        props[at] = {prop_key(o) for o in env.provider.get_prop_offers(player.id)}
        with env.session_factory() as db:
            run = capture_status(
                db, env.provider, env.settings, status_records(env.provider, at, player.id)
            )
            assert run is not None and run.status == "ok"
    # The captures differ, so a row from the wrong capture would show.
    assert props[T0] != props[T1] != props[T2]
    return player.id, props


def prop_key(offer: PropOffer | Any) -> tuple[Any, ...]:
    if isinstance(offer, PropOffer):
        return (
            offer.sportsbook_id,
            offer.market,
            offer.status,
            offer.last_updated,
            offer.line,
            offer.over_american,
            offer.under_american,
        )
    return (
        offer.sportsbook.key,
        offer.market,
        offer.status,
        offer.last_updated,
        offer.line,
        offer.over.american if offer.over else None,
        offer.under.american if offer.under else None,
    )


def expected_capture(as_of: datetime) -> datetime | None:
    earlier = [c for c in CAPTURES if c <= as_of]
    return earlier[-1] if earlier else None


def assert_as_of(
    env: ArchiveEnv, player_id: str, props: dict[datetime, set[tuple[Any, ...]]], as_of: datetime
) -> None:
    """All four read paths at ``as_of``: only rows captured at or before it, with the values
    of the latest capture at or before it."""
    capture = expected_capture(as_of)
    with env.session_factory() as db:
        odds = archived_odds(db, env.provider, env.settings, PREGAME, "moneyline", as_of)
        offers = archived_props(db, env.provider, env.settings, player_id, None, as_of)
        status = archived_status(db, env.provider, env.settings, PREGAME, as_of)
    check_odds(odds.model_dump(mode="python"), as_of, capture)
    dumped = offers.model_dump(mode="python")
    check_props(
        dumped["offers"],
        offers.offers,
        as_of,
        capture,
        props,
        {**dumped["coverage"], "pruned_event_ids": dumped["pruned_event_ids"]},
    )
    check_status([e.model_dump(mode="python") for e in status.entries], as_of, capture)


def check_odds(odds: dict[str, Any], as_of: datetime, capture: datetime | None) -> None:
    assert odds["requested_as_of"] == as_of
    if capture is None:
        assert odds["coverage"]["status"] == "not_captured"
        assert odds["quotes"] == [] and odds["odds"] is None
        return
    if as_of - capture <= timedelta(seconds=840):
        for quote in odds["quotes"]:
            assert quote["captured_at"] <= as_of
            assert quote["last_updated"] is None or quote["last_updated"] <= quote["captured_at"]
        offset = int((capture - T0).total_seconds())
        expected = {
            book: [price for _, _, price in outcomes]
            for book, _, _, outcomes in PREGAME_QUOTES[offset]["moneyline"]
        }
        found = {
            q["sportsbook"]["key"]: [o["price"]["american"] for o in q["outcomes"]]
            for q in odds["quotes"]
        }
        assert found == expected
        assert odds["coverage"] == {
            "status": "captured",
            "captured_at": capture,
            "run_id": odds["coverage"]["run_id"],
        }
        board = odds["odds"]
        assert board is not None and board["as_of"] == as_of
        assert board["data_mode"] == "synthetic"
        for book in board["books"]:
            assert book["last_updated"] is None or book["last_updated"] <= capture
        (best,) = [b for b in board["best"] if b["outcome_key"] == "home"]
        assert (best["sportsbook_key"], best["price"]["american"]) == BEST_HOME[capture]
    else:
        # Quotes are served only for a covered time: older rows are not the market at T.
        assert odds["coverage"]["status"] == "archive_gap" and odds["odds"] is None
        assert odds["quotes"] == []


def check_props(
    dumped: list[dict[str, Any]],
    offers: list[Any],
    as_of: datetime,
    capture: datetime | None,
    props: dict[datetime, set[tuple[Any, ...]]],
    coverage: dict[str, Any],
) -> None:
    """Props are captured on the odds cadence in these tests, so the props gap limit is
    the same 840 s (two intervals and one worker turn)."""
    assert pruned_ids(coverage) == []
    if capture is None:
        assert coverage["status"] == "not_captured" and coverage["captured_at"] is None
        assert offers == []
        return
    if as_of - capture > timedelta(seconds=840):
        assert coverage["status"] == "archive_gap" and coverage["captured_at"] == capture
        assert offers == []
        return
    assert coverage["status"] == "captured" and coverage["captured_at"] == capture
    assert all(o["captured_at"] <= as_of for o in dumped)
    assert {prop_key(o) for o in offers} == props[capture]


def pruned_ids(coverage: dict[str, Any]) -> list[str]:
    return list(coverage["pruned_event_ids"])


def check_status(entries: list[dict[str, Any]], as_of: datetime, capture: datetime | None) -> None:
    if capture is None:
        assert entries == []
        return
    assert all(e["captured_at"] <= as_of for e in entries)
    assert {e["kind"]: e["status"] for e in entries} == dict(
        zip(("lineup", "injury"), STATUSES[capture], strict=True)
    )
    assert all(e["reported_at"] <= e["captured_at"] for e in entries)


def test_a_query_for_T_returns_only_rows_captured_at_or_before_T(
    archive_env: ArchiveEnv, make_app: AppFactory
) -> None:
    env = archive_env
    player_id, props = build_archive(env)

    for as_of in (
        T0 - timedelta(seconds=1),  # before the first capture
        T0,
        T1 - US,  # 1 microsecond before T1: still T0's rows
        T1,  # exactly T1: T1's rows (at or before)
        T1 + timedelta(seconds=100),  # between T1 and T2
        T2 + timedelta(seconds=100),  # after T2
        T2 + timedelta(hours=1),  # after T2, past the gap limit
    ):
        assert_as_of(env, player_id, props, as_of)

    # Random T over the whole span, through all four read paths.
    span = int((T2 - T0 + timedelta(hours=2)).total_seconds() * 1_000_000)

    @settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(st.integers(min_value=0, max_value=span))
    def property_holds(micros: int) -> None:
        assert_as_of(
            env, player_id, props, T0 - timedelta(hours=1) + timedelta(microseconds=micros)
        )

    property_holds()

    # The same through the three /v1/archive routes.
    env.provider.current = T2 + timedelta(hours=2)
    with TestClient(make_app(provider=env.provider, **_archive_settings(env))) as client:
        headers = auth_headers(client)
        for as_of in (
            T0 - timedelta(seconds=1),
            T1 - US,
            T1,
            T1 + timedelta(seconds=100),
            T2 + timedelta(hours=1),
        ):
            capture = expected_capture(as_of)
            params = {"as_of": as_of.isoformat()}
            odds = client.get(
                f"/v1/archive/events/{PREGAME}/odds",
                params={**params, "market": "moneyline"},
                headers=headers,
            )
            assert odds.status_code == 200, odds.text
            check_odds(_parse_times(odds.json()), as_of, capture)
            offers = client.get(
                f"/v1/archive/players/{player_id}/props", params=params, headers=headers
            )
            assert offers.status_code == 200, offers.text
            body = _parse_times(offers.json())
            parsed = body["offers"]
            check_props(
                parsed,
                [_PropView(o) for o in parsed],
                as_of,
                capture,
                props,
                {**body["coverage"], "pruned_event_ids": body["pruned_event_ids"]},
            )
            status = client.get(
                f"/v1/archive/events/{PREGAME}/status", params=params, headers=headers
            )
            assert status.status_code == 200, status.text
            check_status(_parse_times(status.json())["entries"], as_of, capture)


def _archive_settings(env: ArchiveEnv) -> dict[str, Any]:
    return {"snapshot_props_interval_seconds": env.settings.snapshot_props_interval_seconds}


_TIME_FIELDS = {
    "requested_as_of",
    "captured_at",
    "last_updated",
    "as_of",
    "reported_at",
    "fetched_at",
}


def _parse_times(value: Any) -> Any:
    """JSON timestamps back to datetimes, so the checks above compare instants."""
    if isinstance(value, dict):
        return {
            k: datetime.fromisoformat(v)
            if k in _TIME_FIELDS and isinstance(v, str)
            else _parse_times(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_parse_times(v) for v in value]
    return value


class _PropView:
    """An offer from the JSON answer with the attributes ``prop_key`` reads."""

    def __init__(self, offer: dict[str, Any]) -> None:
        self.sportsbook = _Obj(key=offer["sportsbook"]["key"])
        self.market = offer["market"]
        self.status = offer["status"]
        self.last_updated = offer["last_updated"]
        self.line = offer["line"]
        self.over = _Obj(american=offer["over"]["american"]) if offer["over"] else None
        self.under = _Obj(american=offer["under"]["american"]) if offer["under"] else None


class _Obj:
    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)


def test_a_later_change_of_stale_threshold_never_rewrites_history(archive_env: ArchiveEnv) -> None:
    """Staleness as of T uses the thresholds stored on the capture run, not today's
    settings: captured with a 900 s pregame limit, read with a 60 s one, the best price is
    the same."""
    env = archive_env
    env.settings = env.settings.model_copy(update={"stale_pregame_seconds": 900})
    build_archive(env)
    stricter = env.settings.model_copy(update={"stale_pregame_seconds": 60})
    as_of = T1 + timedelta(seconds=100)  # T1's quotes are 120 s old then
    with env.session_factory() as db:
        for settings_now in (env.settings, stricter):
            odds = archived_odds(db, env.provider, settings_now, PREGAME, "moneyline", as_of)
            assert odds.odds is not None
            assert odds.odds.stale_after_seconds == 900
            (best,) = [b for b in odds.odds.best if b.outcome_key == "home"]
            assert (best.sportsbook_key, best.price.american) == BEST_HOME[T1]
