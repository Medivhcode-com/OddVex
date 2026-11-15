"""Read models built from provider data: odds comparison, line history, prop research.

This is the only place where provider records are combined with the quant
library. Every number shown to a client comes from here (and therefore from
``quant``), never from the HTTP layer or the assistant.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from statistics import median

from .api.schemas import (
    AveragesOut,
    BestMoneylineOut,
    BestOutcomeOut,
    BookHoldOut,
    BookOddsOut,
    ConsensusOut,
    ConsensusOutcomeOut,
    EventDetailOut,
    EventOddsOut,
    EventSummaryOut,
    GameLogEntryOut,
    HitRateOut,
    LeagueOut,
    LineHistoryOut,
    LinePointOut,
    LineSeriesOut,
    OddsOutcomeOut,
    PlayerDetailOut,
    PlayerOut,
    PlayerPropsOut,
    PropBoardRowOut,
    PropOfferOut,
    ScoreOut,
    SportsbookOut,
)
from .cache import Cache, cached
from .config import Settings
from .providers import (
    Event,
    GameLogEntry,
    OddsSnapshot,
    Player,
    PropOffer,
    SportsDataProvider,
    Team,
)
from .quant import american_to_decimal, hit_rate, no_vig
from .schemas import BestPriceOut, PriceOut, SportsbookRef, TeamRef, price_out

HIT_RATE_CAVEAT = (
    "Hit rate is a historical frequency over a small sample, shown with a 95% Wilson "
    "interval. It describes what already happened and is not a prediction or a "
    "probability of a future result."
)
SYNTHETIC_NOTICE = (
    "All teams, players, sportsbooks, odds and statistics shown are synthetic sample "
    "data generated for demonstration. They do not describe real games or real prices."
)

_WINDOW_SIZES = {"5": 5, "10": 10, "20": 20}
_GAME_LOG_TTL_SECONDS = 30.0
_BOARD_TTL_SECONDS = 10.0


def consensus_line(lines: Sequence[float]) -> float | None:
    """Most common line; ties go to the line nearest the median, then the lower one."""
    if not lines:
        return None
    counts = Counter(lines)
    top = max(counts.values())
    candidates = sorted(line for line, count in counts.items() if count == top)
    mid = median(lines)
    return min(candidates, key=lambda line: (abs(line - mid), line))


def _mean(values: Sequence[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


class Board:
    """Per-request facade over a :class:`SportsDataProvider`."""

    def __init__(self, provider: SportsDataProvider, settings: Settings, cache: Cache) -> None:
        self.provider = provider
        self.settings = settings
        self.cache = cache
        self.now: datetime = provider.now()
        self._books = {
            b.id: SportsbookRef(key=b.key, name=b.name) for b in provider.list_sportsbooks()
        }
        self._summaries: dict[str, EventSummaryOut] = {}

    # ------------------------------------------------------------ references
    def _sportsbooks(self) -> list[SportsbookOut]:
        return [SportsbookOut(key=b.key, name=b.name) for b in self.provider.list_sportsbooks()]

    def sportsbooks(self) -> list[SportsbookOut]:
        return self._sportsbooks()

    def leagues(self) -> list[LeagueOut]:
        return [
            LeagueOut(
                key=league.key,  # type: ignore[arg-type]
                name=league.name,
                sport=league.sport,
                has_draw=league.has_draw,
                markets=league.markets,  # type: ignore[arg-type]
                prop_markets=league.prop_markets,
            )
            for league in self.provider.list_leagues()
        ]

    def book_ref(self, sportsbook_id: str) -> SportsbookRef:
        return self._books.get(sportsbook_id) or SportsbookRef(
            key=sportsbook_id, name=sportsbook_id
        )

    def team_ref(self, team_id: str) -> TeamRef:
        team: Team | None = self.provider.get_team(team_id)
        if team is None:
            return TeamRef(id=team_id, name=team_id, abbreviation=team_id[:3].upper())
        return TeamRef(id=team.id, name=team.name, abbreviation=team.abbreviation)

    # -------------------------------------------------------------- freshness
    def stale_after_seconds(self, event_status: str) -> int:
        if event_status == "live":
            return self.settings.stale_live_seconds
        return self.settings.stale_pregame_seconds

    def is_stale(self, last_updated: datetime | None, event_status: str) -> bool:
        if last_updated is None:
            return False
        age = (self.now - last_updated).total_seconds()
        return age > self.stale_after_seconds(event_status)

    @staticmethod
    def _api_status(provider_status: str) -> str:
        """Provider 'closed' (market no longer offered) is reported as 'unavailable'."""
        return provider_status if provider_status in ("open", "suspended") else "unavailable"

    # ----------------------------------------------------------------- events
    def _best_moneyline(self, event: Event) -> BestMoneylineOut | None:
        if event.status == "final":
            return None
        best: dict[str, tuple[Decimal, str]] = {}
        for snap in self.provider.get_odds(event.id, "moneyline"):
            if snap.status != "open" or self.is_stale(snap.last_updated, event.status):
                continue
            for outcome in snap.outcomes:
                price = american_to_decimal(outcome.price_american)
                if outcome.key not in best or price > best[outcome.key][0]:
                    best[outcome.key] = (price, snap.sportsbook_id)
        if not best:
            return None

        def side(key: str) -> BestPriceOut | None:
            if key not in best:
                return None
            price, book = best[key]
            return BestPriceOut(price=price_out(price), sportsbook=self.book_ref(book))

        return BestMoneylineOut(home=side("home"), away=side("away"), draw=side("draw"))

    def event_summary(self, event: Event) -> EventSummaryOut:
        hit = self._summaries.get(event.id)
        if hit is not None:
            return hit
        summary = EventSummaryOut(
            id=event.id,
            league=event.league,  # type: ignore[arg-type]
            home_team=self.team_ref(event.home_team_id),
            away_team=self.team_ref(event.away_team_id),
            start_time=event.start_time,
            status=event.status,
            score=ScoreOut(home=event.score.home, away=event.score.away) if event.score else None,
            status_detail=event.period_text,
            best_moneyline=self._best_moneyline(event),
        )
        self._summaries[event.id] = summary
        return summary

    def event_detail(self, event: Event) -> EventDetailOut:
        league = next(lg for lg in self.provider.list_leagues() if lg.key == event.league)
        players = [
            self.player_out(p)
            for team_id in (event.home_team_id, event.away_team_id)
            for p in self.provider.list_players(team_id=team_id)
        ]
        return EventDetailOut(
            **self.event_summary(event).model_dump(),
            league_name=league.name,
            has_draw=league.has_draw,
            available_markets=event.markets,  # type: ignore[arg-type]
            players=players,
            as_of=self.now,
            data_mode="synthetic",
        )

    # ------------------------------------------------------------------- odds
    def event_odds(self, event: Event, market: str) -> EventOddsOut:
        snapshots: list[OddsSnapshot] = self.provider.get_odds(event.id, market)
        rows: list[tuple[OddsSnapshot, str, bool, list[Decimal]]] = []
        for snap in snapshots:
            status = self._api_status(snap.status)
            stale = status != "unavailable" and self.is_stale(snap.last_updated, event.status)
            prices = (
                []
                if status == "unavailable"
                else [american_to_decimal(o.price_american) for o in snap.outcomes]
            )
            rows.append((snap, status, stale, prices))

        usable = [r for r in rows if r[1] == "open" and not r[2] and len(r[3]) >= 2]
        line: float | None = None
        if market != "moneyline":
            line = consensus_line(
                [r[0].outcomes[0].line for r in usable if r[0].outcomes[0].line is not None]
            )
            comparable = [r for r in usable if r[0].outcomes[0].line == line]
        else:
            comparable = usable

        best: dict[str, tuple[Decimal, str, float | None]] = {}
        probability_sums: dict[str, float] = {}
        names: dict[str, str] = {}
        for snap, _, _, prices in comparable:
            fair = no_vig(prices).fair_probabilities
            for outcome, price, probability in zip(snap.outcomes, prices, fair, strict=True):
                names.setdefault(outcome.key, outcome.name)
                probability_sums[outcome.key] = probability_sums.get(outcome.key, 0.0) + probability
                if outcome.key not in best or price > best[outcome.key][0]:
                    best[outcome.key] = (price, snap.sportsbook_id, outcome.line)

        comparable_ids = {id(r[0]) for r in comparable}
        books: list[BookOddsOut] = []
        holds: list[BookHoldOut] = []
        for snap, status, stale, prices in rows:
            outcomes = [
                OddsOutcomeOut(
                    key=o.key,
                    name=o.name,
                    line=o.line,
                    price=price_out(price),
                    is_best=id(snap) in comparable_ids and price == best[o.key][0],
                )
                for o, price in zip(snap.outcomes, prices, strict=False)
            ]
            books.append(
                BookOddsOut(
                    sportsbook=self.book_ref(snap.sportsbook_id),
                    status=status,  # type: ignore[arg-type]
                    last_updated=snap.last_updated if status != "unavailable" else None,
                    is_stale=stale,
                    outcomes=outcomes,
                )
            )
            if len(prices) >= 2:
                holds.append(
                    BookHoldOut(
                        sportsbook_key=snap.sportsbook_id, hold=round(no_vig(prices).hold, 6)
                    )
                )

        count = len(comparable)
        return EventOddsOut(
            event=self.event_summary(event),
            market=market,  # type: ignore[arg-type]
            as_of=self.now,
            data_mode="synthetic",
            stale_after_seconds=self.stale_after_seconds(event.status),
            books=books,
            consensus=ConsensusOut(
                outcomes=[
                    ConsensusOutcomeOut(
                        key=key, name=names[key], no_vig_probability=round(total / count, 6)
                    )
                    for key, total in probability_sums.items()
                ],
                books_used=count,
                line=line,
            ),
            holds=holds,
            best=[
                BestOutcomeOut(
                    outcome_key=key, sportsbook_key=book, price=price_out(price), line=best_line
                )
                for key, (price, book, best_line) in best.items()
            ],
        )

    def line_history(self, event: Event, market: str) -> LineHistoryOut:
        series = [
            LineSeriesOut(
                sportsbook=self.book_ref(s.sportsbook_id),
                outcome_key=s.outcome_key,
                outcome_name=s.outcome_name,
                points=[
                    LinePointOut(
                        timestamp=p.timestamp,
                        line=p.line,
                        price=price_out(american_to_decimal(p.price_american)),
                    )
                    for p in s.points
                ],
            )
            for s in self.provider.get_line_history(event.id, market)
        ]
        return LineHistoryOut(
            event=self.event_summary(event),
            market=market,  # type: ignore[arg-type]
            as_of=self.now,
            data_mode="synthetic",
            series=series,
        )

    # ---------------------------------------------------------------- players
    def player_out(self, player: Player) -> PlayerOut:
        return PlayerOut(
            id=player.id,
            name=player.name,
            league=player.league,  # type: ignore[arg-type]
            team=self.team_ref(player.team_id),
            position=player.position,
            jersey_number=player.jersey_number,
            prop_markets=player.prop_markets,
        )

    def _next_event(self, player: Player) -> tuple[Event | None, TeamRef | None]:
        event = self.provider.next_event_for_team(player.team_id)
        if event is None:
            return None, None
        opponent_id = (
            event.away_team_id if event.home_team_id == player.team_id else event.home_team_id
        )
        return event, self.team_ref(opponent_id)

    def player_detail(self, player: Player) -> PlayerDetailOut:
        event, opponent = self._next_event(player)
        return PlayerDetailOut(
            **self.player_out(player).model_dump(),
            next_event=self.event_summary(event) if event else None,
            opponent=opponent,
            as_of=self.now,
            data_mode="synthetic",
        )

    def _game_log(self, player_id: str) -> list[GameLogEntry]:
        return cached(
            self.cache,
            f"gamelog:{player_id}",
            _GAME_LOG_TTL_SECONDS,
            lambda: self.provider.get_player_game_log(player_id),
        )

    def _prop_offers(
        self, offers: Sequence[PropOffer], event_status: str
    ) -> tuple[list[PropOfferOut], float | None, BestPriceOut | None, BestPriceOut | None]:
        """Offer rows, consensus line, and best over / under at that line."""
        rows: list[tuple[PropOffer, str, bool, Decimal | None, Decimal | None]] = []
        for offer in offers:
            status = self._api_status(offer.status)
            priced = status != "unavailable" and offer.line is not None
            over = (
                american_to_decimal(offer.over_american)
                if priced and offer.over_american is not None
                else None
            )
            under = (
                american_to_decimal(offer.under_american)
                if priced and offer.under_american is not None
                else None
            )
            stale = status != "unavailable" and self.is_stale(offer.last_updated, event_status)
            rows.append((offer, status, stale, over, under))

        usable = [r for r in rows if r[1] == "open" and not r[2] and r[0].line is not None]
        line = consensus_line([r[0].line for r in usable if r[0].line is not None])
        comparable = [r for r in usable if r[0].line == line]
        best_over = max((r[3] for r in comparable if r[3] is not None), default=None)
        best_under = max((r[4] for r in comparable if r[4] is not None), default=None)
        comparable_ids = {id(r[0]) for r in comparable}

        out: list[PropOfferOut] = []
        best_over_ref: BestPriceOut | None = None
        best_under_ref: BestPriceOut | None = None
        for offer, status, stale, over, under in rows:
            in_play = id(offer) in comparable_ids
            is_best_over = in_play and over is not None and over == best_over
            is_best_under = in_play and under is not None and under == best_under
            book = self.book_ref(offer.sportsbook_id)
            if is_best_over and best_over_ref is None and over is not None:
                best_over_ref = BestPriceOut(price=price_out(over), sportsbook=book)
            if is_best_under and best_under_ref is None and under is not None:
                best_under_ref = BestPriceOut(price=price_out(under), sportsbook=book)
            out.append(
                PropOfferOut(
                    sportsbook=book,
                    status=status,  # type: ignore[arg-type]
                    line=offer.line if status != "unavailable" else None,
                    over=price_out(over) if over is not None else None,
                    under=price_out(under) if under is not None else None,
                    last_updated=offer.last_updated if status != "unavailable" else None,
                    is_stale=stale,
                    is_best_over=is_best_over,
                    is_best_under=is_best_under,
                )
            )
        return out, line, best_over_ref, best_under_ref

    def player_props(
        self, player: Player, market: str, window: str = "10", split: str = "all"
    ) -> PlayerPropsOut:
        event, opponent = self._next_event(player)
        offers = self.provider.get_prop_offers(player.id, market) if event else []
        offer_rows, line, _, _ = self._prop_offers(offers, event.status if event else "upcoming")

        log = [entry for entry in self._game_log(player.id) if market in entry.stats]
        season_values = [entry.stats[market] for entry in log]
        if split == "home":
            selected = [e for e in log if e.is_home]
        elif split == "away":
            selected = [e for e in log if not e.is_home]
        elif split == "vs_opponent":
            selected = [e for e in log if opponent and e.opponent_team_id == opponent.id]
        else:
            selected = list(log)
        if window in _WINDOW_SIZES:
            selected = selected[: _WINDOW_SIZES[window]]

        if line is not None:
            grading_line, line_source = line, "consensus"
        else:
            base = median(season_values) if season_values else 0.0
            grading_line, line_source = float(int(base)) + 0.5, "season_median"

        values = [entry.stats[market] for entry in selected]
        rate = hit_rate(values, grading_line, "over")
        game_log = [
            GameLogEntryOut(
                event_id=entry.event_id,
                date=entry.game_time,
                opponent=self.team_ref(entry.opponent_team_id),
                is_home=entry.is_home,
                value=entry.stats[market],
                result=(
                    "push"
                    if entry.stats[market] == grading_line
                    else "over"
                    if entry.stats[market] > grading_line
                    else "under"
                ),
            )
            for entry in selected
        ]
        return PlayerPropsOut(
            player=self.player_out(player),
            market=market,
            available_markets=player.prop_markets,
            window=window,  # type: ignore[arg-type]
            split=split,  # type: ignore[arg-type]
            next_event=self.event_summary(event) if event else None,
            opponent=opponent,
            offers=offer_rows,
            consensus_line=line,
            game_log=game_log,
            hit_rate=HitRateOut(
                line=grading_line,
                line_source=line_source,  # type: ignore[arg-type]
                over_count=rate.hits,
                under_count=rate.misses,
                pushes=rate.pushes,
                sample_size=rate.sample_size,
                rate=round(rate.rate, 4) if rate.rate is not None else None,
                ci_low=round(rate.ci_low, 4) if rate.ci_low is not None else None,
                ci_high=round(rate.ci_high, 4) if rate.ci_high is not None else None,
            ),
            averages=AveragesOut(
                window=_mean(values),
                season=_mean(season_values),
                home=_mean([e.stats[market] for e in log if e.is_home]),
                away=_mean([e.stats[market] for e in log if not e.is_home]),
                vs_opponent=_mean(
                    [e.stats[market] for e in log if opponent and e.opponent_team_id == opponent.id]
                ),
            ),
            caveat=HIT_RATE_CAVEAT,
            as_of=self.now,
            data_mode="synthetic",
        )

    def props_board(self, league: str | None, market: str | None) -> list[PropBoardRowOut]:
        return cached(
            self.cache,
            f"propsboard:{league or '*'}:{market or '*'}",
            _BOARD_TTL_SECONDS,
            lambda: self._props_board(league, market),
        )

    def _props_board(self, league: str | None, market: str | None) -> list[PropBoardRowOut]:
        rows: list[PropBoardRowOut] = []
        for player in self.provider.list_players(league=league):
            markets = [m for m in player.prop_markets if market is None or m == market]
            if not markets:
                continue
            event, _ = self._next_event(player)
            if event is None:
                continue
            offers = self.provider.get_prop_offers(player.id)
            log = self._game_log(player.id)
            for prop_market in markets:
                market_offers = [o for o in offers if o.market == prop_market]
                _, line, best_over, best_under = self._prop_offers(market_offers, event.status)
                l10_rate: float | None = None
                over_count = sample = 0
                if line is not None:
                    recent = [e.stats[prop_market] for e in log if prop_market in e.stats][:10]
                    result = hit_rate(recent, line, "over")
                    over_count, sample = result.hits, result.sample_size
                    l10_rate = round(result.rate, 4) if result.rate is not None else None
                rows.append(
                    PropBoardRowOut(
                        player=self.player_out(player),
                        event=self.event_summary(event),
                        market=prop_market,
                        consensus_line=line,
                        best_over=best_over,
                        best_under=best_under,
                        l10_hit_rate=l10_rate,
                        l10_over_count=over_count,
                        l10_sample=sample,
                    )
                )
        rows.sort(key=lambda r: (r.event.start_time, r.event.id, r.player.name, r.market))
        return rows


__all__ = ["HIT_RATE_CAVEAT", "SYNTHETIC_NOTICE", "Board", "PriceOut", "consensus_line"]
