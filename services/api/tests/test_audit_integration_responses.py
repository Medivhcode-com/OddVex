"""Answers that must say what they mean: ``has_more`` is always sent by the auto-settle
route, as the generated client types declare it, and the sync-finished notification says
how many bets a run left out."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from oddvex_api.bets import service as bets_service
from oddvex_api.notifications import templates

Headers = dict[str, str]


def _bet(**overrides: Any) -> dict[str, Any]:
    return {
        "bet_type": "straight",
        "stake": 10,
        "sportsbook": "Northline",
        "legs": [{"selection": "Harbor City Tides ML", "market": "moneyline", "odds": -110}],
        **overrides,
    }


# -------------------------------------------------------------- auto-settle
def test_auto_settle_always_sends_has_more(client: TestClient, headers: Headers) -> None:
    # The generated client types declare the field as always present (it has a default).
    # Nothing pending at all.
    empty = client.post("/v1/bets/auto-settle", headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"checked": 0, "settled": [], "skipped": [], "has_more": False}

    # A bet that cannot be graded: examined, skipped, nothing more to do.
    created = client.post("/v1/bets", json=_bet(), headers=headers)
    assert created.status_code == 201, created.text
    body = client.post("/v1/bets/auto-settle", headers=headers).json()
    assert set(body) == {"checked", "settled", "skipped", "has_more"}
    assert body["has_more"] is False and body["checked"] == 1


def test_auto_settle_has_more_is_true_when_the_call_stops_early(
    client: TestClient, headers: Headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bets_service, "AUTO_SETTLE_MAX_PER_CALL", 1)
    final = client.get("/v1/events", params={"status": "final", "league": "nba"}).json()[0]
    leg = {
        "selection": "Home",
        "market": "moneyline",
        "odds": -110,
        "event_id": final["id"],
        "outcome_key": "home",
    }
    for minute in range(2):
        response = client.post(
            "/v1/bets",
            json=_bet(legs=[leg], placed_at=f"2026-03-01T12:0{minute}:00Z"),
            headers=headers,
        )
        assert response.status_code == 201, response.text
    first = client.post("/v1/bets/auto-settle", headers=headers).json()
    assert len(first["settled"]) == 1 and first["has_more"] is True
    second = client.post("/v1/bets/auto-settle", headers=headers).json()
    assert len(second["settled"]) == 1 and second["has_more"] is False


# ------------------------------------------------------------ sync finished
def _finished(**overrides: Any) -> Any:
    values: dict[str, Any] = {
        "run_id": "r1",
        "connection_id": "c1",
        "label": "Weekly account",
        "succeeded": True,
        "imported": 2,
        "duplicates": 1,
        "attempts": 1,
        **overrides,
    }
    return templates.sync_finished(**values)


def test_sync_finished_says_how_many_bets_the_run_left_out() -> None:
    assert _finished().body == "Weekly account import finished: 2 new, 1 already imported."
    assert _finished(not_imported=0).body == _finished().body
    assert _finished(not_imported=1).body == (
        "Weekly account import finished: 2 new, 1 already imported. "
        "1 bet was not imported; the import history says why."
    )
    assert _finished(not_imported=7).body == (
        "Weekly account import finished: 2 new, 1 already imported. "
        "7 bets were not imported; the import history says why."
    )
    # The data is unchanged, and a failed run keeps its own wording.
    assert set(_finished(not_imported=7).data) == {
        "run_id",
        "connection_id",
        "status",
        "imported",
        "duplicates",
    }
    failed = _finished(succeeded=False, imported=0, duplicates=0, not_imported=3)
    assert (
        failed.body
        == "Weekly account import did not finish after 1 attempt(s). No bets were added."
    )


def test_every_sync_finished_body_comes_from_a_template_and_reads_plainly() -> None:
    """The same checks as ``test_notification_copy.py`` for the new variants."""
    from .test_notification_copy import BANNED_PHRASES

    for draft in (_finished(not_imported=1), _finished(not_imported=40)):
        lowered = draft.body.lower()
        assert not any(phrase in lowered for phrase in BANNED_PHRASES), draft.body
        assert "!" not in draft.body and "%" not in draft.body and "  " not in draft.body
        assert draft.body.endswith(".") and draft.title == "Import finished"
