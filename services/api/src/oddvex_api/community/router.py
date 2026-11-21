"""Community routes. Every one of them is behind the ``community`` feature flag: while it
is off they all answer ``404 feature_disabled``, signed in or not.

Research discussion, not tipping: no money, no stakes or units, no paid picks, no links
and no direct messages. Every route except the guidelines needs a signed-in user.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db import (
    CommunityBlock,
    CommunityComment,
    CommunityFollow,
    CommunityLike,
    CommunityPick,
    CommunityReport,
)
from ..deps import BoardDep, CurrentUserDep, DbDep, NowDep, ProviderDep, SettingsDep, write_audit
from ..errors import (
    AUTH_ERROR_RESPONSES,
    RATE_LIMIT_RESPONSE,
    ApiError,
    ErrorResponse,
    not_found,
)
from ..flags.service import require_flag
from ..notifications import service as notifications
from ..notifications import templates
from ..ratelimit import check_user_quota, use_user_quota
from . import guidelines, service
from .schemas import (
    BlockListOut,
    BlockStateOut,
    CommentCreate,
    CommentOut,
    CommentPageOut,
    CommunityGuidelinesOut,
    FeedScope,
    FollowListOut,
    FollowStateOut,
    GuidelineRuleOut,
    LeaderboardOut,
    LeaderboardWindow,
    LikeStateOut,
    MyProfileOut,
    PickCreate,
    PickOut,
    PickPageOut,
    PickStatus,
    ProfileOut,
    ProfileUpsert,
    ReportCreate,
    ReportOut,
)

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorResponse,
        "description": "Not found, not visible to you, or the `community` flag is off",
    }
}
_PROFILE_REQUIRED: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse, "description": "A public community profile is required"}
}
_CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorResponse, "description": "Conflicts with the current state"}
}

router = APIRouter(
    prefix="/community",
    tags=["community"],
    dependencies=[Depends(require_flag("community"))],
    responses={**AUTH_ERROR_RESPONSES, **_NOT_FOUND},
)

Limit = Annotated[int, Query(ge=1, le=100)]
Before = Annotated[
    str | None, Query(max_length=80, description="`next_before` from the previous page.")
]


# ------------------------------------------------------------------ guidelines
@router.get(
    "/guidelines",
    response_model=CommunityGuidelinesOut,
    operation_id="get_community_guidelines",
    summary="The community rules, as one structured list",
    description=(
        "The one source of truth for clients. No sign-in needed, but like every community "
        "route it answers `404 feature_disabled` while the `community` flag is off."
    ),
)
def get_community_guidelines() -> CommunityGuidelinesOut:
    return CommunityGuidelinesOut(
        version=guidelines.GUIDELINES_VERSION,
        intro=guidelines.INTRO,
        rules=[
            GuidelineRuleOut(key=key, title=title, text=text)
            for key, title, text in guidelines.RULES
        ],
        enforcement=guidelines.ENFORCEMENT,
        help=guidelines.HELP,
    )


# ------------------------------------------------------------------- profiles
@router.put(
    "/profile",
    response_model=MyProfileOut,
    operation_id="upsert_my_profile",
    summary="Create or update your community profile",
    description=(
        "Opt-in: nobody has a profile until they create one. `handle` is 3 to 20 "
        "characters of `a-z`, `0-9` and `_` (`422 invalid_handle`), unique whatever the "
        "case (`409 handle_taken`) and not a reserved word (`422 handle_reserved`). "
        "`bio` is plain text, at most 280 characters, without links "
        "(`422 links_not_allowed`) and within the content rules "
        "(`422 content_not_allowed`). Only a public profile can post picks and comments, "
        "follow others and be found. Answers 201 when the profile was created. A profile "
        "that moderators hid or removed stays hidden or removed when you edit it: a "
        "changed handle or bio is saved and sent to the moderators for review, and only "
        "they can make it visible again."
    ),
    responses={
        201: {"model": MyProfileOut, "description": "The profile was created"},
        **_CONFLICT,
    },
)
def upsert_my_profile(
    body: ProfileUpsert,
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    response: Response,
    now: NowDep,
) -> MyProfileOut:
    profile, created = service.upsert_profile(db, request, user, body, now)
    if created:
        response.status_code = 201
    return service.my_profile_out(db, profile)


@router.get(
    "/profile",
    response_model=MyProfileOut,
    operation_id="get_my_profile",
    summary="Your community profile",
    description="`404 not_found` until you create one with `PUT /v1/community/profile`.",
)
def get_my_profile(
    user: CurrentUserDep, db: DbDep, request: Request, provider: ProviderDep
) -> MyProfileOut:
    service.grade_if_due(request, db, provider)
    profile = service.get_own_profile(db, user.id)
    if profile is None:
        raise ApiError(404, "not_found", "You have no community profile yet")
    return service.my_profile_out(db, profile)


@router.get(
    "/profiles/{handle}",
    response_model=ProfileOut,
    operation_id="get_profile",
    summary="A public profile and its verified record",
    description=(
        "Handle, bio, the month it was created, follower and following counts and the "
        "record of its graded picks. Never an email address, a name, a plan or tracker "
        "data. `404` for a handle that does not exist, is not public, was hidden by "
        "moderators, belongs to a suspended account or has blocked you: the answer is "
        "the same in every case."
    ),
)
def get_profile(
    handle: str, user: CurrentUserDep, db: DbDep, request: Request, provider: ProviderDep
) -> ProfileOut:
    service.grade_if_due(request, db, provider)
    return service.profile_out(db, user.id, service.find_profile(db, user.id, handle))


# ---------------------------------------------------------------------- picks
@router.post(
    "/picks",
    response_model=PickOut,
    status_code=201,
    operation_id="create_pick",
    summary="Post a structured pick on an upcoming event",
    description=(
        "A structured, gradeable selection only: `event_id`, `market`, `outcome_key` and, "
        "for spread and total, `line`, plus optional `analysis` text. There is no stake, "
        "no unit size and no confidence rating. The server records the best open, "
        "non-stale price at that moment as the pick's price (`422 price_not_available` "
        "when no sportsbook has one, for spread and total at exactly that line) and the "
        "time as `posted_at`. The event has to be upcoming (`422 event_not_open`). One "
        "pick per event and market (`409 pick_exists`), 20 picks per day. Needs a public "
        "profile (`403 profile_required`). The pick is graded automatically from the "
        "final score."
    ),
    responses={**_PROFILE_REQUIRED, **_CONFLICT, **RATE_LIMIT_RESPONSE},
)
def create_pick(
    body: PickCreate,
    user: CurrentUserDep,
    db: DbDep,
    board: BoardDep,
    request: Request,
    settings: SettingsDep,
) -> PickOut:
    profile = service.require_posting_profile(db, user)
    analysis = service.checked_text("analysis", body.analysis)
    pick = service.build_pick(board, user.id, body, analysis)
    duplicate = service.existing_pick(db, user.id, pick.event_id, pick.market)
    if duplicate is not None:
        raise ApiError(
            409,
            "pick_exists",
            "You already have a pick on this market of this event",
            details={"pick_id": duplicate.id},
        )
    check_user_quota(request, "community_day_limiter", user.id, settings.community_picks_per_day)
    db.add(pick)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            409, "pick_exists", "You already have a pick on this market of this event"
        ) from exc
    write_audit(
        db,
        request,
        "community.pick_created",
        user_id=user.id,
        entity_type="community_pick",
        entity_id=pick.id,
        details={"event_id": pick.event_id, "market": pick.market},
    )
    db.commit()
    use_user_quota(request, "community_day_limiter", user.id)
    return service.pick_outs(db, user.id, [(pick, profile.handle)], board.provider.data_mode)[0]


@router.get(
    "/picks",
    response_model=PickPageOut,
    operation_id="list_picks",
    summary="Picks, newest first",
    description=(
        "Filter by author `handle`, `event_id`, `league` and `status` (`pending`, "
        "`graded`, `void`). Picks of people you blocked or who blocked you, hidden or "
        "removed picks and picks of suspended or non-public accounts are left out. Your "
        "own picks are always included."
    ),
)
def list_picks(
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    provider: ProviderDep,
    handle: Annotated[str | None, Query(max_length=20)] = None,
    event_id: Annotated[str | None, Query(max_length=64)] = None,
    league: Annotated[str | None, Query(max_length=32)] = None,
    status: Annotated[PickStatus | None, Query()] = None,
    before: Before = None,
    limit: Limit = 50,
) -> PickPageOut:
    service.grade_if_due(request, db, provider)
    query = service.picks_query(user.id)
    if handle is not None:
        author = service.find_profile(db, user.id, handle, include_blocked_by_me=False)
        query = query.where(CommunityPick.user_id == author.user_id)
    if event_id:
        query = query.where(CommunityPick.event_id == event_id)
    if league and league.strip():
        query = query.where(CommunityPick.league == league.strip().lower())
    if status is not None:
        query = query.where(CommunityPick.status == status)
    page, cursor = service.picks_page(db, user.id, query, before, limit)
    return PickPageOut(
        items=service.pick_outs(db, user.id, page, provider.data_mode), next_before=cursor
    )


@router.get(
    "/feed",
    response_model=PickPageOut,
    operation_id="get_feed",
    summary="The pick feed, newest first",
    description=(
        "`scope=following` (the default): picks of the profiles you follow. "
        "`scope=everyone`: every public pick. Either way without people you blocked or "
        "who blocked you, hidden or removed content and suspended authors. Ordered by "
        "time only: there is no ranking by results or popularity."
    ),
)
def get_feed(
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    provider: ProviderDep,
    scope: Annotated[FeedScope, Query()] = "following",
    before: Before = None,
    limit: Limit = 50,
) -> PickPageOut:
    service.grade_if_due(request, db, provider)
    query = service.picks_query(user.id)
    if scope == "following":
        query = query.where(
            CommunityPick.user_id.in_(
                select(CommunityFollow.followed_id).where(CommunityFollow.follower_id == user.id)
            )
        )
    page, cursor = service.picks_page(db, user.id, query, before, limit)
    return PickPageOut(
        items=service.pick_outs(db, user.id, page, provider.data_mode), next_before=cursor
    )


@router.get(
    "/picks/{pick_id}",
    response_model=PickOut,
    operation_id="get_pick",
    summary="One pick",
    description=(
        "`404` when it does not exist or you may not see it. The author still gets a "
        "pick that moderators hid, without its analysis and with `moderation_note`."
    ),
)
def get_pick(
    pick_id: str, user: CurrentUserDep, db: DbDep, request: Request, provider: ProviderDep
) -> PickOut:
    service.grade_if_due(request, db, provider)
    return service.pick_outs(
        db, user.id, [service.find_pick(db, user.id, pick_id)], provider.data_mode
    )[0]


@router.delete(
    "/picks/{pick_id}",
    status_code=204,
    operation_id="delete_pick",
    summary="Delete your pick while the event is still upcoming",
    description=(
        "Only the author, and only before the event starts. Once it has started the pick "
        "stays, so that a record cannot be tidied up afterwards: `409 pick_locked`."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Not your pick"},
        **_CONFLICT,
    },
)
def delete_pick(
    pick_id: str, user: CurrentUserDep, db: DbDep, request: Request, provider: ProviderDep
) -> Response:
    pick, _ = service.find_pick(db, user.id, pick_id)
    if pick.user_id != user.id:
        raise ApiError(403, "forbidden", "Only the author can delete a pick")
    event = provider.get_event(pick.event_id)
    if pick.status != "pending" or event is None or event.status != "upcoming":
        raise ApiError(
            409,
            "pick_locked",
            "A pick cannot be deleted once its event has started",
            details={"event_status": event.status if event else "unavailable"},
        )
    db.delete(pick)
    write_audit(
        db,
        request,
        "community.pick_deleted",
        user_id=user.id,
        entity_type="community_pick",
        entity_id=pick_id,
        details={"event_id": pick.event_id, "market": pick.market},
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------- likes
def _like_state(db: DbDep, viewer_id: str, pick_id: str) -> LikeStateOut:
    likes, _, liked = service.counts(db, viewer_id, [pick_id])
    return LikeStateOut(
        pick_id=pick_id, liked_by_me=pick_id in liked, like_count=likes.get(pick_id, 0)
    )


@router.put(
    "/picks/{pick_id}/like",
    response_model=LikeStateOut,
    operation_id="like_pick",
    summary="Like a pick",
    description="Idempotent: liking a pick you already like changes nothing.",
)
def like_pick(pick_id: str, user: CurrentUserDep, db: DbDep, now: NowDep) -> LikeStateOut:
    pick, _ = service.find_open_pick(db, user.id, pick_id)
    if db.get(CommunityLike, (pick.id, user.id)) is None:
        db.add(CommunityLike(pick_id=pick.id, user_id=user.id, created_at=now))
        try:
            db.commit()
        except IntegrityError:  # liked in a concurrent request: same end state
            db.rollback()
    return _like_state(db, user.id, pick.id)


@router.delete(
    "/picks/{pick_id}/like",
    response_model=LikeStateOut,
    operation_id="unlike_pick",
    summary="Remove your like",
    description="Idempotent: removing a like that is not there changes nothing.",
)
def unlike_pick(pick_id: str, user: CurrentUserDep, db: DbDep) -> LikeStateOut:
    pick, _ = service.find_pick(db, user.id, pick_id)
    like = db.get(CommunityLike, (pick.id, user.id))
    if like is not None:
        db.delete(like)
        db.commit()
    return _like_state(db, user.id, pick.id)


# ------------------------------------------------------------------- comments
@router.post(
    "/picks/{pick_id}/comments",
    response_model=CommentOut,
    status_code=201,
    operation_id="create_comment",
    summary="Comment on a pick",
    description=(
        "Plain text, at most 500 characters, stored and returned exactly as sent: "
        "clients escape it when they render it. A body with a link is "
        "`422 links_not_allowed`; one that breaks a content rule is "
        "`422 content_not_allowed` with `details.rule`. 30 comments per hour. Needs a "
        "public profile (`403 profile_required`)."
    ),
    responses={**_PROFILE_REQUIRED, **RATE_LIMIT_RESPONSE},
)
def create_comment(
    pick_id: str,
    body: CommentCreate,
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    settings: SettingsDep,
    now: NowDep,
) -> CommentOut:
    profile = service.require_posting_profile(db, user)
    pick, _ = service.find_open_pick(db, user.id, pick_id)
    text = service.checked_text("body", body.body, required=True)
    assert text is not None
    check_user_quota(
        request,
        "community_hour_limiter",
        f"comment:{user.id}",
        settings.community_comments_per_hour,
    )
    comment = CommunityComment(pick_id=pick.id, user_id=user.id, body=text, created_at=now)
    db.add(comment)
    db.flush()
    write_audit(
        db,
        request,
        "community.comment_created",
        user_id=user.id,
        entity_type="community_comment",
        entity_id=comment.id,
        details={"pick_id": pick.id},
    )
    if pick.user_id != user.id:
        delivered = notifications.notify(
            db,
            pick.user_id,
            templates.pick_comment(
                comment_id=comment.id,
                pick_id=pick.id,
                handle=profile.handle,
                selection=pick.selection,
            ),
        )
        if delivered == "delivered":
            notifications.trim(db, pick.user_id)
    db.commit()
    use_user_quota(request, "community_hour_limiter", f"comment:{user.id}")
    return service.comment_out(comment, profile.handle, user.id)


@router.get(
    "/picks/{pick_id}/comments",
    response_model=CommentPageOut,
    operation_id="list_comments",
    summary="Comments on a pick, newest first",
    description=(
        "Without comments of people you blocked or who blocked you, hidden or removed "
        "comments and comments of suspended accounts. Your own comment that moderators "
        "removed is listed for you with a null `body` and `moderation_note`."
    ),
)
def list_comments(
    pick_id: str,
    user: CurrentUserDep,
    db: DbDep,
    before: Before = None,
    limit: Limit = 50,
) -> CommentPageOut:
    pick, _ = service.find_pick(db, user.id, pick_id)
    page, cursor = service.comments_page(db, user.id, pick.id, before, limit)
    return CommentPageOut(
        items=[service.comment_out(comment, handle, user.id) for comment, handle in page],
        next_before=cursor,
    )


@router.delete(
    "/comments/{comment_id}",
    status_code=204,
    operation_id="delete_comment",
    summary="Delete a comment (its author or a moderator)",
    description=(
        "The author can delete their own comment. An administrator can delete any "
        "comment; that is recorded in the audit log as a moderator action. Anyone else "
        "gets `403 forbidden`."
    ),
    responses={403: {"model": ErrorResponse, "description": "Not your comment"}},
)
def delete_comment(comment_id: str, user: CurrentUserDep, db: DbDep, request: Request) -> Response:
    is_moderator = user.role == "admin"
    if is_moderator:
        comment = db.get(CommunityComment, comment_id)
        if comment is None:
            raise not_found("Comment", comment_id[:32])
    else:
        comment, _ = service.find_comment(db, user.id, comment_id)
        if comment.user_id != user.id:
            raise ApiError(403, "forbidden", "Only the author or a moderator can delete a comment")
    by_moderator = comment.user_id != user.id
    db.delete(comment)
    write_audit(
        db,
        request,
        "community.comment_deleted",
        user_id=user.id,
        entity_type="community_comment",
        entity_id=comment_id,
        details={
            "pick_id": comment.pick_id,
            "by_moderator": by_moderator,
            **({"author_id": comment.user_id} if by_moderator else {}),
        },
    )
    db.commit()
    return Response(status_code=204)


# -------------------------------------------------------------------- follows
@router.post(
    "/follows/{handle}",
    response_model=FollowStateOut,
    operation_id="follow_profile",
    summary="Follow a profile",
    description=(
        "Idempotent. You cannot follow yourself (`422 cannot_follow_self`) or a profile "
        "you blocked (`409 profile_blocked`); a profile that blocked you is `404`, like "
        "one that does not exist. Needs a public profile (`403 profile_required`). The "
        "followed profile gets one `new_follower` notification."
    ),
    responses={**_PROFILE_REQUIRED, **_CONFLICT, **RATE_LIMIT_RESPONSE},
)
def follow_profile(
    handle: str,
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    settings: SettingsDep,
    now: NowDep,
) -> FollowStateOut:
    mine = service.require_posting_profile(db, user)
    target = service.find_profile(db, user.id, handle)
    if target.user_id == user.id:
        raise service.invalid("cannot_follow_self", "You cannot follow your own profile")
    if db.get(CommunityBlock, (user.id, target.user_id)) is not None:
        raise ApiError(409, "profile_blocked", "Unblock this profile before following it")
    if db.get(CommunityFollow, (user.id, target.user_id)) is None:
        check_user_quota(
            request,
            "community_hour_limiter",
            f"follow:{user.id}",
            settings.community_follows_per_hour,
        )
        db.add(CommunityFollow(follower_id=user.id, followed_id=target.user_id, created_at=now))
        write_audit(
            db,
            request,
            "community.followed",
            user_id=user.id,
            entity_type="community_profile",
            entity_id=target.user_id,
        )
        delivered = notifications.notify(
            db, target.user_id, templates.new_follower(follower_id=user.id, handle=mine.handle)
        )
        if delivered == "delivered":
            notifications.trim(db, target.user_id)
        try:
            db.commit()
        except IntegrityError:  # followed in a concurrent request: same end state
            db.rollback()
        else:
            use_user_quota(request, "community_hour_limiter", f"follow:{user.id}")
    return FollowStateOut(handle=target.handle, is_following=True)


@router.delete(
    "/follows/{handle}",
    status_code=204,
    operation_id="unfollow_profile",
    summary="Stop following a profile",
    description="Idempotent: `204` whether or not you were following it.",
)
def unfollow_profile(handle: str, user: CurrentUserDep, db: DbDep, request: Request) -> Response:
    target = service.profile_by_handle(db, handle)
    follow = db.get(CommunityFollow, (user.id, target.user_id)) if target else None
    if follow is not None and target is not None:
        db.delete(follow)
        write_audit(
            db,
            request,
            "community.unfollowed",
            user_id=user.id,
            entity_type="community_profile",
            entity_id=target.user_id,
        )
        db.commit()
    return Response(status_code=204)


@router.get(
    "/following",
    response_model=FollowListOut,
    operation_id="list_following",
    summary="Profiles you follow, most recent first",
)
def list_following(user: CurrentUserDep, db: DbDep) -> FollowListOut:
    return FollowListOut(items=service.follow_entries(db, user.id, followers=False))


@router.get(
    "/followers",
    response_model=FollowListOut,
    operation_id="list_followers",
    summary="Profiles that follow you, most recent first",
)
def list_followers(user: CurrentUserDep, db: DbDep) -> FollowListOut:
    return FollowListOut(items=service.follow_entries(db, user.id, followers=True))


# --------------------------------------------------------------------- blocks
@router.put(
    "/blocks/{handle}",
    response_model=BlockStateOut,
    operation_id="block_profile",
    summary="Block a profile",
    description=(
        "Idempotent. Removes the follow in both directions and hides each of you from "
        "the other everywhere: profiles, picks, feed, comments, follower lists and the "
        "leaderboard. The blocked person is not told. You do not need a profile to "
        "block someone."
    ),
)
def block_profile(
    handle: str, user: CurrentUserDep, db: DbDep, request: Request, now: NowDep
) -> BlockStateOut:
    target = service.find_profile(db, user.id, handle)
    if target.user_id == user.id:
        raise service.invalid("cannot_block_self", "You cannot block your own profile")
    if db.get(CommunityBlock, (user.id, target.user_id)) is None:
        db.add(CommunityBlock(blocker_id=user.id, blocked_id=target.user_id, created_at=now))
        removed = service.remove_follows_between(db, user.id, target.user_id)
        write_audit(
            db,
            request,
            "community.blocked",
            user_id=user.id,
            entity_type="community_profile",
            entity_id=target.user_id,
            details={"follows_removed": removed},
        )
        try:
            db.commit()
        except IntegrityError:  # blocked in a concurrent request: same end state
            db.rollback()
    return BlockStateOut(handle=target.handle, is_blocked=True)


@router.delete(
    "/blocks/{handle}",
    status_code=204,
    operation_id="unblock_profile",
    summary="Unblock a profile",
    description=(
        "Idempotent: `204` whether or not it was blocked. Follows removed by the block "
        "are not restored."
    ),
)
def unblock_profile(handle: str, user: CurrentUserDep, db: DbDep, request: Request) -> Response:
    target = service.profile_by_handle(db, handle)
    block = db.get(CommunityBlock, (user.id, target.user_id)) if target else None
    if block is not None and target is not None:
        db.delete(block)
        write_audit(
            db,
            request,
            "community.unblocked",
            user_id=user.id,
            entity_type="community_profile",
            entity_id=target.user_id,
        )
        db.commit()
    return Response(status_code=204)


@router.get(
    "/blocks",
    response_model=BlockListOut,
    operation_id="list_blocks",
    summary="Profiles you blocked",
)
def list_blocks(user: CurrentUserDep, db: DbDep) -> BlockListOut:
    return BlockListOut(items=service.block_entries(db, user.id))


# -------------------------------------------------------------------- reports
@router.post(
    "/reports",
    response_model=ReportOut,
    status_code=201,
    operation_id="create_report",
    summary="Report a pick, a comment or a profile to the moderators",
    description=(
        "`target_id` is the pick id, the comment id or, for a profile, its handle. The "
        "target has to be something you can see (`404` otherwise) and not your own "
        "(`422 cannot_report_own_content`). One open report per person and target: "
        "reporting the same thing again returns the open report with `200`. 10 reports "
        "per hour. The reported person is not told who reported them. A copy of the "
        "reported text (analysis, comment or handle and bio) is kept with the report for "
        "the moderators, and deleted with it; it is not returned to you."
    ),
    responses={
        200: {"model": ReportOut, "description": "You already have an open report on it"},
        **RATE_LIMIT_RESPONSE,
    },
)
def create_report(
    body: ReportCreate,
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
    now: NowDep,
) -> ReportOut:
    target = service.resolve_report_target(db, user.id, body)
    target_id, author_id = target.target_id, target.author_id
    details = body.details.strip() if body.details and body.details.strip() else None
    if details is not None and service.CONTROL_CHARS.search(details):
        raise service.invalid(
            "invalid_text", "The details contain characters that are not allowed", field="details"
        )
    existing = service.open_report(db, user.id, body.target_type, author_id, target_id)
    if existing is not None:
        response.status_code = 200
        return service.report_out(existing)
    check_user_quota(
        request, "community_hour_limiter", f"report:{user.id}", settings.community_reports_per_hour
    )
    report = CommunityReport(
        reporter_id=user.id,
        target_type=body.target_type,
        target_id=target_id,
        target_user_id=author_id,
        reason=body.reason,
        details=details,
        status="open",
        created_at=now,
        # A copy for the moderator, in case the author deletes or edits it meanwhile.
        target_text_snapshot=target.text,
        target_summary_snapshot=target.summary,
    )
    db.add(report)
    db.flush()
    write_audit(
        db,
        request,
        "community.reported",
        user_id=user.id,
        entity_type="community_report",
        entity_id=report.id,
        details={"target_type": body.target_type, "target_id": target_id, "reason": body.reason},
    )
    db.commit()
    use_user_quota(request, "community_hour_limiter", f"report:{user.id}")
    return service.report_out(report)


# ---------------------------------------------------------------- leaderboard
@router.get(
    "/leaderboard",
    response_model=LeaderboardOut,
    operation_id="get_leaderboard",
    summary="Profiles ranked by the Wilson lower bound of their win rate",
    description=(
        "Behind a second flag, `community_leaderboard`, which is off by default: "
        "leaderboards need a responsible-gambling review before they go live. Only "
        "profiles with at least 30 graded picks in the window are ranked, by the lower "
        "bound of the Wilson 95% interval of their win rate, not by the raw win rate "
        "and not by ROI. The price of the picks is not part of the order either, so a "
        "high win rate at short prices can rank first and still lose money. Each row "
        "shows the sample size, the interval, the average price and the flat-stake "
        "return. `caveat` says that past results do not predict future results."
    ),
    dependencies=[Depends(require_flag("community_leaderboard"))],
)
def get_leaderboard(
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    provider: ProviderDep,
    league: Annotated[str | None, Query(max_length=32)] = None,
    window: Annotated[LeaderboardWindow, Query()] = "90d",
) -> LeaderboardOut:
    service.grade_if_due(request, db, provider)
    return service.leaderboard(
        db,
        user.id,
        provider.now(),
        window,
        league.strip().lower() if league and league.strip() else None,
        provider.data_mode,
    )
