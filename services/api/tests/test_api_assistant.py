from __future__ import annotations

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oddvex_api.assistant import Assistant, Explainer, TemplateExplainer
from oddvex_api.board import Board
from oddvex_api.cache import InMemoryTTLCache
from oddvex_api.config import Settings
from oddvex_api.providers import SyntheticProvider

ALLOWED_HREF = re.compile(r"^/(app/(games/evt_\w+|props(/plr_\w+)?|tools|tracker|odds)|login)$")


def ask(client: TestClient, message: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    response = client.post("/v1/assistant/query", json={"message": message}, headers=headers or {})
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "intent",
        "answer",
        "data",
        "sources",
        "suggestions",
        "disclaimer",
        "support",
    }
    assert body["answer"]
    # Set only on a responsible-gambling reply: tests/test_audit_assistant_support.py.
    assert body["support"] is None and body["intent"] != "support"
    assert "not betting advice" in body["disclaimer"]
    assert "synthetic" in body["disclaimer"].lower()
    assert "call 1-800-MY-RESET (1-800-697-3738) or text 800GAM" in body["disclaimer"]
    for source in body["sources"]:
        assert set(source) == {"label", "as_of", "data_mode"}
    for suggestion in body["suggestions"]:
        assert ALLOWED_HREF.match(suggestion["href"]), suggestion
    return body


@pytest.fixture
def team(client: TestClient) -> dict[str, Any]:
    return client.get("/v1/events", params={"league": "nba", "status": "upcoming"}).json()[0]


def test_compare_odds_matches_the_odds_endpoint(client: TestClient, team: dict[str, Any]) -> None:
    name = team["home_team"]["name"]
    reply = ask(client, f"Who has the best odds for the {name}?")
    assert reply["intent"] == "compare_odds"
    data = reply["data"]
    odds = client.get(f"/v1/events/{data['event_id']}/odds").json()
    best = next(b for b in odds["best"] if b["outcome_key"] == data["side"])
    book = next(
        b["sportsbook"]["name"]
        for b in odds["books"]
        if b["sportsbook"]["key"] == best["sportsbook_key"]
    )
    assert data["best"]["american"] == best["price"]["american"]
    assert data["best"]["sportsbook"] == book
    assert data["books_compared"] == odds["consensus"]["books_used"]
    shown = (
        f"+{best['price']['american']}"
        if best["price"]["american"] > 0
        else str(best["price"]["american"])
    )
    assert shown in reply["answer"]
    assert book in reply["answer"] and name in reply["answer"]
    assert "not a prediction" in reply["answer"]
    assert reply["sources"][0]["data_mode"] == "synthetic"
    assert {"label": "Open this game", "href": f"/app/games/{data['event_id']}"} in reply[
        "suggestions"
    ]


def test_compare_odds_by_nickname_city_and_abbreviation(client: TestClient) -> None:
    for message in ("best price on the Tides", "harbor city moneyline?", "odds for HCT"):
        reply = ask(client, message)
        assert reply["intent"] == "compare_odds", message
        assert reply["data"]["team"] == "Harbor City Tides"


def test_compare_odds_without_a_team(client: TestClient) -> None:
    reply = ask(client, "what are the best odds tonight")
    assert reply["intent"] == "compare_odds"
    assert reply["data"] is None
    assert "couldn't match a team" in reply["answer"]
    assert reply["suggestions"] == [{"label": "Browse the odds board", "href": "/app/odds"}]


def test_line_movement(client: TestClient, team: dict[str, Any]) -> None:
    reply = ask(client, f"How has the line moved for {team['away_team']['name']}?")
    assert reply["intent"] == "line_movement"
    data = reply["data"]
    assert data["status"] == "ok" and data["side"] == "away"
    history = client.get(f"/v1/events/{data['event_id']}/line-history").json()
    series = [s for s in history["series"] if s["outcome_key"] == "away"]
    assert data["books"] == len(series)
    by_book = {m["sportsbook"]: m for m in data["moves"]}
    for line in series:
        move = by_book[line["sportsbook"]["name"]]
        assert move["open_american"] == line["points"][0]["price"]["american"]
        assert move["current_american"] == line["points"][-1]["price"]["american"]
    assert f"{data['open_implied'] * 100:.1f}%" in reply["answer"]
    assert f"{data['current_implied'] * 100:.1f}%" in reply["answer"]
    assert "does not say what happens next" in reply["answer"]
    assert ask(client, "any line movement today?")["data"] is None


def test_player_trend_matches_the_props_endpoint(client: TestClient) -> None:
    player = client.get("/v1/players", params={"league": "nba"}).json()[2]
    reply = ask(client, f"How has {player['name']} done on rebounds over his last 5?")
    assert reply["intent"] == "player_trend"
    data = reply["data"]
    assert (data["player_id"], data["market"], data["window"]) == (player["id"], "rebounds", "5")
    props = client.get(
        f"/v1/players/{player['id']}/props", params={"market": "rebounds", "window": "5"}
    ).json()
    for key in ("over_count", "sample_size", "rate", "ci_low", "ci_high", "line", "pushes"):
        assert data[key] == props["hit_rate"][key], key
    assert f"{data['over_count']} of {data['sample_size']}" in reply["answer"]
    assert f"{data['line']:g}" in reply["answer"]
    assert "not a prediction" in reply["answer"]
    assert reply["suggestions"][0]["href"] == f"/app/props/{player['id']}"


