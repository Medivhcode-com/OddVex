"""Best price against the no-vig consensus of the other books (quant.value)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oddvex_api.quant import QuantError, expected_value, no_vig
from oddvex_api.quant.value import (
    MIN_CONSENSUS_BOOKS,
    BookQuote,
    best_price_vs_consensus,
    consensus_probability,
)

A = BookQuote("a", [Decimal("2.10"), Decimal("1.80")])
B = BookQuote("b", [Decimal("2.00"), Decimal("1.90")])
C = BookQuote("c", [Decimal("1.95"), Decimal("1.95")])


def test_known_values_two_way() -> None:
    result = best_price_vs_consensus([A, B, C], 0)
    assert result is not None
    assert result.best_book == "a" and result.best_price == Decimal("2.10")
    assert result.books_in_consensus == 2
    # B: (1/2.00) / (1/2.00 + 1/1.90) = 19/39. C: 1/2. Mean = 77/156.
    assert result.consensus_probability == pytest.approx(77 / 156, abs=1e-12)
    # EV per unit = p * decimal - 1 = 77/156 * 2.10 - 1 = 5.7/156.
    assert result.ev.ev_per_unit == pytest.approx(5.7 / 156, abs=1e-12)
    assert result.ev.breakeven_probability == pytest.approx(1 / 2.10, abs=1e-12)


def test_the_best_book_is_excluded_from_its_own_consensus() -> None:
    result = best_price_vs_consensus([A, B, C], 0)
    assert result is not None
    with_itself = consensus_probability([A, B, C], 0)
    assert with_itself == pytest.approx(113 / 234, abs=1e-12)
    without = consensus_probability([B, C], 0)
    assert result.consensus_probability == without != with_itself
    # A's long price on outcome 0 pulls its own fair probability down, so leaving it in
    # would understate the consensus it is compared with.
    assert no_vig(A.prices).fair_probabilities[0] == pytest.approx(6 / 13)
    assert with_itself < without


def test_the_other_side_has_its_own_best_book_and_consensus() -> None:
    result = best_price_vs_consensus([A, B, C], 1)
    assert result is not None
    assert result.best_book == "c" and result.best_price == Decimal("1.95")
    # Others are A (7/13 for outcome 1) and B (20/39).
    assert result.consensus_probability == pytest.approx((7 / 13 + 20 / 39) / 2, abs=1e-12)
    assert result.ev.ev_per_unit == pytest.approx((7 / 13 + 20 / 39) / 2 * 1.95 - 1, abs=1e-12)


def test_edge_is_quant_ev_at_the_consensus_probability() -> None:
    result = best_price_vs_consensus([A, B, C], 0)
    assert result is not None
    assert result.ev == expected_value(result.consensus_probability, result.best_price)


def test_identical_books_have_a_negative_edge_equal_to_the_margin() -> None:
    books = [BookQuote(name, [Decimal("1.909091"), Decimal("1.909091")]) for name in "abc"]
    result = best_price_vs_consensus(books, 0)
    assert result is not None
    assert result.best_book == "a"  # the first book wins a tie
    assert result.consensus_probability == pytest.approx(0.5)
    assert result.ev.ev_per_unit == pytest.approx(0.5 * 1.909091 - 1, abs=1e-9)
    assert result.ev.ev_per_unit < 0


def test_three_way_market() -> None:
    books = [
        BookQuote("a", [Decimal("2.60"), Decimal("3.40"), Decimal("2.90")]),
        BookQuote("b", [Decimal("2.40"), Decimal("3.30"), Decimal("3.00")]),
        BookQuote("c", [Decimal("2.45"), Decimal("3.20"), Decimal("3.10")]),
    ]
    result = best_price_vs_consensus(books, 0)
    assert result is not None and result.best_book == "a"

    def fair(prices: list[float]) -> float:
        implied = [1 / p for p in prices]
        return implied[0] / sum(implied)

    expected = (fair([2.40, 3.30, 3.00]) + fair([2.45, 3.20, 3.10])) / 2
    assert result.consensus_probability == pytest.approx(expected, abs=1e-12)
    assert result.ev.ev_per_unit == pytest.approx(expected * 2.60 - 1, abs=1e-12)


@pytest.mark.parametrize("books", [[], [A], [A, B]])
def test_fewer_than_two_other_books_is_skipped(books: list[BookQuote]) -> None:
    assert MIN_CONSENSUS_BOOKS == 2
    assert best_price_vs_consensus(books, 0) is None


def test_min_other_books_can_be_raised_or_lowered() -> None:
    assert best_price_vs_consensus([A, B, C], 0, min_other_books=3) is None
    one = best_price_vs_consensus([A, B], 0, min_other_books=1)
    assert one is not None and one.books_in_consensus == 1
    assert one.consensus_probability == pytest.approx(19 / 39)
    with pytest.raises(QuantError):
        best_price_vs_consensus([A, B, C], 0, min_other_books=0)


def test_invalid_input_is_rejected() -> None:
    with pytest.raises(QuantError):
        best_price_vs_consensus([A, B, C], 2)  # no such outcome
    with pytest.raises(QuantError):
        best_price_vs_consensus([A, B, C], -1)
    with pytest.raises(QuantError):
        best_price_vs_consensus([A, B, BookQuote("a", C.prices)], 0)  # a book twice
    with pytest.raises(QuantError):
        best_price_vs_consensus([A, B, BookQuote("d", [Decimal("1.0"), Decimal("2.0")])], 0)
    with pytest.raises(QuantError):
        best_price_vs_consensus([A, B, BookQuote("d", [Decimal("2.0")])], 0)  # one-sided book
    with pytest.raises(QuantError):
        consensus_probability([], 0)


_price = st.decimals(min_value=Decimal("1.05"), max_value=Decimal("15"), places=3)


@given(st.lists(st.tuples(_price, _price), min_size=3, max_size=8), st.integers(0, 1))
def test_properties(prices: list[tuple[Decimal, Decimal]], index: int) -> None:
    books = [BookQuote(f"book{i}", list(pair)) for i, pair in enumerate(prices)]
    result = best_price_vs_consensus(books, index)
    assert result is not None
    assert result.best_price == max(pair[index] for pair in prices)
    assert result.books_in_consensus == len(books) - 1
    assert 0 < result.consensus_probability < 1
    others = [b for b in books if b.book != result.best_book]
    assert result.consensus_probability == pytest.approx(consensus_probability(others, index))
    assert result.ev.ev_per_unit == pytest.approx(
        result.consensus_probability * float(result.best_price) - 1, abs=1e-9
    )
    # The two sides' consensus over the same books sums to 1.
    assert consensus_probability(others, 0) + consensus_probability(others, 1) == pytest.approx(1)
