"""Only comparable quotes are compared (audit quant-data#2 and the board half of quant-data#5).

* The value screen lists upcoming events only.
* A quote is stale when it is older than the threshold, has no timestamp, carries a
  timestamp from the future, or, in a live game, was made before the latest score change.
* A stale quote is never marked best, never counts in the consensus and is never the best
  price handed to alerts and community picks.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oddvex_api.board import VALUE_METHOD, Board
from oddvex_api.cache import InMemoryTTLCache
from oddvex_api.config import Settings
from oddvex_api.providers import Event, OddsOutcome, OddsSnapshot, PropOffer, SyntheticProvider

from .conftest import FROZEN_NOW, AppFactory
from .fakes import ControlledProvider, moneyline, spread, total

#: (sportsbook, status, last_updated, american prices home / away)
Stamped = tuple[str, str, datetime | None, tuple[int, int]]


class StampedProvider(SyntheticProvider):
    """Synthetic schedule; moneylines and prop offers carry the timestamps the test gives."""

    def __init__(self) -> None:
        super().__init__(seed=20260101, clock=lambda: FROZEN_NOW)
        self.quotes: list[Stamped] = []
        self.props: list[tuple[str, datetime | None, int, int]] = []
        #: When set, the time the score of every game in progress last changed.
        self.score_changed: datetime | None = None

    def next_event_for_team(self, team_id: str) -> Event | None:
        event = super().next_event_for_team(team_id)
        if event is not None and event.status == "live" and self.score_changed is not None:
            return event.model_copy(update={"score_updated_at": self.score_changed})
        return event

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]:
        return [
            OddsSnapshot(
                provider="test",
                provider_id=f"{event_id}:{book}",
                fetched_at=FROZEN_NOW,
                event_id=event_id,
                market=market,
                sportsbook_id=book,
                status=status,  # type: ignore[arg-type]
                last_updated=updated,
                outcomes=[
                    OddsOutcome(key="home", name="Home", price_american=prices[0]),
                    OddsOutcome(key="away", name="Away", price_american=prices[1]),
                ],
            )
            for book, status, updated, prices in self.quotes
        ]

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        event = self.next_event_for_team(self.get_player(player_id).team_id)  # type: ignore[union-attr]
        assert event is not None
        return [
            PropOffer(
                provider="test",
                provider_id=f"{player_id}:{book}",
                fetched_at=FROZEN_NOW,
                player_id=player_id,
                event_id=event.id,
                market=market or "points",
                sportsbook_id=book,
                status="open",
                last_updated=updated,
                line=20.5,
                over_american=over,
                under_american=under,
            )
            for book, updated, over, under in self.props
        ]


def ago(seconds: float) -> datetime:
    return FROZEN_NOW - timedelta(seconds=seconds)


@pytest.fixture
def stamped() -> StampedProvider:
    return StampedProvider()


@pytest.fixture
def board(stamped: StampedProvider) -> Board:
    return Board(stamped, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]


def flagged(odds) -> set[tuple[str, str]]:  # type: ignore[no-untyped-def]
    return {(b.sportsbook.key, o.key) for b in odds.books for o in b.outcomes if o.is_best}


def stale_books(odds) -> set[str]:  # type: ignore[no-untyped-def]
    return {b.sportsbook.key for b in odds.books if b.is_stale}


def live_event(provider: SyntheticProvider, changed_seconds_ago: float | None) -> Event:
    """A live event whose score last changed the given number of seconds ago."""
    event = provider.list_events(league="mlb", status="upcoming")[0]
    return event.model_copy(
        update={
            "status": "live",
            "score_updated_at": None if changed_seconds_ago is None else ago(changed_seconds_ago),
        }
    )


# ------------------------------------------------- missing and future timestamps
def test_a_quote_without_a_timestamp_is_stale(board: Board) -> None:
    assert board.is_stale(None, "upcoming") is True
    assert board.is_stale(None, "live") is True


def test_a_timestamp_from_the_future_is_stale_beyond_a_small_clock_skew(board: Board) -> None:
    assert board.is_stale(FROZEN_NOW + timedelta(hours=5), "upcoming") is True
    assert board.is_stale(FROZEN_NOW + timedelta(hours=5), "live") is True
    assert board.is_stale(FROZEN_NOW + timedelta(seconds=61), "upcoming") is True
    # A sportsbook clock a few seconds ahead of ours is normal.
    assert board.is_stale(FROZEN_NOW + timedelta(seconds=30), "upcoming") is False
    assert board.is_stale(FROZEN_NOW + timedelta(seconds=30), "live") is False
    assert board.is_stale(FROZEN_NOW, "live") is False
    assert board.is_stale(ago(121), "live") is True
    assert board.is_stale(ago(119), "live") is False


def test_untimed_and_future_quotes_are_never_best_and_never_in_the_consensus(
    stamped: StampedProvider, board: Board
) -> None:
    event = stamped.list_events(league="nba", status="upcoming")[0]
    stamped.quotes = [
        ("northline", "open", ago(60), (-150, 130)),
        ("cardinal", "open", ago(60), (-152, 128)),
        ("summit", "open", None, (300, 300)),  # far better, no timestamp
        ("kestrel", "open", FROZEN_NOW + timedelta(hours=5), (400, 400)),  # from the future
    ]
    odds = board.event_odds(event, "moneyline")
    assert stale_books(odds) == {"summit", "kestrel"}
    assert flagged(odds) == {("northline", "home"), ("northline", "away")}
    assert {b.sportsbook_key for b in odds.best} == {"northline"}
    assert odds.consensus.books_used == 2
    for side in ("home", "away"):
        best = board.best_price(event, "moneyline", side)
        assert best is not None and best.sportsbook.key == "northline"
    summary = board.event_summary(event)
    assert summary.best_moneyline.home.sportsbook.key == "northline"  # type: ignore[union-attr]
    assert summary.best_moneyline.away.sportsbook.key == "northline"  # type: ignore[union-attr]
    assert board._event_value_rows(event, "moneyline") == []


def test_untimed_prop_offers_are_stale_and_never_best(
    stamped: StampedProvider, board: Board
) -> None:
    player = stamped.list_players(league="nba")[0]
    stamped.props = [
        ("northline", ago(30), -115, -105),
        ("cardinal", ago(30), -110, -112),
        ("summit", None, 250, 250),
        ("kestrel", FROZEN_NOW + timedelta(hours=1), 300, 300),
    ]
    offers = {o.sportsbook.key: o for o in board.player_props(player, "points").offers}
    assert offers["summit"].is_stale and offers["kestrel"].is_stale
    assert [k for k, o in offers.items() if o.is_best_over] == ["cardinal"]
    assert [k for k, o in offers.items() if o.is_best_under] == ["northline"]


# ------------------------------------------------------- live: the score changed
def test_a_live_quote_from_before_the_latest_score_change_is_stale(board: Board) -> None:
    changed = ago(30)
    assert board.is_stale(ago(68), "live", changed) is True  # 68 s old, score changed 30 s ago
    assert board.is_stale(ago(8), "live", changed) is False
    assert board.is_stale(ago(30), "live", changed) is False  # requoted at the change itself
    assert board.is_stale(ago(68), "live", None) is False  # unknown: only the age rule applies
    # The score rule is about games in progress only.
    assert board.is_stale(ago(68), "upcoming", changed) is False


def test_the_audit_scenario_an_outdated_live_price_is_not_marked_best(
    stamped: StampedProvider, board: Board
) -> None:
    """Top of the ninth, the away side scored 30 s ago. One book has requoted; the others
    still show the price from before. Before the fix the old away price was marked best."""
    event = live_event(stamped, changed_seconds_ago=30)
    stamped.quotes = [
        ("summit", "open", ago(8), (460, -650)),
        ("northline", "open", ago(47), (-113, -105)),
        ("blueharbor", "open", ago(55), (-112, -106)),
        ("kestrel", "open", ago(68), (-116, -102)),
    ]
    odds = board.event_odds(event, "moneyline")
    assert stale_books(odds) == {"northline", "blueharbor", "kestrel"}
    assert flagged(odds) == {("summit", "home"), ("summit", "away")}
    assert {b.sportsbook_key for b in odds.best} == {"summit"}
    assert odds.consensus.books_used == 1
    away = board.best_price(event, "moneyline", "away")
    assert away is not None and away.sportsbook.key == "summit"
    assert float(away.price) == pytest.approx(1 + 100 / 650)
    best = board._best_moneyline(event)
    assert best is not None
    assert best.away.sportsbook.key == "summit"  # type: ignore[union-attr]
    assert best.away.price.american == -650  # type: ignore[union-attr]


def test_without_a_score_change_time_the_age_rule_still_applies(
    stamped: StampedProvider, board: Board
) -> None:
    event = live_event(stamped, changed_seconds_ago=None)
    stamped.quotes = [
        ("summit", "open", ago(8), (-110, -110)),
        ("northline", "open", ago(100), (-108, -112)),
        ("kestrel", "open", ago(300), (150, 150)),  # older than 120 s in play
    ]
    odds = board.event_odds(event, "moneyline")
    assert stale_books(odds) == {"kestrel"}
    assert flagged(odds) == {("northline", "home"), ("summit", "away")}


def test_live_prop_offers_follow_the_score_rule(stamped: StampedProvider) -> None:
    player = stamped.list_players(league="nba")[0]
    offers = [
        PropOffer(
            provider="test",
            provider_id=book,
            fetched_at=FROZEN_NOW,
            player_id=player.id,
            event_id="evt",
            market="points",
            sportsbook_id=book,
            status="open",
            last_updated=updated,
            line=20.5,
            over_american=over,
            under_american=-110,
        )
        for book, updated, over in (
            ("northline", ago(5), -110),
            ("cardinal", ago(6), -112),
            ("kestrel", ago(50), 180),
        )
    ]
    board = Board(stamped, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]
    rows, _, best_over, _ = board._prop_offers(offers, "live", ago(20))
    by_book = {row.sportsbook.key: row for row in rows}
    assert by_book["kestrel"].is_stale and not by_book["kestrel"].is_best_over
    assert best_over is not None and best_over.sportsbook.key == "northline"
    rows, _, best_over, _ = board._prop_offers(offers, "live", None)
    assert best_over is not None and best_over.sportsbook.key == "kestrel"


def test_the_public_prop_reads_use_the_score_change_time_of_the_players_game(
    stamped: StampedProvider, board: Board, make_app: AppFactory
) -> None:
    """``GET /v1/players/{id}/props`` and ``GET /v1/props`` in a game in progress: an offer
    made before the latest score change is stale and never the best price, although it is
    younger than the live age threshold."""
    live = stamped.list_events(league="nba", status="live")[0]
    player = next(p for p in stamped.list_players(league="nba") if p.team_id == live.home_team_id)
    assert "points" in player.prop_markets
    stamped.score_changed = ago(30)
    stamped.props = [
        ("northline", FROZEN_NOW, -115, -105),
        ("cardinal", FROZEN_NOW, -110, -112),
        ("kestrel", ago(40), 250, 250),  # far better, made 10 s before the score changed
    ]
    assert board.is_stale(ago(40), "live") is False  # by age alone it would be fresh

    def check_player(offers: dict[str, dict]) -> None:  # type: ignore[type-arg]
        assert offers["kestrel"]["is_stale"] is True
        assert not offers["kestrel"]["is_best_over"] and not offers["kestrel"]["is_best_under"]
        assert not offers["northline"]["is_stale"] and not offers["cardinal"]["is_stale"]
        assert [k for k, o in offers.items() if o["is_best_over"]] == ["cardinal"]
        assert [k for k, o in offers.items() if o["is_best_under"]] == ["northline"]

    def check_row(rows: list[dict]) -> None:  # type: ignore[type-arg]
        (row,) = [r for r in rows if r["player"]["id"] == player.id and r["market"] == "points"]
        assert row["event"]["id"] == live.id and row["event"]["status"] == "live"
        assert row["best_over"]["sportsbook"]["key"] == "cardinal"
        assert row["best_over"]["price"]["american"] == -110
        assert row["best_under"]["sportsbook"]["key"] == "northline"
        assert row["best_under"]["price"]["american"] == -105

    props = board.player_props(player, "points")
    assert props.next_event is not None and props.next_event.id == live.id
    check_player({o.sportsbook.key: o.model_dump(mode="json") for o in props.offers})
    check_row([r.model_dump(mode="json") for r in board.props_board("nba", "points")])

    with TestClient(make_app(provider=stamped)) as client:
        response = client.get(f"/v1/players/{player.id}/props", params={"market": "points"})
        assert response.status_code == 200, response.text
        check_player({o["sportsbook"]["key"]: o for o in response.json()["offers"]})
        for params in ({"league": "nba", "market": "points"}, {"league": "nba"}, {}):
            response = client.get("/v1/props", params=params)
            assert response.status_code == 200, response.text
            check_row(response.json())

    # Without a score change since the offer, the same offer is fresh and the best price.
    stamped.score_changed = ago(50)
    board.cache.clear()
    offers = {o.sportsbook.key: o for o in board.player_props(player, "points").offers}
    assert not offers["kestrel"].is_stale
    assert offers["kestrel"].is_best_over and offers["kestrel"].is_best_under
    (row,) = [
        r
        for r in board.props_board("nba", "points")
        if r.player.id == player.id and r.market == "points"
    ]
    assert row.best_over is not None and row.best_over.sportsbook.key == "kestrel"
    assert row.best_under is not None and row.best_under.sportsbook.key == "kestrel"


def test_synthetic_live_quotes_are_stale_only_until_the_book_requotes() -> None:
    """Every synthetic in-play quote the board calls fresh was made for the current score."""
    checked = stale = 0
    for minute in range(0, 180, 7):
        now = datetime(2026, 11, 19, 20, 0, tzinfo=UTC) + timedelta(minutes=minute, seconds=13)
        provider = SyntheticProvider(seed=20260101, clock=lambda now=now: now)
        board = Board(provider, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]
        for event in provider.list_events(status="live"):
            assert event.score_updated_at is not None
            assert event.start_time <= event.score_updated_at <= now
            for market in event.markets:
                odds = board.event_odds(event, market)
                snapshots = {s.sportsbook_id: s for s in provider.get_odds(event.id, market)}
                for book in odds.books:
                    if book.status == "unavailable":
                        continue
                    checked += 1
                    updated = snapshots[book.sportsbook.key].last_updated
                    assert updated is not None
                    if updated < event.score_updated_at:
                        stale += 1
                        assert book.is_stale
                        assert not any(o.is_best for o in book.outcomes)
                    elif book.sportsbook.key != "oldmill":
                        assert not book.is_stale
    assert checked > 500
    assert 0 < stale < checked / 2  # a book that has not requoted yet is the exception


# ------------------------------------------------------------- the value screen
@pytest.fixture
def world() -> ControlledProvider:
    return ControlledProvider()


@pytest.fixture
def app(make_app: AppFactory, world: ControlledProvider) -> FastAPI:
    return make_app(provider=world)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def discrepancy(world: ControlledProvider, event: Event) -> None:
    """One clear discrepancy on the event's moneyline and nothing else on its markets."""
    for market in event.markets:
        world.set_odds(event.id, market, [])
    world.set_odds(
        event.id,
        "moneyline",
        [
            ("northline", "open", 1.0, moneyline(460, -650)),
            ("cardinal", "open", 1.0, moneyline(-113, -105)),
            ("summit", "open", 1.0, moneyline(-112, -106)),
            ("kestrel", "open", 1.0, moneyline(-116, -102)),
        ],
    )