def test_player_trend_defaults_and_misses(client: TestClient) -> None:
    player = client.get("/v1/players", params={"league": "nfl"}).json()[0]
    reply = ask(client, f"{player['name']} trend")
    assert reply["data"]["market"] == player["prop_markets"][0]
    assert reply["data"]["window"] == "10"
    season = ask(client, f"{player['name']} this season")
    assert season["data"]["window"] == "season" and season["data"]["games"] >= 25
    nobody = ask(client, "what's the hit rate for that guy")
    assert nobody["intent"] == "player_trend" and nobody["data"] is None
    assert "couldn't match a player" in nobody["answer"]


def test_ambiguous_last_name_asks_which_player(
    client: TestClient, provider: SyntheticProvider
) -> None:
    last_names: dict[str, list[str]] = {}
    for player in provider.list_players():
        last_names.setdefault(player.name.split()[-1], []).append(player.name)
    shared = next((name for name, players in last_names.items() if len(players) > 1), None)
    if shared is None:
        pytest.skip("no shared last name in this seed")
    reply = ask(client, f"{shared} points")
    assert reply["intent"] == "player_trend"
    assert reply["data"]["status"] == "ambiguous_player"
    assert set(reply["data"]["candidates"]) <= set(last_names[shared])
    assert all(s["href"].startswith("/app/props/plr_") for s in reply["suggestions"])


def test_explain_ev_concept_and_computed(client: TestClient) -> None:
    concept = ask(client, "What is expected value?")
    assert concept["intent"] == "explain_ev"
    assert concept["data"]["status"] == "example"
    assert "+12.50%" in concept["answer"] and "Worked example" in concept["answer"]
    computed = ask(client, "what's the EV of -110 at 55%?")
    assert computed["data"]["status"] == "computed"
    direct = client.post("/v1/quant/ev", json={"odds": -110, "win_probability": 0.55}).json()
    assert computed["data"]["ev_percent"] == direct["ev_percent"]
    assert f"{direct['ev_percent']:+.2f}%" in computed["answer"]
    assert "does not estimate" in computed["answer"]
    assert computed["sources"][0]["data_mode"] == "calculation"
    assert computed["suggestions"] == [{"label": "Open the calculators", "href": "/app/tools"}]
    invalid = ask(
        client, "ev of +150 at 0%"
    )  # not a usable probability -> falls back to the example
    assert invalid["data"]["status"] == "example"


def test_explain_no_vig(client: TestClient) -> None:
    concept = ask(client, "explain no-vig odds")
    assert concept["intent"] == "explain_no_vig"
    assert "4.76%" in concept["answer"] and "50.00% / 50.00%" in concept["answer"]
    computed = ask(client, "remove the vig from -150 and +130")
    direct = client.post("/v1/quant/no-vig", json={"odds": [-150, 130]}).json()
    assert computed["data"]["status"] == "computed"
    assert [o["no_vig_probability"] for o in computed["data"]["outcomes"]] == [
        o["no_vig_probability"] for o in direct["outcomes"]
    ]
    assert computed["data"]["overround"] == direct["overround"]
    assert ask(client, "what is the juice?")["intent"] == "explain_no_vig"


def test_bet_summary_needs_login(client: TestClient) -> None:
    reply = ask(client, "how are my bets doing?")
    assert reply["intent"] == "bet_summary"
    assert reply["data"] is None
    assert "Log in" in reply["answer"]
    assert {"label": "Log in", "href": "/login"} in reply["suggestions"]


def test_bet_summary_for_a_logged_in_user(
    client: TestClient, headers: dict[str, str], other_headers: dict[str, str]
) -> None:
    empty = ask(client, "what's my ROI?", headers)
    assert empty["intent"] == "bet_summary" and empty["data"] is None
    assert "haven't tracked any bets" in empty["answer"]

    def add(stake: float, result: str | None, who: dict[str, str]) -> None:
        bet = client.post(
            "/v1/bets",
            json={
                "bet_type": "straight",
                "stake": stake,
                "sportsbook": "Northline",
                "legs": [{"selection": "x", "market": "moneyline", "odds": 100}],
            },
            headers=who,
        ).json()
        if result:
            client.post(f"/v1/bets/{bet['id']}/settle", json={"result": result}, headers=who)

    add(100, "won", headers)
    add(50, "lost", headers)
    add(20, None, headers)
    add(999, "lost", other_headers)  # must not leak into the first user's answer
    reply = ask(client, "what's my record?", headers)
    totals = client.get("/v1/bets/summary", headers=headers).json()["totals"]
    assert {k: reply["data"][k] for k in totals} == totals
    assert "2 settled bets: 1 won, 1 lost" in reply["answer"]
    assert "profit +50.00" in reply["answer"] and "ROI +33.3%" in reply["answer"]
    assert "1 pending with 20.00 at stake" in reply["answer"]
    assert "999" not in reply["answer"]
    assert reply["sources"][0]["data_mode"] == "user"
    assert reply["suggestions"] == [{"label": "Open your tracker", "href": "/app/tracker"}]


