"""Test doubles: a synthetic provider whose clock, events and odds the test controls."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from oddvex_api.providers import Event, OddsOutcome, OddsSnapshot, Score, SyntheticProvider

from .conftest import FROZEN_NOW

#: (sportsbook key, status, quote age in seconds, [(outcome key, line, american price)])
Quote = tuple[str, str, float, list[tuple[str, float | None, int]]]


class ControlledProvider(SyntheticProvider):
    """The seeded synthetic schedule with a movable clock and optional overrides.

    Without overrides it behaves exactly like :class:`SyntheticProvider` at ``self.current``.
    ``set_odds`` replaces a market's quotes, ``finish`` makes an event final with a chosen
    score and ``hide`` makes the provider forget an event.
    """

    def __init__(self, now: datetime = FROZEN_NOW) -> None:
        self.current = now
        super().__init__(seed=20260101, clock=lambda: self.current)
        self._quotes: dict[tuple[str, str], list[Quote]] = {}
        self._finished: dict[str, Score] = {}
        self._hidden: set[str] = set()

    # ------------------------------------------------------------- controls
    def advance(self, **delta: float) -> None:
        self.current += timedelta(**delta)

    def set_odds(self, event_id: str, market: str, quotes: list[Quote]) -> None:
        self._quotes[(event_id, market)] = quotes

    def finish(self, event_id: str, home: int, away: int) -> None:
        self._finished[event_id] = Score(home=home, away=away)

    def hide(self, event_id: str) -> None:
        self._hidden.add(event_id)

    # ------------------------------------------------------------ overrides
    def _apply(self, event: Event | None) -> Event | None:
        if event is None or event.id in self._hidden:
            return None
        score = self._finished.get(event.id)
        if score is None:
            return event
        return event.model_copy(
            update={
                "status": "final",
                "score": score,
                "period_text": "Final",
                "score_updated_at": None,  # only a live event has one
            }
        )

    def get_event(self, event_id: str) -> Event | None:
        return self._apply(super().get_event(event_id))

    def list_events(
        self, league: str | None = None, status: str | None = None, on_date: date | None = None
    ) -> list[Event]:
        events = [self._apply(e) for e in super().list_events(league=league, on_date=on_date)]
        return [e for e in events if e is not None and (status is None or e.status == status)]

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]:
        quotes = self._quotes.get((event_id, market))
        if quotes is None:
            return super().get_odds(event_id, market)
        return [
            OddsSnapshot(
                provider="test",
                provider_id=f"{event_id}:{market}:{book}",
                fetched_at=self.current,
                event_id=event_id,
                market=market,
                sportsbook_id=book,
                status=status,  # type: ignore[arg-type]
                last_updated=(
                    None if status == "unavailable" else self.current - timedelta(seconds=age)
                ),
                outcomes=[
                    OddsOutcome(key=key, name=key.title(), line=line, price_american=price)
                    for key, line, price in outcomes
                ],
            )
            for book, status, age, outcomes in quotes
        ]


def moneyline(home: int, away: int) -> list[tuple[str, float | None, int]]:
    return [("home", None, home), ("away", None, away)]


def spread(
    home_line: float, home: int = -110, away: int = -110
) -> list[tuple[str, float | None, int]]:
    return [("home", home_line, home), ("away", -home_line, away)]


def total(line: float, over: int = -110, under: int = -110) -> list[tuple[str, float | None, int]]:
    return [("over", line, over), ("under", line, under)]
