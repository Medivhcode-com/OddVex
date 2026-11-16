"""Tracker analytics over a user's settled bets. Arithmetic comes from :mod:`..quant`."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal

from ..db import Bet
from ..quant import money, roi
from ..quant import tracker as stats
from ..schemas import price_out
from .schemas import (
    AnalyticsRowOut,
    BetAnalyticsOut,
    ClvAnalyticsOut,
    ClvBucketOut,
    CurrentStreakOut,
    StakeBucketOut,
)
from .service import bet_clv

#: Below this many settled bets the response carries ``sample_note``.
SMALL_SAMPLE = 30
ANALYTICS_NOTE = (
    "Computed from your settled bets only. Void bets are left out of staked, average "
    "stake and average odds. Win rate is wins divided by wins plus losses. Weekdays use "
    "the day the bet was placed and months the day it was settled, both in UTC. Past "
    "results do not predict future results."
)
#: Shown next to the streak numbers. Neutral on purpose: no praise for a winning run and
#: no suggestion that a losing run is about to end.
STREAK_NOTE = (
    "Streaks describe the order of past results only. A run of wins or losses says "
    "nothing about what happens next: each result is independent of the run before it."
)
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def sample_note(settled_count: int) -> str | None:
    if settled_count >= SMALL_SAMPLE:
        return None
    noun = "bet" if settled_count == 1 else "bets"
    return (
        f"Small sample: {settled_count} settled {noun}. With fewer than {SMALL_SAMPLE}, "
        "these results are mostly noise and say little about anything but the bets "
        "themselves."
    )


def _settled_when(bet: Bet) -> datetime:
    return (bet.settled_at or bet.placed_at).astimezone(UTC)


def _round(value: float | None, places: int = 6) -> float | None:
    return round(value, places) if value is not None else None


def _row(key: str, label: str, bets: Sequence[Bet]) -> AnalyticsRowOut:
    staked = sum((b.stake for b in bets if b.result != "void"), Decimal(0))
    total_profit = sum((b.profit or Decimal(0) for b in bets), Decimal(0))
    wins = sum(1 for b in bets if (b.profit or 0) > 0)
    losses = sum(1 for b in bets if (b.profit or 0) < 0)
    return AnalyticsRowOut(
        key=key,
        label=label,
        bets=len(bets),
        staked=float(staked),
        profit=float(total_profit),
        roi=_round(roi(total_profit, staked)),
        win_rate=_round(stats.win_rate(wins, losses)),
    )


def _grouped(
    bets: Sequence[Bet], key_of: Callable[[Bet], str], labels: Sequence[tuple[str, str]]
) -> list[AnalyticsRowOut]:
    """One row per ``labels`` entry, in that order, including empty ones."""
    groups: dict[str, list[Bet]] = {key: [] for key, _ in labels}
    for bet in bets:
        groups[key_of(bet)].append(bet)
    return [_row(key, label, groups[key]) for key, label in labels]


def analyze(bets: Sequence[Bet]) -> BetAnalyticsOut:
    """Analytics for ``bets``. Anything that is not settled is ignored."""
    settled = sorted(
        (b for b in bets if b.status == "settled"),
        key=lambda b: (_settled_when(b), b.placed_at, b.id),
    )
    counted = [b for b in settled if b.result != "void"]

    month_keys = sorted({_settled_when(b).strftime("%Y-%m") for b in settled})
    month_labels = [(key, f"{_MONTHS[int(key[5:]) - 1]} {key[:4]}") for key in month_keys]

    runs = stats.streaks([b.profit or Decimal(0) for b in settled])
    average_stake = stats.mean([b.stake for b in counted])
    average_odds = stats.mean([b.odds_decimal for b in counted])

    clvs = [value for value in (bet_clv(b) for b in settled) if value is not None]
    clv_counts = [0] * len(stats.CLV_BUCKETS)
    for value in clvs:
        clv_counts[stats.bucket_index(value, stats.CLV_BOUNDS)] += 1
    average_clv = stats.mean(clvs)

    stake_groups: list[list[Bet]] = [[] for _ in stats.STAKE_BUCKETS]
    for bet in counted:
        stake_groups[stats.bucket_index(bet.stake, stats.STAKE_BOUNDS)].append(bet)

    return BetAnalyticsOut(
        settled_count=len(settled),
        by_odds_band=_grouped(settled, lambda b: stats.odds_band(b.odds_decimal), stats.ODDS_BANDS),
        by_weekday=_grouped(
            settled,
            lambda b: _WEEKDAYS[b.placed_at.astimezone(UTC).weekday()],
            [(day, day.capitalize()) for day in _WEEKDAYS],
        ),
        by_month=_grouped(settled, lambda b: _settled_when(b).strftime("%Y-%m"), month_labels),
        longest_win_streak=runs.longest_win,
        longest_loss_streak=runs.longest_loss,
        current_streak=CurrentStreakOut(kind=runs.current_kind, length=runs.current_length),  # type: ignore[arg-type]
        streak_note=STREAK_NOTE,
        average_stake=float(money(average_stake)) if average_stake is not None else None,
        average_odds=price_out(average_odds) if average_odds is not None else None,
        clv=ClvAnalyticsOut(
            sample=len(clvs),
            average=_round(float(average_clv)) if average_clv is not None else None,
            share_beating_close=(
                _round(sum(1 for value in clvs if value > 0) / len(clvs)) if clvs else None
            ),
            buckets=[
                ClvBucketOut(key=key, label=label, count=count)
                for (key, label), count in zip(stats.CLV_BUCKETS, clv_counts, strict=True)
            ],
        ),
        stake_distribution=[
            StakeBucketOut(
                key=key,
                label=label,
                bets=len(group),
                staked=float(sum((b.stake for b in group), Decimal(0))),
            )
            for (key, label), group in zip(stats.STAKE_BUCKETS, stake_groups, strict=True)
        ],
        sample_note=sample_note(len(settled)),
        note=ANALYTICS_NOTE,
    )
