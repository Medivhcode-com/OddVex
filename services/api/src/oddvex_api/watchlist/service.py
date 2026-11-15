"""Watchlist domain logic: resolving provider entities and collecting watched events."""

from __future__ import annotations

from collections.abc import Sequence

from ..api.schemas import EventSummaryOut
from ..board import Board
from ..db import WatchlistItem
from ..providers import Event
from .schemas import WatchlistItemOut


def describe(board: Board, kind: str, ref_id: str) -> tuple[str, str] | None:
    """``(label, league)`` of a provider entity, or ``None`` if the provider does not have it."""
    provider = board.provider
    if kind == "team":
        team = provider.get_team(ref_id)
        return (team.name, team.league) if team else None
    if kind == "player":
        player = provider.get_player(ref_id)
        return (player.name, player.league) if player else None
    event = provider.get_event(ref_id)
    if event is None:
        return None
    home, away = board.team_ref(event.home_team_id), board.team_ref(event.away_team_id)
    return f"{away.name} at {home.name}", event.league


def item_out(board: Board, item: WatchlistItem) -> WatchlistItemOut:
    out = WatchlistItemOut(
        id=item.id,
        kind=item.kind,  # type: ignore[arg-type]
        ref_id=item.ref_id,
        label=item.label,
        league=item.league,
        created_at=item.created_at,
        available=False,
    )
    provider = board.provider
    if item.kind == "team":
        if provider.get_team(item.ref_id) is not None:
            out.team = board.team_ref(item.ref_id)
    elif item.kind == "player":
        player = provider.get_player(item.ref_id)
        if player is not None:
            out.player = board.player_out(player)
    elif item.kind == "event":
        event = provider.get_event(item.ref_id)
        if event is not None:
            out.event = board.event_summary(event)
    out.available = any(value is not None for value in (out.team, out.player, out.event))
    return out


def watched_events(board: Board, items: Sequence[WatchlistItem]) -> list[EventSummaryOut]:
    """Live and upcoming events for the watched teams, watched players' teams and events.

    De-duplicated; live events first, then by start time.
    """
    provider = board.provider
    team_ids: set[str] = set()
    event_ids: list[str] = []
    for item in items:
        if item.kind == "team":
            team_ids.add(item.ref_id)
        elif item.kind == "player":
            player = provider.get_player(item.ref_id)
            if player is not None:
                team_ids.add(player.team_id)
        elif item.kind == "event":
            event_ids.append(item.ref_id)

    found: dict[str, Event] = {}
    if team_ids:
        for event in provider.list_events():
            if event.status == "final":
                continue
            if event.home_team_id in team_ids or event.away_team_id in team_ids:
                found[event.id] = event
    for event_id in event_ids:
        if event_id in found:
            continue
        watched = provider.get_event(event_id)
        if watched is not None and watched.status != "final":
            found[watched.id] = watched
    ordered = sorted(found.values(), key=lambda e: (e.status != "live", e.start_time, e.id))
    return [board.event_summary(event) for event in ordered]
