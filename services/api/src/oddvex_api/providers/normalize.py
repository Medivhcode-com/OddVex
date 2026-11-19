"""Normalisation of raw provider payloads into the canonical contract.

This is the adapter seam for a future real data vendor: the vendor's wire
format (camelCase keys, string prices, vendor enumerations) is translated to
the canonical models in :mod:`oddvex_api.providers.base`. The sample payloads
in ``data/fixtures`` are synthetic and exist to pin this behaviour in contract
tests.

Nothing is guessed at. A payload is rejected with :class:`ProviderContractError`
when it has:

* a missing required field, an unknown enumeration or a value of the wrong shape;
* an identifier or a label that is not a text of at most 200 characters or a whole
  number, or that holds a character that cannot be shown as it is (a control, format,
  surrogate, private-use or unassigned character, a line or paragraph separator);
* a league the API does not serve, or the same team on both sides of an event;
* a clock of a live event that is not such a text (it may be absent or blank);
* a priced quote (open, suspended or closed) without ``updatedAt``, or any timestamp
  that is malformed, longer than 64 characters, has no timezone or lies further in the
  future than ``MAX_CLOCK_SKEW_SECONDS`` after the time the payload was fetched;
* a price that is not a whole American price outside (-100, 100), or one beyond
  +/-1,000,000;
* a line or a statistic that is not a finite number written in plain decimal form in at
  most 40 characters, a spread line beyond +/-1,000, a total line that is not above 0 or
  is above 1,000, or a statistic beyond +/-100,000;
* two keys of one stat line that mean the same statistic;
* selections that do not fit the market: a side of another market, the same side
  twice, a side missing, spread lines that are not mirrored (-3.5 / +3.5; 0 / 0 is a
  pick'em) or total lines that differ;
* a score that is negative, not a whole number or above 1,000.

The size limits are far outside anything a sportsbook or a box score contains; they are
there so that a corrupt value is rejected here instead of being stored and shown. The
length limits are checked before a text is read, and no check takes more time than the
length of its input: a field of any size is refused at once.

Every rejection is counted per provider, record type and reason
(:func:`rejection_counts`) and logged with those three values only. Neither the
log line nor the error message contains any value from the payload.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import unicodedata
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from ..quant import QuantError, american_to_decimal
from .base import (
    MAX_CLOCK_SKEW_SECONDS,
    Event,
    GameLogEntry,
    OddsOutcome,
    OddsSnapshot,
    Score,
)

logger = logging.getLogger("oddvex.providers")


class ProviderContractError(ValueError):
    """A raw payload does not satisfy the expected provider contract.

    ``reason`` is a short fixed code for counting and logging. The message names the
    field and the rule that was broken, never the value that was received.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


_EVENT_STATES = {"SCHEDULED": "upcoming", "IN_PROGRESS": "live", "FINAL": "final"}
_MARKET_TYPES = {"h2h": "moneyline", "spreads": "spread", "totals": "total"}
_OFFER_STATES = {
    "OPEN": "open",
    "SUSPENDED": "suspended",
    "OFF": "unavailable",
    "CLOSED": "closed",
}
_SIDES = {"HOME": "home", "AWAY": "away", "DRAW": "draw", "OVER": "over", "UNDER": "under"}
#: Sides of each market in the order the rest of the code expects them. The first outcome's
#: line is read as the market line (the home line for a spread).
_MARKET_SIDES: dict[str, tuple[str, ...]] = {
    "moneyline": ("home", "draw", "away"),
    "spread": ("home", "away"),
    "total": ("over", "under"),
}
#: Sides a market may leave out.
_OPTIONAL_SIDES = frozenset({"draw"})
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
#: The leagues the API serves: the same keys as ``LeagueKey`` in ``api/schemas.py``, which
#: the response models require (a test keeps the two equal).
_LEAGUES = frozenset({"nba", "nfl", "mlb", "nhl", "soccer"})
_LEAGUE_MARKETS = {"soccer": ["moneyline", "total"]}
# ``[0-9]`` and not ``\d``: ``\d``, ``int()`` and ``float()`` also take digits of other
# scripts and ``float()`` takes ``1_0``. A feed is expected to send plain ASCII numbers.
_AMERICAN = re.compile(r"[+-]?[0-9]{1,8}")
_WHOLE = re.compile(r"[0-9]{1,5}")
# Each run of digits can be matched in one way only (the digits after the point belong to
# the optional group that starts with the point), so a text that does not fit is refused
# in one pass. With two adjacent digit runs the time would grow with the square of the
# length. Texts longer than ``_MAX_NUMBER_LENGTH`` never reach the pattern at all.
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
#: Size limits. Each is far outside what the field can really hold.
_MAX_AMERICAN = 1_000_000
_MAX_LINE = 1_000.0
_MAX_SCORE = 1_000
_MAX_STATISTIC = 100_000.0
_MAX_TEXT_LENGTH = 200
#: Length limits of a number and of a timestamp sent as text. The longest plain form of a
#: real number (``-1.7976931348623157e+308``) has 24 characters and an ISO-8601 timestamp
#: with nanoseconds and an offset has 35.
_MAX_NUMBER_LENGTH = 40
_MAX_TIMESTAMP_LENGTH = 64

