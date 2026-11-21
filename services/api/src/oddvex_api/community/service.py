"""Community domain logic: profiles, picks, grading, records, follows, comments, likes,
blocks, reports and moderation.

Rules that hold everywhere in this module:

* Other users are identified by handle only. No function here returns an email address,
  a display name, a plan or anything from the bet tracker.
* "Visible to a viewer" always means the same thing (:func:`_pick_visible`,
  :func:`_comment_visible`): the author has a public profile that moderators have not
  hidden, the account is active and not suspended, the item itself was not hidden or
  removed, and neither side has blocked the other. The only exception is the author's
  own items, which the author always sees (with a placeholder once moderated).
* Picks are graded by :func:`quant.grade_leg`, the function the bet tracker's
  auto-settlement uses. Record numbers come from :func:`quant.record.pick_record`.

Nothing here commits unless a function says so.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import Request
from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..bets.storage import stored_odds
from ..board import Board
from ..db import (
    CommunityBlock,
    CommunityComment,
    CommunityFollow,
    CommunityLike,
    CommunityPick,
    CommunityProfile,
    CommunityReport,
    User,
)
from ..db.base import new_id
from ..deps import write_audit
from ..errors import ApiError, not_found
from ..notifications import service as notifications
from ..notifications import templates
from ..providers import Event, SportsDataProvider
from ..quant import QuantError, grade_leg, valid_outcome_keys
from ..quant.record import FLAT_STAKE_METHOD, SMALL_SAMPLE, PickRecord, pick_record
from ..schemas import SportsbookRef, price_out
from . import content_rules, handles
from .guidelines import (
    LEADERBOARD_CAVEAT,
    LEADERBOARD_METHOD,
    MODERATED_PLACEHOLDER,
    RECORD_CAVEAT,
)
from .schemas import (
    HANDLE_MAX,
    HANDLE_MIN,
    AdminCommunityOverviewOut,
    AdminReportOut,
    AdminReportPartyOut,
    AuthorOut,
    BlockEntryOut,
    CommentOut,
    CommunityExportOut,
    CommunityRecordOut,
    FinalScoreOut,
    FollowEntryOut,
    LeaderboardOut,
    LeaderboardRowOut,
    MyProfileOut,
    PickCreate,
    PickOut,
    ProfileOut,
    ProfileUpsert,
    ReportCreate,
    ReportOut,
    WinRateIntervalOut,
)

logger = logging.getLogger("oddvex.community")

#: A profile needs this many graded picks in the window to be ranked.
MIN_LEADERBOARD_PICKS = SMALL_SAMPLE
#: A pending pick whose event the provider no longer serves is voided after this long.
VOID_AFTER = timedelta(days=7)
#: Picks graded, and events looked up, in one grading pass. What is left is picked up
#: by the next pass.
GRADE_BATCH = 500
GRADE_EVENT_BATCH = 500

_HANDLE_RE = re.compile(rf"^[a-z0-9_]{{{HANDLE_MIN},{HANDLE_MAX}}}$")
#: Not available as a handle at all.
RESERVED_HANDLES = frozenset(
    {
        "about",
        "account",
        "anonymous",
        "api",
        "blocks",
        "community",
        "deleted",
        "everyone",
        "feed",
        "followers",
        "following",
        "guidelines",
        "help",
        "leaderboard",
        "me",
        "null",
        "picks",
        "profile",
        "profiles",
        "reports",
        "root",
        "settings",
        "system",
        "undefined",
        "unknown",
        "user",
    }
)
#: Not available as a handle or as one of its underscore-separated parts, so
#: ``admin_jo`` and ``official_picks`` cannot pose as the service either.
RESERVED_HANDLE_PARTS = frozenset(
    {
        "admin",
        "administrator",
        "compliance",
        "helpdesk",
        "mod",
        "moderator",
        "moderators",
        "mods",
        "oddvex",
        "official",
        "security",
        "staff",
        "support",
    }
)
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def invalid(code: str, message: str, **details: object) -> ApiError:
    return ApiError(422, code, message, details=details or None)


# ----------------------------------------------------------------- user text
def checked_text(field: str, text: str | None, *, required: bool = False) -> str | None:
    """Validate free text against the content rules. Returns it unchanged (plain text is
    stored and returned verbatim; clients escape it), or ``None`` when it is blank."""
    if text is None or not text.strip():
        if required:
            raise invalid("invalid_text", f"The {field} cannot be blank", field=field)
        return None
    if CONTROL_CHARS.search(text):
        raise invalid(
            "invalid_text", f"The {field} contains characters that are not allowed", field=field
        )
    violation = content_rules.check_text(text)
    if violation is not None:
        raise invalid(violation.code, violation.message, field=field, rule=violation.rule)
    return text


def validate_handle(raw: str) -> str:
    """Lower-case ``raw`` and check it. 422 ``invalid_handle`` / ``handle_reserved`` /
    ``content_not_allowed``."""
    handle = raw.strip().lower()
    if not _HANDLE_RE.fullmatch(handle):
        raise invalid(
            "invalid_handle",
            f"A handle is {HANDLE_MIN} to {HANDLE_MAX} characters: letters a-z, digits "
            "and underscores",
            field="handle",
        )
    parts = set(handle.split("_"))
    if handle in RESERVED_HANDLES or parts & RESERVED_HANDLE_PARTS or "oddvex" in handle:
        raise invalid("handle_reserved", "This handle is not available", field="handle")
    violation = content_rules.check_text(handle.replace("_", " "))
    if violation is not None:
        raise invalid("content_not_allowed", violation.message, field="handle", rule=violation.rule)
    return handle


# ----------------------------------------------------------------- visibility
def _public_author() -> ColumnElement[bool]:
    """On a query joined to ``CommunityProfile`` and ``User`` of an item's author."""
    return and_(
        CommunityProfile.is_public.is_(True),
        CommunityProfile.moderation_status == "visible",
        User.status == "active",
        User.is_active.is_(True),
    )


def _i_blocked(viewer_id: str) -> Select[tuple[str]]:
    return select(CommunityBlock.blocked_id).where(CommunityBlock.blocker_id == viewer_id)


