"""Best price against the no-vig consensus of the *other* books.

Pure functions. A "discrepancy" here only means one book's price is longer than the
average fair price implied by the other books at the same line. That average can be
wrong, so this is a description of prices, not a prediction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .errors import QuantError
from .ev import EVResult, expected_value
from .novig import no_vig
from .odds import Number, validate_decimal_odds

#: Other books needed before a consensus is reported.
MIN_CONSENSUS_BOOKS = 2


@dataclass(frozen=True, slots=True)
class BookQuote:
    """One book's decimal prices for every outcome of one market at one line."""

    book: str
    prices: Sequence[Number]


@dataclass(frozen=True, slots=True)
class ValueResult:
    #: The book offering the best price and that price.
    best_book: str
    best_price: Decimal
    #: Mean no-vig probability of the outcome over the other books.
    consensus_probability: float
    #: How many books that mean covers (the best book is never one of them).
    books_in_consensus: int
    #: EV of the best price if the consensus probability were the true probability.
    ev: EVResult


def consensus_probability(quotes: Sequence[BookQuote], outcome_index: int) -> float:
    """Mean multiplicative no-vig probability of one outcome over ``quotes``."""
    if not quotes:
        raise QuantError("a consensus needs at least one book", code="invalid_market")
    total = 0.0
    for quote in quotes:
        if not 0 <= outcome_index < len(quote.prices):
            raise QuantError(
                f"book {quote.book!r} has no outcome {outcome_index}", code="invalid_market"
            )
        total += no_vig(quote.prices).fair_probabilities[outcome_index]
    return total / len(quotes)


def best_price_vs_consensus(
    quotes: Sequence[BookQuote],
    outcome_index: int,
    min_other_books: int = MIN_CONSENSUS_BOOKS,
) -> ValueResult | None:
    """Compare the best price for one outcome with the consensus of the other books.

    ``quotes`` are the comparable books: open, fresh and on the same line. The best book
    is the one with the highest price for the outcome (the first one wins a tie). It is
    left out of the consensus, so its own price cannot pull the consensus towards
    itself. Returns ``None`` when fewer than ``min_other_books`` other books remain.
    """
    if min_other_books < 1:
        raise QuantError("min_other_books must be at least 1")
    if len({quote.book for quote in quotes}) != len(quotes):
        raise QuantError("each book can be quoted once per market", code="invalid_market")
    if len(quotes) < min_other_books + 1:
        return None
    best: BookQuote | None = None
    best_price = Decimal(0)
    for quote in quotes:
        if not 0 <= outcome_index < len(quote.prices):
            raise QuantError(
                f"book {quote.book!r} has no outcome {outcome_index}", code="invalid_market"
            )
        price = validate_decimal_odds(quote.prices[outcome_index])
        if best is None or price > best_price:
            best, best_price = quote, price
    assert best is not None
    others = [quote for quote in quotes if quote is not best]
    probability = consensus_probability(others, outcome_index)
    return ValueResult(
        best_book=best.book,
        best_price=best_price,
        consensus_probability=probability,
        books_in_consensus=len(others),
        ev=expected_value(probability, best_price),
    )