def value_rows(client: TestClient, **params: str) -> list[dict]:
    client.app.state.cache.clear()  # type: ignore[attr-defined]
    response = client.get("/v1/value", params={"limit": "200", **params})
    assert response.status_code == 200, response.text
    return response.json()["rows"]


def test_live_events_are_not_on_the_value_screen(
    client: TestClient, world: ControlledProvider
) -> None:
    live = world.list_events(status="live")
    assert live
    for event in live:
        discrepancy(world, event)
    upcoming = world.list_events(league="nba", status="upcoming")[0]
    discrepancy(world, upcoming)
    rows = value_rows(client)
    assert rows
    assert {row["event"]["status"] for row in rows} == {"upcoming"}
    listed = {row["event"]["id"] for row in rows}
    assert upcoming.id in listed
    assert not listed & {event.id for event in live}
    for league in {event.league for event in live}:
        assert {row["event"]["status"] for row in value_rows(client, league=league)} <= {"upcoming"}


def test_an_event_leaves_the_value_screen_when_it_starts(
    client: TestClient, world: ControlledProvider
) -> None:
    event = world.list_events(league="nba", status="upcoming")[0]
    discrepancy(world, event)
    assert [r for r in value_rows(client) if r["event"]["id"] == event.id]
    world.current = event.start_time + timedelta(minutes=10)
    assert world.get_event(event.id).status == "live"  # type: ignore[union-attr]
    assert [r for r in value_rows(client) if r["event"]["id"] == event.id] == []
    # The odds comparison of the live game is still there.
    odds = client.get(f"/v1/events/{event.id}/odds").json()
    assert odds["event"]["status"] == "live" and len(odds["books"]) == 4


