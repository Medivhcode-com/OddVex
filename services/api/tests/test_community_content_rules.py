"""The automatic content rules for community text: a pure function, tested exhaustively.

Every rule has true positives and near misses here. The near misses matter as much as the
hits: a rule that rejects "locker room" would make the feature unusable."""

from __future__ import annotations

import pytest

from oddvex_api.community import content_rules
from oddvex_api.community.content_rules import RULE_KEYS, RULES, check_text, normalise

CURLY = chr(0x2019)

#: (text, rule that has to reject it)
REJECTED: list[tuple[str, str]] = [
    # ---- guaranteed outcomes
    ("This one is guaranteed.", "guaranteed_outcome"),
    ("GUARANTEED winner tonight", "guaranteed_outcome"),
    ("I guarantee the over", "guaranteed_outcome"),
    ("Nothing guarantees it but still", "guaranteed_outcome"),
    ("Lock of the week", "guaranteed_outcome"),
    ("my lock of the day: Tides", "guaranteed_outcome"),
    ("lock of the century", "guaranteed_outcome"),
    ("You can't lose with this", "guaranteed_outcome"),
    (f"You can{CURLY}t lose with this", "guaranteed_outcome"),
    ("cant lose", "guaranteed_outcome"),
    ("cannot lose here", "guaranteed_outcome"),
    ("Can  NOT   lose", "guaranteed_outcome"),
    ("can't miss spot", "guaranteed_outcome"),
    ("a sure thing", "guaranteed_outcome"),
    ("Sure Thing", "guaranteed_outcome"),
    ("this is risk-free", "guaranteed_outcome"),
    ("risk free play", "guaranteed_outcome"),
    ("totally riskfree", "guaranteed_outcome"),
    (f"risk{chr(0x2013)}free", "guaranteed_outcome"),  # en dash
    ("it is free money", "guaranteed_outcome"),
    ("FREE  MONEY", "guaranteed_outcome"),
    # ---- inducement
    ("bet the house on it", "inducement_to_bet"),
    ("Bet the farm", "inducement_to_bet"),
    ("bet the mortgage", "inducement_to_bet"),
    ("max bet this", "inducement_to_bet"),
    ("Maximum bet spot", "inducement_to_bet"),
    ("time to chase your losses", "inducement_to_bet"),
    ("chasing losses with this one", "inducement_to_bet"),
    ("after those losses I am chasing", "inducement_to_bet"),
    ("one loss, chase it", "inducement_to_bet"),
    ("win it back tonight", "inducement_to_bet"),
    ("win it all back", "inducement_to_bet"),
    # ---- selling picks, promotions, payments
    ("use my promo code", "selling_or_promotion"),
    ("promo codes inside", "selling_or_promotion"),
    ("promotional code TIDES", "selling_or_promotion"),
    ("sign up bonus", "selling_or_promotion"),
    ("sign-up bonuses", "selling_or_promotion"),
    ("signup bonus", "selling_or_promotion"),
    ("send it on cashapp", "selling_or_promotion"),
    ("Cash App me", "selling_or_promotion"),
    ("venmo for the full card", "selling_or_promotion"),
    ("PayPal accepted", "selling_or_promotion"),
    # ---- contact solicitation
    ("dm me for more", "contact_solicitation"),
    ("DM ME", "contact_solicitation"),
    ("join my telegram", "contact_solicitation"),
    ("Telegram group", "contact_solicitation"),
    ("whatsapp group", "contact_solicitation"),
    ("Whats App me", "contact_solicitation"),
    # ---- contact details
    ("mail picks@example.test", "contact_details"),
    ("write to First.Last+tag@mail.example.co", "contact_details"),
    ("call 555-123-4567", "contact_details"),
    ("call (555) 123-4567", "contact_details"),
    ("555.123.4567", "contact_details"),
    ("555 123 4567", "contact_details"),
    ("5551234567", "contact_details"),
    ("text 15551234567 for picks", "contact_details"),
    ("+44 20 7946 0958", "contact_details"),
    ("+1-555-123-4567", "contact_details"),
]

