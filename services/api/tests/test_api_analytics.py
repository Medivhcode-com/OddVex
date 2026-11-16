"""Tracker analytics, checked against a hand-computed bet history."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from oddvex_api.bets.analytics import SMALL_SAMPLE, sample_note

from .conftest import admin_headers, auth_headers, set_flag

Headers = dict[str, str]

#: (placed, settled, stake, american odds, result, closing american odds)
HISTORY: list[tuple[str, str, float, int, str, int | None]] = [
    ("2026-01-05", "2026-01-05", 10, -250, "won", -280),  # Monday    +4.00   CLV +3.1579%
    ("2026-01-06", "2026-01-06", 20, -150, "lost", -140),  # Tuesday  -20.00  CLV -2.7778%
    ("2026-01-07", "2026-01-07", 25, -105, "won", None),  # Wednesday +23.81
    ("2026-01-12", "2026-02-01", 50, 150, "won", 130),  # Monday      +75.00  CLV +8.6957%
    ("2026-01-13", "2026-02-02", 100, 250, "lost", None),  # Tuesday  -100.00
    ("2026-01-17", "2026-02-03", 5, 100, "push", None),  # Saturday     0.00
    ("2026-01-18", "2026-02-04", 30, -110, "void", None),  # Sunday     0.00, not staked
]


def add_bet(
    client: TestClient,
    headers: Headers,
    placed: str,
    settled: str | None,
    stake: float,
    odds: int,
    result: str | None,
    closing: int | None = None,
) -> str:
    leg: dict[str, Any] = {"selection": "x", "market": "moneyline", "odds": odds}
    if closing is not None:
        leg["closing_odds"] = closing
    created = client.post(
        "/v1/bets",
        json={
            "bet_type": "straight",
            "stake": stake,
            "sportsbook": "Northline",
            "placed_at": f"{placed}T18:00:00Z",
            "legs": [leg],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    bet_id: str = created.json()["id"]
    if result is not None:
        done = client.post(
            f"/v1/bets/{bet_id}/settle",
            json={"result": result, "settled_at": f"{settled}T22:00:00Z"},
            headers=headers,
        )
        assert done.status_code == 200, done.text
    return bet_id


def analytics(client: TestClient, headers: Headers) -> dict[str, Any]:
    response = client.get("/v1/bets/analytics", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def row(
    key: str,
    label: str,
    bets: int = 0,
    staked: float = 0.0,
    profit: float = 0.0,
    roi: float | None = None,
    win_rate: float | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "bets": bets,
        "staked": staked,
        "profit": profit,
        "roi": roi,
        "win_rate": win_rate,
    }


@pytest.fixture
def history(client: TestClient, headers: Headers) -> Headers:
    for placed, settled, stake, odds, result, closing in HISTORY:
        add_bet(client, headers, placed, settled, stake, odds, result, closing)
    # A pending bet: it must not show up anywhere.
    add_bet(client, headers, "2026-01-20", None, 999, 500, None, 450)
    return headers


def test_analytics_match_the_hand_computed_history(client: TestClient, history: Headers) -> None:
    body = analytics(client, history)
    assert set(body) == {
        "settled_count",
        "by_odds_band",
        "by_weekday",
        "by_month",
        "longest_win_streak",
        "longest_loss_streak",
        "current_streak",
        "average_stake",
        "average_odds",
        "clv",
        "stake_distribution",
        "sample_note",
        "note",
    }
    assert body["settled_count"] == 7

    assert body["by_odds_band"] == [
        row("-200_or_shorter", "-200 or shorter", 1, 10.0, 4.0, 0.4, 1.0),
        # -150 lost and the void -110: the void bet counts as a bet but not as staked.
        row("-199_to_-110", "-199 to -110", 2, 20.0, -20.0, -1.0, 0.0),
        # -105 won 23.81 on 25; +100 pushed on 5.  23.81 / 30 = 0.793667
        row("-109_to_+100", "-109 to +100", 2, 30.0, 23.81, 0.793667, 1.0),
        row("+101_to_+200", "+101 to +200", 1, 50.0, 75.0, 1.5, 1.0),
        row("longer_than_+200", "Longer than +200", 1, 100.0, -100.0, -1.0, 0.0),
    ]

    assert body["by_weekday"] == [
        row("monday", "Monday", 2, 60.0, 79.0, 1.316667, 1.0),  # 79 / 60
        row("tuesday", "Tuesday", 2, 120.0, -120.0, -1.0, 0.0),
        row("wednesday", "Wednesday", 1, 25.0, 23.81, 0.9524, 1.0),  # 23.81 / 25
        row("thursday", "Thursday"),
        row("friday", "Friday"),
        row("saturday", "Saturday", 1, 5.0, 0.0, 0.0, None),  # a push: nothing decided
        row("sunday", "Sunday", 1, 0.0, 0.0, None, None),  # a void: nothing staked
    ]

    assert body["by_month"] == [
        # Settled in January: +4.00, -20.00, +23.81 on 55 staked.  7.81 / 55 = 0.142
        row("2026-01", "January 2026", 3, 55.0, 7.81, 0.142, 0.666667),
        # Settled in February: +75, -100, push, void on 155 staked.  -25 / 155
        row("2026-02", "February 2026", 4, 155.0, -25.0, -0.16129, 0.5),
    ]

    # In settlement order: W L W W L push void.
    assert body["longest_win_streak"] == 2
    assert body["longest_loss_streak"] == 1
    assert body["current_streak"] == {"kind": "loss", "length": 1}

    # Void bet excluded: (10 + 20 + 25 + 50 + 100 + 5) / 6
    assert body["average_stake"] == 35.0
    # (1.4 + 1.666667 + 1.952381 + 2.5 + 3.5 + 2.0) / 6 = 2.169841
    assert body["average_odds"] == {
        "american": 117,
        "decimal": 2.1698,
        "fractional": "62/53",
        "implied_probability": 0.460863,
    }

    assert body["clv"] == {
        "sample": 3,
        # (0.031579 - 0.027778 + 0.086957) / 3
        "average": 0.030253,
        "share_beating_close": 0.666667,
        "buckets": [
            {"key": "below_-5", "label": "Below -5%", "count": 0},
            {"key": "-5_to_-2", "label": "-5% to -2%", "count": 1},
            {"key": "-2_to_0", "label": "-2% to 0%", "count": 0},
            {"key": "0_to_2", "label": "0% to 2%", "count": 0},
            {"key": "2_to_5", "label": "2% to 5%", "count": 1},
            {"key": "5_or_more", "label": "5% or more", "count": 1},
        ],
    }

    assert body["stake_distribution"] == [
        {"key": "under_10", "label": "Under $10", "bets": 1, "staked": 5.0},
        {"key": "10_to_25", "label": "$10 to $24.99", "bets": 2, "staked": 30.0},
        {"key": "25_to_50", "label": "$25 to $49.99", "bets": 1, "staked": 25.0},
        {"key": "50_to_100", "label": "$50 to $99.99", "bets": 1, "staked": 50.0},
        {"key": "100_or_more", "label": "$100 or more", "bets": 1, "staked": 100.0},
    ]

    assert body["sample_note"] == (
        "Small sample: 7 settled bets. With fewer than 30, these results are mostly noise "
        "and say little about anything but the bets themselves."
    )
    assert "settled bets only" in body["note"] and "do not predict" in body["note"]


def test_analytics_agree_with_the_summary(client: TestClient, history: Headers) -> None:
    body = analytics(client, history)
    totals = client.get("/v1/bets/summary", headers=history).json()["totals"]
    assert totals["settled_count"] == body["settled_count"] == 7
    for group in ("by_odds_band", "by_weekday", "by_month"):
        assert sum(r["bets"] for r in body[group]) == 7, group
        assert round(sum(r["staked"] for r in body[group]), 2) == totals["staked"] == 210.0
        assert round(sum(r["profit"] for r in body[group]), 2) == totals["profit"] == -17.19
    assert sum(b["bets"] for b in body["stake_distribution"]) == 6  # the void bet is left out
    assert sum(b["count"] for b in body["clv"]["buckets"]) == body["clv"]["sample"]


def test_no_settled_bets(client: TestClient, headers: Headers) -> None:
    add_bet(client, headers, "2026-01-20", None, 50, -110, None)  # pending only
    body = analytics(client, headers)
    assert body["settled_count"] == 0
    assert [r["bets"] for r in body["by_odds_band"]] == [0] * 5
    assert all(r["roi"] is None and r["win_rate"] is None for r in body["by_odds_band"])
    assert len(body["by_weekday"]) == 7 and body["by_month"] == []
    assert body["longest_win_streak"] == body["longest_loss_streak"] == 0
    assert body["current_streak"] == {"kind": "none", "length": 0}
    assert body["average_stake"] is None and body["average_odds"] is None
    assert body["clv"]["sample"] == 0 and body["clv"]["average"] is None
    assert body["clv"]["share_beating_close"] is None
    assert [b["bets"] for b in body["stake_distribution"]] == [0] * 5
    assert body["sample_note"].startswith("Small sample: 0 settled bets.")


def test_sample_note_goes_away_at_thirty_settled_bets(client: TestClient, headers: Headers) -> None:
    assert SMALL_SAMPLE == 30
    assert sample_note(1) is not None and "1 settled bet." in (sample_note(1) or "")
    assert sample_note(29) is not None and sample_note(30) is None
    for index in range(29):
        add_bet(
            client, headers, "2026-01-05", "2026-01-06", 10, -110, "won" if index % 2 else "lost"
        )
    body = analytics(client, headers)
    assert body["settled_count"] == 29 and "mostly noise" in body["sample_note"]
    add_bet(client, headers, "2026-01-05", "2026-01-07", 10, -110, "won")
    body = analytics(client, headers)
    assert body["settled_count"] == 30 and body["sample_note"] is None


def test_a_parlay_is_banded_by_its_combined_price(client: TestClient, headers: Headers) -> None:
    created = client.post(
        "/v1/bets",
        json={
            "bet_type": "parlay",
            "stake": 10,
            "sportsbook": "Northline",
            "placed_at": "2026-01-05T18:00:00Z",
            "legs": [
                {"selection": "a", "market": "moneyline", "odds": -110},
                {"selection": "b", "market": "moneyline", "odds": -110},
            ],
        },
        headers=headers,
    ).json()
    client.post(f"/v1/bets/{created['id']}/settle", json={"result": "won"}, headers=headers)
    assert created["combined_price"]["american"] == 264
    bands = {r["key"]: r["bets"] for r in analytics(client, headers)["by_odds_band"]}
    assert bands == {
        "-200_or_shorter": 0,
        "-199_to_-110": 0,
        "-109_to_+100": 0,
        "+101_to_+200": 0,
        "longer_than_+200": 1,
    }


def test_analytics_are_owner_scoped(
    client: TestClient, history: Headers, other_headers: Headers
) -> None:
    assert client.get("/v1/bets/analytics").status_code == 401
    theirs = analytics(client, other_headers)
    assert theirs["settled_count"] == 0 and theirs["by_month"] == []
    add_bet(client, other_headers, "2026-03-02", "2026-03-03", 77, 300, "won")
    theirs = analytics(client, other_headers)
    assert theirs["settled_count"] == 1 and theirs["average_stake"] == 77.0
    assert [r["key"] for r in theirs["by_month"]] == ["2026-03"]
    mine = analytics(client, history)
    assert mine["settled_count"] == 7 and mine["average_stake"] == 35.0
    assert [r["key"] for r in mine["by_month"]] == ["2026-01", "2026-02"]


def test_analytics_flag_off(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    user = auth_headers(admin_client)
    set_flag(admin_client, admin, "tracker_analytics", False)
    off = admin_client.get("/v1/bets/analytics", headers=user)
    assert off.status_code == 404
    assert off.json()["error"]["code"] == "feature_disabled"
    assert off.json()["error"]["details"] == {"flag": "tracker_analytics"}
    assert admin_client.get("/v1/bets/summary", headers=user).status_code == 200
