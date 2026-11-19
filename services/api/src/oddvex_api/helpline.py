"""The problem-gambling helpline and crisis-line facts, in one place.

Every text the API produces that mentions a helpline imports from here: assistant answers
and disclaimers, notification templates, email templates and the community guidelines.
Nothing else in the API spells a helpline number out, and ``tests/test_audit_helpline.py``
fails if something does.

The facts were checked on :data:`HELPLINE_VERIFIED_ON` against the National Council on
Problem Gambling's own pages. docs/compliance/RESPONSIBLE_GAMBLING.md asks for them to be
checked again before each release: do that, then change this file and the date together.

- The National Problem Gambling Helpline is 1-800-MY-RESET (1-800-697-3738), in service
  since :data:`HELPLINE_IN_SERVICE_SINCE`. It takes calls, and texts to 800GAM (800426).
- It is confidential and answers 24 hours a day, every day.
- It is not an emergency service. In a crisis the numbers are 988 (the Suicide and Crisis
  Lifeline, call or text) and 911.
- The number the national helpline used before that date is run by the Council on
  Compulsive Gambling of New Jersey. It is not the national helpline and no API text gives
  it as one.

Online chat is offered on the Council's site. Link to the site (:data:`HELPLINE_WEBSITE`),
never to a deeper chat address.
"""

from __future__ import annotations

from datetime import date

HELPLINE_NAME = "National Problem Gambling Helpline"
HELPLINE_OPERATOR = "National Council on Problem Gambling"
HELPLINE_WEBSITE = "https://www.ncpgambling.org"

#: The number as it is shown, and the same number in digits.
HELPLINE_NUMBER = "1-800-MY-RESET"
HELPLINE_DIGITS = "1-800-697-3738"
#: For a ``tel:`` link.
HELPLINE_TEL = "+18006973738"

#: The code to text, as it is shown, and the same code in digits.
HELPLINE_TEXT_CODE = "800GAM"
HELPLINE_TEXT_DIGITS = "800426"

HELPLINE_IN_SERVICE_SINCE = date(2026, 1, 29)
HELPLINE_VERIFIED_ON = date(2026, 11, 19)

#: Call or text.
CRISIS_LINE = "988"
CRISIS_LINE_NAME = "Suicide and Crisis Lifeline"
EMERGENCY_NUMBER = "911"

#: How to reach the helpline, as the end of a sentence.
HELPLINE_CONTACT = f"call {HELPLINE_NUMBER} ({HELPLINE_DIGITS}) or text {HELPLINE_TEXT_CODE}"

#: The one-line form, for footers and other places where space is tight.
HELPLINE_SHORT = (
    f"Gambling problem? Call {HELPLINE_NUMBER} ({HELPLINE_DIGITS}) or text {HELPLINE_TEXT_CODE}."
)

#: What the helpline offers, without its name and without asking a question. For places
#: where the reader has not said anything is wrong, such as the staking reminder.
HELPLINE_AVAILABLE = f"Confidential help is available 24 hours a day, every day: {HELPLINE_CONTACT}."

#: The full sentence form.
HELPLINE_SENTENCE = (
    f"The {HELPLINE_NAME} is confidential and answers 24 hours a day, every day: call "
    f"{HELPLINE_NUMBER} ({HELPLINE_DIGITS}) or text {HELPLINE_TEXT_CODE} ({HELPLINE_TEXT_DIGITS})."
)

#: Goes with :data:`HELPLINE_SENTENCE` wherever the reader may be in more trouble than a
#: helpline can handle.
CRISIS_SENTENCE = (
    f"The helpline is not an emergency service. In a crisis, call or text {CRISIS_LINE} (the "
    f"{CRISIS_LINE_NAME}) or call {EMERGENCY_NUMBER}."
)
