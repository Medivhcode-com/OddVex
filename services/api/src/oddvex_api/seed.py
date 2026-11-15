"""Demo data: one demo account with a varied, deterministic bet history.

For local development and demos only. Nothing here runs in production unless
someone runs ``scripts/seed_demo.py`` by hand, and the app refuses to
auto-seed when ``ODDVEX_ENV=production``.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .alerts import service as alerts_service
from .alerts.schemas import (
    GameFinalAlertCreate,
    GameStartAlertCreate,
    LineMoveAlertCreate,
    PriceAtLeastAlertCreate,
)
from .auth.security import hash_password
from .bets import service
from .bets.schemas import BetCreate, BetLegIn, BetSettleRequest, LegResultIn
from .board import Board
from .cache import InMemoryTTLCache
from .config import Settings, get_settings
from .db import AlertRule, Bet, User
from .errors import ApiError
from .providers import Event, SportsDataProvider

DEMO_EMAIL = "demo@oddvex.test"
DEMO_DISPLAY_NAME = "Demo Bettor"
SEED_PROVIDER = "demo-seed"
DEMO_BET_COUNT = 40
#: Extra pending bets with structured legs on events that are already final, so
#: ``POST /v1/bets/auto-settle`` has something to settle. Only seeded with a provider.
DEMO_GRADEABLE_COUNT = 4
#: Fixed so the demo history is the same everywhere. Results are drawn at roughly the
#: price-implied win rate; this seed gives a varied history with a small net loss.
DEMO_SEED = 4424

_BOOKS = ("Northline", "Cardinal Sports", "Summit Wager", "BlueHarbor Book", "Kestrel Bets")
# (league, away, home, total line, a player, prop market, prop line) - all fictional.
_GAMES = (
    ("nba", "Ironvale Anvils", "Harbor City Tides", 224.5, "Dax Varrow", "points", 22.5),
    ("nba", "Port Sable Lanterns", "Emberton Cinders", 219.5, "Tobin Ashdown", "rebounds", 8.5),
    (
        "nfl",
        "Westmere Wardens",
        "Granite Falls Boulders",
        44.5,
        "Marek Stennard",
        "receptions",
        5.5,
    ),
    (
        "nfl",
        "Cinder Lake Voyagers",
        "Thornfield Stags",
        41.5,
        "Quill Halloway",
        "rushing_yards",
        68.5,
    ),
    ("mlb", "Sunhaven Skylarks", "Millbrook Millwrights", 8.5, "Osric Rookwood", "strikeouts", 5.5),
    ("nhl", "Coldspring Ospreys", "Frostholm Glaciers", 6.5, "Levan Faircloth", "shots", 2.5),
    ("soccer", "Brightwater Rovers", "Aldermoor Athletic", 2.5, "Corwin Underhay", "shots", 2.5),
)
_SIDE_PRICES = (-125, -118, -112, -110, -108, -105, 100, 104, 110, 118, 130, 145, 165)


def _leg(rng: random.Random) -> BetLegIn:
    league, away, home, total, player, prop_market, prop_line = rng.choice(_GAMES)
    label = f"{away} at {home}"
    kind = rng.choice(("moneyline", "moneyline", "spread", "total", "prop"))
    american = rng.choice(_SIDE_PRICES)
    line: float | None = None
    if kind == "moneyline":
        selection, market = f"{rng.choice((home, away))} ML", "moneyline"
    elif kind == "spread" and league != "soccer":
        line = rng.choice((-6.5, -4.5, -3.5, -2.5, -1.5, 1.5, 2.5, 3.5, 4.5, 6.5))
        selection, market = f"{rng.choice((home, away))} {line:+g}", "spread"
        american = rng.choice((-115, -112, -110, -108, -105))
    elif kind == "prop":
        side = rng.choice(("Over", "Under"))
        line = prop_line
        selection = f"{player} {side.lower()} {prop_line:g} {prop_market.replace('_', ' ')}"
        market = f"player_{prop_market}"
        american = rng.choice((-125, -118, -112, -105, 100, 104, 110))
    else:
        line = total
        selection, market = f"{rng.choice(('Over', 'Under'))} {total:g}", "total"
        american = rng.choice((-115, -112, -110, -108, -105))
    closing: int | None = None
    if rng.random() < 0.8:
        closing = american + rng.choice((-12, -8, -5, -3, 0, 3, 5, 8))
        if -100 < closing < 100:
            closing = american
    return BetLegIn(
        selection=selection,
        market=market,
        league=league,
        event_label=label,
        line=line,
        odds=american,
        odds_format="american",
        closing_odds=closing,
    )


def _grade(rng: random.Random, bet: Bet) -> BetSettleRequest:
    """Pick a result with a win chance close to the price's implied probability."""
    roll = rng.random()
    if len(bet.legs) > 1:
        results = []
        for leg in bet.legs:
            won = rng.random() < 0.97 / float(leg.odds_decimal)
            results.append(LegResultIn(leg_id=leg.id, result="won" if won else "lost"))
        if bet.odds_source == "legs" and rng.random() < 0.15:
            results[-1] = LegResultIn(leg_id=results[-1].leg_id, result="push")
        return BetSettleRequest(leg_results=results)
    if roll < 0.05:
        return BetSettleRequest(result="push")
    if roll < 0.08:
        return BetSettleRequest(result="void")
    if roll < 0.11:
        return BetSettleRequest(result=rng.choice(("half_won", "half_lost")))
    if roll < 0.15:
        amount = round(float(bet.stake) * rng.choice((0.6, 0.8, 1.2, 1.4)), 2)
        return BetSettleRequest(result="cashout", cashout_amount=amount)
    won = rng.random() < 0.97 / float(bet.odds_decimal)
    return BetSettleRequest(result="won" if won else "lost")