#: Text that has to pass. Each one is close to a rule on purpose.
ALLOWED: list[str] = [
    # "lock" without "of the", and words that merely contain it
    "The locker room was quiet after the game.",
    "They need to unlock the half-court offense.",
    "A blocked shot changed the fourth quarter.",
    "Their shot blocker is out.",
    "The clock ran out.",
    "A lockdown defender on the wing.",
    "Flock of the season ticket holders",
    # "chase" without losses, "losses" without chase
    "The chase for the eighth seed is close.",
    "Three straight losses on the road.",
    "They chased the game in the second half.",
    "A purchase of new jerseys.",
    # near misses of the guarantee rules
    "I am not sure about this one.",
    "Sure, the thing about pace is real.",
    "Nothing is certain in a seven game series.",
    "The risk is the back to back.",
    "Free throws decided it. Money line moved.",
    "They can lose this if the bench is cold.",
    "Can't miss him: he plays 38 minutes.",  # "can't miss" is banned, see below
    # near misses of the inducement rules
    "The max was 41 points last month.",
    "I would not bet on a rookie here.",
    "Home teams in the house tonight.",
    "They win it at the line.",
    # near misses of the selling and contact rules
    "A promotion from the second division.",
    "The code of the league bans it.",
    "He signed up for another year. Bonus: his brother too.",
    "Cash considerations in the trade. App is down.",
    "The team telegraphs every pass.",
    "What's up with the app tonight?",
    "DMs are not a thing here, and that is fine.",
    "Paying a pal back for the tickets.",
    # numbers that are not phone numbers
    "Won 112-108 at home.",
    "Final was 112-108, 2-1 in the series.",
    "The 2025-26 season starts soon.",
    "Over 224.5 at -110, was 221.5 this morning.",
    "+150 on the moneyline, -3.5 on the spread.",
    "Attendance was 18,203.",
    "He averages 27.4 points on 19.8 shots in 36.1 minutes.",
    "Record: 41-27. Home: 24-10. Last 10: 7-3.",
    "Game 7 is on 6/14 at 7:30.",
    "123456",  # six digits in a row is not a phone number
    # "@" without an address
    "@sample_sam I see it differently.",
    "Tides @ Anvils tonight.",
    "Line is 3.5 @ -110",
    # other scripts and punctuation pass untouched
    "Très bon match hier soir.",
    "Ünïcode ist kein Problem.",
    "No links, just numbers.",
    "https is a protocol.",  # the word alone, without ://
    "the www of sports",  # no dot after www
]


@pytest.mark.parametrize(("text", "rule"), REJECTED)
def test_rejected_text_names_the_rule(text: str, rule: str) -> None:
    violation = check_text(text)
    assert violation is not None, text
    assert (violation.code, violation.rule) == ("content_not_allowed", rule), text
    assert violation.message and "!" not in violation.message


@pytest.mark.parametrize("text", [t for t in ALLOWED if not t.startswith("Can't miss him")])
def test_obvious_false_positives_pass(text: str) -> None:
    assert check_text(text) is None, text


@pytest.mark.parametrize(
    "text",
    [
        "see http://example.test/picks",
        "see https://example.test",
        "HTTPS://EXAMPLE.TEST",
        "www.example.test has it",
        "(www.example.test)",
        "go to WWW.example.test",
        "line shopping at https://a.example and promo code X",  # the link is reported first
    ],
)
def test_links_are_rejected_with_their_own_code(text: str) -> None:
    violation = check_text(text)
    assert violation is not None
    assert (violation.code, violation.rule) == ("links_not_allowed", "links")
    assert content_rules.contains_link(text)


def test_every_rule_has_a_true_positive_in_this_file() -> None:
    covered = {rule for _, rule in REJECTED}
    assert covered == set(RULE_KEYS)
    assert RULE_KEYS == (
        "guaranteed_outcome",
        "inducement_to_bet",
        "selling_or_promotion",
        "contact_solicitation",
        "contact_details",
    )
    # And every pattern, not only every key, matches at least one of the examples.
    for rule in RULES:
        assert any(rule.pattern.search(normalise(text)) for text, _ in REJECTED), rule.pattern


def test_the_phrases_the_brief_lists_are_all_rejected() -> None:
    for phrase in (
        "guaranteed",
        "lock of the",
        "can't lose",
        "risk-free",
        "free money",
        "sure thing",
        "bet the house",
        "max bet",
        "chase your losses",
        "dm me",
        "telegram",
        "whatsapp",
        "cashapp",
        "venmo",
        "paypal",
        "promo code",
        "sign up bonus",
    ):
        for text in (phrase, phrase.upper(), f"Honestly, {phrase} tonight."):
            assert check_text(text) is not None, text


def test_blank_text_is_acceptable_and_normalise_is_stable() -> None:
    assert check_text(None) is None and check_text("") is None and check_text("  \n ") is None
    assert normalise(f"  Can{CURLY}t   LOSE\n") == "can't lose"
    assert normalise(normalise("A  B")) == normalise("A  B") == "a b"
    fullwidth = "".join(chr(ord(c) + 0xFEE0) for c in "GUARANTEED")
    assert check_text(fullwidth) is not None  # compatibility forms are folded first


def test_documented_limits_of_the_rules() -> None:
    """Pinned on purpose, so a change to either is a decision and not an accident."""
    # Blunt: the rules match phrases, not intent, so sensible advice is rejected too.
    assert check_text("Do not chase your losses.") is not None
    assert check_text("No result is guaranteed.") is not None
    assert check_text("Can't miss him: he plays 38 minutes.") is not None
    assert check_text("He can't lose the ball that often.") is not None
    # A score followed by a year has the shape of a US phone number.
    assert check_text("112-108 2025") is not None
    # Spelling tricks get past the phrases. Reports and moderators are the backstop.
    assert check_text("g.u.a.r.a.n.t.e.e.d") is None
    assert check_text("l0ck of the week") is None
