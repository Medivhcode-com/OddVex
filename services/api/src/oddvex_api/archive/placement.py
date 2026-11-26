"""The best price across the user's books at a stored bet's placement time.

For each leg, ``placement_prices`` answers either ``priced`` (the best open, non-stale
price overall and at the user's books, read from the archive as of ``placed_at`` through
the live :class:`Board` code) or ``cannot_price`` with a named reason. It never guesses:
an unstructured leg, an event the archive does not cover at ``placed_at``, or quotes that
were stale then all say so (hard rule 3).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..board import BestQuote, Board
from ..config import Settings
from ..db import Bet, BetLeg
from ..errors import ApiError
from ..providers import Event, SportsDataProvider
from ..schemas import price_out
from ..textnorm import fold
from .schemas import ArchivedBestOut, LegPlacementPriceOut
from .service import coverage_out
from .view import ArchiveView, board_at

CANNOT_PRICE_REASONS = (
    "leg_not_structured",
    "not_captured",
    "archive_gap",
    "archive_pruned",
    "stale_at_placement",
    "no_usable_quote",
)
#: Markets the archive can price; anything else is ``leg_not_structured``.
STRUCTURED_MARKETS = ("moneyline", "spread", "total")
#: Most sportsbooks the ``books`` parameter may list.
MAX_BOOKS = 20


def resolve_books(
    session: Session, provider: SportsDataProvider, user_id: str, books: str | None
) -> tuple[list[str], str]:
    """The user's books as provider sportsbook keys, and where they came from.

    1. The ``books`` query parameter: a comma list of at most 20 keys the provider has
       (422 ``unknown_sportsbook`` or ``too_many_books`` otherwise).
    2. The profile's books held, once P0.4 exists (not built yet).
    3. The books of the user's own recorded bets, matched to a provider sportsbook by its
       folded key or name.
    4. None.
    """
    known = provider.list_sportsbooks()
    keys = [b.key for b in known]
    if books is not None and books.strip():
        wanted = list(dict.fromkeys(k.strip() for k in books.split(",") if k.strip()))
        if len(wanted) > MAX_BOOKS:
            raise ApiError(
                422,
                "too_many_books",
                f"At most {MAX_BOOKS} sportsbooks",
                details={"max": MAX_BOOKS},
            )
        unknown = [k for k in wanted if k not in keys]
        if unknown:
            raise ApiError(
                422,
                "unknown_sportsbook",
                "Unknown sportsbook key",
                details={"unknown": unknown[:MAX_BOOKS]},
            )
        return wanted, "query"
    # P0.4 inserts the profile's books held here.
    by_fold: dict[str, str] = {}
    for book in known:
        by_fold.setdefault(fold(book.key), book.key)
        by_fold.setdefault(fold(book.name), book.key)
    stored = set(
        session.scalars(select(Bet.sportsbook_key).where(Bet.user_id == user_id).distinct())
    )
    found = {by_fold[s] for s in stored if s and s in by_fold}
    if found:
        return [k for k in keys if k in found], "bets"
    return [], "none"


def _structured(leg: BetLeg) -> bool:
    if not leg.event_id or not leg.outcome_key or leg.market not in STRUCTURED_MARKETS:
        return False
    return leg.market == "moneyline" or leg.line is not None


def _stale_only(
    board: Board, event: Event, market: str, outcome_key: str, line: float | None
) -> bool:
    """Whether open, fully priced quotes for the outcome (on the leg's line) existed but
    every one was stale at placement. Called only when no usable quote was found."""
    for snap, status, stale, prices in board._quote_rows(event, market):
        if status != "open" or len(prices) < 2:
            continue
        if (
            any(
                o.key == outcome_key and (market == "moneyline" or o.line == line)
                for o in snap.outcomes
            )
            and stale
        ):
            return True
    return False


def _best_out(
    view: ArchiveView, event_id: str, market: str, best: BestQuote, ids: dict[str, str]
) -> ArchivedBestOut:
    row = view.served[(event_id, market, ids.get(best.sportsbook.key, best.sportsbook.key))]
    return ArchivedBestOut(
        price=price_out(best.price),
        sportsbook=best.sportsbook,
        line=best.line,
        captured_at=row.captured_at,
        last_updated=row.last_updated,
    )


def _leg_price(
    view: ArchiveView, leg: BetLeg, book_ids: set[str], ids: dict[str, str]
) -> LegPlacementPriceOut:
    line = float(leg.line) if leg.line is not None else None
    answer = LegPlacementPriceOut(
        leg_id=leg.id,
        position=leg.position,
        event_id=leg.event_id,
        market=leg.market,
        outcome_key=leg.outcome_key,
        line=line,
        your_price=price_out(leg.odds_decimal),
        status="cannot_price",
        your_books_reason=None if book_ids else "books_unknown",
    )
    if not _structured(leg):
        return answer.model_copy(update={"reason": "leg_not_structured"})
    assert leg.event_id is not None and leg.outcome_key is not None
    coverage = view.coverage(leg.event_id)
    answer = answer.model_copy(update={"coverage": coverage_out(coverage)})
    event = view.get_event(leg.event_id)
    if coverage.status != "captured" or event is None:
        return answer.model_copy(update={"reason": coverage.status})
    board = board_at(view, coverage)
    market_line = None if leg.market == "moneyline" else line
    overall = board.best_price(event, leg.market, leg.outcome_key, line=market_line)
    yours = (
        board.best_price(event, leg.market, leg.outcome_key, line=market_line, books=book_ids)
        if book_ids
        else None
    )
    update: dict[str, object] = {}
    if overall is not None:
        update["best_overall"] = _best_out(view, event.id, leg.market, overall, ids)
    if yours is not None:
        update.update(
            status="priced",
            best_at_your_books=_best_out(view, event.id, leg.market, yours, ids),
            your_books_reason=None,
        )
    elif overall is not None:
        update["your_books_reason"] = "none_at_your_books" if book_ids else "books_unknown"
    elif _stale_only(board, event, leg.market, leg.outcome_key, market_line):
        update["reason"] = "stale_at_placement"
    else:
        update["reason"] = "no_usable_quote"
    return answer.model_copy(update=update)


def placement_prices(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    bet: Bet,
    books: Sequence[str],
) -> list[LegPlacementPriceOut]:
    """One answer per leg of ``bet``, in leg order. ``books`` are provider sportsbook keys."""
    view = ArchiveView(session, provider, bet.placed_at, settings)
    ids = {b.key: b.id for b in provider.list_sportsbooks()}
    book_ids = {ids[key] for key in books if key in ids}
    return [_leg_price(view, leg, book_ids, ids) for leg in bet.legs]


__all__ = [
    "CANNOT_PRICE_REASONS",
    "MAX_BOOKS",
    "STRUCTURED_MARKETS",
    "placement_prices",
    "resolve_books",
]
