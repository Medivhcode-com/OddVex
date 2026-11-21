"""The synthetic provider: fictional, deterministic, clock-relative."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest

from oddvex_api.providers import SportsDataProvider, SyntheticProvider
from oddvex_api.quant import american_to_decimal, no_vig

from .conftest import FROZEN_NOW

# A sample of real organisations and brands that must never appear in synthetic data.
REAL_NAMES = (
    "lakers", "celtics", "warriors", "knicks", "bulls", "heat", "cowboys", "patriots", "chiefs",
    "packers", "eagles", "yankees", "dodgers", "red sox", "cubs", "maple leafs", "bruins",
    "canadiens", "manchester", "liverpool", "arsenal", "chelsea", "barcelona", "real madrid",
    "draftkings", "fanduel", "betmgm", "caesars", "bet365", "pinnacle", "espn", "fanatics",
    "pointsbet", "bovada", "lebron", "curry", "mahomes", "ohtani", "mcdavid", "messi",
)  # fmt: skip


def at(moment: datetime) -> SyntheticProvider:
    return SyntheticProvider(seed=20260101, clock=lambda: moment)


def test_implements_the_provider_protocol(provider: SyntheticProvider) -> None:
    assert isinstance(provider, SportsDataProvider)
    assert provider.data_mode == "synthetic"
    assert provider.health().status == "ok"


def test_leagues_and_books(provider: SyntheticProvider) -> None:
    leagues = {league.key: league for league in provider.list_leagues()}
    assert set(leagues) == {"nba", "nfl", "mlb", "nhl", "soccer"}
    assert leagues["soccer"].has_draw is True
    assert not any(leagues[key].has_draw for key in ("nba", "nfl", "mlb", "nhl"))
    assert len(provider.list_sportsbooks()) == 6
    assert len({book.key for book in provider.list_sportsbooks()}) == 6


def test_every_name_is_fictional(provider: SyntheticProvider) -> None:
    names = [team.name for team in provider.list_teams()]
    names += [player.name for player in provider.list_players()]
    names += [book.name for book in provider.list_sportsbooks()]
    names += [league.name for league in provider.list_leagues()]
    haystack = " | ".join(names).lower()
    for real in REAL_NAMES:
        assert real not in haystack, real
    assert all("synthetic" in league.name.lower() for league in provider.list_leagues())


def test_records_carry_provenance(provider: SyntheticProvider) -> None:
    event = provider.list_events()[0]
    snapshot = provider.get_odds(event.id, "moneyline")[0]
    player = provider.list_players()[0]
    log = provider.get_player_game_log(player.id)[0]
    offer = provider.get_prop_offers(player.id)[0]
    for record in (event, snapshot, player, log, offer, provider.list_leagues()[0]):
        assert record.provider == "synthetic"
        assert record.provider_id.startswith("syn:")
        assert record.fetched_at.tzinfo is not None


def test_same_seed_and_clock_give_identical_data() -> None:
    first, second = at(FROZEN_NOW), at(FROZEN_NOW)
    assert first.list_events() == second.list_events()
    event = first.list_events(status="upcoming")[0]
    assert first.get_odds(event.id, "total") == second.get_odds(event.id, "total")
    assert first.get_line_history(event.id, "moneyline") == second.get_line_history(
        event.id, "moneyline"
    )
    player = first.list_players()[5]
    assert first.get_player_game_log(player.id) == second.get_player_game_log(player.id)
    assert first.get_prop_offers(player.id) == second.get_prop_offers(player.id)


def test_a_different_seed_gives_different_data() -> None:
    other = SyntheticProvider(seed=7, clock=lambda: FROZEN_NOW)
    base = at(FROZEN_NOW)
    assert [e.home_team_id for e in other.list_events()] != [
        e.home_team_id for e in base.list_events()
    ]


@pytest.mark.parametrize("hour", range(0, 24))
def test_there_are_always_live_upcoming_and_final_events(hour: int) -> None:
    moment = datetime(2026, 7, 4, hour, 17, tzinfo=UTC)
    counts = Counter(event.status for event in at(moment).list_events())
    assert counts["live"] >= 1
    assert counts["upcoming"] >= 20
    assert counts["final"] >= 20


def test_schedule_follows_the_clock() -> None:
    early = at(FROZEN_NOW)
    live = early.list_events(status="live")[0]
    later = at(FROZEN_NOW + timedelta(hours=6))
    assert later.get_event(live.id).status == "final"  # type: ignore[union-attr]
    assert later.get_event(live.id).score is not None  # type: ignore[union-attr]
    upcoming = early.list_events(status="upcoming")[0]
    assert upcoming.score is None
    assert upcoming.start_time > FROZEN_NOW


def test_event_filters(provider: SyntheticProvider) -> None:
    assert {e.league for e in provider.list_events(league="nhl")} == {"nhl"}
    day = FROZEN_NOW.date()
    todays = provider.list_events(on_date=day)
    assert len(todays) == 20
    assert {e.start_time.date() for e in todays} == {day}
    assert provider.list_events(on_date=day + timedelta(days=365)) == []
    starts = [e.start_time for e in provider.list_events()]
    assert starts == sorted(starts)


def test_unknown_ids_return_nothing(provider: SyntheticProvider) -> None:
    assert provider.get_event("evt_nba_20260314_9") is None
    assert provider.get_event("garbage") is None
    assert provider.get_event("evt_xyz_20260314_0") is None
    assert provider.get_player("nobody") is None
    assert provider.get_odds("garbage", "moneyline") == []
    assert provider.get_player_game_log("nobody") == []
    assert provider.get_prop_offers("nobody") == []


def test_soccer_moneyline_is_three_way_and_has_no_spread(provider: SyntheticProvider) -> None:
    event = provider.list_events(league="soccer", status="upcoming")[0]
    assert event.markets == ["moneyline", "total"]
    priced = [s for s in provider.get_odds(event.id, "moneyline") if s.outcomes]
    assert priced
    for snapshot in priced:
        assert [o.key for o in snapshot.outcomes] == ["home", "draw", "away"]
    assert provider.get_odds(event.id, "spread") == []


def test_two_way_markets_have_sensible_prices_and_lines(provider: SyntheticProvider) -> None:
    event = provider.list_events(league="nba", status="upcoming")[0]
    for market, keys in (
        ("moneyline", ["home", "away"]),
        ("spread", ["home", "away"]),
        ("total", ["over", "under"]),
    ):
        snapshots = provider.get_odds(event.id, market)
        assert len(snapshots) == 6
        for snapshot in snapshots:
            if not snapshot.outcomes:
                assert snapshot.status == "unavailable"
                continue
            assert [o.key for o in snapshot.outcomes] == keys
            hold = no_vig([american_to_decimal(o.price_american) for o in snapshot.outcomes]).hold
            assert 0.0 < hold < 0.12
            if market == "moneyline":
                assert all(o.line is None for o in snapshot.outcomes)
            elif market == "spread":
                assert snapshot.outcomes[0].line == -snapshot.outcomes[1].line  # type: ignore[operator]
            else:
                assert snapshot.outcomes[0].line == snapshot.outcomes[1].line


def test_some_books_are_suspended_or_unavailable_and_one_is_stale(
    provider: SyntheticProvider,
) -> None:
    statuses: Counter[str] = Counter()
    ages: dict[str, list[float]] = {}
    for event in provider.list_events(status="upcoming")[:40]:
        for market in event.markets:
            for snapshot in provider.get_odds(event.id, market):
                statuses[snapshot.status] += 1
                if snapshot.last_updated is not None:
                    ages.setdefault(snapshot.sportsbook_id, []).append(
                        (FROZEN_NOW - snapshot.last_updated).total_seconds()
                    )
    assert statuses["open"] > statuses["suspended"] > 0
    assert statuses["unavailable"] > 0
    assert min(ages["oldmill"]) > 900  # the intentionally stale book
    for book, values in ages.items():
        if book != "oldmill":
            assert max(values) < 900, book


def test_a_live_event_reports_when_its_score_last_changed() -> None:
    seen = 0
    for minute in range(0, 600, 37):
        now = FROZEN_NOW + timedelta(minutes=minute)
        provider = at(now)
        for event in provider.list_events():
            if event.status != "live":
                assert event.score_updated_at is None
                continue
            seen += 1
            assert event.score_updated_at is not None
            assert event.start_time <= event.score_updated_at <= now
            if event.score == (0, 0) or (event.score.home, event.score.away) == (0, 0):  # type: ignore[union-attr]
                assert event.score_updated_at == event.start_time  # the start counts
            # A moment before the change the score was different (or the game had not begun).
            earlier = at(event.score_updated_at - timedelta(seconds=1)).get_event(event.id)
            assert earlier is not None
            assert earlier.status == "upcoming" or earlier.score != event.score
    assert seen > 30


def test_in_play_quotes_are_a_few_seconds_old_or_from_before_the_last_score_change() -> None:
    fresh = waiting = 0
    for minute in range(0, 600, 5):
        now = FROZEN_NOW + timedelta(minutes=minute, seconds=11)
        provider = at(now)
        for event in provider.list_events(status="live"):
            assert event.score_updated_at is not None
            for market in event.markets:
                for snapshot in provider.get_odds(event.id, market):
                    if snapshot.last_updated is None or snapshot.sportsbook_id == "oldmill":
                        continue
                    if snapshot.last_updated >= event.score_updated_at:
                        fresh += 1
                        assert (now - snapshot.last_updated).total_seconds() <= 3.0
                    else:
                        waiting += 1  # the book has not requoted since the score changed
                        assert (now - event.score_updated_at).total_seconds() <= 6.0
    assert fresh > 2000 and 0 < waiting < fresh / 4


def test_a_market_that_is_all_but_decided_is_suspended_not_open() -> None:
    """Past 98% the price grid could not stay at or below the fair price."""
    decided = 0
    for minute in range(0, 900, 23):
        provider = at(FROZEN_NOW + timedelta(minutes=minute))
        for event in provider.list_events(status="live"):
            for market in event.markets:
                for snapshot in provider.get_odds(event.id, market):
                    if not snapshot.outcomes:
                        continue
                    fair = no_vig(
                        [american_to_decimal(o.price_american) for o in snapshot.outcomes]
                    ).fair_probabilities
                    if snapshot.status == "open":
                        # 98% fair, plus the book's noise and the rounding of the price.
                        assert max(fair) < 0.985, (event.id, market, snapshot.sportsbook_id)
                    elif max(fair) > 0.975:
                        decided += 1
    assert decided > 20


def test_final_events_are_closed(provider: SyntheticProvider) -> None:
    event = provider.list_events(status="final")[0]
    assert {s.status for s in provider.get_odds(event.id, "moneyline")} <= {"closed", "unavailable"}


def test_line_history_covers_about_48_hours(provider: SyntheticProvider) -> None:
    event = provider.list_events(league="nfl", status="upcoming")[0]
    series = provider.get_line_history(event.id, "spread")
    assert series
    for line in series:
        stamps = [point.timestamp for point in line.points]
        assert stamps == sorted(stamps)
        assert len(stamps) >= 40
        span = stamps[-1] - stamps[0]
        assert timedelta(hours=44) <= span <= timedelta(hours=48)
        assert stamps[-1] <= FROZEN_NOW
        assert all(point.line is not None for point in line.points)
    assert {s.outcome_key for s in series} == {"home", "away"}


def test_every_player_has_at_least_25_game_logs(provider: SyntheticProvider) -> None:
    players = provider.list_players()
    assert len(players) == 160
    for player in players:
        log = provider.get_player_game_log(player.id)
        assert len(log) >= 25
        times = [entry.game_time for entry in log]
        assert times == sorted(times, reverse=True)
        assert all(entry.game_time < FROZEN_NOW for entry in log)
        assert all(set(entry.stats) == set(player.prop_markets) for entry in log)
        assert all(value >= 0 for entry in log for value in entry.stats.values())
        assert {entry.is_home for entry in log} == {True, False}
    assert len(provider.get_player_game_log(players[0].id, limit=5)) == 5


def test_player_search(provider: SyntheticProvider) -> None:
    target = provider.list_players(league="mlb")[0]
    last_name = target.name.split()[-1]
    found = provider.list_players(query=last_name.upper())
    assert target in found
    assert all(last_name.lower() in p.name.lower() for p in found)
    assert provider.list_players(query="zzzzzz") == []
    assert {p.team_id for p in provider.list_players(team_id=target.team_id)} == {target.team_id}


def test_prop_offers(provider: SyntheticProvider) -> None:
    player = provider.list_players(league="nba")[0]
    offers = provider.get_prop_offers(player.id, "points")
    assert len(offers) == 6
    assert {o.market for o in offers} == {"points"}
    for offer in offers:
        if offer.status == "unavailable":
            assert offer.line is None and offer.over_american is None
        else:
            assert offer.line is not None and offer.line % 1 == 0.5
            assert offer.over_american is not None and offer.under_american is not None
    assert {o.market for o in provider.get_prop_offers(player.id)} == set(player.prop_markets)
    next_event = provider.next_event_for_team(player.team_id)
    assert next_event is not None and next_event.status in ("live", "upcoming")
    assert {o.event_id for o in offers} == {next_event.id}