_TOTAL_LINES = {"nba": 224.5, "nfl": 44.5, "mlb": 8.5, "nhl": 6.5, "soccer": 2.5}


def _gradeable_bets(provider: SportsDataProvider, now: datetime) -> list[tuple[str, BetCreate]]:
    """Pending bets with structured legs on finished synthetic events.

    Deterministic for a given provider and ``now``: the four most recently started final
    events, one bet each for moneyline and total, a spread (or second moneyline) and a
    two-leg parlay.
    """
    finals = sorted(
        (e for e in provider.list_events(status="final") if e.start_time <= now),
        key=lambda e: (e.start_time, e.id),
        reverse=True,
    )
    if len(finals) < 4:
        return []
    first, second, third, fourth = finals[:4]

    def name(team_id: str) -> str:
        team = provider.get_team(team_id)
        return team.name if team else team_id

    def moneyline(event: Event, side: str, odds: int) -> BetLegIn:
        team = name(event.home_team_id if side == "home" else event.away_team_id)
        return BetLegIn(
            selection=f"{team} ML",
            market="moneyline",
            event_id=event.id,
            outcome_key=side,  # type: ignore[arg-type]
            odds=odds,
        )

    def total(event: Event, side: str, odds: int) -> BetLegIn:
        line = _TOTAL_LINES.get(event.league, 2.5)
        return BetLegIn(
            selection=f"{side.capitalize()} {line:g}",
            market="total",
            event_id=event.id,
            outcome_key=side,  # type: ignore[arg-type]
            line=line,
            odds=odds,
        )

    def spread_or_moneyline(event: Event) -> BetLegIn:
        if "spread" not in event.markets:
            return moneyline(event, "away", 120)
        return BetLegIn(
            selection=f"{name(event.home_team_id)} -1.5",
            market="spread",
            event_id=event.id,
            outcome_key="home",
            line=-1.5,
            odds=-108,
        )

    def bet(event: Event, legs: list[BetLegIn], stake: float, book: str) -> BetCreate:
        return BetCreate(
            bet_type="parlay" if len(legs) > 1 else "straight",
            legs=service.resolve_structured_legs(legs, provider),
            stake=stake,
            sportsbook=book,
            placed_at=event.start_time - timedelta(hours=2),
            notes="Demo data: can be settled automatically from the final score",
        )

    return [
        ("demo-auto-01", bet(first, [moneyline(first, "home", -118)], 20, _BOOKS[0])),
        ("demo-auto-02", bet(second, [total(second, "over", -110)], 15, _BOOKS[1])),
        ("demo-auto-03", bet(third, [spread_or_moneyline(third)], 25, _BOOKS[2])),
        (
            "demo-auto-04",
            bet(
                fourth,
                [moneyline(fourth, "away", 110), total(first, "under", -105)],
                10,
                _BOOKS[3],
            ),
        ),
    ]