def _blocked_me(viewer_id: str) -> Select[tuple[str]]:
    return select(CommunityBlock.blocker_id).where(CommunityBlock.blocked_id == viewer_id)


def _not_blocked(column: Any, viewer_id: str) -> ColumnElement[bool]:
    """Neither side has blocked the other."""
    return and_(column.not_in(_i_blocked(viewer_id)), column.not_in(_blocked_me(viewer_id)))


def _pick_visible(viewer_id: str) -> ColumnElement[bool]:
    return or_(
        CommunityPick.user_id == viewer_id,
        and_(
            _public_author(),
            CommunityPick.moderation_status == "visible",
            _not_blocked(CommunityPick.user_id, viewer_id),
        ),
    )


def _comment_visible(viewer_id: str) -> ColumnElement[bool]:
    return or_(
        CommunityComment.user_id == viewer_id,
        and_(
            _public_author(),
            CommunityComment.moderation_status == "visible",
            _not_blocked(CommunityComment.user_id, viewer_id),
        ),
    )


def picks_query(viewer_id: str) -> Select[tuple[CommunityPick, str]]:
    """Picks ``viewer_id`` may see, each with its author's handle."""
    return (
        select(CommunityPick, CommunityProfile.handle)
        .join(CommunityProfile, CommunityProfile.user_id == CommunityPick.user_id)
        .join(User, User.id == CommunityPick.user_id)
        .where(_pick_visible(viewer_id))
    )


def comments_query(viewer_id: str) -> Select[tuple[CommunityComment, str]]:
    return (
        select(CommunityComment, CommunityProfile.handle)
        .join(CommunityProfile, CommunityProfile.user_id == CommunityComment.user_id)
        .join(User, User.id == CommunityComment.user_id)
        .where(_comment_visible(viewer_id))
    )


# -------------------------------------------------------------------- cursors
def encode_cursor(moment: datetime, row_id: str) -> str:
    micros = int(moment.timestamp()) * 1_000_000 + moment.microsecond
    return f"{micros}-{row_id}"


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    error = ApiError(422, "invalid_cursor", "The 'before' value is not a cursor from this API")
    micros, _, row_id = cursor.partition("-")
    if not micros.isdigit() or not row_id or len(micros) > 18:
        raise error
    seconds, remainder = divmod(int(micros), 1_000_000)
    try:
        return datetime.fromtimestamp(seconds, UTC).replace(microsecond=remainder), row_id
    except (OverflowError, OSError, ValueError) as exc:
        raise error from exc


# --------------------------------------------------------------------- record
def sample_note(graded: int) -> str | None:
    if graded >= SMALL_SAMPLE:
        return None
    noun = "pick" if graded == 1 else "picks"
    return (
        f"Small sample: {graded} graded {noun}. Fewer than {SMALL_SAMPLE} is too few to "
        "tell skill from luck."
    )


def record_out(record: PickRecord) -> CommunityRecordOut:
    interval = None
    if record.ci_low is not None and record.ci_high is not None:
        interval = WinRateIntervalOut(
            low=round(record.ci_low, 6),
            high=round(record.ci_high, 6),
            confidence_level=record.confidence_level,
        )
    return CommunityRecordOut(
        picks=record.picks,
        wins=record.wins,
        losses=record.losses,
        pushes=record.pushes,
        win_rate=round(record.win_rate, 6) if record.win_rate is not None else None,
        win_rate_interval=interval,
        average_price=(
            price_out(record.average_decimal_odds)
            if record.average_decimal_odds is not None
            else None
        ),
        flat_stake_roi=(
            round(record.flat_stake_roi, 6) if record.flat_stake_roi is not None else None
        ),
        units_profit=round(float(record.units_profit), 4),
        method=FLAT_STAKE_METHOD,
        sample_note=sample_note(record.picks),
        caveat=RECORD_CAVEAT,
    )


def _graded_pairs(
    db: Session, user_id: str, since: datetime | None = None, league: str | None = None
) -> list[tuple[str, Decimal]]:
    """``(result, decimal price)`` of a user's graded picks. A pick moderators hid still
    counts: hiding the text of a pick must not change the record."""
    query = select(CommunityPick.result, CommunityPick.price_decimal).where(
        CommunityPick.user_id == user_id, CommunityPick.status == "graded"
    )
    if since is not None:
        query = query.where(CommunityPick.graded_at >= since)
    if league is not None:
        query = query.where(CommunityPick.league == league)
    return [(str(result), Decimal(price)) for result, price in db.execute(query)]


def profile_record(db: Session, user_id: str) -> CommunityRecordOut:
    return record_out(pick_record(_graded_pairs(db, user_id)))


# ------------------------------------------------------------------- profiles
def get_own_profile(db: Session, user_id: str) -> CommunityProfile | None:
    return db.get(CommunityProfile, user_id)


def can_post(profile: CommunityProfile | None) -> bool:
    return profile is not None and profile.is_public and profile.moderation_status == "visible"


def require_posting_profile(db: Session, user: User) -> CommunityProfile:
    """The caller's profile, or ``403 profile_required`` when it cannot post."""
    profile = get_own_profile(db, user.id)
    if profile is None:
        reason = "no_profile"
    elif profile.moderation_status != "visible":
        reason = "profile_moderated"
    elif not profile.is_public:
        reason = "profile_not_public"
    else:
        return profile
    raise ApiError(
        403,
        "profile_required",
        "A public community profile is required for this",
        details={"reason": reason},
    )


def profile_by_handle(db: Session, handle: str) -> CommunityProfile | None:
    return db.scalar(select(CommunityProfile).where(CommunityProfile.handle == handle.lower()))