# ------------------------------------------------------------------ rejections
_rejections: Counter[tuple[str, str, str]] = Counter()
_rejections_lock = threading.Lock()


def rejection_counts() -> dict[tuple[str, str, str], int]:
    """Payloads rejected since the process started: (provider, record type, reason) -> count."""
    with _rejections_lock:
        return dict(_rejections)


def reset_rejection_counts() -> None:
    with _rejections_lock:
        _rejections.clear()


def _checked[T](provider: str, record: str, build: Callable[[], T]) -> T:
    """Run one normalisation; count and log a rejection, without the payload."""
    try:
        try:
            return build()
        except ProviderContractError:
            raise
        except (AttributeError, LookupError, TypeError, ValueError, ArithmeticError):
            # A value of the wrong shape that no named check foresaw.
            raise ProviderContractError(
                "malformed_payload", f"{record} payload is not shaped as expected"
            ) from None
    except ProviderContractError as exc:
        key = (provider, record, exc.reason)
        with _rejections_lock:
            _rejections[key] += 1
            total = _rejections[key]
        logger.warning(
            "provider_payload_rejected",
            extra={
                "provider": provider,
                "record": record,
                "reason": exc.reason,
                "rejected_total": total,
            },
        )
        raise


# ---------------------------------------------------------------------- fields
def _object(raw: Any, what: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProviderContractError("malformed_payload", f"{what} must be an object")
    return raw


def _require(raw: dict[str, Any], key: str) -> Any:
    if key not in raw or raw[key] is None:
        raise ProviderContractError("missing_field", f"missing required field '{key}'")
    return raw[key]


def _lookup(mapping: dict[str, str], value: Any, what: str) -> str:
    # Only a text can be one of the known values; ``str()`` of anything else is not tried.
    if not isinstance(value, str) or value not in mapping:
        raise ProviderContractError("unknown_value", f"unknown {what}")
    return mapping[value]


def _short_text(value: Any) -> str | None:
    """``value`` without surrounding blanks when it is a text of at most
    ``_MAX_TEXT_LENGTH`` characters that can be stored and shown as it is, else ``None``.

    Not allowed: control characters (NUL, newline, tab, ...), format characters (zero-width
    and direction marks), surrogates (a lone one cannot be written into a response),
    private-use and unassigned characters, line and paragraph separators. Letters, digits,
    punctuation, symbols and spaces of any script are allowed.
    """
    if not isinstance(value, str) or len(value) > _MAX_TEXT_LENGTH:
        return None
    text = value.strip()
    for character in text:
        category = unicodedata.category(character)
        if category[0] == "C" or category in ("Zl", "Zp"):
            return None
    return text


def _text(raw: dict[str, Any], key: str) -> str:
    """A required identifier or label: a short, non-blank text or a whole number.

    Anything else (an object, a list, a fraction, a boolean) is rejected and never turned
    into its text form.
    """
    value = _require(raw, key)
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and abs(value) < 10**_MAX_TEXT_LENGTH  # checked before the number is written out
    ):
        value = str(value)
    text = _short_text(value)
    if not text:
        raise ProviderContractError(
            "invalid_identifier", f"'{key}' must be a short text or a whole number"
        )
    return text