@pytest.mark.parametrize("hour", [1, 9, 17, 22])
def test_the_synthetic_value_screen_has_no_live_row_at_any_time_of_day(hour: int) -> None:
    now = datetime(2026, 11, 19, hour, 49, tzinfo=UTC)
    provider = SyntheticProvider(seed=20260101, clock=lambda: now)
    assert provider.list_events(status="live")
    board = Board(provider, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]
    screen = board.value_screen(None, None, 0.0, 200)
    assert {row.event.status for row in screen.rows} <= {"upcoming"}
    # Without a game in progress on the screen, no synthetic row is far from its consensus.
    assert all(row.edge < 0.1 for row in screen.rows)


def test_the_method_and_the_routes_say_what_is_compared(client: TestClient) -> None:
    assert "upcoming" in VALUE_METHOD
    assert "in progress" in VALUE_METHOD
    schema = client.get("/openapi.json").json()
    value = schema["paths"]["/v1/value"]["get"]["description"]
    assert "upcoming events" in value and "live and upcoming" not in value
    assert "in progress" in value
    odds = schema["paths"]["/v1/events/{event_id}/odds"]["get"]["description"]
    for phrase in ("no timestamp", "future", "score"):
        assert phrase in odds, phrase
    stale = schema["components"]["schemas"]["BookOddsOut"]["properties"]["is_stale"]
    for phrase in ("stale_after_seconds", "no timestamp", "score"):
        assert phrase in stale["description"], phrase
    prop = schema["components"]["schemas"]["PropOfferOut"]["properties"]["is_stale"]
    assert "score" in prop["description"]