def find_profile(
    db: Session, viewer_id: str, handle: str, *, include_blocked_by_me: bool = True
) -> CommunityProfile:
    """The profile behind ``handle`` as ``viewer_id`` may see it, or 404.

    One answer for every reason it cannot be seen (no such handle, not public, hidden by
    moderators, suspended account, they blocked the viewer), so the 404 gives nothing away.
    The viewer's own profile is always found. A profile the viewer blocked is found unless
    ``include_blocked_by_me`` is false, so it can be looked at and unblocked.
    """
    missing = not_found("Profile", handle[:HANDLE_MAX])
    if not _HANDLE_RE.fullmatch(handle.lower()):
        raise missing
    row = db.execute(
        select(CommunityProfile, User)
        .join(User, User.id == CommunityProfile.user_id)
        .where(CommunityProfile.handle == handle.lower())
    ).first()
    if row is None:
        raise missing
    profile, owner = row
    if profile.user_id == viewer_id:
        return profile
    if not (
        profile.is_public
        and profile.moderation_status == "visible"
        and owner.status == "active"
        and owner.is_active
    ):
        raise missing
    if db.get(CommunityBlock, (profile.user_id, viewer_id)) is not None:
        raise missing
    blocked_by_me = db.get(CommunityBlock, (viewer_id, profile.user_id)) is not None
    if blocked_by_me and not include_blocked_by_me:
        raise missing
    return profile


def _follow_count(db: Session, user_id: str, *, followers: bool) -> int:
    """Followers of, or profiles followed by, ``user_id``: public, active ones only."""
    mine, other = (
        (CommunityFollow.followed_id, CommunityFollow.follower_id)
        if followers
        else (CommunityFollow.follower_id, CommunityFollow.followed_id)
    )
    return int(
        db.scalar(
            select(func.count())
            .select_from(CommunityFollow)
            .join(CommunityProfile, CommunityProfile.user_id == other)
            .join(User, User.id == other)
            .where(mine == user_id, _public_author())
        )
        or 0
    )


def _profile_fields(db: Session, viewer_id: str, profile: CommunityProfile) -> dict[str, Any]:
    is_me = profile.user_id == viewer_id
    moderated = profile.moderation_status != "visible"
    return {
        "handle": profile.handle,
        "bio": None if moderated else profile.bio,
        "joined": profile.created_at.astimezone(UTC).strftime("%Y-%m"),
        "follower_count": _follow_count(db, profile.user_id, followers=True),
        "following_count": _follow_count(db, profile.user_id, followers=False),
        "record": profile_record(db, profile.user_id),
        "is_following": (
            not is_me and db.get(CommunityFollow, (viewer_id, profile.user_id)) is not None
        ),
        "is_blocked": (
            not is_me and db.get(CommunityBlock, (viewer_id, profile.user_id)) is not None
        ),
        "is_me": is_me,
    }


def profile_out(db: Session, viewer_id: str, profile: CommunityProfile) -> ProfileOut:
    return ProfileOut(**_profile_fields(db, viewer_id, profile))


def my_profile_out(db: Session, profile: CommunityProfile) -> MyProfileOut:
    moderated = profile.moderation_status != "visible"
    return MyProfileOut(
        **_profile_fields(db, profile.user_id, profile),
        is_public=profile.is_public,
        can_post=can_post(profile),
        moderation_status=profile.moderation_status,  # type: ignore[arg-type]
        moderation_note=MODERATED_PLACEHOLDER if moderated else None,
    )


def handle_taken() -> ApiError:
    """The one answer for a handle nobody else may take: in use by another profile, or
    reserved because its account was deleted while suspended. It does not say which."""
    return ApiError(409, "handle_taken", "This handle is already in use")


#: ``details`` of the queue entry opened when an author edits a moderated profile.
AUTHOR_EDIT_DETAILS = (
    "The author edited this profile after moderators hid or removed it. Restore it if the "
    "new handle and bio follow the guidelines."
)


def is_author_edit(report: CommunityReport) -> bool:
    """An entry the API opened for an edited moderated profile. Members cannot report their
    own content (``cannot_report_own_content``), so only these have the author as the
    reporter."""
    return report.reporter_id == report.target_user_id


def _queue_author_edit(db: Session, profile: CommunityProfile, now: datetime) -> CommunityReport:
    """Put an edited moderated profile back in the report queue: one open entry per
    profile, holding a copy of the latest handle and bio."""
    entry = open_report(db, profile.user_id, "profile", profile.user_id, profile.handle)
    if entry is None:
        entry = CommunityReport(
            id=new_id(),
            reporter_id=profile.user_id,
            target_type="profile",
            target_user_id=profile.user_id,
            reason="other",
            details=AUTHOR_EDIT_DETAILS,
            status="open",
            created_at=now,
        )
        db.add(entry)
    entry.target_id = profile.handle
    entry.target_text_snapshot, entry.target_summary_snapshot = target_view(profile)
    return entry


