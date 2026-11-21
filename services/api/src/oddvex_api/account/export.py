"""The account export as a stream.

One JSON document of the shape :class:`.schemas.AccountExportOut` describes, written out
piece by piece. The parts that grow with an account for as long as it is used are read
from the database in batches and written as they are read: its bets, its import runs, its
audit entries, and its community picks, comments and reports. So the size of the account
decides how long the response is, not how much memory it takes. Everything else is built
in one go before the first byte is sent, so an error there is still an ordinary error
response: the parts with a cap of their own (watchlist items, alert rules, notifications,
one sync connection per provider) and three lists of short texts that can only be as long
as the community is large (handles followed, handles blocked, ids of liked picks).

The text is what the response model serialises to: same keys, same order, same number
and date formats. Clients keep parsing it as one JSON document.

While a client is reading, the stream holds one batch as text and no database
connection: each batch opens a session, reads, and closes it before the batch is handed
on. The batches are separate reads, not one snapshot: a row that is changed while its own
account is being exported can be in the document in its old or its new state.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic_core import to_json
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session, sessionmaker

from ..alerts import service as alerts_service
from ..auth.schemas import UserOut
from ..bets import service as bets_service
from ..board import Board
from ..community import service as community_service
from ..community.schemas import CommunityExportOut
from ..db import (
    AlertRule,
    AuditLog,
    Bet,
    CommunityBlock,
    CommunityComment,
    CommunityFollow,
    CommunityLike,
    CommunityPick,
    CommunityProfile,
    CommunityReport,
    Notification,
    SyncConnection,
    SyncImportRun,
    User,
    WatchlistItem,
    utcnow,
)
from ..errors import not_found
from ..notifications import service as notifications_service
from ..ratelimit import UserStreamResponse
from ..sync import service as sync_service
from ..watchlist import service as watchlist_service
from .schemas import AccountExportOut, ExportAuditEntryOut

#: Bets read and written per batch. A bet can carry 20 legs and 2,000 characters of
#: notes, about 20 KB of JSON, so a batch is about a megabyte of text.
BET_BATCH = 50
#: Import runs and audit entries read and written per batch. They are small.
RUN_BATCH = 1000
AUDIT_BATCH = 1000
#: Community picks, comments and reports read and written per batch. A pick carries up to
#: 1,000 characters of analysis, a comment or a report up to 500 characters.
PICK_BATCH = 200
COMMENT_BATCH = 1000
REPORT_BATCH = 1000

Key = tuple[datetime, str]
#: Turns one batch of rows into JSON texts, inside the session that read them.
ToTexts = Callable[[Session, list[Any]], list[str]]


def _community_head(session: Session, user_id: str) -> tuple[CommunityExportOut, str]:
    """The community part without its picks, comments and reports, which are streamed,
    and the handle those carry as their author ("" without a profile).

    The profile and the three short lists are read the way
    ``community.service.export_out`` reads them; the document is the same.
    """
    profile = community_service.get_own_profile(session, user_id)
    following = session.scalars(
        select(CommunityProfile.handle)
        .join(CommunityFollow, CommunityFollow.followed_id == CommunityProfile.user_id)
        .where(CommunityFollow.follower_id == user_id)
        .order_by(CommunityProfile.handle)
    )
    blocks = session.scalars(
        select(CommunityProfile.handle)
        .join(CommunityBlock, CommunityBlock.blocked_id == CommunityProfile.user_id)
        .where(CommunityBlock.blocker_id == user_id)
        .order_by(CommunityProfile.handle)
    )
    likes = session.scalars(
        select(CommunityLike.pick_id)
        .where(CommunityLike.user_id == user_id)
        .order_by(CommunityLike.created_at, CommunityLike.pick_id)
    )
    head = CommunityExportOut(
        profile=community_service.my_profile_out(session, profile) if profile else None,
        picks=[],
        comments=[],
        following=list(following),
        likes=list(likes),
        blocks=list(blocks),
        reports=[],
    )
    return head, profile.handle if profile else ""


def _head(app: FastAPI, session: Session, user: User) -> tuple[dict[str, Any], str, str]:
    """Everything except the streamed parts, as JSON-ready values in document order, then
    the user's community handle and the provider's data mode (both go on every pick)."""
    board = Board(app.state.provider, app.state.settings, app.state.cache)
    community, handle = _community_head(session, user.id)
    registry = app.state.sync_registry
    watchlist = session.scalars(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.created_at, WatchlistItem.id)
    )
    connections = list(
        session.scalars(
            select(SyncConnection)
            .where(SyncConnection.user_id == user.id)
            .order_by(SyncConnection.created_at, SyncConnection.id)
        )
    )
    alerts = session.scalars(
        select(AlertRule)
        .where(AlertRule.user_id == user.id)
        .order_by(AlertRule.created_at, AlertRule.id)
    )
    notifications = session.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at, Notification.id)
    )
    document = AccountExportOut(
        exported_at=utcnow(),
        format_version=1,
        user=UserOut.model_validate(user),
        bets=[],
        watchlist=[watchlist_service.item_out(board, item) for item in watchlist],
        sync_connections=[
            sync_service.connection_out(session, c, registry.get(c.provider)) for c in connections
        ],
        sync_runs=[],
        audit_log=[],
        alerts=[alerts_service.rule_out(board, rule) for rule in alerts],
        notifications=[notifications_service.notification_out(row) for row in notifications],
        notification_preferences=notifications_service.preferences_out(session, user.id),
        stake_reminder=notifications_service.stake_reminder_out(session, user.id, board.now),
        community=community,
    )
    return document.model_dump(mode="json"), handle, board.provider.data_mode


def _audit_json(row: AuditLog) -> str:
    return ExportAuditEntryOut(
        id=row.id,
        created_at=row.created_at,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        ip=row.ip,
        request_id=row.request_id,
        details=row.details,
    ).model_dump_json()


def _each(as_json: Callable[[Any], str]) -> ToTexts:
    """:data:`ToTexts` for rows that are turned into JSON one by one."""
    return lambda _session, rows: [as_json(row) for row in rows]


def _read_batch(
    session_factory: sessionmaker[Session],
    rows_of_user: Select[Any],
    when: InstrumentedAttribute[datetime],
    ident: InstrumentedAttribute[str],
    after: Key | None,
    size: int,
    to_texts: ToTexts,
) -> tuple[list[str], Key | None]:
    """Up to ``size`` rows after the key ``after``, oldest first, as JSON texts, and the
    key of the last one. Read in a session of its own; the rows are not kept."""
    query = rows_of_user
    if after is not None:
        query = query.where(or_(when > after[0], and_(when == after[0], ident > after[1])))
    with session_factory() as session:
        rows = list(session.scalars(query.order_by(when, ident).limit(size)))
        texts = to_texts(session, rows) if rows else []
        return texts, (getattr(rows[-1], when.key), getattr(rows[-1], ident.key)) if rows else None


def _array(
    session_factory: sessionmaker[Session],
    rows_of_user: Select[Any],
    when: InstrumentedAttribute[datetime],
    ident: InstrumentedAttribute[str],
    size: Callable[[], int],
    to_texts: ToTexts,
) -> Iterator[bytes]:
    """The elements of a JSON array, one chunk per batch, without the brackets.

    The rows are paged on the key ``(when, ident)``, which is unique, so rows that share a
    timestamp are neither repeated nor lost where one batch ends and the next begins.
    """
    after: Key | None = None
    first = True
    while True:
        limit = size()
        texts, last = _read_batch(
            session_factory, rows_of_user, when, ident, after, limit, to_texts
        )
        if not texts:
            return
        full = len(texts) >= limit
        chunk = (",".join(texts) if first else "," + ",".join(texts)).encode()
        first = False
        after = last
        # Only the chunk is held while the client reads it, and nothing while the next
        # batch is read.
        del texts
        yield chunk
        del chunk
        if not full:
            return


def _object(value: dict[str, Any], streamed: dict[str, Any]) -> Iterator[bytes]:
    """``value`` as a JSON object, key by key in its own order.

    A key named in ``streamed`` is not taken from ``value``: a callable there yields the
    elements of an array (see :func:`_array`), a dictionary describes a nested object
    with streamed keys of its own.
    """
    opening = b"{"
    for key, item in value.items():
        name = opening + to_json(key) + b":"
        opening = b","
        part = streamed.get(key)
        if part is None:
            yield name + to_json(item)
        elif callable(part):
            yield name + b"["
            yield from part()
            yield b"]"
        else:
            yield name
            yield from _object(item, part)
    yield b"}" if opening == b"," else b"{}"


def _missing(value: Any, streamed: dict[str, Any], path: str = "") -> list[str]:
    """Streamed keys the document does not have (none, while the response model has them)."""
    missing: list[str] = []
    for key, part in streamed.items():
        if not isinstance(value, dict) or key not in value:
            missing.append(path + key)
        elif isinstance(part, dict):
            missing += _missing(value[key], part, f"{path}{key}.")
    return missing


def _chunks(
    session_factory: sessionmaker[Session],
    user_id: str,
    head: dict[str, Any],
    handle: str,
    data_mode: str,
) -> Iterator[bytes]:
    def picks_json(session: Session, rows: list[Any]) -> list[str]:
        # One call per batch: the like and comment counts of the batch are two queries.
        pairs = [(pick, handle) for pick in rows]
        outs = community_service.pick_outs(session, user_id, pairs, data_mode)
        return [out.model_dump_json() for out in outs]

    streamed: dict[str, Any] = {
        "bets": lambda: _array(
            session_factory,
            select(Bet).where(Bet.user_id == user_id),
            Bet.placed_at,
            Bet.id,
            lambda: BET_BATCH,
            _each(lambda bet: bets_service.bet_json(bet).decode()),
        ),
        "sync_runs": lambda: _array(
            session_factory,
            select(SyncImportRun)
            .join(SyncConnection, SyncImportRun.connection_id == SyncConnection.id)
            .where(SyncConnection.user_id == user_id),
            SyncImportRun.started_at,
            SyncImportRun.id,
            lambda: RUN_BATCH,
            _each(lambda run: sync_service.run_out(run).model_dump_json()),
        ),
        "audit_log": lambda: _array(
            session_factory,
            select(AuditLog).where(AuditLog.user_id == user_id),
            AuditLog.created_at,
            AuditLog.id,
            lambda: AUDIT_BATCH,
            _each(_audit_json),
        ),
        "community": {
            "picks": lambda: _array(
                session_factory,
                select(CommunityPick).where(CommunityPick.user_id == user_id),
                CommunityPick.posted_at,
                CommunityPick.id,
                lambda: PICK_BATCH,
                picks_json,
            ),
            "comments": lambda: _array(
                session_factory,
                select(CommunityComment).where(CommunityComment.user_id == user_id),
                CommunityComment.created_at,
                CommunityComment.id,
                lambda: COMMENT_BATCH,
                _each(
                    lambda comment: community_service.comment_out(
                        comment, handle, user_id
                    ).model_dump_json()
                ),
            ),
            "reports": lambda: _array(
                session_factory,
                select(CommunityReport).where(CommunityReport.reporter_id == user_id),
                CommunityReport.created_at,
                CommunityReport.id,
                lambda: REPORT_BATCH,
                _each(lambda report: community_service.report_out(report).model_dump_json()),
            ),
        },
    }
    missing = _missing(head, streamed)
    if missing:  # pragma: no cover - the response model has these keys
        raise RuntimeError(f"AccountExportOut no longer has {missing}")
    return _object(head, streamed)


def stream_export(app: FastAPI, user_id: str) -> Iterator[bytes]:
    """The export of ``user_id`` as chunks of one JSON document.

    The fixed part of the document is built before this returns, so anything that goes
    wrong there is raised here, to the caller, and not in the middle of the response.
    Callers write their audit entry first: the export includes the user's audit entries.
    """
    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        user = session.get(User, user_id)
        if user is None:
            raise not_found("User", user_id)
        head, handle, data_mode = _head(app, session, user)
    return _chunks(session_factory, user_id, head, handle, data_mode)


def export_response(
    app: FastAPI, user_id: str, release: Callable[[], None] | None = None
) -> StreamingResponse:
    """:func:`stream_export` as an HTTP response (``application/json``, no length).

    ``release`` is the call :func:`ratelimit.take_user_stream_slot` returned, when the
    caller counts the response against the streams one user can have in progress: it is
    called when the response ends. Any error is raised before a response exists; the
    caller then gives the slot back itself.
    """
    chunks = stream_export(app, user_id)
    if release is None:
        return StreamingResponse(chunks, media_type="application/json")
    return UserStreamResponse(chunks, release, media_type="application/json")