def _clock(raw: dict[str, Any]) -> str | None:
    """The clock of a live event ("P2 11:42"): a short text, or ``None`` when it is absent
    or blank."""
    value = raw.get("clock")
    if value is None:
        return None
    text = _short_text(value)
    if text is None:
        raise ProviderContractError("invalid_text", "'clock' must be a short text")
    return text or None


def parse_timestamp(value: Any, field: str = "timestamp") -> datetime:
    """Parse an ISO-8601 timestamp and convert it to aware UTC."""
    if not isinstance(value, str):
        raise ProviderContractError("invalid_timestamp", f"{field} must be a string")
    if len(value) > _MAX_TIMESTAMP_LENGTH:
        raise ProviderContractError("invalid_timestamp", f"{field} is not an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise ProviderContractError(
            "invalid_timestamp", f"{field} is not an ISO-8601 timestamp"
        ) from None
    if parsed.tzinfo is None:
        raise ProviderContractError("invalid_timestamp", f"{field} has no timezone")
    return parsed.astimezone(UTC)


def _past_timestamp(value: Any, field: str, fetched_at: datetime) -> datetime:
    """A timestamp of something that has already happened: not after ``fetched_at``,
    apart from a small allowance for clocks that are not in step."""
    parsed = parse_timestamp(value, field)
    fetched = fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=UTC)
    if parsed > fetched + timedelta(seconds=MAX_CLOCK_SKEW_SECONDS):
        raise ProviderContractError(
            "future_timestamp",
            f"{field} is more than {MAX_CLOCK_SKEW_SECONDS} seconds after the fetch time",
        )
    return parsed


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _american(value: Any) -> int:
    text = value.strip() if isinstance(value, str) else value
    if isinstance(text, bool) or not isinstance(text, int | str):
        raise ProviderContractError("invalid_price", "priceAmerican must be a whole number")
    if isinstance(text, str) and not _AMERICAN.fullmatch(text):
        raise ProviderContractError("invalid_price", "priceAmerican must be a whole number")
    try:
        price = int(text)
        if abs(price) > _MAX_AMERICAN:
            raise ValueError
        american_to_decimal(price)
    except (ValueError, QuantError):
        raise ProviderContractError(
            "invalid_price", "priceAmerican is not a valid American price"
        ) from None
    return price


def _number(value: Any, field: str, limit: float) -> float:
    """A finite number within ``-limit`` .. ``limit``, sent as a JSON number or as a string
    in plain decimal form of at most ``_MAX_NUMBER_LENGTH`` characters."""
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ProviderContractError("invalid_number", f"{field} must be a number")
    if isinstance(value, str) and len(value) > _MAX_NUMBER_LENGTH:
        # Refused before it is read: no real number needs a text this long.
        raise ProviderContractError("invalid_number", f"{field} must be a number")
    text = value.strip() if isinstance(value, str) else value
    try:
        number = float(text)
    except (ValueError, OverflowError):
        raise ProviderContractError("invalid_number", f"{field} must be a number") from None
    if not math.isfinite(number):
        raise ProviderContractError("non_finite_number", f"{field} must be a finite number")
    if isinstance(text, str) and not _DECIMAL.fullmatch(text):
        raise ProviderContractError("invalid_number", f"{field} must be a number")
    if abs(number) > limit:
        raise ProviderContractError(
            "out_of_range", f"{field} must be between -{limit:g} and {limit:g}"
        )
    return number + 0.0  # -0.0 becomes 0.0: a pick'em line is shown as 0, not as -0.0


