"""Mock sync provider: a fictional sportsbook account with a deterministic bet history.

No network, no credentials. "Authorization" is a no-op that records when the
connection was made. Failures can be simulated to exercise the retry path.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from ..quant import american_to_decimal, settle_bet
from .base import (
    Authorization,
    ExternalBet,
    ExternalLeg,
    FetchResult,
    SyncProviderError,
    SyncProviderInfo,
)

MOCK_BOOK_NAME = "Mockingbird Sportsbook (mock)"
#: Bets visible on the first import; later imports see the full history.
FIRST_PAGE = 10

# (days ago, bet type, stake, result, legs[(selection, market, league, event, american, closing)])
_Leg = tuple[str, str, str, str, int, int | None]
_HISTORY: tuple[tuple[int, str, str, str | None, tuple[_Leg, ...]], ...] = (
    (
        21,
        "straight",
        "25.00",
        "won",
        (
            (
                "Harbor City Tides ML",
                "moneyline",
                "nba",
                "Ironvale Anvils at Harbor City Tides",
                -135,
                -150,
            ),
        ),
    ),
    (
        19,
        "straight",
        "20.00",
        "lost",
        (("Over 44.5", "total", "nfl", "Westmere Wardens at Granite Falls Boulders", -110, -105),),
    ),
    (
        17,
        "straight",
        "30.00",
        "won",
        (
            (
                "Frostholm Glaciers -1.5",
                "spread",
                "nhl",
                "Coldspring Ospreys at Frostholm Glaciers",
                165,
                150,
            ),
        ),
    ),
    (
        15,
        "parlay",
        "10.00",
        "lost",
        (
            (
                "Sunhaven Skylarks ML",
                "moneyline",
                "mlb",
                "Sunhaven Skylarks at Millbrook Millwrights",
                120,
                110,
            ),
            (
                "Under 8.5",
                "total",
                "mlb",
                "Fairwind Halyards at Pinecrest Lamplighters",
                -105,
                -112,
            ),
        ),
    ),
    (
        13,
        "straight",
        "40.00",
        "push",
        (
            (
                "Thornfield Stags -3",
                "spread",
                "nfl",
                "Cinder Lake Voyagers at Thornfield Stags",
                -110,
                -118,
            ),
        ),
    ),
    (
        11,
        "straight",
        "15.00",
        "won",
        (("Draw", "moneyline", "soccer", "Brightwater Rovers at Aldermoor Athletic", 240, 255),),
    ),
    (
        9,
        "straight",
        "25.00",
        "lost",
        (
            (
                "Dax Varrow over 22.5 points",
                "player_points",
                "nba",
                "Port Sable Lanterns at Emberton Cinders",
                -115,
                -125,
            ),
        ),
    ),
    (
        6,
        "parlay",
        "12.00",
        "won",
        (
            (
                "Northgate Gales ML",
                "moneyline",
                "nba",
                "Northgate Gales at Larkspur Bay Herons",
                -120,
                -128,
            ),
            (
                "Icefall Marmots ML",
                "moneyline",
                "nhl",
                "Winterbourne Lodestars at Icefall Marmots",
                105,
                100,
            ),
        ),
    ),
    (
        4,
        "straight",
        "20.00",
        "lost",
        (("Under 6.5", "total", "nhl", "Stonewick Gantries at Borealis Bay Starlings", 100, -104),),
    ),
    (
        2,
        "straight",
        "35.00",
        "won",
        (
            (
                "Castlereach United ML",
                "moneyline",
                "soccer",
                "Castlereach United at Dunhallow Town",
                150,
                138,
            ),
        ),
    ),
    (
        1,
        "straight",
        "22.00",
        None,
        (
            (
                "Copper Ridge Kestrels +4.5",
                "spread",
                "nba",
                "Copper Ridge Kestrels at Saltmarsh Drifters",
                -108,
                None,
            ),
        ),
    ),
    (
        0,
        "straight",
        "18.00",
        None,
        (
            (
                "Over 2.5",
                "total",
                "soccer",
                "Eastmarch Wanderers at Fenwick Vale Albion",
                -102,
                None,
            ),
        ),
    ),
)


class MockSyncProvider:
    info = SyncProviderInfo(
        key="mock",
        name="Mock sportsbook account",
        description=(
            "A fictional account with sample bets, for trying the import flow. No real "
            "sportsbook is contacted and no credentials are requested."
        ),
        is_mock=True,
        requires_credentials=False,
    )

    def authorize(self, options: dict[str, Any], now: datetime) -> Authorization:
        """Mock authorization: always granted. ``fail_next`` simulates fetch failures."""
        fail_next = int(options.get("fail_next", 0) or 0)
        return Authorization(
            label=str(options.get("label") or "Mock account"),
            state={
                "authorized_at": now.isoformat(),
                "fail_next": max(0, min(fail_next, 20)),
                "imports": 0,
            },
        )

    def fetch_bets(self, state: dict[str, Any], now: datetime) -> FetchResult:
        remaining_failures = int(state.get("fail_next", 0))
        if remaining_failures > 0:
            # The decremented counter is persisted by the caller even on failure.
            state["fail_next"] = remaining_failures - 1
            raise SyncProviderError(
                "The mock sportsbook is temporarily unavailable (simulated)", retryable=True
            )
        anchor = datetime.fromisoformat(state["authorized_at"])
        imports = int(state.get("imports", 0))
        visible = _HISTORY if imports > 0 else _HISTORY[:FIRST_PAGE]
        bets = tuple(self._bet(index, row, anchor) for index, row in enumerate(visible, start=1))
        return FetchResult(bets=bets, state={**state, "imports": imports + 1})

    @staticmethod
    def _bet(index: int, row: tuple[Any, ...], anchor: datetime) -> ExternalBet:
        days_ago, bet_type, stake_text, result, raw_legs = row
        stake = Decimal(stake_text)
        placed = (anchor - timedelta(days=days_ago, hours=3)).replace(microsecond=0)
        legs = tuple(
            ExternalLeg(
                selection=selection,
                market=market,
                league=league,
                event_label=event,
                odds_decimal=american_to_decimal(american),
                closing_odds_decimal=american_to_decimal(closing) if closing is not None else None,
                result=(
                    None
                    if result is None
                    else result
                    if len(raw_legs) == 1
                    else "won"
                    if result == "won" or position > 0
                    else "lost"
                ),
            )
            for position, (selection, market, league, event, american, closing) in enumerate(
                raw_legs
            )
        )
        combined = Decimal(1)
        for leg in legs:
            combined *= leg.odds_decimal
        payout = settle_bet(stake, combined, result).payout if result else None
        return ExternalBet(
            external_bet_id=f"mock-{index:04d}",
            bet_type=bet_type,
            sportsbook=MOCK_BOOK_NAME,
            stake=stake,
            placed_at=placed,
            legs=legs,
            result=result,
            payout=payout,
            settled_at=placed + timedelta(hours=5) if result else None,
        )