def upsert_profile(
    db: Session, request: Request, user: User, body: ProfileUpsert, now: datetime
) -> tuple[CommunityProfile, bool]:
    """Create or update the caller's profile. Returns ``(profile, created)``. Commits.

    A profile moderators hid or removed stays hidden or removed whatever its owner
    changes: only an administrator restores it (:func:`restore_content`). A change to the
    handle or the bio is saved and puts the profile back in the report queue, as an entry
    that says the author edited it (:data:`AUTHOR_EDIT_DETAILS`), so the owner is not shut
    out for good. A handle in use by another profile or reserved (:mod:`.handles`) is
    ``409 handle_taken`` either way.
    """
    handle = validate_handle(body.handle)
    bio = checked_text("bio", body.bio)
    profile = get_own_profile(db, user.id)
    taken = db.scalar(
        select(CommunityProfile.user_id).where(
            CommunityProfile.handle == handle, CommunityProfile.user_id != user.id
        )
    )
    keeps_own_handle = profile is not None and profile.handle == handle
    if taken is not None or (not keeps_own_handle and handles.is_reserved(db, handle)):
        raise handle_taken()
    created = profile is None
    content_changed = False
    if profile is None:
        profile = CommunityProfile(
            user_id=user.id,
            handle=handle,
            bio=bio,
            is_public=body.is_public,
            created_at=now,
            updated_at=now,
        )
        db.add(profile)
        before: dict[str, Any] | None = None
    else:
        before = {"handle": profile.handle, "is_public": profile.is_public}
        content_changed = profile.handle != handle or profile.bio != bio
        profile.handle = handle
        profile.bio = bio
        profile.is_public = body.is_public
        profile.updated_at = now
    details: dict[str, Any] = {
        "before": before,
        "after": {"handle": handle, "is_public": body.is_public},
    }
    if content_changed and profile.moderation_status != "visible":
        details["moderation_status"] = profile.moderation_status
        # No flush before the commit below, which turns a handle taken meanwhile into 409.
        with db.no_autoflush:
            details["review_report_id"] = _queue_author_edit(db, profile, now).id
    write_audit(
        db,
        request,
        "community.profile_created" if created else "community.profile_updated",
        user_id=user.id,
        entity_type="community_profile",
        entity_id=user.id,
        details=details,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise handle_taken() from exc
    return profile, created


# ---------------------------------------------------------------------- picks
def _three_way(provider: SportsDataProvider) -> dict[str, bool]:
    return {league.key: league.has_draw for league in provider.list_leagues()}


def _team_names(board: Board, event: Event) -> tuple[str, str]:
    return board.team_ref(event.home_team_id).name, board.team_ref(event.away_team_id).name


def build_pick(board: Board, user_id: str, body: PickCreate, analysis: str | None) -> CommunityPick:
    """Validate a selection against the provider and snapshot its price.

    The event must exist (``422 unknown_event``) and be upcoming (``422 event_not_open``),
    offer the market (``422 market_not_available``) and the outcome must fit it
    (``422 invalid_selection``). The price is :meth:`Board.best_price`, the same code the
    odds endpoint and the price alerts use: the best open, non-stale price, for spread
    and total among the books quoting exactly this line (``422 price_not_available``
    when no such book has one). The client never supplies a price.
    """
    provider = board.provider
    event = provider.get_event(body.event_id)
    if event is None:
        raise invalid("unknown_event", f"Event '{body.event_id}' was not found")
    if event.status != "upcoming":
        raise invalid(
            "event_not_open",
            "Picks can only be posted before the event starts",
            event_status=event.status,
        )
    if body.market not in event.markets:
        raise invalid(
            "market_not_available",
            f"Market '{body.market}' is not offered for this event",
            available_markets=event.markets,
        )
    allowed = valid_outcome_keys(body.market, _three_way(provider).get(event.league, False))
    if body.outcome_key not in allowed:
        raise invalid(
            "invalid_selection",
            f"Outcome '{body.outcome_key}' is not valid for {body.market} on this event",
            valid_outcome_keys=list(allowed),
        )
    if body.market == "moneyline" and body.line is not None:
        raise invalid("invalid_selection", "A moneyline pick has no line")
    if body.market != "moneyline" and body.line is None:
        raise invalid("invalid_selection", f"A {body.market} pick needs a line")
    best = board.best_price(event, body.market, body.outcome_key, body.line)
    if best is None:
        raise invalid(
            "price_not_available",
            "No sportsbook has an open, current price for this selection"
            + ("" if body.market == "moneyline" else " at this line"),
        )
    home, away = _team_names(board, event)
    line = Decimal(str(body.line)).quantize(Decimal("0.01")) if body.line is not None else None
    return CommunityPick(
        user_id=user_id,
        event_id=event.id,
        league=event.league,
        event_label=templates.matchup(home, away)[:200],
        selection=templates.selection_label(body.market, body.outcome_key, line, home, away)[:200],
        event_start_time=event.start_time,
        market=body.market,
        outcome_key=body.outcome_key,
        line=line,
        # Rounded to what the column holds, so the pick reads the same before and after
        # it is stored, on every database; a price the column cannot hold is a 422.
        price_decimal=stored_odds(best.price, "The current price"),
        sportsbook_key=best.sportsbook.key,
        sportsbook_name=best.sportsbook.name,
        analysis=analysis,
        posted_at=board.now,
        status="pending",
    )


def existing_pick(db: Session, user_id: str, event_id: str, market: str) -> CommunityPick | None:
    return db.scalar(
        select(CommunityPick).where(
            CommunityPick.user_id == user_id,
            CommunityPick.event_id == event_id,
            CommunityPick.market == market,
        )
    )


def find_pick(db: Session, viewer_id: str, pick_id: str) -> tuple[CommunityPick, str]:
    """A pick the viewer may see and its author's handle, or 404."""
    row = db.execute(picks_query(viewer_id).where(CommunityPick.id == pick_id)).first()
    if row is None:
        raise not_found("Pick", pick_id[:32])
    return row[0], row[1]


def find_open_pick(db: Session, viewer_id: str, pick_id: str) -> tuple[CommunityPick, str]:
    """Like :func:`find_pick`, but a pick moderators hid is gone for its author too:
    nobody can comment on it or like it."""
    pick, handle = find_pick(db, viewer_id, pick_id)
    if pick.moderation_status != "visible":
        raise not_found("Pick", pick_id[:32])
    return pick, handle


def counts(
    db: Session, viewer_id: str, pick_ids: Sequence[str]
) -> tuple[dict[str, int], dict[str, int], set[str]]:
    """``(likes, visible comments, liked by the viewer)`` for a page of picks."""
    if not pick_ids:
        return {}, {}, set()
    likes: dict[str, int] = {
        pick_id: int(count)
        for pick_id, count in db.execute(
            select(CommunityLike.pick_id, func.count())
            .where(CommunityLike.pick_id.in_(pick_ids))
            .group_by(CommunityLike.pick_id)
        )
    }
    comments: dict[str, int] = {
        pick_id: int(count)
        for pick_id, count in db.execute(
            select(CommunityComment.pick_id, func.count())
            .join(CommunityProfile, CommunityProfile.user_id == CommunityComment.user_id)
            .join(User, User.id == CommunityComment.user_id)
            .where(
                CommunityComment.pick_id.in_(pick_ids),
                CommunityComment.moderation_status == "visible",
                _public_author(),
                _not_blocked(CommunityComment.user_id, viewer_id),
            )
            .group_by(CommunityComment.pick_id)
        )
    }
    liked = set(
        db.scalars(
            select(CommunityLike.pick_id).where(
                CommunityLike.pick_id.in_(pick_ids), CommunityLike.user_id == viewer_id
            )
        )
    )
    return likes, comments, liked


def pick_outs(
    db: Session, viewer_id: str, rows: Iterable[tuple[CommunityPick, str]], data_mode: str
) -> list[PickOut]:
    rows = list(rows)
    likes, comments, liked = counts(db, viewer_id, [pick.id for pick, _ in rows])
    result = []
    for pick, handle in rows:
        moderated = pick.moderation_status != "visible"
        score = None
        if pick.home_score is not None and pick.away_score is not None:
            score = FinalScoreOut(home=pick.home_score, away=pick.away_score)
        result.append(
            PickOut(
                id=pick.id,
                author=AuthorOut(handle=handle),
                event_id=pick.event_id,
                event_label=pick.event_label,
                event_start_time=pick.event_start_time,
                league=pick.league,
                market=pick.market,  # type: ignore[arg-type]
                outcome_key=pick.outcome_key,  # type: ignore[arg-type]
                line=float(pick.line) if pick.line is not None else None,
                selection=pick.selection,
                price=price_out(pick.price_decimal),
                sportsbook=SportsbookRef(key=pick.sportsbook_key, name=pick.sportsbook_name),
                posted_at=pick.posted_at,
                status=pick.status,  # type: ignore[arg-type]
                result=pick.result,  # type: ignore[arg-type]
                graded_at=pick.graded_at,
                final_score=score,
                # Only the author ever gets a moderated pick, and then without its text.
                analysis=None if moderated else pick.analysis,
                like_count=likes.get(pick.id, 0),
                comment_count=comments.get(pick.id, 0),
                liked_by_me=pick.id in liked,
                is_mine=pick.user_id == viewer_id,
                moderation_status=pick.moderation_status,  # type: ignore[arg-type]
                moderation_note=MODERATED_PLACEHOLDER if moderated else None,
                data_mode=data_mode,  # type: ignore[arg-type]
            )
        )
    return result


def picks_page(
    db: Session,
    viewer_id: str,
    query: Select[tuple[CommunityPick, str]],
    before: str | None,
    limit: int,
) -> tuple[list[tuple[CommunityPick, str]], str | None]:
    """Newest first. Returns the page and the cursor of the next (older) page, if any."""
    if before is not None:
        moment, row_id = decode_cursor(before)
        query = query.where(
            (CommunityPick.posted_at < moment)
            | ((CommunityPick.posted_at == moment) & (CommunityPick.id < row_id))
        )
    rows = [
        (pick, handle)
        for pick, handle in db.execute(
            query.order_by(CommunityPick.posted_at.desc(), CommunityPick.id.desc()).limit(limit + 1)
        )
    ]
    page = rows[:limit]
    cursor = None
    if len(rows) > limit and page:
        cursor = encode_cursor(page[-1][0].posted_at, page[-1][0].id)
    return page, cursor


# -------------------------------------------------------------------- grading
@dataclass(frozen=True, slots=True)
class GradingTotals:
    #: Events that have started and still had pending picks.
    checked: int
    graded: int
    voided: int


def grade_due_picks(
    db: Session,
    provider: SportsDataProvider,
    now: datetime,
    request: Request | None = None,
    limit: int = GRADE_BATCH,
) -> GradingTotals:
    """Grade pending picks whose event is final. Idempotent; not committed.

    Looks at pending picks whose event has started, oldest event first. A final event with
    a score is graded with :func:`quant.grade_leg` and its author gets one ``pick_graded``
    notification (unless they switched that kind off). An event that is not final yet is
    left alone. A pick whose event the provider no longer serves is marked ``void`` after
    :data:`VOID_AFTER`; a void pick counts in no record.
    """
    pending = (CommunityPick.status == "pending", CommunityPick.event_start_time <= now)
    # Work per event, not per pick: the events that have started and still have pending
    # picks are few (the ones in play, plus any the provider dropped), however many picks
    # there are. Picks on events that are not final yet therefore never crowd out picks
    # that can be graded.
    started = db.execute(
        select(CommunityPick.event_id, func.min(CommunityPick.event_start_time))
        .where(*pending)
        .group_by(CommunityPick.event_id)
        .order_by(func.min(CommunityPick.event_start_time), CommunityPick.event_id)
        .limit(GRADE_EVENT_BATCH)
    ).all()
    if not started:
        return GradingTotals(0, 0, 0)
    three_way = _three_way(provider)
    events: dict[str, Event | None] = {}
    settled: list[str] = []
    for event_id, start_time in started:
        event = events[event_id] = provider.get_event(event_id)
        if event is None:
            # Gone from the provider: nothing to do until the pick is old enough to void.
            if now - start_time >= VOID_AFTER:
                settled.append(event_id)
        elif event.status == "final" and event.score is not None:
            settled.append(event_id)
    due = (
        list(
            db.scalars(
                select(CommunityPick)
                .where(*pending, CommunityPick.event_id.in_(settled))
                .order_by(CommunityPick.event_start_time, CommunityPick.id)
                .limit(limit)
            )
        )
        if settled
        else []
    )
    graded = voided = 0
    for pick in due:
        event = events[pick.event_id]
        if event is None or event.score is None:
            pick.status = "void"
            pick.graded_at = now
            voided += 1
            continue
        try:
            result = grade_leg(
                pick.market,
                pick.outcome_key,
                pick.line,
                event.score.home,
                event.score.away,
                three_way=three_way.get(event.league, False),
            )
        except QuantError:
            # Cannot happen for a pick created through the API. Voided, not left pending,
            # so that it is not looked at again on every pass.
            logger.warning("pick_not_gradeable", extra={"pick_id": pick.id})
            pick.status = "void"
            pick.graded_at = now
            voided += 1
            continue
        pick.status = "graded"
        pick.result = result
        pick.graded_at = now
        pick.home_score = event.score.home
        pick.away_score = event.score.away
        graded += 1
        write_audit(
            db,
            request,
            "community.pick_graded",
            user_id=pick.user_id,
            entity_type="community_pick",
            entity_id=pick.id,
            details={"result": result},
        )
        delivered = notifications.notify(
            db,
            pick.user_id,
            templates.pick_graded(
                pick_id=pick.id,
                selection=pick.selection,
                event_label=pick.event_label,
                result=result,
                home_score=event.score.home,
                away_score=event.score.away,
            ),
        )
        if delivered == "delivered":
            db.flush()
            notifications.trim(db, pick.user_id)
    return GradingTotals(len(started), graded, voided)


def grade_if_due(request: Request, db: Session, provider: SportsDataProvider) -> None:
    """Run a grading pass unless one ran recently. Commits. Never raises: a failure here
    must not stop anyone from reading the community."""
    now = provider.now()
    throttle = request.app.state.community_grade_throttle
    min_seconds: int = request.app.state.settings.community_grade_min_seconds
    if not throttle.should_run("picks", now, min_seconds):
        return
    try:
        totals = grade_due_picks(db, provider, now, request)
        if totals.graded or totals.voided:
            db.commit()
    except Exception:
        db.rollback()
        throttle.forget("picks")
        logger.exception("pick_grading_failed")


# ------------------------------------------------------------------- comments
def find_comment(db: Session, viewer_id: str, comment_id: str) -> tuple[CommunityComment, str]:
    row = db.execute(comments_query(viewer_id).where(CommunityComment.id == comment_id)).first()
    if row is None:
        raise not_found("Comment", comment_id[:32])
    return row[0], row[1]


def comment_out(comment: CommunityComment, handle: str, viewer_id: str) -> CommentOut:
    moderated = comment.moderation_status != "visible"
    return CommentOut(
        id=comment.id,
        pick_id=comment.pick_id,
        author=AuthorOut(handle=handle),
        body=None if moderated else comment.body,
        created_at=comment.created_at,
        is_mine=comment.user_id == viewer_id,
        moderation_status=comment.moderation_status,  # type: ignore[arg-type]
        moderation_note=MODERATED_PLACEHOLDER if moderated else None,
    )


def comments_page(
    db: Session, viewer_id: str, pick_id: str, before: str | None, limit: int
) -> tuple[list[tuple[CommunityComment, str]], str | None]:
    query = comments_query(viewer_id).where(CommunityComment.pick_id == pick_id)
    if before is not None:
        moment, row_id = decode_cursor(before)
        query = query.where(
            (CommunityComment.created_at < moment)
            | ((CommunityComment.created_at == moment) & (CommunityComment.id < row_id))
        )
    rows = [
        (comment, handle)
        for comment, handle in db.execute(
            query.order_by(CommunityComment.created_at.desc(), CommunityComment.id.desc()).limit(
                limit + 1
            )
        )
    ]
    page = rows[:limit]
    cursor = None
    if len(rows) > limit and page:
        cursor = encode_cursor(page[-1][0].created_at, page[-1][0].id)
    return page, cursor


# -------------------------------------------------------- follows and blocks
def follow_entries(db: Session, viewer_id: str, *, followers: bool) -> list[FollowEntryOut]:
    """The caller's followers, or the profiles the caller follows, newest first. Only
    public, active profiles that are not blocked in either direction."""
    mine, other = (
        (CommunityFollow.followed_id, CommunityFollow.follower_id)
        if followers
        else (CommunityFollow.follower_id, CommunityFollow.followed_id)
    )
    rows = db.execute(
        select(CommunityProfile, CommunityFollow.created_at)
        .join(CommunityFollow, CommunityProfile.user_id == other)
        .join(User, User.id == other)
        .where(mine == viewer_id, _public_author(), _not_blocked(other, viewer_id))
        .order_by(CommunityFollow.created_at.desc(), CommunityProfile.handle)
        .limit(500)
    ).all()
    i_follow = set(
        db.scalars(
            select(CommunityFollow.followed_id).where(CommunityFollow.follower_id == viewer_id)
        )
    )
    return [
        FollowEntryOut(
            handle=profile.handle,
            bio=profile.bio,
            since=since,
            is_following=profile.user_id in i_follow,
        )
        for profile, since in rows
    ]


def block_entries(db: Session, viewer_id: str) -> list[BlockEntryOut]:
    rows = db.execute(
        select(CommunityProfile.handle, CommunityBlock.created_at)
        .join(CommunityBlock, CommunityBlock.blocked_id == CommunityProfile.user_id)
        .where(CommunityBlock.blocker_id == viewer_id)
        .order_by(CommunityBlock.created_at.desc(), CommunityProfile.handle)
    )
    return [BlockEntryOut(handle=handle, since=since) for handle, since in rows]


def remove_follows_between(db: Session, first: str, second: str) -> int:
    removed = 0
    for key in ((first, second), (second, first)):
        follow = db.get(CommunityFollow, key)
        if follow is not None:
            db.delete(follow)
            removed += 1
    return removed


# -------------------------------------------------------------------- reports
def report_out(report: CommunityReport) -> ReportOut:
    return ReportOut(
        id=report.id,
        target_type=report.target_type,  # type: ignore[arg-type]
        target_id=report.target_id,
        reason=report.reason,  # type: ignore[arg-type]
        details=report.details,
        status=report.status,  # type: ignore[arg-type]
        created_at=report.created_at,
    )


@dataclass(frozen=True, slots=True)
class ReportTarget:
    #: The pick id, the comment id or the profile's handle.
    target_id: str
    author_id: str
    #: What the moderator judges, copied onto the report (:func:`target_view`).
    text: str | None
    summary: str | None


def target_view(
    target: CommunityPick | CommunityComment | CommunityProfile,
) -> tuple[str | None, str | None]:
    """``(text, summary)`` a moderator judges: the analysis, the comment body or the bio;
    for a pick "selection (event)", for a profile "@handle", for a comment nothing."""
    if isinstance(target, CommunityPick):
        return target.analysis, f"{target.selection} ({target.event_label})"
    if isinstance(target, CommunityComment):
        return target.body, None
    return target.bio, f"@{target.handle}"


def resolve_report_target(db: Session, viewer_id: str, body: ReportCreate) -> ReportTarget:
    """The target of a new report: something the reporter can actually see, with a copy
    of what it says. 404 otherwise, 422 ``cannot_report_own_content`` for the reporter's
    own content."""
    target: CommunityPick | CommunityComment | CommunityProfile
    if body.target_type == "pick":
        target, _ = find_pick(db, viewer_id, body.target_id)
        target_id = target.id
    elif body.target_type == "comment":
        target, _ = find_comment(db, viewer_id, body.target_id)
        target_id = target.id
    else:
        target = find_profile(db, viewer_id, body.target_id)
        target_id = target.handle
    if target.user_id == viewer_id:
        raise invalid("cannot_report_own_content", "You cannot report your own content")
    text, summary = target_view(target)
    return ReportTarget(target_id, target.user_id, text, summary)


def open_report(
    db: Session, reporter_id: str, target_type: str, target_user_id: str, target_id: str
) -> CommunityReport | None:
    query = select(CommunityReport).where(
        CommunityReport.reporter_id == reporter_id,
        CommunityReport.target_type == target_type,
        CommunityReport.status == "open",
    )
    # A profile is the same target whatever its handle was when it was reported.
    if target_type == "profile":
        query = query.where(CommunityReport.target_user_id == target_user_id)
    else:
        query = query.where(CommunityReport.target_id == target_id)
    return db.scalar(query)


# ----------------------------------------------------------------- moderation
def _report_target(
    db: Session, report: CommunityReport
) -> CommunityPick | CommunityComment | CommunityProfile | None:
    if report.target_type == "pick":
        return db.get(CommunityPick, report.target_id)
    if report.target_type == "comment":
        return db.get(CommunityComment, report.target_id)
    return db.get(CommunityProfile, report.target_user_id)


def _party(db: Session, user_id: str) -> AdminReportPartyOut:
    user = db.get(User, user_id)
    profile = db.get(CommunityProfile, user_id)
    return AdminReportPartyOut(
        user_id=user_id,
        handle=profile.handle if profile else None,
        status=user.status if user else "deleted",
    )


_REMOVALS = ("hide_content", "remove_content")


def earlier_removals(db: Session, report: CommunityReport) -> int:
    """Decisions that hid or removed content of the report's author, one per decision
    however many reports it closed. For a resolved report only the decisions made up to
    its own, not counting the one that closed it.

    Counted from the reports that are left: a decision whose every report went with a
    deleted account is no longer counted."""
    query = select(
        CommunityReport.target_type, CommunityReport.target_id, CommunityReport.resolved_at
    ).where(
        CommunityReport.target_user_id == report.target_user_id,
        CommunityReport.status == "resolved",
        CommunityReport.resolution_action.in_(_REMOVALS),
    )
    if report.resolved_at is not None:
        query = query.where(CommunityReport.resolved_at <= report.resolved_at)

    def decision(
        target_type: str, target_id: str, resolved_at: datetime | None
    ) -> tuple[str, str, datetime | None]:
        # Every report a decision closes gets the same time; a profile is one target
        # whatever its handle was when it was reported.
        return (target_type, "" if target_type == "profile" else target_id, resolved_at)

    decisions = {decision(*row) for row in db.execute(query)}
    if report.status == "resolved" and report.resolution_action in _REMOVALS:
        decisions.discard(decision(report.target_type, report.target_id, report.resolved_at))
    return len(decisions)


def admin_report_out(db: Session, report: CommunityReport) -> AdminReportOut:
    target = _report_target(db, report)
    text, summary = target_view(target) if target is not None else (None, None)
    reported = (report.target_text_snapshot, report.target_summary_snapshot)
    copied = reported != (None, None)
    changed = target is None or (copied and (text, summary) != reported)
    return AdminReportOut(
        id=report.id,
        status=report.status,  # type: ignore[arg-type]
        created_at=report.created_at,
        reason=report.reason,  # type: ignore[arg-type]
        details=report.details,
        target_type=report.target_type,  # type: ignore[arg-type]
        target_id=report.target_id,
        target_exists=target is not None,
        target_text=text,
        target_summary=summary,
        target_moderation_status=target.moderation_status if target else None,  # type: ignore[arg-type]
        reported_text=report.target_text_snapshot,
        reported_summary=report.target_summary_snapshot,
        target_changed_since_report=changed,
        author_edit=is_author_edit(report),
        author_earlier_removals=earlier_removals(db, report),
        author=_party(db, report.target_user_id),
        reporter=_party(db, report.reporter_id),
        resolved_at=report.resolved_at,
        resolved_by=report.resolved_by,
        resolution_action=report.resolution_action,  # type: ignore[arg-type]
        resolution_note=report.resolution_note,
    )


def apply_moderation(
    db: Session, report: CommunityReport, action: str
) -> tuple[str | None, str | None]:
    """Hide or remove the reported content. Returns its moderation status before and
    after (``None`` twice when the content no longer exists)."""
    target = _report_target(db, report)
    if target is None:
        return None, None
    before = target.moderation_status
    target.moderation_status = "hidden" if action == "hide_content" else "removed"
    return before, target.moderation_status


def _open_reports_on(
    target_type: str, target_user_id: str, target_id: str
) -> Select[tuple[CommunityReport]]:
    """Open reports on one pick, comment or profile (a profile whatever its handle was)."""
    query = select(CommunityReport).where(
        CommunityReport.status == "open",
        CommunityReport.target_type == target_type,
        CommunityReport.target_user_id == target_user_id,
    )
    if target_type != "profile":
        query = query.where(CommunityReport.target_id == target_id)
    return query


def _close(
    rows: Iterable[CommunityReport], admin_id: str, action: str, note: str, now: datetime
) -> int:
    closed = 0
    for row in rows:
        row.status = "resolved"
        row.resolved_at = now
        row.resolved_by = admin_id
        row.resolution_action = action
        row.resolution_note = note
        closed += 1
    return closed


def close_reports_on_target(
    db: Session, report: CommunityReport, admin_id: str, action: str, note: str, now: datetime
) -> int:
    """Resolve ``report`` and every other open report on the same content the same way."""
    same_target = _open_reports_on(report.target_type, report.target_user_id, report.target_id)
    others = db.scalars(same_target.where(CommunityReport.id != report.id))
    return _close([report, *others], admin_id, action, note, now)


def find_moderation_target(
    db: Session, target_type: str, target_id: str
) -> CommunityPick | CommunityComment | CommunityProfile:
    """A pick or comment by id, or a profile by its current handle, whatever its state.
    404 when there is none."""
    target: CommunityPick | CommunityComment | CommunityProfile | None
    if target_type == "pick":
        target = db.get(CommunityPick, target_id)
    elif target_type == "comment":
        target = db.get(CommunityComment, target_id)
    else:
        target = profile_by_handle(db, target_id)
    if target is None:
        raise not_found(target_type.capitalize(), target_id[:32])
    return target


def target_key(target: CommunityPick | CommunityComment | CommunityProfile) -> str:
    """How a report names its target: the pick or comment id, the profile's handle."""
    return target.handle if isinstance(target, CommunityProfile) else target.id


def restore_content(
    db: Session,
    target: CommunityPick | CommunityComment | CommunityProfile,
    target_type: str,
    admin_id: str,
    note: str,
    now: datetime,
) -> tuple[str, int]:
    """Make moderated content visible again and close every open report on it as
    ``restore_content``. Returns ``(status before, reports closed)``.
    ``409 content_not_moderated`` when it is visible already. Not committed."""
    before = target.moderation_status
    if before == "visible":
        raise ApiError(
            409, "content_not_moderated", "This content was not hidden or removed by moderators"
        )
    target.moderation_status = "visible"
    reports = db.scalars(_open_reports_on(target_type, target.user_id, target_key(target)))
    return before, _close(list(reports), admin_id, "restore_content", note, now)


def admin_overview(db: Session) -> AdminCommunityOverviewOut:
    def count(model: type, *where: ColumnElement[bool]) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(*where)) or 0)

    moderated = sum(
        count(model, model.moderation_status != "visible")  # type: ignore[attr-defined]
        for model in (CommunityPick, CommunityComment, CommunityProfile)
    )
    return AdminCommunityOverviewOut(
        profiles=count(CommunityProfile),
        public_profiles=count(CommunityProfile, CommunityProfile.is_public.is_(True)),
        picks=count(CommunityPick),
        graded_picks=count(CommunityPick, CommunityPick.status == "graded"),
        comments=count(CommunityComment),
        open_reports=count(CommunityReport, CommunityReport.status == "open"),
        hidden_or_removed_items=moderated,
    )