def _score(value: Any, field: str) -> int:
    """A whole score from 0 to ``_MAX_SCORE``. 3, "3" and 3.0 are accepted; 3.5, -1, NaN
    and 100000 are not."""
    score: int | None = None
    if isinstance(value, bool):
        pass
    elif isinstance(value, int):
        score = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        score = int(value)
    elif isinstance(value, str) and _WHOLE.fullmatch(value.strip()):
        score = int(value.strip())
    if score is None or not 0 <= score <= _MAX_SCORE:
        raise ProviderContractError(
            "invalid_score", f"score {field} must be a whole number from 0 to {_MAX_SCORE}"
        )
    return score


def _provenance(provider: str, provider_id: str, fetched_at: datetime) -> dict[str, Any]:
    return {"provider": provider, "provider_id": provider_id, "fetched_at": fetched_at}


# ---------------------------------------------------------------------- events
def normalize_event(raw: Any, provider: str, fetched_at: datetime) -> Event:
    return _checked(provider, "event", lambda: _event(raw, provider, fetched_at))


def _event(raw: Any, provider: str, fetched_at: datetime) -> Event:
    raw = _object(raw, "event")
    event_id = _text(raw, "eventId")
    league = _text(raw, "leagueKey").lower()
    if league not in _LEAGUES:
        raise ProviderContractError("unknown_value", "unknown league")
    status = _lookup(_EVENT_STATES, _require(raw, "state"), "event state")
    score_raw = raw.get("score")
    score = None
    if status != "upcoming":
        if not isinstance(score_raw, dict):
            raise ProviderContractError("missing_field", "live and final events must carry a score")
        score = Score(
            home=_score(_require(score_raw, "home"), "home"),
            away=_score(_require(score_raw, "away"), "away"),
        )
    home_team = _text(_object(_require(raw, "home"), "home"), "teamId")
    away_team = _text(_object(_require(raw, "away"), "away"), "teamId")
    if home_team == away_team:
        raise ProviderContractError("same_team", "the home and the away team must differ")
    score_updated = raw.get("scoreUpdatedAt")
    return Event(
        id=event_id,
        league=league,
        home_team_id=home_team,
        away_team_id=away_team,
        start_time=parse_timestamp(_require(raw, "startsAt"), "startsAt"),
        status=status,  # type: ignore[arg-type]
        score=score,
        period_text=_clock(raw) if status == "live" else ("Final" if score else None),
        score_updated_at=(
            _past_timestamp(score_updated, "scoreUpdatedAt", fetched_at)
            if status == "live" and not _blank(score_updated)
            else None
        ),
        markets=_LEAGUE_MARKETS.get(league, ["moneyline", "spread", "total"]),
        **_provenance(provider, event_id, fetched_at),
    )


# ----------------------------------------------------------------------- odds
def normalize_odds_snapshot(raw: Any, provider: str, fetched_at: datetime) -> OddsSnapshot:
    return _checked(provider, "odds_snapshot", lambda: _odds_snapshot(raw, provider, fetched_at))


def _outcomes(market: str, selections: Any) -> list[OddsOutcome]:
    """The market's outcomes in canonical order, after checking that they fit the market."""
    if not isinstance(selections, list):
        raise ProviderContractError("malformed_payload", "selections must be a list")
    allowed = _MARKET_SIDES[market]
    by_side: dict[str, OddsOutcome] = {}
    for selection in selections:
        selection = _object(selection, "a selection")
        side = _lookup(_SIDES, _require(selection, "side"), "selection side")
        if side not in allowed:
            raise ProviderContractError(
                "side_not_in_market", f"a {market} market has no {side} side"
            )
        if side in by_side:
            raise ProviderContractError(
                "duplicate_side", f"the {side} side of a {market} market is listed twice"
            )
        line: float | None = None
        if market != "moneyline":
            if selection.get("handicap") is None:
                raise ProviderContractError("missing_field", f"{market} selections need a handicap")
            line = _number(selection["handicap"], "handicap", _MAX_LINE)
            if market == "total" and line <= 0:
                raise ProviderContractError("out_of_range", "a total handicap must be above 0")
        by_side[side] = OddsOutcome(
            key=side,
            name=_text(selection, "label"),
            line=line,
            price_american=_american(_require(selection, "priceAmerican")),
        )
    missing = [side for side in allowed if side not in by_side and side not in _OPTIONAL_SIDES]
    if missing:
        raise ProviderContractError(
            "missing_side", f"a priced {market} market needs its {' and '.join(allowed)} sides"
        )
    outcomes = [by_side[side] for side in allowed if side in by_side]
    first, last = outcomes[0].line, outcomes[-1].line
    if market == "spread" and first is not None and last is not None and first + last != 0:
        raise ProviderContractError(
            "lines_do_not_match", "spread handicaps must mirror each other (-3.5 and +3.5)"
        )
    if market == "total" and first != last:
        raise ProviderContractError(
            "lines_do_not_match", "the over and the under must be on the same handicap"
        )
    return outcomes


