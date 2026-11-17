"""Replay provider: real history shifted in time, with simulated books. Fixture is fictional."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from oddvex_api.providers import ReplayProvider, SportsDataProvider
from oddvex_api.providers.replay import ReplayDataError, load_replay_dataset
from oddvex_api.quant import american_to_decimal

from .replay_support import QB, ROOKIE, SHIFT_DAYS, WR, replay_dataset, shifted

QB_ID, WR_ID, ROOKIE_ID = "plr_nfl_pqb", "plr_nfl_pwr", "plr_nfl_prookie"
WEEK4 = "evt_nfl_2024_04_hct_rvr"


def at(moment: datetime) -> ReplayProvider:
    return ReplayProvider(replay_dataset(), shift_days=SHIFT_DAYS, clock=lambda: moment)


def test_implements_the_provider_protocol_and_labels_itself() -> None:
    provider = at(shifted(4, -2))
    assert isinstance(provider, SportsDataProvider)
    assert (provider.name, provider.data_mode) == ("replay", "replay")
    assert "simulated" in provider.notice and "real" in provider.notice
    assert provider.attribution == "Test fixture: fictional teams and players."
    health = provider.health()
    assert (health.status, health.data_mode) == ("ok", "replay")
    assert "12 games" in health.detail


def test_reference_data() -> None:
    provider = at(shifted(4, -2))
    (league,) = provider.list_leagues()
    assert (league.key, league.has_draw) == ("nfl", False)
    assert league.markets == ["moneyline", "spread", "total"]
    assert league.prop_markets == [
        "passing_yards",
        "rushing_yards",
        "receiving_yards",
        "receptions",
    ]
    assert provider.list_leagues()[0].provider == "replay"
    assert {t.abbreviation for t in provider.list_teams("nfl")} == {"HCT", "RVR", "MSA", "GLD"}
    assert provider.list_teams("nba") == []
    assert provider.get_team("team_nfl_hct").name == "Harbor City Tides"  # type: ignore[union-attr]
    assert len(provider.list_sportsbooks()) == 6
    # A player without a single stat line is not listed.
    assert {p.id for p in provider.list_players()} == {QB_ID, WR_ID, ROOKIE_ID}
    assert [p.id for p in provider.list_players(query="varrow")] == [QB_ID]
    assert provider.list_players(league="nba") == []
    assert provider.get_player("plr_nfl_pghost") is None
    assert QB and WR and ROOKIE


def test_games_are_shifted_by_whole_weeks_and_statuses_follow_the_clock() -> None:
    before = at(shifted(4, -2))
    event = before.get_event(WEEK4)
    assert event is not None
    assert event.start_time == shifted(4)
    assert event.start_time.weekday() == 6  # still a Sunday
    assert (event.status, event.score, event.period_text) == ("upcoming", None, None)

    live = at(shifted(4, 1)).get_event(WEEK4)
    # The source has no in-play data: no score is invented for a game in progress.
    assert (live.status, live.score, live.period_text) == ("live", None, "In progress")  # type: ignore[union-attr]

    final = at(shifted(4, 4)).get_event(WEEK4)
    assert final.status == "final"  # type: ignore[union-attr]
    assert (final.score.home, final.score.away) == (24, 17)  # type: ignore[union-attr]
    assert before.get_event("evt_nfl_nope") is None


def test_shift_must_be_whole_weeks() -> None:
    with pytest.raises(ReplayDataError, match="whole number of weeks"):
        ReplayProvider(replay_dataset(), shift_days=10)


def test_list_events_window_filters_and_order() -> None:
    provider = at(shifted(4, -2))
    events = provider.list_events()
    # 4 days back and 7 ahead: week 4 (today) and week 5 (in 7 days), not week 3.
    assert [e.id for e in events] == [
        "evt_nfl_2024_04_hct_rvr",
        "evt_nfl_2024_04_msa_gld",
        "evt_nfl_2024_05_rvr_hct",
        "evt_nfl_2024_05_gld_msa",
    ]
    assert provider.list_events(league="nba") == []
    assert provider.list_events(status="final") == []
    assert len(provider.list_events(on_date=shifted(3).date())) == 2
    assert [e.status for e in provider.list_events(on_date=shifted(3).date())] == ["final"] * 2


def test_closing_line_is_the_recorded_one_and_books_add_a_margin() -> None:
    provider = at(shifted(4, -2))
    spread = [s for s in provider.get_odds(WEEK4, "spread") if s.outcomes]
    assert spread
    for snapshot in spread:
        assert [(o.key, o.line) for o in snapshot.outcomes] == [("home", -3.0), ("away", 3.0)]
        implied = sum(1 / float(american_to_decimal(o.price_american)) for o in snapshot.outcomes)
        assert 1.02 < implied < 1.08
    totals = [s for s in provider.get_odds(WEEK4, "total") if s.outcomes]
    assert {o.line for s in totals for o in s.outcomes} == {44.5}
    moneyline = [s for s in provider.get_odds(WEEK4, "moneyline") if s.status == "open"]
    assert all(s.outcomes[0].price_american < 0 < s.outcomes[1].price_american for s in moneyline)
    assert all(s.provider == "replay" for s in moneyline)
    assert provider.get_odds(WEEK4, "nope") == []
    assert provider.get_odds("evt_nfl_nope", "moneyline") == []


def test_missing_market_is_not_offered() -> None:
    provider = at(shifted(6, -2))
    event = provider.get_event("evt_nfl_2024_06_hct_rvr")
    assert event.markets == ["moneyline", "spread"]  # type: ignore[union-attr]
    assert provider.get_odds("evt_nfl_2024_06_hct_rvr", "total") == []
    assert provider.get_line_history("evt_nfl_2024_06_hct_rvr", "total") == []


def test_no_open_prices_once_the_game_has_started() -> None:
    for hours in (1, 5):
        statuses = {s.status for s in at(shifted(4, hours)).get_odds(WEEK4, "moneyline")}
        assert statuses <= {"closed", "unavailable"}
    closed = [s for s in at(shifted(4, 5)).get_odds(WEEK4, "moneyline") if s.status == "closed"]
    assert closed and all(s.last_updated == shifted(4) for s in closed)


def test_line_history_ends_at_the_close_and_never_after_kickoff() -> None:
    upcoming = at(shifted(4, -2)).get_line_history(WEEK4, "moneyline")
    assert upcoming
    assert all(p.timestamp < shifted(4) for s in upcoming for p in s.points)
    assert all(len(s.points) >= 40 for s in upcoming if s.sportsbook_id != "oldmill")
    final = at(shifted(4, 30)).get_line_history(WEEK4, "moneyline")
    assert {s.points[-1].timestamp for s in final} == {shifted(4) - timedelta(seconds=1)}


def test_results_and_stats_are_never_revealed_early() -> None:
    provider = at(shifted(4, 1))  # week 4 is in progress
    log = provider.get_player_game_log(QB_ID)
    assert [e.event_id for e in log] == [
        "evt_nfl_2024_03_rvr_hct",
        "evt_nfl_2024_02_hct_rvr",
        "evt_nfl_2024_01_rvr_hct",
    ]
    assert log[0].stats == {"passing_yards": 230.0, "rushing_yards": 13.0}
    assert (log[0].is_home, log[0].opponent_team_id) == (True, "team_nfl_rvr")
    assert (log[1].is_home, log[1].opponent_team_id) == (False, "team_nfl_rvr")
    assert len(provider.get_player_game_log(QB_ID, limit=1)) == 1
    assert provider.get_player_game_log("plr_nfl_nope") == []
    after = at(shifted(4, 4)).get_player_game_log(QB_ID)
    assert after[0].event_id == WEEK4


def test_player_team_follows_the_season() -> None:
    assert at(shifted(3, 1)).get_player(WR_ID).team_id == "team_nfl_hct"  # type: ignore[union-attr]
    assert at(shifted(4, 1)).get_player(WR_ID).team_id == "team_nfl_rvr"  # type: ignore[union-attr]
    # Before a player's first game they are listed with their first team.
    assert at(shifted(1, -5)).get_player(ROOKIE_ID).team_id == "team_nfl_rvr"  # type: ignore[union-attr]
    names = {p.id for p in at(shifted(4, 1)).list_players(team_id="team_nfl_rvr")}
    assert names == {WR_ID, ROOKIE_ID}


def test_next_event_for_team() -> None:
    provider = at(shifted(4, 1))
    assert provider.next_event_for_team("team_nfl_hct").id == WEEK4  # type: ignore[union-attr]
    assert at(shifted(4, 4)).next_event_for_team("team_nfl_hct").id == "evt_nfl_2024_05_rvr_hct"  # type: ignore[union-attr]
    assert at(shifted(6, 4)).next_event_for_team("team_nfl_hct") is None  # season over
    assert at(shifted(1, -24 * 30)).next_event_for_team("team_nfl_hct") is None  # too far ahead
    assert provider.next_event_for_team("team_nfl_nope") is None


def test_prop_lines_use_only_games_before_the_one_priced() -> None:
    provider = at(shifted(4, -2))
    offers = [o for o in provider.get_prop_offers(QB_ID, "passing_yards") if o.line is not None]
    assert offers and {o.event_id for o in offers} == {WEEK4}
    # Weeks 1-3 were 210, 220, 230: the base line is the half point at their mean (220.5),
    # and a book may sit one point either side. Week 4 itself (240) is not used.
    assert {o.line for o in offers} <= {219.5, 220.5, 221.5}
    assert all(o.over_american and o.under_american for o in offers)
    markets = {o.market for o in provider.get_prop_offers(QB_ID)}
    assert markets == {"passing_yards", "rushing_yards"}
    assert provider.get_prop_offers("plr_nfl_nope") == []


def test_no_prop_without_enough_history_or_without_a_next_game() -> None:
    # Week 2: only one earlier game. Week 5: the rookie's first appearance.
    assert at(shifted(2, -2)).get_prop_offers(QB_ID) == []
    assert at(shifted(5, -2)).get_prop_offers(ROOKIE_ID) == []
    assert at(shifted(6, 4)).get_prop_offers(QB_ID) == []
    started = at(shifted(4, 1)).get_prop_offers(QB_ID)
    assert started and {o.status for o in started} <= {"closed", "unavailable"}


def test_deterministic_for_a_seed_and_clock() -> None:
    first, second = at(shifted(4, -2)), at(shifted(4, -2))
    assert first.get_odds(WEEK4, "moneyline") == second.get_odds(WEEK4, "moneyline")
    assert first.get_prop_offers(QB_ID) == second.get_prop_offers(QB_ID)


def test_load_replay_dataset(tmp_path: Path) -> None:
    good = tmp_path / "ok.json"
    good.write_text(json.dumps(replay_dataset()), encoding="utf-8")
    assert load_replay_dataset(good)["season"] == 2024

    with pytest.raises(ReplayDataError, match="build_replay_data"):
        load_replay_dataset(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ReplayDataError, match="could not be read"):
        load_replay_dataset(broken)
    old = tmp_path / "old.json"
    old.write_text(json.dumps({**replay_dataset(), "format_version": 0}), encoding="utf-8")
    with pytest.raises(ReplayDataError, match="format_version"):
        load_replay_dataset(old)
    partial = replay_dataset()
    del partial["stats"]
    (tmp_path / "partial.json").write_text(json.dumps(partial), encoding="utf-8")
    with pytest.raises(ReplayDataError, match="'stats'"):
        load_replay_dataset(tmp_path / "partial.json")


def test_malformed_dataset_is_reported_as_a_data_error() -> None:
    dataset = replay_dataset()
    dataset["games"][0]["home"] = "ZZZ"
    with pytest.raises(ReplayDataError, match="malformed"):
        ReplayProvider(dataset)