def seed_demo_alerts(
    db: Session,
    user: User,
    provider: SportsDataProvider,
    now: datetime,
    settings: Settings | None = None,
) -> int:
    """Give the demo user a few alert rules and run them once. Returns the rules created.

    Idempotent: does nothing when the user already has alert rules. The rules are built
    and evaluated by the same code the API uses, so the resulting notifications are real
    output of the engine on the current synthetic data:

    * a price alert whose threshold is already met (fires at once, becomes ``triggered``),
    * a price alert far above the market and a 3-point line-move alert (stay ``active``),
    * a final-score alert for a team, armed as if before its last two games (two
      notifications, stays ``active``),
    * a game-start alert for a team, 24 hours ahead (fires for its next game, stays
      ``active``).
    """
    if db.scalar(select(AlertRule.id).where(AlertRule.user_id == user.id).limit(1)) is not None:
        return 0
    board = Board(provider, settings or get_settings(), InMemoryTTLCache())
    upcoming = sorted(provider.list_events(status="upcoming"), key=lambda e: (e.start_time, e.id))
    finals = sorted(provider.list_events(status="final"), key=lambda e: (e.start_time, e.id))
    rules: list[AlertRule] = []

    def add(body: alerts_service.AlertCreateBody) -> AlertRule | None:
        rule = alerts_service.from_body(body)
        try:
            alerts_service.arm(board, rule)
        except ApiError:
            return None
        rule.user_id = user.id
        rules.append(rule)
        return rule

    priced = [
        (event, best)
        for event in upcoming
        if (best := board.best_price(event, "moneyline", "home")) is not None
    ]
    if priced:
        # The game priced closest to even money reads best in a demo.
        event, best = min(priced, key=lambda pair: (abs(float(pair[1].price) - 2.0), pair[0].id))
        start_team_id = event.home_team_id
        # Slightly below the current best price, so the rule is met as soon as it runs.
        add(
            PriceAtLeastAlertCreate(
                kind="price_at_least",
                event_id=event.id,
                market="moneyline",
                outcome_key="home",
                threshold=round(float(best.price) * 0.97, 4),
                odds_format="decimal",
            )
        )
        event, best = priced[-1]
        add(
            PriceAtLeastAlertCreate(
                kind="price_at_least",
                event_id=event.id,
                market="moneyline",
                outcome_key="home",
                threshold=round(float(best.price) * 1.6, 4),
                odds_format="decimal",
            )
        )
        add(GameStartAlertCreate(kind="game_start", team_id=start_team_id, minutes_before=1440))
    for event in upcoming:
        if "total" in event.markets and add(
            LineMoveAlertCreate(
                kind="line_move", event_id=event.id, market="total", outcome_key="over", min_move=3
            )
        ):
            break
    if finals:
        team_id = finals[-1].home_team_id
        final_rule = add(GameFinalAlertCreate(kind="game_final", team_id=team_id))
        if final_rule is not None:
            # Arming marks every finished game as handled. Un-mark the last two, as if
            # the rule had been created before they were played.
            final_rule.fired_event_ids = list(final_rule.fired_event_ids)[:-2]
    db.add_all(rules)
    db.flush()
    alerts_service.evaluate_user_alerts(db, user, now, board)
    return len(rules)


def seed_demo(
    db: Session,
    password: str,
    now: datetime,
    seed: int = DEMO_SEED,
    provider: SportsDataProvider | None = None,
    settings: Settings | None = None,
) -> int:
    """Create the demo user and any missing demo bets. Returns the number of bets created.

    Idempotent: each demo bet has a stable external id, so running this again
    creates nothing new. An existing demo user's password is left untouched.
    With a ``provider``, ``DEMO_GRADEABLE_COUNT`` pending bets on already final
    events are added as well (see :func:`_gradeable_bets`), and so are a few alert rules
    with the notifications they produce (see :func:`seed_demo_alerts`).
    """
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(password),
            display_name=DEMO_DISPLAY_NAME,
            role="user",
            age_confirmed_at=now,
        )
        db.add(user)
        db.flush()
    existing = set(
        db.scalars(
            select(Bet.external_bet_id).where(
                Bet.user_id == user.id, Bet.external_provider == SEED_PROVIDER
            )
        )
    )
    rng = random.Random(seed)
    created = 0
    for index in range(DEMO_BET_COUNT):
        # Draw everything first so the sequence is identical whether or not the bet exists.
        days_ago = 60 - index * 1.5 + rng.random()
        kind_roll = rng.random()
        if index == 3:
            bet_type, leg_count = "future", 1
        elif kind_roll < 0.72:
            bet_type, leg_count = "straight", 1
        elif kind_roll < 0.92:
            bet_type, leg_count = "parlay", rng.choice((2, 2, 3))
        else:
            bet_type, leg_count = "sgp", 2
        legs = [_leg(rng) for _ in range(leg_count)]
        if bet_type == "future":
            legs[0] = BetLegIn(
                selection="Harbor City Tides to win the title",
                market="futures",
                league="nba",
                event_label="Pro Basketball (synthetic) title",
                odds=850,
            )
        stake = float(rng.choice((5, 10, 10, 15, 20, 25, 25, 30, 40, 50)))
        override = rng.choice((240, 275, 310)) if bet_type == "sgp" else None
        placed = now - timedelta(days=max(days_ago, 0.05))
        pending = index >= DEMO_BET_COUNT - 7 or bet_type == "future"
        grade_seed = rng.random()
        external_id = f"demo-{index + 1:03d}"
        if external_id in existing:
            continue
        bet = service.create_bet(
            user.id,
            BetCreate(
                bet_type=bet_type,
                legs=legs,
                stake=stake,
                sportsbook=_BOOKS[index % len(_BOOKS)],
                placed_at=placed,
                notes="Demo data" if index % 9 == 0 else None,
                odds=override,
            ),
        )
        bet.external_provider = SEED_PROVIDER
        bet.external_bet_id = external_id
        db.add(bet)
        db.flush()
        if not pending:
            request = _grade(random.Random(f"{seed}|{grade_seed}"), bet)
            request.settled_at = min(placed + timedelta(hours=4), now)
            service.settle(bet, request)
        created += 1
    if provider is not None:
        for external_id, data in _gradeable_bets(provider, now):
            if external_id in existing:
                continue
            bet = service.create_bet(user.id, data)
            bet.external_provider = SEED_PROVIDER
            bet.external_bet_id = external_id
            db.add(bet)
            created += 1
        db.flush()
        seed_demo_alerts(db, user, provider, now, settings)
    db.commit()
    return created