def test_invalid_token_is_rejected_rather_than_treated_as_anonymous(client: TestClient) -> None:
    response = client.post(
        "/v1/assistant/query", json={"message": "my bets"}, headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


def test_help(client: TestClient) -> None:
    for message in ("help", "What can you do?", "hello"):
        reply = ask(client, message)
        assert reply["intent"] == "help", message
        assert reply["data"] is None and reply["sources"] == []
        assert reply["support"] is None
        # "help" may not be about the product, so the answer always ends with the helpline.
        assert reply["answer"].endswith(
            "Looking for help with gambling itself? The National Problem Gambling Helpline is "
            "confidential and answers 24 hours a day, every day: call 1-800-MY-RESET "
            "(1-800-697-3738) or text 800GAM (800426)."
        )
    hrefs = {s["href"] for s in ask(client, "help")["suggestions"]}
    assert hrefs == {"/app/odds", "/app/props", "/app/tools", "/app/tracker"}


@pytest.mark.parametrize(
    "message",
    [
        "Who will win the championship this year?",
        "What's the weather in Paris?",
        "Write me a poem",
        "asdf qwer zxcv",
    ],
)
def test_fallback_is_honest_and_number_free(client: TestClient, message: str) -> None:
    reply = ask(client, message)
    assert reply["intent"] == "fallback"
    assert reply["data"] is None and reply["sources"] == []
    assert "can't answer" in reply["answer"]
    assert "predictions" in reply["answer"]
    assert not re.search(r"\d", reply["answer"])


def test_a_request_for_a_certain_winner_is_declined_without_numbers(client: TestClient) -> None:
    """RESPONSIBLE_GAMBLING.md section 5, row 3. More phrasings in the audit test file."""
    reply = ask(client, "Give me a lock for tonight")
    assert reply["intent"] == "fallback"
    assert reply["data"] is None and reply["sources"] == []
    assert "No result in sports is certain" in reply["answer"]
    assert "can't answer" in reply["answer"] and "predictions" in reply["answer"]
    assert not re.search(r"\d", reply["answer"])
    assert "lock" not in reply["answer"].lower()


def test_request_validation(client: TestClient) -> None:
    assert client.post("/v1/assistant/query", json={"message": ""}).status_code == 422
    assert client.post("/v1/assistant/query", json={"message": "x" * 501}).status_code == 422
    assert client.post("/v1/assistant/query", json={}).status_code == 422


def test_answers_only_contain_numbers_the_tools_produced(
    client: TestClient, team: dict[str, Any]
) -> None:
    """Every number in a data-backed answer must be traceable to the response's `data`."""
    player = client.get("/v1/players", params={"league": "nhl"}).json()[0]
    for message in (
        f"best odds for {team['home_team']['name']}",
        f"{player['name']} shots last 10",
        "ev of +200 at 30%",
    ):
        reply = ask(client, message)

        def numbers(value: Any) -> set[str]:
            found: set[str] = set()
            if isinstance(value, dict):
                for item in value.values():
                    found |= numbers(item)
            elif isinstance(value, list):
                for item in value:
                    found |= numbers(item)
            elif isinstance(value, bool) or value is None:
                pass
            elif isinstance(value, int | float):
                number = float(value)
                found |= {
                    f"{abs(number):g}",
                    f"{abs(number):.2f}",
                    f"{abs(number):.4f}",
                    f"{abs(number) * 100:.1f}",
                    f"{abs(number) * 100:.2f}",
                }
            elif isinstance(value, str):
                found |= set(re.findall(r"\d+(?:\.\d+)?", value))
            return found

        allowed = numbers(reply["data"]) | {"95", "1"}  # "95% interval", "(1 - p)" in the formula
        for token in re.findall(r"\d+(?:\.\d+)?", reply["answer"]):
            assert token in allowed, (message, token, reply["answer"])


class ShoutingExplainer:
    def explain(self, intent: str, facts: dict[str, Any]) -> str:
        return f"{intent.upper()}:{sorted(facts)}"


def test_explainer_is_pluggable_and_only_sees_tool_facts(provider: SyntheticProvider) -> None:
    assert isinstance(TemplateExplainer(), Explainer)
    assert isinstance(ShoutingExplainer(), Explainer)
    board = Board(provider, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]
    reply = Assistant(board, explainer=ShoutingExplainer()).answer("what is ev")
    assert reply.intent == "explain_ev"
    assert reply.answer.startswith("EXPLAIN_EV:")
    assert reply.data is not None and reply.data["ev_percent"] == 12.5
    assert TemplateExplainer().explain("unknown_intent", {}).startswith("I can't answer that")