def _odds_snapshot(raw: Any, provider: str, fetched_at: datetime) -> OddsSnapshot:
    raw = _object(raw, "odds snapshot")
    event_id = _text(raw, "eventId")
    market = _lookup(_MARKET_TYPES, _require(raw, "marketType"), "market type")
    book = _text(raw, "book").lower()
    status = _lookup(_OFFER_STATES, _require(raw, "state"), "offer state")
    outcomes = _outcomes(market, _require(raw, "selections")) if status != "unavailable" else []
    updated = raw.get("updatedAt")
    if _blank(updated):
        if status != "unavailable":
            # Without it the quote's age is unknown, and it could be shown as fresh for ever.
            raise ProviderContractError(
                "missing_timestamp", "a priced quote needs its updatedAt timestamp"
            )
        last_updated = None
    else:
        last_updated = _past_timestamp(updated, "updatedAt", fetched_at)
    return OddsSnapshot(
        event_id=event_id,
        market=market,
        sportsbook_id=book,
        status=status,  # type: ignore[arg-type]
        last_updated=last_updated,
        outcomes=outcomes,
        **_provenance(provider, f"{event_id}:{market}:{book}", fetched_at),
    )


# ------------------------------------------------------------------ game logs
def normalize_game_log(raw: Any, provider: str, fetched_at: datetime) -> list[GameLogEntry]:
    return _checked(provider, "game_log", lambda: _game_log(raw, provider, fetched_at))


def _game_log(raw: Any, provider: str, fetched_at: datetime) -> list[GameLogEntry]:
    raw = _object(raw, "game log")
    player_id = _text(raw, "playerId")
    games = _require(raw, "games")
    if not isinstance(games, list):
        raise ProviderContractError("malformed_payload", "games must be a list")
    entries: list[GameLogEntry] = []
    for game in games:
        game = _object(game, "a game")
        venue = _require(game, "venue")
        if venue not in ("H", "A"):
            raise ProviderContractError("unknown_value", "unknown venue")
        event_id = _text(game, "eventId")
        stats: dict[str, float] = {}
        for key, value in _object(_require(game, "statLine"), "statLine").items():
            statistic = _lookup(_STAT_KEYS, key, "stat key")
            if statistic in stats:
                # ``PTS`` and ``P`` both mean points: the two values cannot both be right.
                raise ProviderContractError(
                    "duplicate_statistic", f"the {statistic} statistic is listed twice"
                )
            stats[statistic] = _number(value, "a statistic", _MAX_STATISTIC)
        entries.append(
            GameLogEntry(
                player_id=player_id,
                event_id=event_id,
                game_time=_past_timestamp(_require(game, "date"), "date", fetched_at),
                opponent_team_id=_text(game, "opp"),
                is_home=venue == "H",
                stats=stats,
                **_provenance(provider, f"{player_id}:{event_id}", fetched_at),
            )
        )
    entries.sort(key=lambda entry: entry.game_time, reverse=True)
    return entries


__all__ = [
    "ProviderContractError",
    "normalize_event",
    "normalize_game_log",
    "normalize_odds_snapshot",
    "parse_timestamp",
    "rejection_counts",
    "reset_rejection_counts",
]