def test_spread_and_total_marks_follow_the_same_rule(world: ControlledProvider) -> None:
    board = Board(world, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]
    event = world.list_events(league="nba", status="upcoming")[0]
    live = event.model_copy(update={"status": "live", "score_updated_at": ago(20)})
    world.set_odds(
        event.id,
        "spread",
        [
            ("northline", "open", 5.0, spread(-3.5, -110, -110)),
            ("cardinal", "open", 6.0, spread(-3.5, -112, -108)),
            ("kestrel", "open", 40.0, spread(-3.5, 140, 140)),  # before the score change
        ],
    )
    world.set_odds(
        event.id,
        "total",
        [
            ("northline", "open", 5.0, total(220.5, -110, -110)),
            ("kestrel", "open", 40.0, total(220.5, 150, 150)),
        ],
    )
    for market in ("spread", "total"):
        odds = board.event_odds(live, market)
        assert stale_books(odds) == {"kestrel"}
        assert "kestrel" not in {book for book, _ in flagged(odds)}
        # Before the game the same 40-second-old quote is fresh and best.
        assert "kestrel" in {book for book, _ in flagged(board.event_odds(event, market))}
    assert board.best_price(live, "spread", "home", -3.5).sportsbook.key == "northline"  # type: ignore[union-attr]
    assert board.best_price(event, "spread", "home", -3.5).sportsbook.key == "kestrel"  # type: ignore[union-attr]
