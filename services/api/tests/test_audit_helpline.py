"""One source for the helpline facts, and the right facts (audit finding compliance#2).

The National Problem Gambling Helpline is 1-800-MY-RESET (1-800-697-3738), in service
since 2026-01-29, verified on 2026-11-19. The number every surface showed before that is
run by the New Jersey council and is not the national helpline. ``oddvex_api.helpline``
holds the facts; these tests pin them, check that every API text that mentions a helpline
is built from that module, and check that the old number is gone.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from oddvex_api import helpline
from oddvex_api.assistant import engine as assistant_engine
from oddvex_api.assistant import safeguards
from oddvex_api.community import guidelines
from oddvex_api.mailer import templates as email_templates
from oddvex_api.notifications import templates as notification_templates

API_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = API_ROOT / "src" / "oddvex_api"

#: The old number. Joined when the test runs, so that a search of this directory for it
#: finds nothing, not even in the compiled copy of this file.
OLD_VANITY = "".join(["GAMB", "LER"])
OLD_DIGITS = ("-".join(["426", "2537"]), "".join(["426", "2537"]))
#: The vanity word in capitals, or after "800" in any letter case. Lower-case "gambler" is
#: an ordinary word and the assistant's patterns use it.
OLD_NUMBER = re.compile(rf"{OLD_VANITY}|800[-. ]?(?i:{OLD_VANITY})|" + "|".join(OLD_DIGITS))

SHORT = "Gambling problem? Call 1-800-MY-RESET (1-800-697-3738) or text 800GAM."


def test_the_facts() -> None:
    assert helpline.HELPLINE_NAME == "National Problem Gambling Helpline"
    assert helpline.HELPLINE_OPERATOR == "National Council on Problem Gambling"
    assert helpline.HELPLINE_NUMBER == "1-800-MY-RESET"
    assert helpline.HELPLINE_DIGITS == "1-800-697-3738"
    assert helpline.HELPLINE_TEL == "+18006973738"
    assert helpline.HELPLINE_TEXT_CODE == "800GAM"
    assert helpline.HELPLINE_TEXT_DIGITS == "800426"
    assert helpline.HELPLINE_WEBSITE == "https://www.ncpgambling.org"
    assert date(2026, 1, 29) == helpline.HELPLINE_IN_SERVICE_SINCE
    assert date(2026, 11, 19) == helpline.HELPLINE_VERIFIED_ON
    assert helpline.CRISIS_LINE == "988"
    assert helpline.CRISIS_LINE_NAME == "Suicide and Crisis Lifeline"
    assert helpline.EMERGENCY_NUMBER == "911"


def test_the_digits_spell_the_number_on_a_phone_keypad() -> None:
    keypad = {
        letter: str(digit)
        for digit, letters in enumerate(
            ("abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz"), start=2
        )
        for letter in letters
    }

    def dial(text: str) -> str:
        return "".join(keypad.get(ch, ch) for ch in text.lower() if ch.isalnum())

    assert dial(helpline.HELPLINE_NUMBER) == dial(helpline.HELPLINE_DIGITS) == "18006973738"
    assert "+" + dial(helpline.HELPLINE_DIGITS) == helpline.HELPLINE_TEL
    assert dial(helpline.HELPLINE_TEXT_CODE) == helpline.HELPLINE_TEXT_DIGITS


def test_the_sentence_forms() -> None:
    assert helpline.HELPLINE_SHORT == SHORT
    assert helpline.HELPLINE_CONTACT == "call 1-800-MY-RESET (1-800-697-3738) or text 800GAM"
    assert helpline.HELPLINE_AVAILABLE == (
        "Confidential help is available 24 hours a day, every day: call 1-800-MY-RESET "
        "(1-800-697-3738) or text 800GAM."
    )
    assert helpline.HELPLINE_SENTENCE == (
        "The National Problem Gambling Helpline is confidential and answers 24 hours a day, "
        "every day: call 1-800-MY-RESET (1-800-697-3738) or text 800GAM (800426)."
    )
    assert helpline.CRISIS_SENTENCE == (
        "The helpline is not an emergency service. In a crisis, call or text 988 (the Suicide "
        "and Crisis Lifeline) or call 911."
    )


def helpline_texts() -> dict[str, str]:
    """Every API text that mentions a helpline."""
    reminder = notification_templates.stake_reminder(
        week_start=datetime(2026, 3, 9, tzinfo=UTC),
        staked=Decimal("520"),
        threshold=Decimal("500"),
    )
    return {
        "assistant disclaimer": assistant_engine.DISCLAIMER,
        "assistant replay disclaimer": assistant_engine.REPLAY_DISCLAIMER,
        "assistant crisis reply": safeguards.reply(safeguards.Signals(crisis=True)),
        "assistant distress reply": safeguards.reply(safeguards.Signals(distress=True)),
        "assistant under-21 reply": safeguards.reply(safeguards.Signals(underage=True)),
        "staking reminder template": notification_templates.TEMPLATES["stake_reminder"]["body"],
        "staking reminder": reminder.body,
        "email footer": email_templates.FOOTER,
        "verification email": email_templates.verify_email("http://x.test/v?t=a", 60).body_text,
        "password reset email": email_templates.password_reset("http://x.test/r?t=a", 60).body_text,
        "community guidelines": guidelines.HELP,
    }


@pytest.mark.parametrize("where", helpline_texts())
def test_every_text_gives_the_national_helpline(where: str) -> None:
    text = helpline_texts()[where]
    contact = helpline.HELPLINE_CONTACT
    assert contact in text or contact[0].upper() + contact[1:] in text
    assert "1-800-MY-RESET (1-800-697-3738)" in text and "800GAM" in text
    assert not OLD_NUMBER.search(text)
    # 988 is the crisis line. It is never offered as the gambling helpline.
    assert "988" not in text or "Suicide and Crisis Lifeline" in text


def test_the_exact_wording_of_each_short_text() -> None:
    texts = helpline_texts()
    assert texts["email footer"] == (
        f"OddVex is for information only and does not accept or place wagers. 21+. {SHORT}"
    )
    assert texts["community guidelines"] == (
        f"21+. OddVex does not accept wagers. {SHORT} The helpline is confidential and "
        "answers 24 hours a day, every day."
    )
    assert texts["staking reminder"] == (
        "You have staked $520.00 this week, at or above the $500.00 reminder you set. This "
        "is a reminder, not a limit. Confidential help is available 24 hours a day, every "
        "day: call 1-800-MY-RESET (1-800-697-3738) or text 800GAM."
    )
    assert texts["assistant disclaimer"] == (
        "OddVex gives information and math, not betting advice or predictions. All sports "
        "data shown is synthetic sample data. For adults 21+. If gambling is causing "
        "problems, call 1-800-MY-RESET (1-800-697-3738) or text 800GAM (US)."
    )
    assert texts["assistant replay disclaimer"] == (
        "OddVex gives information and math, not betting advice or predictions. The games "
        "shown are a replay of past results; sportsbook prices and prop lines are simulated. "
        "For adults 21+. If gambling is causing problems, call 1-800-MY-RESET "
        "(1-800-697-3738) or text 800GAM (US)."
    )


def source_files() -> list[Path]:
    files = sorted(SOURCE_ROOT.rglob("*.py"))
    assert len(files) > 50
    return files


def test_the_old_number_is_nowhere_in_the_api() -> None:
    checked = [*source_files(), API_ROOT / "README.md", *sorted((API_ROOT / "tests").rglob("*.py"))]
    for path in checked:
        found = OLD_NUMBER.search(path.read_text(encoding="utf-8"))
        assert found is None, (path, found)
    assert OLD_NUMBER.search("Call 1-800-" + OLD_VANITY) and OLD_NUMBER.search("1-800-gamb" + "ler")
    assert not OLD_NUMBER.search("am I a problem gambler")


def test_only_the_helpline_module_spells_a_helpline_number() -> None:
    """Everything else imports it, so one edit changes every text."""
    number = re.compile(
        r"MY-RESET|697-3738|6973738|800GAM|800426|\b988\b|\b911\b|ncpgambling", re.IGNORECASE
    )
    offenders = [
        str(path.relative_to(SOURCE_ROOT))
        for path in source_files()
        if path.name != "helpline.py" and number.search(path.read_text(encoding="utf-8"))
    ]
    # The assistant's schema describes the crisis reply in the API documentation.
    assert offenders == ["assistant/schemas.py"]
    schema = (SOURCE_ROOT / "assistant" / "schemas.py").read_text(encoding="utf-8")
    assert not re.search(r"MY-RESET|697-3738|800GAM|800426", schema)


def test_no_text_calls_the_helpline_free_or_an_emergency_service() -> None:
    """Only what was verified is claimed: confidential, and answering at all hours."""
    for where, text in helpline_texts().items():
        assert not re.search(r"\bfree\b", text, re.IGNORECASE), where
        assert "24/7" not in text, where
