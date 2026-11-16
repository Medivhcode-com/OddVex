"""Demo data for the community: fictional profiles with picks, comments, follows and likes.

For local development and demos only, like :mod:`oddvex_api.seed`. Every profile is
invented, says so in its bio and has an obviously fictional handle. Nothing here is a
real person's record.

Upcoming picks go through :func:`service.build_pick`, the code the API uses, so their
prices are real output of the board on the current synthetic data. Graded picks cannot
be created that way (a pick is only accepted before its event starts), so they are
written as picks posted a few hours before events that are final by now, priced from
the synthetic line history at that moment, and then graded by
:func:`service.grade_due_picks`: the same grading the API runs.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..board import Board
from ..cache import InMemoryTTLCache
from ..config import Settings
from ..db import (
    CommunityComment,
    CommunityFollow,
    CommunityLike,
    CommunityPick,
    CommunityProfile,
    User,
)
from ..errors import ApiError
from ..notifications import templates
from ..providers import Event, SportsDataProvider
from ..quant import american_to_decimal
from . import service
from .schemas import PickCreate

DEMO_HANDLE = "demo_bettor"
DEMO_BIO = "Demo account for trying the community. Fictional data only."
SEED_DOMAIN = "community.oddvex.test"
#: (handle, bio, graded picks to aim for). All invented. Two have 30 or more graded
#: picks, so the leaderboard has something to rank when its flag is on.
FICTIONAL_PROFILES: tuple[tuple[str, str, int], ...] = (
    ("fictional_fox", "Fictional demo profile. Mostly totals. Not a real person.", 36),
    ("sample_sam", "Fictional demo profile. Spreads and moneylines. Not a real person.", 32),
    ("madeup_mara", "Fictional demo profile. Small sample on purpose. Not a real person.", 12),
    ("placeholder_pat", "Fictional demo profile. Underdogs only. Not a real person.", 18),
    ("notreal_nia", "Fictional demo profile. A bit of everything. Not a real person.", 9),
    ("example_eli", "Fictional demo profile. New here. Not a real person.", 4),
)
_ANALYSES = (
    "Both teams played yesterday. Looking at pace over the last five games.",
    "The line has moved half a point since it opened. Taking the earlier number.",
    "Small sample, so this is a lean and nothing more.",
    None,
    "Comparing the price with the no-vig consensus of the other books.",
    None,
)
_COMMENTS = (
    "Thanks for showing the reasoning.",
    "I read the pace numbers differently, but I see the case.",
    "Which games is that sample from?",
    "The consensus line was half a point lower when I looked.",
)
_GRADED_DEMO_PICKS = 6
_UPCOMING_PER_PROFILE = 2


def _user(db: Session, handle: str, password_hash: str, now: datetime) -> User:
    email = f"{handle}@{SEED_DOMAIN}"
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=f"Fictional profile {handle}",
            role="user",
            age_confirmed_at=now,
            email_verified_at=now,
        )
        db.add(user)
        db.flush()
    return user


def _profile(db: Session, user: User, handle: str, bio: str, joined: datetime) -> None:
    if db.get(CommunityProfile, user.id) is None:
        db.add(
            CommunityProfile(
                user_id=user.id,
                handle=handle,
                bio=bio,
                is_public=True,
                created_at=joined,
                updated_at=joined,
            )
        )
        db.flush()


def _past_pick(
    board: Board, user_id: str, event: Event, rng: random.Random, analysis: str | None
) -> CommunityPick | None:
    """A pick as it would have been posted a few hours before ``event`` started, priced
    from the line history at that moment. ``None`` when there is no history to price it."""
    provider = board.provider
    market = rng.choice(event.markets)
    keys = sorted({s.outcome_key for s in provider.get_line_history(event.id, market)})
    if not keys:
        return None
    outcome = rng.choice(keys)
    hours_before = rng.randint(2, 20)
    posted_at = event.start_time - timedelta(hours=hours_before)
    series = [
        s
        for s in provider.get_line_history(event.id, market)
        if s.outcome_key == outcome and s.points
    ]
    if not series:
        return None
    book = series[rng.randrange(len(series))]
    point = max(
        (p for p in book.points if p.timestamp <= posted_at),
        key=lambda p: p.timestamp,
        default=book.points[0],
    )
    home = board.team_ref(event.home_team_id).name
    away = board.team_ref(event.away_team_id).name
    line = Decimal(str(point.line)).quantize(Decimal("0.01")) if point.line is not None else None
    sportsbook = board.book_ref(book.sportsbook_id)
    return CommunityPick(
        user_id=user_id,
        event_id=event.id,
        league=event.league,
        event_label=templates.matchup(home, away)[:200],
        selection=templates.selection_label(market, outcome, line, home, away)[:200],
        event_start_time=event.start_time,
        market=market,
        outcome_key=outcome,
        line=line,
        price_decimal=american_to_decimal(point.price_american),
        sportsbook_key=sportsbook.key,
        sportsbook_name=sportsbook.name,
        analysis=analysis,
        posted_at=posted_at,
        status="pending",
    )


def _upcoming_pick(
    board: Board, user_id: str, event: Event, rng: random.Random, analysis: str | None
) -> CommunityPick | None:
    market = rng.choice(event.markets)
    outcome = rng.choice(("over", "under") if market == "total" else ("home", "away"))
    line = board.consensus_outcome_line(event, market, outcome)
    if market != "moneyline" and line is None:
        return None
    try:
        return service.build_pick(
            board,
            user_id,
            PickCreate(event_id=event.id, market=market, outcome_key=outcome, line=line),  # type: ignore[arg-type]
            analysis,
        )
    except ApiError:
        return None


def _final_events(provider: SportsDataProvider, now: datetime, days: int = 21) -> list[Event]:
    """Final events of the last ``days`` days, most recent first."""
    events: dict[str, Event] = {}
    for offset in range(days + 1):
        for event in provider.list_events(
            status="final", on_date=(now - timedelta(days=offset)).date()
        ):
            if event.score is not None and event.start_time <= now:
                events[event.id] = event
    return sorted(events.values(), key=lambda e: (e.start_time, e.id), reverse=True)


def seed_demo_community(
    db: Session,
    demo_user: User,
    password_hash: str,
    provider: SportsDataProvider,
    now: datetime,
    settings: Settings,
) -> dict[str, int]:
    """Create the fictional profiles and their activity. Idempotent; not committed.

    Returns what this run created. Running it again creates nothing that already exists:
    users are found by email, a profile by its user, a pick by user, event and market, a
    follow or a like by its key, and comments are only added to picks created in the
    same run.
    """
    board = Board(provider, settings, InMemoryTTLCache())
    finals = _final_events(provider, now)
    upcoming = sorted(provider.list_events(status="upcoming"), key=lambda e: (e.start_time, e.id))
    created = {"profiles": 0, "picks": 0, "comments": 0, "follows": 0, "likes": 0}

    members: list[tuple[User, str, int]] = []
    for index, (handle, bio, graded_target) in enumerate(FICTIONAL_PROFILES):
        user = _user(db, handle, password_hash, now)
        had_profile = db.get(CommunityProfile, user.id) is not None
        _profile(db, user, handle, bio, now - timedelta(days=30 * (index + 1)))
        created["profiles"] += 0 if had_profile else 1
        members.append((user, handle, graded_target))
    had_demo_profile = db.get(CommunityProfile, demo_user.id) is not None
    _profile(db, demo_user, DEMO_HANDLE, DEMO_BIO, now - timedelta(days=14))
    created["profiles"] += 0 if had_demo_profile else 1
    members.append((demo_user, DEMO_HANDLE, _GRADED_DEMO_PICKS))

    new_picks: list[CommunityPick] = []
    for user, handle, graded_target in members:
        rng = random.Random(f"community|{handle}")
        taken = {
            (event_id, market)
            for event_id, market in db.execute(
                select(CommunityPick.event_id, CommunityPick.market).where(
                    CommunityPick.user_id == user.id
                )
            )
        }
        candidates: list[CommunityPick | None] = [
            _past_pick(board, user.id, event, rng, rng.choice(_ANALYSES))
            for event in rng.sample(finals, min(graded_target, len(finals)))
        ]
        candidates += [
            _upcoming_pick(board, user.id, event, rng, rng.choice(_ANALYSES))
            for event in rng.sample(upcoming, min(_UPCOMING_PER_PROFILE, len(upcoming)))
        ]
        for pick in candidates:
            if pick is None or (pick.event_id, pick.market) in taken:
                continue
            taken.add((pick.event_id, pick.market))
            db.add(pick)
            new_picks.append(pick)
    db.flush()
    created["picks"] = len(new_picks)

    # Everyone follows the next two members in the list; the demo user follows three.
    for index, (user, _handle, _target) in enumerate(members):
        reach = 3 if user.id == demo_user.id else 2
        for step in range(1, reach + 1):
            other = members[(index + step) % len(members)][0]
            if other.id != user.id and db.get(CommunityFollow, (user.id, other.id)) is None:
                db.add(CommunityFollow(follower_id=user.id, followed_id=other.id, created_at=now))
                created["follows"] += 1

    rng = random.Random("community|activity")
    for pick in new_picks:
        others = [user for user, _handle, _target in members if user.id != pick.user_id]
        for liker in rng.sample(others, rng.randint(0, 3)):
            if db.get(CommunityLike, (pick.id, liker.id)) is None:
                db.add(CommunityLike(pick_id=pick.id, user_id=liker.id, created_at=now))
                created["likes"] += 1
        if rng.random() < 0.25:
            author = rng.choice(others)
            db.add(
                CommunityComment(
                    pick_id=pick.id,
                    user_id=author.id,
                    body=rng.choice(_COMMENTS),
                    created_at=min(now, pick.posted_at + timedelta(minutes=rng.randint(5, 90))),
                )
            )
            created["comments"] += 1
    db.flush()
    # Grade what is final, with the same code the API uses.
    while service.grade_due_picks(db, provider, now).graded:
        db.flush()
    return created
