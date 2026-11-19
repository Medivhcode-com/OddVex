"""Synthetic results come from the same model that prices the markets (audit quant-data#4).

Over a long synthetic season every side of every market must win about as often as its
no-vig price says, before the start and in play. The check is a z-score per side:

    z = (wins - sum of priced probabilities) / sqrt(sum of p * (1 - p))

For a calibrated model z is close to a standard normal value. The tolerance is 4: with
the 58 statistics of one pre-start season sample, a calibrated model exceeds it by chance
in about one sample in 270, and the seed is fixed, so the result does not vary between
runs (the largest pre-start value on the fixed seed is 3.06, on baseball totals). A later
change to the generator draws a new sample: if one statistic then lands just above 4,
read the report in the failure message before blaming the change. With 600 games per
league the check sees a bias of about 9 points in one league's win rate and of about 4
points over all leagues together. The defect this test was written for was larger
than that: on the same sample it gave z = 8 on totals over all leagues and in soccer
(Overs won 69% against a price of 51%), 6.7 on hockey totals, 5.5 on the hockey home
moneyline and 4.6 on the home moneyline over all leagues.

Small biases are out of reach of any season statistic, so two further tests leave nothing
to chance: one checks game by game that the result is the scoring model's draw at the
rates the closing price quotes, with the overtime rule the pricing assumes, and one checks
the pricing formulas against a plain enumeration of every final score.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import pytest

from oddvex_api.providers import Event, SyntheticProvider
from oddvex_api.providers.synthetic import _LEAGUES, _Outlook, _points_pmf
from oddvex_api.quant import american_to_decimal, no_vig

LEAGUES = ("nba", "nfl", "mlb", "nhl", "soccer")
DURATION_HOURS = {"nba": 2.5, "nfl": 3.0, "mlb": 3.0, "nhl": 2.5, "soccer": 2.0}
SEASON_START = datetime(2026, 1, 1, tzinfo=UTC)
#: 150 days of 4 games a day: 600 games per league, 3,000 in all.
SEASON_DAYS = 150
Z_TOLERANCE = 4.0
BOOK = "northline"


class Clock:
    def __init__(self) -> None:
        self.now = SEASON_START

    def __call__(self) -> datetime:
        return self.now


class Tally:
    """Wins against priced probabilities for one side of one market."""

    def __init__(self) -> None:
        self.bets = 0
        self.wins = 0
        self.priced = 0.0
        self.variance = 0.0
        self.profit = 0.0

    def add(self, won: bool, probability: float, decimal_price: float) -> None:
        self.bets += 1
        self.wins += won
        self.priced += probability
        self.variance += probability * (1 - probability)
        self.profit += decimal_price - 1 if won else -1.0

    @property
    def z(self) -> float:
        return (self.wins - self.priced) / math.sqrt(self.variance)

    @property
    def roi(self) -> float:
        return self.profit / self.bets


def won(key: str, line: float | None, home: int, away: int) -> bool:
    if key == "home":
        return home + (line or 0.0) > away
    if key == "away":
        return away + (line or 0.0) > home
    if key == "draw":
        return home == away
    assert line is not None
    return home + away > line if key == "over" else home + away < line


def season(when: float | None, seed: int = 20260101) -> dict[tuple[str, str, str], Tally]:
    """Price every game of the season at one moment and settle it on its final score.

    ``when`` is ``None`` for five minutes before the start, otherwise the played fraction
    of the game. Only one book's open quotes are used, so no line shopping is involved,
    and a quote made before the latest score change is left out, as the board leaves it out.
    """
    clock = Clock()
    provider = SyntheticProvider(seed=seed, clock=clock)
    tallies: dict[tuple[str, str, str], Tally] = defaultdict(Tally)
    for league in LEAGUES:
        for offset in range(SEASON_DAYS):
            day = SEASON_START + timedelta(days=offset)
            for slot in range(4):
                event_id = f"evt_{league}_{day:%Y%m%d}_{slot}"
                clock.now = day
                event = provider.get_event(event_id)
                assert event is not None
                clock.now = event.start_time + timedelta(hours=5)
                final = provider.get_event(event_id)
                assert final is not None and final.status == "final" and final.score is not None
                if when is None:
                    clock.now = event.start_time - timedelta(minutes=5)
                else:
                    clock.now = event.start_time + timedelta(hours=DURATION_HOURS[league] * when)
                current = provider.get_event(event_id)
                assert current is not None
                _price_and_settle(provider, current, final, tallies)
    return tallies


def _price_and_settle(
    provider: SyntheticProvider,
    event: Event,
    final: Event,
    tallies: dict[tuple[str, str, str], Tally],
) -> None:
    assert final.score is not None
    for market in event.markets:
        for snapshot in provider.get_odds(event.id, market):
            if snapshot.sportsbook_id != BOOK or snapshot.status != "open":
                continue
            assert snapshot.last_updated is not None
            if event.score_updated_at and snapshot.last_updated < event.score_updated_at:
                continue  # quoted for an earlier score: stale, as the board treats it
            prices = [american_to_decimal(o.price_american) for o in snapshot.outcomes]
            fair = no_vig(prices).fair_probabilities
            favourite = max(range(len(fair)), key=lambda i: fair[i])
            for index, (outcome, probability, price) in enumerate(
                zip(snapshot.outcomes, fair, prices, strict=True)
            ):
                result = won(outcome.key, outcome.line, final.score.home, final.score.away)
                sides = [outcome.key]
                if market != "total":
                    sides.append("favourite" if index == favourite else "not_favourite")
                for side in sides:
                    for scope in (event.league, "all"):
                        tallies[(scope, market, side)].add(result, probability, float(price))


def _report(tallies: dict[tuple[str, str, str], Tally]) -> str:
    return "\n".join(
        f"{key}: n={t.bets} won={t.wins / t.bets:.3f} priced={t.priced / t.bets:.3f} "
        f"z={t.z:+.2f} roi={t.roi:+.3f}"
        for key, t in sorted(tallies.items())
    )


@pytest.fixture(scope="module")
def before_start() -> dict[tuple[str, str, str], Tally]:
    return season(None)


def test_every_side_wins_about_as_often_as_its_pre_start_price_says(
    before_start: dict[tuple[str, str, str], Tally],
) -> None:
    report = _report(before_start)
    # Every league has every side of its markets in the sample.
    for league in LEAGUES:
        assert before_start[(league, "moneyline", "home")].bets > 400, report
        assert before_start[(league, "total", "over")].bets > 400, report
    for key, tally in before_start.items():
        assert abs(tally.z) < Z_TOLERANCE, f"{key} is off by z={tally.z:+.2f}\n{report}"


def test_home_favourite_and_over_rates_match_their_prices_over_the_season(
    before_start: dict[tuple[str, str, str], Tally],
) -> None:
    """The three habits the audit named, over all 3,000 games.

    One standard deviation of a win rate over about 2,700 bets is about 1 point, so
    3 points is three standard deviations. The defect gave +4 (home) and +8 (Over).
    """
    for key in (
        ("all", "moneyline", "home"),
        ("all", "moneyline", "favourite"),
        ("all", "spread", "favourite"),
        ("all", "total", "over"),
    ):
        tally = before_start[key]
        assert tally.bets > 2000
        assert tally.wins / tally.bets == pytest.approx(tally.priced / tally.bets, abs=0.03), key


def test_no_flat_stake_habit_beats_the_margin(
    before_start: dict[tuple[str, str, str], Tally],
) -> None:
    """Backing one side of one market in every game, at one book's price, does not pay.

    The expected return is minus about half the book's margin (about -2% to -5%). Over
    2,000 or more bets one standard deviation of the return is about 2 points, so +3% is
    about three standard deviations above the expectation. Sides with fewer bets (the
    draw, quoted in one league only) are too noisy for this check and are covered by the
    z-scores above. The defect returned +11% on every Over and +4% on every home side.
    """
    checked = 0
    for (scope, market, side), tally in before_start.items():
        if scope == "all" and tally.bets >= 2000:
            checked += 1
            assert tally.roi < 0.03, (market, side, tally.roi)
    assert checked >= 10


@pytest.mark.parametrize("fraction", [0.25, 0.5, 0.8])
def test_in_play_prices_are_calibrated_too(fraction: float) -> None:
    """A price quoted during a game is the chance of the final result given the score."""
    tallies = season(fraction)
    report = _report(tallies)
    assert tallies[("all", "moneyline", "favourite")].bets > 1500, report
    for key, tally in tallies.items():
        if tally.bets >= 200:
            assert abs(tally.z) < Z_TOLERANCE, f"{key} is off by z={tally.z:+.2f}\n{report}"
    favourite = tallies[("all", "moneyline", "favourite")]
    assert favourite.wins / favourite.bets == pytest.approx(
        favourite.priced / favourite.bets, abs=0.03
    )


def test_another_seed_is_calibrated_as_well() -> None:
    tallies = season(None, seed=7)
    for key, tally in tallies.items():
        assert abs(tally.z) < Z_TOLERANCE, f"{key} is off by z={tally.z:+.2f}\n{_report(tallies)}"


@pytest.mark.parametrize("cfg", _LEAGUES, ids=lambda cfg: cfg.key)
def test_fair_prices_are_the_exact_probabilities_of_the_scoring_model(cfg) -> None:  # type: ignore[no-untyped-def]
    """Every pricing formula against a plain enumeration of all possible final scores.

    The enumeration applies the rules as stated: each side adds an independent number of
    points, and a game level after regulation in a league without draws is won by one
    more score, taken by the home side with chance ``share``.
    """
    rng = random.Random(cfg.key)
    overtime = None if cfg.has_draw else cfg.overtime_points
    step = cfg.scoring[0][0]
    worst = 0.0
    for _ in range(25):
        home_mean, away_mean = rng.uniform(0.02, 6.0), rng.uniform(0.02, 6.0)
        home_score, away_score = rng.randint(0, 5) * step, rng.randint(0, 5) * step
        share = rng.uniform(0.2, 0.8)
        home_pmf, away_pmf = _points_pmf(cfg, home_mean), _points_pmf(cfg, away_mean)
        assert sum(home_pmf) == pytest.approx(1.0, abs=1e-10)
        outlook = _Outlook(home_score, away_score, home_pmf, away_pmf, share, overtime)

        finals: dict[tuple[int, int], float] = defaultdict(float)
        for home_added, p in enumerate(home_pmf):
            for away_added, q in enumerate(away_pmf):
                home, away = home_score + home_added, away_score + away_added
                if overtime is not None and home == away:
                    finals[(home + overtime, away)] += p * q * share
                    finals[(home, away + overtime)] += p * q * (1 - share)
                else:
                    finals[(home, away)] += p * q

        def chance(test) -> float:  # type: ignore[no-untyped-def]
            return sum(p for (home, away), p in finals.items() if test(home, away))  # noqa: B023

        worst = max(worst, abs(outlook.home_win() - chance(lambda h, a: h > a)))
        worst = max(worst, abs(outlook.draw() - chance(lambda h, a: h == a)))
        for line in (k + 0.5 for k in range(-9, 9)):
            covers = chance(lambda h, a, line=line: h - a + line > 0)
            worst = max(worst, abs(outlook.home_covers(line) - covers))
        current = home_score + away_score
        for line in (current + k + 0.5 for k in range(0, int(home_mean + away_mean) + 12)):
            over = chance(lambda h, a, line=line: h + a > line)
            worst = max(worst, abs(outlook.over(line) - over))
    assert worst < 1e-9


def test_every_result_is_the_draw_of_the_priced_model_game_by_game() -> None:
    """Ties the result generator to the pricing rule without leaving anything to chance.

    The season statistics above only see large biases. Here every game is checked on its
    own: the rates it is played at are the expectation the last quote before the start
    uses; its regulation score is the scoring model's draw at exactly those rates; and in
    a league without draws a game level after regulation goes, by one overtime score, to
    the side picked with the chance the pricing gives the home side.
    """
    clock = Clock()
    provider = SyntheticProvider(seed=20260101, clock=clock)
    level_games = telling = 0
    for cfg in _LEAGUES:
        for offset in range(SEASON_DAYS):
            day = (SEASON_START + timedelta(days=offset)).date()
            clock.now = SEASON_START + timedelta(days=offset)
            for slot in range(4):
                core = provider._core(cfg, day, slot)
                closing = provider._state(core, core.start - timedelta(seconds=1))
                assert closing.status == "upcoming"
                assert (core.home_mean, core.away_mean) == (closing.home_mean, closing.away_mean)
                kick_off = provider._state(core, core.start)
                assert (kick_off.home_mean, kick_off.away_mean) == (core.home_mean, core.away_mean)

                home, away = (
                    sum(
                        count * points
                        for count, (points, _) in zip(
                            provider._play_counts(cfg, core.id, side, mean),
                            cfg.scoring,
                            strict=True,
                        )
                    )
                    for side, mean in (("h", closing.home_mean), ("a", closing.away_mean))
                )
                if home == away and not cfg.has_draw:
                    level_games += 1
                    share = closing.home_mean / (closing.home_mean + closing.away_mean)
                    assert core.home_share == share  # what the pricing uses for a level game
                    pick = provider._u("ot", core.id)
                    telling += (pick < share) != (pick < 0.5)
                    if pick < share:
                        home += cfg.overtime_points
                    else:
                        away += cfg.overtime_points
                clock.now = core.end + timedelta(hours=1)
                event = provider.get_event(core.id)
                assert event is not None and event.status == "final" and event.score is not None
                assert (event.score.home, event.score.away) == (home, away), core.id
    assert level_games > 150
    # Games in which an even coin would have picked the other side, so that rule would fail.
    assert telling > 0


@pytest.mark.parametrize("cfg", _LEAGUES, ids=lambda cfg: cfg.key)
def test_drawn_regulation_points_follow_the_distribution_the_prices_use(cfg) -> None:  # type: ignore[no-untyped-def]
    """The result generator draws a side's regulation points; the prices use ``_points_pmf``
    for the same quantity. Over many draws the two must agree: the largest gap between the
    drawn and the priced cumulative distribution stays under the Kolmogorov bound
    1.95 / sqrt(n), which a correct sampler exceeds less than once in a thousand samples
    (the sample is fixed by the seed, so the result does not vary)."""
    provider = SyntheticProvider(seed=20260101, clock=Clock())
    draws = 4000
    for mean in (cfg.total_mean / 2, cfg.total_mean / 3):
        pmf = _points_pmf(cfg, mean)
        counts = [0] * len(pmf)
        for index in range(draws):
            plays = provider._play_counts(cfg, f"sample-{mean}-{index}", "h", mean)
            points = sum(n * worth for n, (worth, _) in zip(plays, cfg.scoring, strict=True))
            counts[points] += 1
        assert sum(n * k for k, n in enumerate(counts)) / draws == pytest.approx(
            mean, abs=4 * math.sqrt(sum(p * (k - mean) ** 2 for k, p in enumerate(pmf)) / draws)
        )
        gap = drawn = priced = 0.0
        for count, probability in zip(counts, pmf, strict=True):
            drawn += count / draws
            priced += probability
            gap = max(gap, abs(drawn - priced))
        assert gap < 1.95 / math.sqrt(draws), (cfg.key, mean, gap)


def test_final_scores_are_whole_non_negative_and_only_soccer_draws() -> None:
    clock = Clock()
    provider = SyntheticProvider(seed=20260101, clock=clock)
    draws = 0
    for league in LEAGUES:
        for offset in range(60):
            day = SEASON_START + timedelta(days=offset)
            clock.now = day + timedelta(days=2)
            for slot in range(4):
                event = provider.get_event(f"evt_{league}_{day:%Y%m%d}_{slot}")
                assert event is not None and event.score is not None
                assert event.score.home >= 0 and event.score.away >= 0
                if event.score.home == event.score.away:
                    assert league == "soccer"
                    draws += 1
    assert draws > 20


def test_the_score_never_goes_down_during_a_game() -> None:
    clock = Clock()
    provider = SyntheticProvider(seed=20260101, clock=clock)
    for league in LEAGUES:
        event_id = f"evt_{league}_20260310_1"
        clock.now = SEASON_START + timedelta(days=60)
        start = provider.get_event(event_id).start_time  # type: ignore[union-attr]
        previous = (0, 0)
        for step in range(1, 60):
            clock.now = start + timedelta(hours=DURATION_HOURS[league] * step / 60)
            event = provider.get_event(event_id)
            assert event is not None and event.status == "live" and event.score is not None
            assert event.score.home >= previous[0] and event.score.away >= previous[1]
            previous = (event.score.home, event.score.away)
        clock.now = start + timedelta(hours=DURATION_HOURS[league])
        final = provider.get_event(event_id)
        assert final is not None and final.status == "final" and final.score is not None
        assert final.score.home >= previous[0] and final.score.away >= previous[1]
