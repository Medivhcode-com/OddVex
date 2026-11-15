"""Normalisation of raw provider payloads into the canonical contract.

This is the adapter seam for a future real data vendor: the vendor's wire
format (camelCase keys, string prices, vendor enumerations) is translated to
the canonical models in :mod:`oddvex_api.providers.base`. The sample payloads
in ``data/fixtures`` are synthetic and exist to pin this behaviour in contract
tests. Unknown enumerations or malformed prices raise
:class:`ProviderContractError` rather than being guessed at.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..quant import QuantError, american_to_decimal
from .base import Event, GameLogEntry, OddsOutcome, OddsSnapshot, Score


class ProviderContractError(ValueError):
    """A raw payload does not satisfy the expected provider contract."""


_EVENT_STATES = {"SCHEDULED": "upcoming", "IN_PROGRESS": "live", "FINAL": "final"}
_MARKET_TYPES = {"h2h": "moneyline", "spreads": "spread", "totals": "total"}
_OFFER_STATES = {
    "OPEN": "open",
    "SUSPENDED": "suspended",
    "OFF": "unavailable",
    "CLOSED": "closed",
}
_SIDES = {"HOME": "home", "AWAY": "away", "DRAW": "draw", "OVER": "over", "UNDER": "under"}
_STAT_KEYS = {
    "PTS": "points",
    "REB": "rebounds",
    "AST": "assists",
    "3PM": "threes",
    "PASS_YDS": "passing_yards",
    "RUSH_YDS": "rushing_yards",
    "REC": "receptions",
    "H": "hits",
    "SO": "strikeouts",
    "SOG": "shots",
    "P": "points",
}
_LEAGUE_MARKETS = {"soccer": ["moneyline", "total"]}


def _require(raw: dict[str, Any], key: str) -> Any:
    if key not in raw or raw[key] is None:
        raise ProviderContractError(f"missing required field '{key}'")
    return raw[key]


def _lookup(mapping: dict[str, str], value: Any, what: str) -> str:
    try:
        return mapping[str(value)]
    except KeyError as exc:
        raise ProviderContractError(f"unknown {what} {value!r}") from exc


def parse_timestamp(value: Any) -> datetime:
    """Parse an ISO-8601 timestamp and convert it to aware UTC."""
    if not isinstance(value, str):
        raise ProviderContractError(f"timestamp must be a string, got {value!r}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderContractError(f"invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ProviderContractError(f"timestamp {value!r} has no timezone")
    return parsed.astimezone(UTC)


def _american(value: Any) -> int:
    try:
        price = int(str(value).replace("+", ""))
        american_to_decimal(price)
    except (ValueError, QuantError) as exc:
        raise ProviderContractError(f"invalid american price {value!r}") from exc
    return price


def _provenance(provider: str, provider_id: str, fetched_at: datetime) -> dict[str, Any]:
    return {"provider": provider, "provider_id": provider_id, "fetched_at": fetched_at}


def normalize_event(raw: dict[str, Any], provider: str, fetched_at: datetime) -> Event:
    event_id = str(_require(raw, "eventId"))
    league = str(_require(raw, "leagueKey")).lower()
    status = _lookup(_EVENT_STATES, _require(raw, "state"), "event state")
    score_raw = raw.get("score")
    score = None
    if status != "upcoming":
        if not isinstance(score_raw, dict):
            raise ProviderContractError("live and final events must carry a score")
        score = Score(home=int(_require(score_raw, "home")), away=int(_require(score_raw, "away")))
    return Event(
        id=event_id,
        league=league,
        home_team_id=str(_require(_require(raw, "home"), "teamId")),
        away_team_id=str(_require(_require(raw, "away"), "teamId")),
        start_time=parse_timestamp(_require(raw, "startsAt")),
        status=status,  # type: ignore[arg-type]
        score=score,
        period_text=raw.get("clock") if status == "live" else ("Final" if score else None),
        markets=_LEAGUE_MARKETS.get(league, ["moneyline", "spread", "total"]),
        **_provenance(provider, event_id, fetched_at),
    )


def normalize_odds_snapshot(
    raw: dict[str, Any], provider: str, fetched_at: datetime
) -> OddsSnapshot:
    event_id = str(_require(raw, "eventId"))
    market = _lookup(_MARKET_TYPES, _require(raw, "marketType"), "market type")
    book = str(_require(raw, "book")).lower()
    status = _lookup(_OFFER_STATES, _require(raw, "state"), "offer state")
    outcomes: list[OddsOutcome] = []
    if status != "unavailable":
        for selection in _require(raw, "selections"):
            handicap = selection.get("handicap")
            if market != "moneyline" and handicap is None:
                raise ProviderContractError(f"{market} selections need a handicap")
            outcomes.append(
                OddsOutcome(
                    key=_lookup(_SIDES, _require(selection, "side"), "selection side"),
                    name=str(_require(selection, "label")),
                    line=None if market == "moneyline" else float(handicap),
                    price_american=_american(_require(selection, "priceAmerican")),
                )
            )
        if len(outcomes) < 2:
            raise ProviderContractError("a priced market needs at least two selections")
    updated = raw.get("updatedAt")
    return OddsSnapshot(
        event_id=event_id,
        market=market,
        sportsbook_id=book,
        status=status,  # type: ignore[arg-type]
        last_updated=parse_timestamp(updated) if updated else None,
        outcomes=outcomes,
        **_provenance(provider, f"{event_id}:{market}:{book}", fetched_at),
    )


def normalize_game_log(
    raw: dict[str, Any], provider: str, fetched_at: datetime
) -> list[GameLogEntry]:
    player_id = str(_require(raw, "playerId"))
    entries: list[GameLogEntry] = []
    for game in _require(raw, "games"):
        venue = _require(game, "venue")
        if venue not in ("H", "A"):
            raise ProviderContractError(f"unknown venue {venue!r}")
        event_id = str(_require(game, "eventId"))
        entries.append(
            GameLogEntry(
                player_id=player_id,
                event_id=event_id,
                game_time=parse_timestamp(_require(game, "date")),
                opponent_team_id=str(_require(game, "opp")),
                is_home=venue == "H",
                stats={
                    _lookup(_STAT_KEYS, key, "stat key"): float(value)
                    for key, value in _require(game, "statLine").items()
                },
                **_provenance(provider, f"{player_id}:{event_id}", fetched_at),
            )
        )
    entries.sort(key=lambda entry: entry.game_time, reverse=True)
    return entries