# ---------------------------------------------------------------- leaderboard
def leaderboard(
    db: Session,
    viewer_id: str,
    now: datetime,
    window: str,
    league: str | None,
    data_mode: str,
    limit: int = 50,
) -> LeaderboardOut:
    """Profiles with enough graded picks in the window, by Wilson lower bound.

    Ranking by the lower bound of the interval instead of the raw win rate keeps a lucky
    short run from ranking first. Neither the price of the picks nor ROI is part of the
    order, so a high win rate at short prices can rank first and still lose money; every
    row carries ``average_price`` and ``flat_stake_roi`` and :data:`LEADERBOARD_METHOD`
    says so.
    """
    since = {"30d": now - timedelta(days=30), "90d": now - timedelta(days=90)}.get(window)
    filters: list[ColumnElement[bool]] = [CommunityPick.status == "graded"]
    if since is not None:
        filters.append(CommunityPick.graded_at >= since)
    if league is not None:
        filters.append(CommunityPick.league == league)
    eligible = db.execute(
        select(CommunityPick.user_id, CommunityProfile.handle)
        .join(CommunityProfile, CommunityProfile.user_id == CommunityPick.user_id)
        .join(User, User.id == CommunityPick.user_id)
        .where(*filters, _public_author(), _not_blocked(CommunityPick.user_id, viewer_id))
        .group_by(CommunityPick.user_id, CommunityProfile.handle)
        .having(func.count() >= MIN_LEADERBOARD_PICKS)
    ).all()
    ranked: list[tuple[float, PickRecord, str]] = []
    for user_id, handle in eligible:
        record = pick_record(_graded_pairs(db, user_id, since, league))
        if record.ci_low is None:
            continue  # nothing but pushes: no win rate to rank
        ranked.append((record.ci_low, record, handle))
    ranked.sort(key=lambda row: (-row[0], -row[1].picks, row[2]))
    return LeaderboardOut(
        window=window,  # type: ignore[arg-type]
        league=league,
        minimum_graded_picks=MIN_LEADERBOARD_PICKS,
        items=[
            LeaderboardRowOut(rank=index, handle=handle, record=record_out(record))
            for index, (_, record, handle) in enumerate(ranked[:limit], start=1)
        ],
        method=LEADERBOARD_METHOD.format(minimum=MIN_LEADERBOARD_PICKS),
        caveat=LEADERBOARD_CAVEAT,
        as_of=now,
        data_mode=data_mode,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------- export
def export_out(db: Session, user_id: str, data_mode: str) -> CommunityExportOut:
    """Everything the community stores about one account, for ``GET /v1/me/export``."""
    profile = get_own_profile(db, user_id)
    handle = profile.handle if profile else ""
    picks = db.scalars(
        select(CommunityPick)
        .where(CommunityPick.user_id == user_id)
        .order_by(CommunityPick.posted_at, CommunityPick.id)
    )
    comments = db.scalars(
        select(CommunityComment)
        .where(CommunityComment.user_id == user_id)
        .order_by(CommunityComment.created_at, CommunityComment.id)
    )
    following = db.scalars(
        select(CommunityProfile.handle)
        .join(CommunityFollow, CommunityFollow.followed_id == CommunityProfile.user_id)
        .where(CommunityFollow.follower_id == user_id)
        .order_by(CommunityProfile.handle)
    )
    blocks = db.scalars(
        select(CommunityProfile.handle)
        .join(CommunityBlock, CommunityBlock.blocked_id == CommunityProfile.user_id)
        .where(CommunityBlock.blocker_id == user_id)
        .order_by(CommunityProfile.handle)
    )
    likes = db.scalars(
        select(CommunityLike.pick_id)
        .where(CommunityLike.user_id == user_id)
        .order_by(CommunityLike.created_at, CommunityLike.pick_id)
    )
    # Reports the account made, and the review entries opened for its own edited profile
    # (reporter and author are the same account). ``account/export.py`` streams the same.
    reports = db.scalars(
        select(CommunityReport)
        .where(CommunityReport.reporter_id == user_id)
        .order_by(CommunityReport.created_at, CommunityReport.id)
    )
    return CommunityExportOut(
        profile=my_profile_out(db, profile) if profile else None,
        picks=pick_outs(db, user_id, [(pick, handle) for pick in picks], data_mode),
        comments=[comment_out(comment, handle, user_id) for comment in comments],
        following=list(following),
        likes=list(likes),
        blocks=list(blocks),
        reports=[report_out(report) for report in reports],
    )
