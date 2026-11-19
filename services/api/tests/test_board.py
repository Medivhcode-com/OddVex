"""Best-price, staleness and consensus rules, exercised with hand-written quotes."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from oddvex_api.board import Board, consensus_line
from oddvex_api.cache import InMemoryTTLCache
from oddvex_api.config import Settings
from oddvex_api.providers import OddsOutcome, OddsSnapshot, PropOffer, SyntheticProvider

from .conftest import FROZEN_NOW

Quote = tuple[str, str, float, list[tuple[str, float | None, int]]]


class ScriptedProvider(SyntheticProvider):
    """Synthetic schedule, but odds and prop offers come from the test."""

    def __init__(self) -> None:
        super().__init__(seed=20260101, clock=lambda: FROZEN_NOW)
        self.quotes: list[Quote] = []
        self.props: list[tuple[str, str, float, float | None, int | None, int | None]] = []

    def _stamp(self, age: float) -> datetime:
        return FROZEN_NOW - timedelta(seconds=age)

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
                last_updated=None if status == "unavailable" else self._stamp(age),
                outcomes=[
                    OddsOutcome(key=key, name=key.title(), line=line, price_american=price)
                    for key, line, price in outcomes
                ],
            )
            for book, status, age, outcomes in self.quotes
        ]

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        event = self.next_event_for_team(self.get_player(player_id).team_id)  # type: ignore[union-attr]
        return [
            PropOffer(
                provider="test",
                provider_id=f"{player_id}:{book}",
                fetched_at=FROZEN_NOW,
                player_id=player_id,
                event_id=event.id,  # type: ignore[union-attr]
                market=market or "points",
                sportsbook_id=book,
                status=status,  # type: ignore[arg-type]
                last_updated=None if status == "unavailable" else self._stamp(age),
                line=line,
                over_american=over,
                under_american=under,
            )
            for book, status, age, line, over, under in self.props
        ]


@pytest.fixture
def scripted() -> ScriptedProvider:
    return ScriptedProvider()


@pytest.fixture
def board(scripted: ScriptedProvider) -> Board:
    return Board(scripted, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]


def ml(home: int, away: int) -> list[tuple[str, float | None, int]]:
    return [("home", None, home), ("away", None, away)]


def by_book(odds, key: str):  # type: ignore[no-untyped-def]
    return next(b for b in odds.books if b.sportsbook.key == key)


def best_books(odds) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {b.outcome_key: b.sportsbook_key for b in odds.best}


def flagged(odds) -> set[tuple[str, str]]:  # type: ignore[no-untyped-def]
    return {(b.sportsbook.key, o.key) for b in odds.books for o in b.outcomes if o.is_best}


def test_best_price_is_the_highest_among_open_fresh_books(
    scripted: ScriptedProvider, board: Board
) -> None:
    event = scripted.list_events(league="nba", status="upcoming")[0]
    scripted.quotes = [
        ("northline", "open", 60, ml(-150, 130)),
        ("cardinal", "open", 60, ml(-145, 125)),
        ("summit", "open", 60, ml(-155, 135)),
    ]
    odds = board.event_odds(event, "moneyline")
    assert best_books(odds) == {"home": "cardinal", "away": "summit"}
    assert flagged(odds) == {("cardinal", "home"), ("summit", "away")}
    assert odds.consensus.books_used == 3
    assert odds.consensus.line is None
    assert sum(o.no_vig_probability for o in odds.consensus.outcomes) == pytest.approx(
        1.0, abs=1e-5
    )
    assert {h.sportsbook_key for h in odds.holds} == {"northline", "cardinal", "summit"}
    assert all(0 < h.hold < 0.1 for h in odds.holds)


def test_stale_suspended_and_unavailable_books_are_never_best(
    scripted: ScriptedProvider, board: Board
) -> None:
    event = scripted.list_events(league="nba", status="upcoming")[0]
    scripted.quotes = [
        ("northline", "open", 60, ml(-150, 130)),
        ("cardinal", "open", 60, ml(-152, 128)),
        ("oldmill", "open", 2000, ml(+200, +200)),  # far better, but stale (> 15 min pre-game)
        ("summit", "suspended", 30, ml(+300, +300)),  # far better, but suspended
        ("kestrel", "unavailable", 0, []),
    ]
    odds = board.event_odds(event, "moneyline")
    assert best_books(odds) == {"home": "northline", "away": "northline"}
    assert flagged(odds) == {("northline", "home"), ("northline", "away")}
    assert by_book(odds, "oldmill").is_stale is True
    assert by_book(odds, "oldmill").status == "open"
    assert by_book(odds, "summit").status == "suspended"
    assert by_book(odds, "summit").is_stale is False
    assert by_book(odds, "kestrel").outcomes == []
    assert by_book(odds, "kestrel").last_updated is None
    assert odds.consensus.books_used == 2
    # The stale and suspended quotes are still shown, and still have a hold figure.
    assert {h.sportsbook_key for h in odds.holds} == {"northline", "cardinal", "oldmill", "summit"}
    summary = board.event_summary(event)
    assert summary.best_moneyline.home.sportsbook.key == "northline"  # type: ignore[union-attr]
    assert summary.best_moneyline.home.price.american == -150  # type: ignore[union-attr]
    assert summary.best_moneyline.draw is None  # type: ignore[union-attr]


def test_stale_threshold_is_tighter_for_live_events(
    scripted: ScriptedProvider, board: Board
) -> None:
    # This test is about the age threshold alone, so the live game reports no score-change
    # time. The rule for quotes made before a score change is tested in
    # test_audit_board_freshness.py.
    live = scripted.list_events(league="nba", status="live")[0].model_copy(
        update={"score_updated_at": None}
    )
    upcoming = scripted.list_events(league="nba", status="upcoming")[0]
    scripted.quotes = [
        ("northline", "open", 100, ml(-150, 130)),
        ("cardinal", "open", 300, ml(-140, 140)),  # stale live (> 120s), fresh pre-game (< 900s)
    ]
    live_odds = board.event_odds(live, "moneyline")
    assert live_odds.stale_after_seconds == 120
    assert by_book(live_odds, "cardinal").is_stale is True
    assert best_books(live_odds) == {"home": "northline", "away": "northline"}
    pre_odds = board.event_odds(upcoming, "moneyline")
    assert pre_odds.stale_after_seconds == 900
    assert by_book(pre_odds, "cardinal").is_stale is False
    assert best_books(pre_odds) == {"home": "cardinal", "away": "cardinal"}


def test_stale_thresholds_are_configurable(scripted: ScriptedProvider) -> None:
    event = scripted.list_events(league="nba", status="upcoming")[0]
    scripted.quotes = [
        ("northline", "open", 100, ml(-150, 130)),
        ("cardinal", "open", 50, ml(-160, 120)),
    ]
    strict = Board(scripted, Settings(_env_file=None, stale_pregame_seconds=60), InMemoryTTLCache())  # type: ignore[call-arg]
    odds = strict.event_odds(event, "moneyline")
    assert by_book(odds, "northline").is_stale is True
    assert best_books(odds) == {"home": "cardinal", "away": "cardinal"}


def test_spread_best_only_compares_books_on_the_consensus_line(
    scripted: ScriptedProvider, board: Board
) -> None:
    event = scripted.list_events(league="nba", status="upcoming")[0]

    def spread(line: float, home: int, away: int) -> list[tuple[str, float | None, int]]:
        return [("home", line, home), ("away", -line, away)]

    scripted.quotes = [
        ("northline", "open", 60, spread(-3.5, -110, -110)),
        ("cardinal", "open", 60, spread(-3.5, -108, -112)),
        ("summit", "open", 60, spread(-3.5, -112, -105)),
        ("kestrel", "open", 60, spread(-2.5, +150, +150)),  # different line: not comparable
        ("oldmill", "open", 5000, spread(-4.5, +400, +400)),  # stale: no vote on the line
    ]
    odds = board.event_odds(event, "spread")
    assert odds.consensus.line == -3.5
    assert odds.consensus.books_used == 3
    assert best_books(odds) == {"home": "cardinal", "away": "summit"}
    assert {b.line for b in odds.best} == {-3.5, 3.5}
    assert not any(book == "kestrel" for book, _ in flagged(odds))
    assert [o.line for o in by_book(odds, "kestrel").outcomes] == [-2.5, 2.5]


def test_total_consensus_and_tied_prices(scripted: ScriptedProvider, board: Board) -> None:
    event = scripted.list_events(league="nba", status="upcoming")[0]

    def total(line: float, over: int, under: int) -> list[tuple[str, float | None, int]]:
        return [("over", line, over), ("under", line, under)]

    scripted.quotes = [
        ("northline", "open", 60, total(224.5, -110, -110)),
        ("cardinal", "open", 60, total(224.5, -110, -108)),
        ("summit", "open", 60, total(225.5, -101, -101)),
    ]
    odds = board.event_odds(event, "total")
    assert odds.consensus.line == 224.5
    assert [o.key for o in odds.consensus.outcomes] == ["over", "under"]
    # Tied best prices are all flagged; `best` names the first book.
    assert flagged(odds) == {("northline", "over"), ("cardinal", "over"), ("cardinal", "under")}
    assert best_books(odds) == {"over": "northline", "under": "cardinal"}


def test_no_usable_books_means_no_best_and_empty_consensus(
    scripted: ScriptedProvider, board: Board
) -> None:
    event = scripted.list_events(league="nba", status="upcoming")[0]
    scripted.quotes = [
        ("oldmill", "open", 5000, ml(-150, 130)),
        ("summit", "suspended", 10, ml(-150, 130)),
    ]
    odds = board.event_odds(event, "moneyline")
    assert odds.best == []
    assert odds.consensus.outcomes == []
    assert odds.consensus.books_used == 0
    assert flagged(odds) == set()
    assert board.event_summary(event).best_moneyline is None


def test_closed_markets_are_reported_as_unavailable(
    scripted: ScriptedProvider, board: Board
) -> None:
    event = scripted.list_events(league="nba", status="final")[0]
    scripted.quotes = [("northline", "closed", 9000, ml(-150, 130))]
    odds = board.event_odds(event, "moneyline")
    assert by_book(odds, "northline").status == "unavailable"
    assert by_book(odds, "northline").outcomes == []
    assert odds.best == []
    assert board.event_summary(event).best_moneyline is None


def test_consensus_line_rules() -> None:
    assert consensus_line([]) is None
    assert consensus_line([3.5]) == 3.5
    assert consensus_line([3.5, 3.5, 4.5]) == 3.5
    assert consensus_line([2.5, 3.5, 4.5]) == 3.5  # all tied: nearest the median
    assert consensus_line([3.5, 4.5]) == 3.5  # still tied: the lower line
    assert consensus_line([-3.5, -3.5, -2.5, -2.5, -4.5]) == -3.5


def test_prop_best_flags_follow_the_same_rules(scripted: ScriptedProvider, board: Board) -> None:
    player = scripted.list_players(league="nba")[0]
    scripted.props = [
        ("northline", "open", 60, 20.5, -115, -105),
        ("cardinal", "open", 60, 20.5, -110, -112),
        ("summit", "open", 60, 21.5, +120, -150),  # other line
        ("oldmill", "open", 5000, 20.5, +200, +200),  # stale
        ("blueharbor", "suspended", 10, 20.5, +250, +250),
        ("kestrel", "unavailable", 0, None, None, None),
    ]
    props = board.player_props(player, "points", "10", "all")
    assert props.consensus_line == 20.5
    offers = {o.sportsbook.key: o for o in props.offers}
    assert [k for k, o in offers.items() if o.is_best_over] == ["cardinal"]
    assert [k for k, o in offers.items() if o.is_best_under] == ["northline"]
    assert offers["oldmill"].is_stale is True
    assert offers["kestrel"].line is None and offers["kestrel"].over is None
    assert props.hit_rate.line == 20.5
    assert props.hit_rate.line_source == "consensus"
    assert {entry.result for entry in props.game_log} <= {"over", "under", "push"}
    for entry in props.game_log:
        expected = "push" if entry.value == 20.5 else "over" if entry.value > 20.5 else "under"
        assert entry.result == expected


def test_props_fall_back_to_a_reference_line_when_nothing_is_offered(
    scripted: ScriptedProvider, board: Board
) -> None:
    player = scripted.list_players(league="nba")[0]
    scripted.props = [("kestrel", "unavailable", 0, None, None, None)]
    props = board.player_props(player, "points", "season", "all")
    assert props.consensus_line is None
    assert props.hit_rate.line_source == "season_median"
    assert props.hit_rate.line % 1 == 0.5
    assert props.hit_rate.pushes == 0
    assert props.hit_rate.sample_size == len(props.game_log) >= 25


# ------------------------------------------------ best price for one outcome
def test_single_outcome_best_price_matches_the_odds_endpoint_on_synthetic_data() -> None:
    """``Board.best_price`` (used by alerts) and ``event_odds`` share one implementation."""
    provider = SyntheticProvider(seed=20260101, clock=lambda: FROZEN_NOW)
    board = Board(provider, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]
    compared = 0
    for event in provider.list_events():
        for market in event.markets:
            odds = board.event_odds(event, market)
            keys = {o.key for book in odds.books for o in book.outcomes}
            for key in keys:
                expected = next((b for b in odds.best if b.outcome_key == key), None)
                line = expected.line if expected is not None else None
                if market != "moneyline" and expected is None:
                    continue
                found = board.best_price(event, market, key, line)
                if expected is None:
                    assert found is None
                    continue
                assert found is not None
                assert found.sportsbook.key == expected.sportsbook_key
                assert found.line == expected.line
                assert float(found.price) == pytest.approx(expected.price.decimal, abs=1e-4)
                compared += 1
            if event.status == "final":
                assert odds.best == []
                assert board.best_price(event, market, "home") is None
                assert board.consensus_outcome_line(event, market, "home") is None
    assert compared > 200


def test_single_outcome_best_price_ignores_unusable_books_and_other_lines(
    scripted: ScriptedProvider, board: Board
) -> None:
    event = scripted.list_events(league="nba", status="upcoming")[0]
    scripted.quotes = [
        ("oldmill", "open", 5000, ml(400, -500)),  # stale
        ("cardinal", "suspended", 60, ml(300, -400)),
        ("summit", "unavailable", 60, []),
        ("northline", "open", 60, ml(120, -140)),
        ("kestrel", "open", 60, ml(118, -135)),
    ]
    home = board.best_price(event, "moneyline", "home")
    away = board.best_price(event, "moneyline", "away")
    assert home is not None and away is not None
    assert (home.sportsbook.key, float(home.price)) == ("northline", 2.2)
    assert away.sportsbook.key == "kestrel" and home.line is None
    assert board.best_price(event, "moneyline", "draw") is None

    scripted.quotes = [
        ("northline", "open", 60, [("home", -3.5, 130), ("away", 3.5, -150)]),
        ("cardinal", "open", 60, [("home", -4.5, -108), ("away", 4.5, -112)]),
        ("summit", "open", 60, [("home", -4.5, -104), ("away", 4.5, -116)]),
        ("oldmill", "open", 5000, [("home", -4.5, 200), ("away", 4.5, -240)]),
    ]
    at_line = board.best_price(event, "spread", "home", -4.5)
    assert at_line is not None
    assert (at_line.sportsbook.key, at_line.line) == ("summit", -4.5)
    other_line = board.best_price(event, "spread", "home", -3.5)
    assert other_line is not None and other_line.sportsbook.key == "northline"
    away_side = board.best_price(event, "spread", "away", 4.5)
    assert away_side is not None and away_side.sportsbook.key == "cardinal"
    assert board.best_price(event, "spread", "home", -5.5) is None  # nobody quotes it
    assert board.best_price(event, "spread", "home", 4.5) is None  # that is the away line
    assert board.best_price(event, "spread", "home") is None  # a spread needs its line

    # The consensus line, per outcome. Two of three usable books are on -4.5.
    assert board.consensus_outcome_line(event, "spread", "home") == -4.5
    assert board.consensus_outcome_line(event, "spread", "away") == 4.5
    assert board.consensus_outcome_line(event, "spread", "over") is None
    assert board.consensus_outcome_line(event, "moneyline", "home") is None
    assert board.event_odds(event, "spread").consensus.line == -4.5
    scripted.quotes = [("oldmill", "open", 5000, [("home", -4.5, 200), ("away", 4.5, -240)])]
    assert board.consensus_outcome_line(event, "spread", "home") is None
