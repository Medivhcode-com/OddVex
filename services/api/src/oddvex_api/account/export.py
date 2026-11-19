"""The account export as a stream.

One JSON document of the shape :class:`.schemas.AccountExportOut` describes, written out
piece by piece. The three parts that grow with an account for as long as it is used, its
bets, its import runs and its audit entries, are read from the database in batches and
written as they are read, so the size of the account decides how long the response is,
not how much memory it takes. Everything else in the document has a cap of its own
(watchlist items, alert rules, notifications, one sync connection per provider) and is
built in one go before the first byte is sent, so an error there is still an ordinary
error response.

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
from ..db import (
    AlertRule,
    AuditLog,
    Bet,
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

#: The keys of the document that are streamed.
_STREAMED = ("bets", "sync_runs", "audit_log")

Key = tuple[datetime, str]


def _head(app: FastAPI, session: Session, user: User) -> dict[str, Any]:
    """Everything except the streamed parts, as JSON-ready values in document order."""
    board = Board(app.state.provider, app.state.settings, app.state.cache)
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
        community=community_service.export_out(session, user.id, board.provider.data_mode),
    )
    return document.model_dump(mode="json")


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


def _read_batch(
    session_factory: sessionmaker[Session],
    rows_of_user: Select[Any],
    when: InstrumentedAttribute[datetime],
    ident: InstrumentedAttribute[str],
    after: Key | None,
    size: int,
    as_json: Callable[[Any], str],
) -> tuple[list[str], Key | None]:
    """Up to ``size`` rows after the key ``after``, oldest first, as JSON texts, and the
    key of the last one. Read in a session of its own; the rows are not kept."""
    query = rows_of_user
    if after is not None:
        query = query.where(or_(when > after[0], and_(when == after[0], ident > after[1])))
    with session_factory() as session:
        rows = list(session.scalars(query.order_by(when, ident).limit(size)))
        texts = [as_json(row) for row in rows]
        return texts, (getattr(rows[-1], when.key), getattr(rows[-1], ident.key)) if rows else None


def _array(
    session_factory: sessionmaker[Session],
    rows_of_user: Select[Any],
    when: InstrumentedAttribute[datetime],
    ident: InstrumentedAttribute[str],
    size: Callable[[], int],
    as_json: Callable[[Any], str],
) -> Iterator[bytes]:
    """The elements of a JSON array, one chunk per batch, without the brackets.

    The rows are paged on the key ``(when, ident)``, which is unique, so rows that share a
    timestamp are neither repeated nor lost where one batch ends and the next begins.
    """
    after: Key | None = None
    first = True
    while True:
        limit = size()
        texts, last = _read_batch(session_factory, rows_of_user, when, ident, after, limit, as_json)
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


def _chunks(
    session_factory: sessionmaker[Session], user_id: str, head: dict[str, Any]
) -> Iterator[bytes]:
    streamed: dict[str, Callable[[], Iterator[bytes]]] = {
        "bets": lambda: _array(
            session_factory,
            select(Bet).where(Bet.user_id == user_id),
            Bet.placed_at,
            Bet.id,
            lambda: BET_BATCH,
            lambda bet: bets_service.bet_json(bet).decode(),
        ),
        "sync_runs": lambda: _array(
            session_factory,
            select(SyncImportRun)
            .join(SyncConnection, SyncImportRun.connection_id == SyncConnection.id)
            .where(SyncConnection.user_id == user_id),
            SyncImportRun.started_at,
            SyncImportRun.id,
            lambda: RUN_BATCH,
            lambda run: sync_service.run_out(run).model_dump_json(),
        ),
        "audit_log": lambda: _array(
            session_factory,
            select(AuditLog).where(AuditLog.user_id == user_id),
            AuditLog.created_at,
            AuditLog.id,
            lambda: AUDIT_BATCH,
            _audit_json,
        ),
    }
    for index, (key, value) in enumerate(head.items()):
        opening = b"{" if index == 0 else b","
        name = to_json(key) + b":"
        if key in streamed:
            yield opening + name + b"["
            yield from streamed[key]()
            yield b"]"
        else:
            yield opening + name + to_json(value)
    yield b"}"


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
        head = _head(app, session, user)
    missing = [key for key in _STREAMED if key not in head]
    if missing:  # pragma: no cover - the response model has these keys
        raise RuntimeError(f"AccountExportOut no longer has {missing}")
    return _chunks(session_factory, user_id, head)


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
