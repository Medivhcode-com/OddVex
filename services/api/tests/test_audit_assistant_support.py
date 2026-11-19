"""The assistant's responsible-gambling replies (audit finding compliance#1).

docs/compliance/RESPONSIBLE_GAMBLING.md section 5 is the specification. One block of tests
per row: distress about gambling, crisis or self-harm language, a request for a certain
winner, a bet sized to recover losses, and a user who says they are under 21. Each block
sends several phrasings through ``POST /v1/assistant/query``, mixed with the keywords, team
names and player names that used to win the routing, and checks that the reply carries help
and no betting data. The last block is the other direction: ordinary sports questions that
look similar must still get their normal answer.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oddvex_api.assistant import Assistant
from oddvex_api.board import Board
from oddvex_api.cache import InMemoryTTLCache
from oddvex_api.config import Settings
from oddvex_api.providers import SyntheticProvider

TEAM = "Harbor City Tides"
HELPLINE = "1-800-MY-RESET (1-800-697-3738)"
RESOURCES = {"label": "Help and support resources", "href": "/responsible-gambling"}

#: An American price or a percentage: what a betting answer contains and a support reply must not.
PRICE = re.compile(r"(?<![\w.])[+-]\d{3,5}(?![\d.%])|\d\s?%|\bdecimal \d")
#: Words the product never uses (PROJECT_CONSTITUTION.md, BRAND_VOICE.md).
BANNED = ("lock", "guaranteed", "can't lose", "risk-free", "risk free", "sure thing", "win either")
#: Wording that would blame the user.
SHAMING = (
    "your fault",
    "irresponsible",
    "reckless",
    "stupid",
    "foolish",
    "you should have",
    "shame",
    "addict",
    "weak",
    "you must",
    "you need to",
    "!",
)


def ask(client: TestClient, message: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    response = client.post("/v1/assistant/query", json={"message": message}, headers=headers or {})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert set(body) == {
        "intent",
        "answer",
        "data",
        "sources",
        "suggestions",
        "disclaimer",
        "support",
    }
    return body


def assert_support_reply(reply: dict[str, Any], case: str, message: str) -> str:
    """What every support reply has in common. Returns the answer text."""
    assert reply["intent"] == "support", (message, reply["intent"], reply["answer"])
    assert reply["support"] == {"case": case}, (message, reply["support"])
    assert reply["data"] is None, message
    assert reply["sources"] == [], message
    answer: str = reply["answer"]
    assert not PRICE.search(answer), (message, answer)
    assert TEAM not in answer and "Tides" not in answer, (message, answer)
    lowered = answer.lower()
    for phrase in (*BANNED, *SHAMING):
        assert phrase not in lowered, (message, phrase)
    for suggestion in reply["suggestions"]:
        assert suggestion["href"] in {"/responsible-gambling", "/app/settings", "/app/tracker"}
    return answer


@pytest.fixture
def player(client: TestClient) -> str:
    name: str = client.get("/v1/players", params={"league": "nba"}).json()[0]["name"]
    return name


# ------------------------------------------------ row 2: self-harm or crisis language
CRISIS_MESSAGES = [
    "I want to kill myself after losing my bankroll, show my record",
    "im thinking about suicide",
    "I don’t want to live anymore. Best odds on the Harbor City Tides?",  # curly apostrophe
    "lost it all tonight, i want to end it all",
    "I wish I was dead",
    "I can't go on like this, what's my ROI",
    "thinking of hurting myself",
    "There's no way out for me",
    "I'd be better off dead than paying this back",
    "KMS if this parlay loses",
    "I feel suicidal. What is the EV of -110 at 55%?",
    "I WANT TO DIE",
    "sometimes I think about ending my life",
    "{player} points last 10, honestly i want to hurt myself",
]


@pytest.mark.parametrize("template", CRISIS_MESSAGES)
def test_crisis_language_gets_only_support(client: TestClient, player: str, template: str) -> None:
    message = template.format(player=player)
    reply = ask(client, message)
    answer = assert_support_reply(reply, "crisis", message)
    # 988 and 911 come first, then the gambling helpline.
    assert "Call or text 988 (the Suicide and Crisis Lifeline)" in answer
    assert "call 911" in answer
    assert HELPLINE in answer and "800GAM" in answer
    assert answer.index("988") < answer.index("911") < answer.index("1-800-MY-RESET")
    # Row 2: encourage reaching out to someone now.
    assert "someone you trust" in answer
    # Only support: no analysis, no product pitch, no way back into the betting screens.
    lowered = answer.lower()
    for word in ("odds", "price", "tracker", "calculator", "staking", "parlay", "bet "):
        assert word not in lowered, (message, word)
    assert player not in answer
    assert reply["suggestions"] == [RESOURCES]


def test_crisis_reply_is_the_same_signed_in(client: TestClient, headers: dict[str, str]) -> None:
    message = "I want to kill myself after losing my bankroll, show my record"
    signed_in = ask(client, message, headers)
    assert_support_reply(signed_in, "crisis", message)
    assert signed_in["answer"] == ask(client, message)["answer"]
    assert "haven't tracked any bets" not in signed_in["answer"]


# ------------------------------------------- rows 1 and 4: distress about gambling
DISTRESS_MESSAGES = [
    "I need to win it back tonight, best odds on the Harbor City Tides?",  # the audit's probe
    "I can't stop betting",
    "I can’t stop gambling, what's my ROI?",  # curly apostrophe
    "i cant stop. best price on the Tides",
    "I've lost everything",
    "I lost everything on the Tides last night, what are their odds now",
    "I borrowed money to cover my bets, {player} points last 10",
    "I'm hiding my betting from my wife",
    "my husband doesn't know how much I've lost",
    "I think I have a gambling problem",
    "I lost my rent money on the Tides",
    "how do i stop gambling",
    "I'm addicted to parlays, line movement for the Tides?",
    "I maxed out my credit card on bets, what is no-vig",
    "I can't afford to lose again, who has the best moneyline",
    "I bet more than I can afford and now I'm in debt",
    "I took out a loan to keep betting",
    "gambling is ruining my life",
    "i need help with my gambling",
    "I keep lying to my family about my betting",
]

CHASING_MESSAGES = [
    "How much should I bet to recover my losses?",  # row 4, word for word
    "how do I win back what I lost",
    "I'm chasing my losses again, what is the EV of -110 at 55%?",
    "need to get my money back tonight, odds for HCT",
    "what stake gets me back to even after last night",
    "help me make it all back, best price on the Tides",
    "I have to double up to win my money back",
]


@pytest.mark.parametrize("template", [*DISTRESS_MESSAGES, *CHASING_MESSAGES])
def test_distress_about_gambling_gets_help_and_no_betting_data(
    client: TestClient, player: str, template: str
) -> None:
    message = template.format(player=player)
    reply = ask(client, message)
    answer = assert_support_reply(reply, "distress", message)
    # Row 1: acknowledge without judgement, give the helpline, link to the page.
    assert answer.startswith("Thank you for telling me.")
    assert HELPLINE in answer and "text 800GAM (800426)" in answer
    assert "confidential" in answer and "24 hours a day, every day" in answer
    # The app's own tools, described as what they are: a reminder, not a limit.
    assert "weekly staking reminder" in answer and "bet tracker" in answer
    assert "a reminder, not a limit" in answer
    # The helpline is not an emergency service, so the crisis line is named too.
    assert "988" in answer and "911" in answer
    assert player not in answer
    assert reply["suggestions"] == [
        RESOURCES,
        {"label": "Weekly staking reminder", "href": "/app/settings"},
        {"label": "Bet tracker", "href": "/app/tracker"},
    ]


@pytest.mark.parametrize("message", CHASING_MESSAGES)
def test_a_bet_to_recover_losses_is_declined_and_named_as_a_warning_sign(
    client: TestClient, message: str
) -> None:
    answer = ask(client, message)["answer"]
    assert "I can't help size or pick a bet to win money back" in answer
    assert "recognised warning sign" in answer


def test_distress_without_loss_chasing_is_not_told_about_loss_chasing(client: TestClient) -> None:
    answer = ask(client, "I can't stop betting")["answer"]
    assert "warning sign" not in answer and "win money back" not in answer


def test_distress_reply_does_not_read_the_users_bets(
    client: TestClient, headers: dict[str, str]
) -> None:
    client.post(
        "/v1/bets",
        json={
            "bet_type": "straight",
            "stake": 250,
            "sportsbook": "Northline",
            "legs": [{"selection": "x", "market": "moneyline", "odds": 100}],
        },
        headers=headers,
    )
    message = "I can't stop betting, what's my record?"
    reply = ask(client, message, headers)
    answer = assert_support_reply(reply, "distress", message)
    assert "250" not in answer and "settled" not in answer


# ------------------------------------------------------- row 5: the user is under 21
UNDERAGE_MESSAGES = [
    "I'm 17, show me odds for the Harbor City Tides",  # the audit's probe
    "im 19 and I want the best price on the Tides",
    "I am 16 years old. what is expected value?",
    "I'm under 21, can I still see player props?",
    "I'm in high school, who has the best moneyline?",
    "I turn 21 next month, odds for HCT",
    "I’m only 20 — line movement for the Tides?",  # curly apostrophe
    "as a 17 year old what's the juice",
    "I'm seventeen, best odds tonight",
    "I'm not 21 yet, how are my bets doing?",
    "I'm 18 show me {player} points last 10",
    "17 years old here, best odds for the Harbor City Tides",
    "I'm a minor, what does +150 mean",
    "i'm underage but want to see the odds",
    "I just turned 18, what is the best price on the Tides",
    "I'll be 21 in March. Tides moneyline?",
    "I'm 19 in New Jersey, which book has the best price on the Tides",
]


@pytest.mark.parametrize("template", UNDERAGE_MESSAGES)
def test_a_user_who_says_they_are_under_21_gets_no_betting_information(
    client: TestClient, player: str, template: str
) -> None:
    message = template.format(player=player)
    reply = ask(client, message)
    answer = assert_support_reply(reply, "underage", message)
    assert answer.startswith("OddVex is for adults 21 and over")
    assert "can't give odds, prices or any other betting information" in answer
    assert HELPLINE in answer  # help is offered either way, without assuming anything
    assert player not in answer
    assert reply["suggestions"] == [RESOURCES]


def test_under_21_and_in_distress_gets_both_messages(client: TestClient, player: str) -> None:
    message = f"I'm 19 and I lost everything, is {player} going over?"  # the checker's probe
    answer = assert_support_reply(ask(client, message), "underage", message)
    assert "21 and over" in answer and HELPLINE in answer
    assert "Thank you for telling me" in answer
    # The limit tools are for account holders, who are 21 or over: not offered here.
    assert "staking reminder" not in answer


def test_crisis_language_wins_over_everything_else(client: TestClient) -> None:
    for message in (
        "I'm 17 and I want to die",
        "I can't stop betting and I want to kill myself",
        "give me a lock or I'll end it all",
    ):
        assert_support_reply(ask(client, message), "crisis", message)


# ------------------------------------------- row 3: a request for a certain winner
CERTAINTY_MESSAGES = [
    "Give me a lock for tonight",
    "What's a sure thing tonight?",
    "Is the Harbor City Tides moneyline a guaranteed winner?",
    "any can't-lose bets?",
    "risk free bet on the Tides?",
    "what's the lock of the day",
    "which bet is 100% going to win",
    "is the Tides moneyline free money",
]


@pytest.mark.parametrize("message", CERTAINTY_MESSAGES)
def test_a_request_for_a_certain_winner_is_declined(client: TestClient, message: str) -> None:
    reply = ask(client, message)
    assert reply["intent"] == "fallback", (message, reply["intent"])
    assert reply["support"] is None
    assert reply["data"] is None and reply["sources"] == []
    answer = reply["answer"]
    assert "No result in sports is certain" in answer
    assert "I don't make picks or predictions" in answer
    assert "market data" in answer  # row 3: offer market data only
    assert not re.search(r"\d", answer), answer
    lowered = answer.lower()
    for phrase in BANNED:
        assert phrase not in lowered, (message, phrase)
    assert reply["suggestions"] == [
        {"label": "Odds board", "href": "/app/odds"},
        {"label": "Calculators", "href": "/app/tools"},
    ]


# ------------------------------------------- ordinary questions keep their answers
@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("best odds for the Harbor City Tides", "compare_odds"),
        ("I'm 25, best odds for the Harbor City Tides", "compare_odds"),
        ("I just turned 21, best odds for the Tides", "compare_odds"),
        ("my son is 17 and loves the Tides. best odds?", "compare_odds"),
        ("I'm 20 dollars down on the Tides, best odds?", "compare_odds"),
        ("Tides under 21.5 in the first quarter, best price?", "compare_odds"),
        ("I'm on the under 21 for the Tides, best price?", "compare_odds"),
        ("The Tides can't stop the run. Best price?", "compare_odds"),
        ("who killed it last night? Tides odds", "compare_odds"),
        ("the Tides lost everything in the fourth quarter, odds for their next game", "compare_odds"),
        ("the Tides are desperate for a win, what's their price", "compare_odds"),
        ("is this a must win for the Tides? moneyline", "compare_odds"),
        ("Tides to win back-to-back games, best price", "compare_odds"),
        ("The Tides lost the game, how did the line move?", "line_movement"),
        ("what's the hit rate over the last 17", "player_trend"),
        ("{player} points last 17", "player_trend"),
        ("I am 10 for 12 on unders, what's the hit rate", "player_trend"),
        ("is there a suicide squeeze prop?", "player_trend"),
        ("I'm 3-0 this week, what's my record?", "bet_summary"),
        ("I'm 15 units up, what's my ROI?", "bet_summary"),
        ("I lost my last bet, what's my record", "bet_summary"),
        ("I'm 18 bets in, how am I doing", "bet_summary"),
        ("What is the break-even probability at -110? EV", "explain_ev"),
        ("what is the hold on -110 and -110", "explain_no_vig"),
        ("help", "help"),
        ("How do I lock my phone screen", "help"),
        ("Who will win the championship this year?", "fallback"),
    ],
)
def test_ordinary_questions_are_not_treated_as_distress(
    client: TestClient, player: str, message: str, intent: str
) -> None:
    reply = ask(client, message.format(player=player))
    assert reply["intent"] == intent, (message, reply["answer"])
    assert reply["support"] is None
    if intent == "fallback":
        assert reply["answer"].startswith("I can't answer that. I'm a rule-based helper")


# ----------------------------------------------------------------- the contract
def test_the_schema_change_is_additive(client: TestClient) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    response = schemas["AssistantResponse"]
    assert {"intent", "answer", "data", "sources", "suggestions", "disclaimer"} <= set(
        response["properties"]
    )
    assert "support" in response["properties"]
    assert "support" not in response.get("required", [])
    assert set(response["properties"]["intent"]["enum"]) == {
        "compare_odds",
        "explain_ev",
        "explain_no_vig",
        "player_trend",
        "line_movement",
        "bet_summary",
        "help",
        "fallback",
        "support",
    }
    assert set(schemas["AssistantSupportOut"]["properties"]["case"]["enum"]) == {
        "crisis",
        "distress",
        "underage",
    }


class ShoutingExplainer:
    def explain(self, intent: str, facts: dict[str, Any]) -> str:
        return f"{intent.upper()}:{sorted(facts)}"


def test_a_custom_explainer_cannot_reword_a_support_reply(provider: SyntheticProvider) -> None:
    board = Board(provider, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]
    shouting = Assistant(board, explainer=ShoutingExplainer())
    plain = Assistant(board)
    for message in ("I want to kill myself", "I can't stop betting", "I'm 17, Tides odds"):
        reply = shouting.answer(message)
        assert reply.intent == "support"
        assert reply.answer == plain.answer(message).answer
        assert "1-800-MY-RESET" in reply.answer
    assert shouting.answer("what is ev").answer.startswith("EXPLAIN_EV:")


def test_a_support_reply_is_logged_by_case_without_the_message(
    client: TestClient, headers: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    logger = logging.getLogger("oddvex.assistant")
    logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger="oddvex.assistant"):
            ask(client, "I'm 17, show me odds for the Harbor City Tides", headers)
            ask(client, "I want to kill myself")
            ask(client, "best odds for the Harbor City Tides")
    finally:
        logger.removeHandler(caplog.handler)
    records = [r for r in caplog.records if r.getMessage() == "assistant_support_reply"]
    assert [(r.case, r.signed_in) for r in records] == [("underage", True), ("crisis", False)]
    standard = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}
    for record in records:
        # Only the case and whether a token was sent: no message text, no user, no address.
        assert set(record.__dict__) - standard == {"case", "signed_in"}
        assert not record.args
