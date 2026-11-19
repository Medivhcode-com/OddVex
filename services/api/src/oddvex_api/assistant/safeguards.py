"""Responsible-gambling checks that run before any intent routing.

docs/compliance/RESPONSIBLE_GAMBLING.md section 5 is the specification. Each message is
tested against four groups of fixed patterns, and the first that applies decides the reply:

1. **crisis**: self-harm or crisis language. The reply is only support.
2. **underage**: the user says they are under 21. No betting information.
3. **distress**: distress about gambling (cannot stop, chasing losses, borrowed or hidden
   money, losses that hurt). The helpline and the app's own tools, no prices.
4. **certainty**: a request for a certain winner. Not a support case: the reply says no
   result is certain and offers market data.

Everything here is a deterministic rule. No language model is involved and nothing is
remembered between messages. Rules like these miss cases and that is a known limit; where
a phrase could be read either way, the patterns lean towards showing help. The tests in
``tests/test_audit_assistant_detection.py`` list what must match and, next to it, the
ordinary sports talk that must not ("the Tides can't stop the run", "under 21.5",
"I'm 15 units up").

The reply wording is in this module too, so that a pluggable ``Explainer`` cannot reword
it. Helpline details come from ``oddvex_api.helpline``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from ..helpline import (
    CRISIS_LINE,
    CRISIS_LINE_NAME,
    CRISIS_SENTENCE,
    EMERGENCY_NUMBER,
    HELPLINE_SENTENCE,
)

SupportCase = Literal["crisis", "distress", "underage"]

#: Marketing page with the helpline, the crisis line and the warning signs.
RESOURCES_HREF = "/responsible-gambling"
RESOURCES_LABEL = "Help and support resources"
#: Where the weekly staking reminder is set.
REMINDER_HREF = "/app/settings"
REMINDER_LABEL = "Weekly staking reminder"
TRACKER_HREF = "/app/tracker"
TRACKER_LABEL = "Bet tracker"


@dataclass(frozen=True, slots=True)
class Signals:
    """Which groups of patterns a message matched."""

    crisis: bool = False
    underage: bool = False
    distress: bool = False
    #: Part of ``distress``: the user wants to win back what they lost.
    chasing_losses: bool = False
    certainty: bool = False

    @property
    def case(self) -> SupportCase | None:
        """The support reply to give, or None. Crisis first, then under 21, then distress."""
        if self.crisis:
            return "crisis"
        if self.underage:
            return "underage"
        if self.distress:
            return "distress"
        return None


# ------------------------------------------------------------------- normalising
_APOSTROPHES = dict.fromkeys(map(ord, "'’‘ʼ`´′＇"), None)
_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―"), "-")


def normalise(message: str) -> str:
    """Lower case, one space between words, apostrophes removed and dashes made plain.

    "I can’t stop", "I can't stop" and "i cant stop" all become ``i cant stop``, so the
    patterns below are written without apostrophes.
    """
    text = unicodedata.normalize("NFKC", message).casefold()
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return " ".join(text.translate(_APOSTROPHES).translate(_DASHES).split())


def _any(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{pattern})" for pattern in patterns))


# First-person openers, after normalising ("i'm" is "im").
_IM = r"\b(?:im|i am|i m)"
_CANT = r"(?:cant|cannot|can not|couldnt|could not)"
_GAMBLING = r"(?:gambling|betting|sports betting|wagering|bets|parlays|sportsbooks?)"

# ------------------------------------------------------------------------ crisis
_CRISIS_RE = _any(
    r"\bkill(?:ing)? my ?self\b",
    r"\bkms\b",
    # "suicide squeeze" is a baseball play and a "suicide pool" is a survivor contest.
    r"\bsuicid(?!e (?:squeeze|pools?)\b)",
    r"\bsucid",
    r"\bend(?:ing)? (?:my (?:own )?life|it all|my (?:pain|suffering))\b",
    r"\btak(?:e|ing) my (?:own )?life\b",
    r"\b(?:want(?:ed)? to|wanna|going to|gonna|ready to|rather|should just|wish i could|"
    r"hope i) die\b",
    r"\bwish i (?:was|were|am) dead\b",
    r"\bbetter off (?:dead|without me)\b",
    r"\b(?:dont|do not) (?:want|wanna) (?:to )?(?:live|be alive|be here|exist|wake up|go on)\b",
    r"\bno (?:reason|point) (?:to|in) (?:live|living|go on|going on)\b",
    r"\bnothing (?:left )?to live for\b",
    r"\b(?:not|isnt) worth living\b",
    r"\bgive up on life\b",
    rf"\bi (?:just |really )?{_CANT} go on\b",
    rf"\b{_CANT} (?:take|do) (?:it|this) any ?more\b",
    r"\bno way out\b",
    r"\b(?:hurt|harm|cut|shoot|hang|drown|poison)(?:ing)? my ?self\b",
    r"\bself[- ]?harm",
    r"\boverdos(?:e|ed|ing)\b",
    r"\bjump(?:ing)? off (?:a|the|my) (?:bridge|roof|building|balcony)\b",
    r"\bthink(?:ing)? (?:of|about) (?:ending|killing|hurting|harming)\b",
)

# --------------------------------------------------------------------- under 21
# What follows a number when it is not an age: a record ("3-0", "10 for 12"), a count
# ("15 units", "18 bets in") or an amount ("20 dollars", "15%").
_NOT_AN_AGE = (
    r"(?![-:/.,]\d)(?!\s?%)(?!\s?(?:k|x|u|pts?|th|st|nd|rd)\b)"
    r"(?!\s(?:and|or|to|of|out of|for|from)\s\d)"
    r"(?!\s(?:units?|bets?|wagers?|picks?|plays?|games?|legs?|parlays?|props?|dollars?|bucks?"
    r"|grand|percent|points?|wins?|loss(?:es)?|for(?! sure)|of|out|up|down|deep|minutes?|mins?"
    r"|hours?|hrs?|days?|weeks?|months?|seasons?|straight|consecutive|under|over|ahead|behind"
    r"|times?|in a row|in the hole|in on|into|cents?|large|bands?)\b)"
    r"(?!\s(?:years?|yrs?) (?:in|into|deep|of|removed|away|ago|behind|sober|clean)\b)"
)
_FILLER = r"(?:(?:only|just|still|currently|like|a|an) )*"
_AGE_WORDS = {
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "twenty one": 21,
    "twenty-one": 21,
    "twentyone": 21,
}
_AGE = r"(\d{1,2}|twenty[- ]?one|" + "|".join(k for k in _AGE_WORDS if k.isalpha()) + r")\b"
_YEARS_OLD = r"[- ]?(?:yo|y/o|years?[- ]old|yrs?[- ]old)\b"
# "twenty" followed by another number word is 21 to 29.
_NOT_TWENTIES = r"(?![- ]?(?:two|three|four|five|six|seven|eight|nine)\b)"

#: "I'm 17", "I am sixteen years old", "I just turned 19", "as a 17 year old": under 21
#: when the number is below 21.
_AGE_NOW_RE = _any(
    rf"(?:{_IM}|\bmy age is|\bi (?:just |recently |only )?turned) {_FILLER}{_AGE}"
    rf"{_NOT_TWENTIES}{_NOT_AN_AGE}",
    rf"\bas an? {_AGE}{_YEARS_OLD}",
    # "17 years old here": an age that opens the message or a sentence is the writer's.
    rf"(?:^|[.!?;] ){_AGE}{_YEARS_OLD}",
)
#: "I turn 21 in March", "I'm not 21 yet", "when I'm 21": not there yet, so under 21 when
#: the number is 21 or below.
_AGE_AHEAD_RE = _any(
    rf"(?:\bi turn|\bill (?:be|turn)|\bi will (?:be|turn)|{_IM} (?:turning|about to (?:be|turn)"
    rf"|almost|nearly|not quite|not(?: even| yet)?)|\b(?:until|till|til|when|once|before) "
    rf"(?:im|i am|i turn)) {_AGE}{_NOT_TWENTIES}{_NOT_AN_AGE}",
)
_UNDERAGE_PHRASE_RE = _any(
    rf"{_IM} {_FILLER}(?:technically )?(?:under ?age|under(?: the age of)? (?:21|18)\b(?![.\d])"
    r"(?! (?:points?|pts|total|goals?|runs?))|(?:under|below) the (?:legal |betting |gambling )?"
    r"age|too young|not old enough|not of (?:legal )?age|not legal age|minor\b(?! league)|kid\b"
    r"(?! at heart)|child\b|teen(?:ager)?\b|in (?:high|middle|junior high) school|in (?:the )?(?:[6-9]th|"
    r"1[0-2]th|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth) grade|(?:high school|hs) "
    r"(?:student|kid|freshman|sophomore|junior|senior)|high ?schooler|(?:freshman|sophomore|"
    r"junior|senior) in (?:high school|hs))",
    # Asked about anyone, the answer is the same: OddVex is for adults 21 and over.
    r"\bunder ?age\b",
    r"\b(?:if youre|if you are|people|someone|anyone|users|kids|those|everyone) under "
    r"(?:21|18)\b(?![.\d])",
)

# ---------------------------------------------------------------------- distress
#: Wanting to win back what was lost. Row 4 of the specification, and part of row 1.
_CHASING_RE = _any(
    r"\bwin(?:ning)? (?:(?:it|it all|everything|them|that|some|some of it|(?:my|the) (?:money|"
    r"loss|losses|rent|cash|stake|savings|bankroll|paycheck|bets?)|my \$?\d+k?|what i(?:ve| have)"
    r"? lost) )?back(?![-\w])",
    r"\b(?:make|making|earn|earning) (?:it|it all|everything|my money|my losses|the money|"
    r"what i(?:ve| have)? lost) back\b",
    r"\bget(?:ting)? (?:it|it all|everything|my money|my losses|the money|what i(?:ve| have)? "
    r"lost) back\b",
    r"\b(?:recover|recoup|recovering|recouping) (?:my|the|those|these|all my|some of my) "
    r"(?:loss|losses|money|bankroll|stake)",
    r"\bchas(?:e|ed|ing) (?:my |the |these |those |all my )?loss(?:es)?\b",
    r"\b(?:back to|get|getting) even\b(?! (?:money|odds|closer|better|more|worse|bigger|longer|"
    r"shorter|higher|lower|though|if|when)\b)",
    r"\bmake up for (?:my loss|my losses|what i lost|last night|yesterday|(?:the|these|those) "
    r"losses)\b",
    r"\bdig my ?self out\b",
    r"\b(?:get|climb|dig) (?:my ?self )?out of (?:this|my) hole\b",
    rf"{_IM} (?:deep )?in (?:a|the) hole\b",
)
#: A refund question ("do I get my money back on a push?") is not loss chasing.
_REFUND_RE = re.compile(
    r"\b(?:push(?:es|ed)?|void(?:ed)?|refund(?:ed|s)?|cancel(?:led|ed|s)?|postponed?|"
    r"withdraw(?:al|als)?|cash ?out|abandoned|no action)\b"
)
_GET_BACK_RE = re.compile(r"\bget(?:ting)? (?:it|my money|the money) back\b")

_DISTRESS_RE = _any(
    # Cannot stop.
    rf"\bi (?:just |really |literally |honestly )?(?:{_CANT}|am unable to) (?:seem to )?"
    r"(?:stop|quit|control|help my ?self|walk away)\b"
    r"(?! (?:watching|laughing|smiling|cheering|reading|talking|thinking about (?:that|the)))",
    rf"\b(?:stop|quit|quitting|stopping|give up|giving up|cut back on|cutting back on|cut down "
    rf"on|take a break from|taking a break from|walk away from|stay away from) (?:my )?{_GAMBLING}"
    r"\b",
    r"\bhelp me (?:stop|quit)\b",
    rf"\b(?:need|want|get|getting|find|seeking) help (?:with|for|to stop|stopping|quitting) "
    rf"(?:my |the |this )?(?:{_GAMBLING}|addiction|problem)\b",
    rf"\bi(?:ve| have)? (?:lost|no) control\b|{_IM} (?:losing|out of) control\b",
    rf"\b{_GAMBLING} is (?:getting |way )?out of control\b",
    r"\b(?:stop|block|ban|exclude) (?:me|my ?self) from\b",
    r"\bself[- ]?exclu",
    r"\brelaps",
    r"\bgamblers? anonymous\b",
    # A gambling problem, in any words.
    rf"\b{_GAMBLING} (?:problem|addiction|addict|disorder)\b",
    r"\bproblem gambl",
    r"\bcompulsive(?:ly)? (?:gambl|bett)",
    rf"\baddicted to (?:{_GAMBLING}|this|it)\b",
    rf"{_IM} (?:so |really |totally |completely )?addicted\b",
    rf"{_IM} (?:an |a )?(?:gambling |betting )?addict\b",
    r"\bi (?:think i |might |may |probably |really |definitely )?(?:have|ve got|got) a "
    r"(?:gambling |betting |serious |real |bad |big )?problem\b"
    r"(?! (?:with|logging|signing|on the|in the|loading|opening|seeing))",
    # Losses that hurt.
    r"\blost (?:everything|it all|all of it|too much|way too much|so much money|thousands|"
    r"more than i (?:can|could|should))\b(?! in the (?:first|second|third|fourth|1st|2nd|3rd|4th))",
    r"\b(?:lost|losing|lose|blew|blown|blowing|gambled away|bet|betting|wagered|spent) (?:all "
    r"(?:of )?)?(?:my|the|our) (?:whole |entire |life )?(?:savings|rent|mortgage|paycheck|"
    r"paycheque|tuition|bankroll|house|college fund|retirement|401k|car payment)\b",
    r"\blost my (?:job|house|home|car|marriage|family|wife|husband|kids|business)\b",
    r"\b(?:rent|mortgage|bill|grocery|tuition) money\b",
    rf"\b{_CANT} afford\b",
    r"\bmore than i (?:can|could) afford\b",
    r"\bmoney i (?:dont|do not) have\b",
    rf"\b{_CANT} (?:pay|cover|make) (?:my|the|our) (?:rent|bills?|mortgage|debts?)\b",
    r"\bbehind on (?:my |the |our )?(?:rent|bills|mortgage|payments)\b",
    r"\b(?:in|into) debt\b",
    r"\b(?:my|gambling|betting) debts?\b",
    r"\bbankrupt",
    r"\bevict",
    r"\bforeclos",
    r"\bbet (?:it all|everything|the house)\b",
    r"\bmy last (?:\$\d|\d+ ?(?:dollars|bucks)|dollars?|bucks|money|paycheck|dime|cent|penny)",
    r"\ball i have left\b|\beverything i have (?:left|on)\b",
    # Borrowed money, or money that was not for betting.
    r"\bborrow",
    r"\b(?:took|take|taking|get|got|getting) (?:out )?(?:a|another) (?:payday )?loan\b",
    r"\bpayday loan",
    r"\bloan shark",
    r"\bmaxed (?:out )?(?:my|the|our|a|another)? ?(?:credit )?cards?\b",
    r"\b(?:sold|selling|pawned|pawning) (?:my|our) (?!bet|ticket|slip|position|pick)",
    r"\b(?:stole|stealing|steal) (?:money|cash|from (?:my|work|him|her|them))\b",
    r"\b(?:took|taking|take) money from\b",
    r"\bdipped into\b",
    # Hiding it.
    rf"\bhid(?:e|ing|den)? (?:it|this|that|everything|(?:my |the |our )?(?:{_GAMBLING}|losses|"
    r"debts?|bank statements?|statements?)) from (?:my|her|him|them|everyone|people|the)\b",
    r"\b(?:wife|husband|partner|girlfriend|boyfriend|fiance|fiancee|spouse|family|parents|mom|"
    r"mum|dad|kids) (?:doesnt|does not|dont|do not|cant|cannot|mustnt|must not|wont|will not) "
    r"(?:know|find out)\b",
    r"\b(?:wife|husband|partner|girlfriend|boyfriend|fiance|fiancee|spouse|family) (?:left|is "
    r"leaving|will leave|is going to leave|threatened to leave|found out|finds out|kicked me "
    r"out)\b",
    rf"\bl(?:ie|ied|ying) (?:to (?:my|everyone|people)|about (?:my |the )?(?:{_GAMBLING}|losses|"
    r"money))\b",
    rf"\bkeep(?:ing)? (?:it|this|my (?:{_GAMBLING})) (?:a )?secret\b",
    r"\bbehind (?:my|her|his|their) (?:wifes |husbands |partners )?back\b",
    # What it is doing to the person.
    rf"\b(?:{_GAMBLING}|losing|losses) (?:is|are|has|have) (?:ruin|destroy|wreck|kill|consum|"
    r"control|tak)\w* (?:my|me|our|over)\b",
    r"\b(?:ruin|destroy|wreck)(?:ed|ing|s)? my (?:life|marriage|family|finances|credit|"
    r"relationship)\b",
    rf"(?:{_IM}|\bi feel|\bi felt) (?:so |really |just |completely |totally )?(?:hopeless|"
    r"desperate|worthless|ashamed|ruined|trapped|a failure|disgusted with my ?self|sick about)\b",
    rf"{_IM} (?:flat |dead |completely |totally |so )?broke\b",
    r"\bhate my ?self\b",
    r"\brock bottom\b",
    r"\bdesperately need\b",
    r"\bon tilt\b",
    rf"\blosing sleep over (?:my |the |this )?(?:{_GAMBLING}|losses|loss|debt)\b",
    rf"\b{_CANT} (?:afford to )?lose (?:any ?more|another|again|this one|the rent)\b",
    r"\bneed(?:ed)? (?:to win|a win|this (?:one |bet )?to (?:hit|win|cash))\b.{0,40}?\b"
    r"(?:rent|mortgage|pay|debt|or im|or else|or my)\b",
)

# --------------------------------------------------------------------- certainty
_CERTAINTY_RE = _any(
    # "lock" as a noun. Not "lock in a price", "lock my account" or a locked market.
    r"(?<!account )(?<!screen )\blocks?\b(?! (?:screen|in\b|my|the|out|up|down|icon|account))",
    r"\bsure[- ]?(?:thing|things|bet|bets|win|winner|winners|shot)\b",
    r"\bguarantee",
    rf"\b(?:{_CANT}|wont)[- ](?:lose|miss)\b",
    r"\bno[- ]lose\b",
    r"\brisk[- ]?free\b",
    r"\bno[- ]risk\b",
    r"\bfree money\b",
    r"\beasy money\b",
    r"\bno[- ]brainer",
    r"\b100 ?(?:%|percent) (?:sure|certain|safe|chance|going|win|winner|hit)",
    r"\bcertain (?:to win|winner|win)\b",
    r"\b(?:safe|safest) bets?\b",
    r"\b(?:never|cant|cannot) loses?\b",
    r"\bwin either way\b",
    r"\bdefinitely (?:going to |gonna |will )?(?:win|hit|cash)\b",
    r"\bfixed (?:game|match|fight)\b",
)


def _age(token: str) -> int:
    return int(token) if token.isdigit() else _AGE_WORDS[token.replace("-", " ")]


def _says_under_21(text: str) -> bool:
    if _UNDERAGE_PHRASE_RE.search(text):
        return True
    for pattern, limit in ((_AGE_NOW_RE, 20), (_AGE_AHEAD_RE, 21)):
        for match in pattern.finditer(text):
            token = next(group for group in match.groups() if group is not None)
            # Nobody younger than ten is typing here; a smaller number is something else.
            if 10 <= _age(token) <= limit:
                return True
    return False


def _chasing_losses(text: str) -> bool:
    for match in _CHASING_RE.finditer(text):
        if _GET_BACK_RE.fullmatch(match.group(0)) and _REFUND_RE.search(text):
            continue
        return True
    return False


def detect(message: str) -> Signals:
    """Every group of patterns ``message`` matches. Pure and deterministic."""
    text = normalise(message)
    chasing = _chasing_losses(text)
    return Signals(
        crisis=_CRISIS_RE.search(text) is not None,
        underage=_says_under_21(text),
        distress=chasing or _DISTRESS_RE.search(text) is not None,
        chasing_losses=chasing,
        certainty=_CERTAINTY_RE.search(text) is not None,
    )


# ---------------------------------------------------------------------- wording
_AUTOMATED = "I'm an automated helper, not a person, so this reply only gives these contacts."

_CRISIS_REPLY = "\n\n".join(
    (
        "I'm sorry you are going through this. You don't have to face it alone, and help is "
        "available right now.",
        f"Call or text {CRISIS_LINE} (the {CRISIS_LINE_NAME}). If you are in immediate danger, "
        f"call {EMERGENCY_NUMBER}.",
        "If you can, tell someone you trust how you are feeling now.",
        "If gambling is part of what is weighing on you, there is a helpline for that too. "
        f"{HELPLINE_SENTENCE}",
        _AUTOMATED,
    )
)

_THANKS = "Thank you for telling me."
_NO_DATA = "I'm leaving prices and other betting data out of this reply."
_NO_CHASING = (
    "I can't help size or pick a bet to win money back. Trying to win back losses is a "
    "recognised warning sign that betting may be causing harm, and it is worth talking to "
    "someone about."
)
_TOOLS = (
    "OddVex has two tools you can use on your own. The weekly staking reminder in Settings "
    "tells you when your stakes for the week reach an amount you choose; it is a reminder, "
    "not a limit. The bet tracker shows what you have staked and how your bets settled."
)
_ADULTS_ONLY = (
    "OddVex is for adults 21 and over, so I can't give odds, prices or any other betting "
    "information here."
)


def reply(signals: Signals) -> str:
    """The whole answer for a support case. Fixed wording; ``signals.case`` must be set."""
    case = signals.case
    if case == "crisis":
        return _CRISIS_REPLY
    if case == "underage":
        lead = (
            "Thank you for telling me what is going on."
            if signals.distress
            else "If gambling is worrying you or someone close to you, help is available."
        )
        return "\n\n".join((_ADULTS_ONLY, f"{lead} {HELPLINE_SENTENCE}", CRISIS_SENTENCE))
    if case == "distress":
        opening = f"{_THANKS} {_NO_DATA}"
        if signals.chasing_losses:
            opening = f"{_THANKS} {_NO_CHASING} {_NO_DATA}"
        return "\n\n".join((opening, HELPLINE_SENTENCE, _TOOLS, CRISIS_SENTENCE))
    raise ValueError("no support case")


#: Kept next to the support wording because the same review covers it.
NO_CERTAINTY_REPLY = (
    "I can't answer that with a pick. No result in sports is certain, and I don't make picks "
    "or predictions. I can show market data instead: the best current price for a team, a "
    "player's recent prop results, line movement, or EV and no-vig math."
)

__all__ = [
    "NO_CERTAINTY_REPLY",
    "REMINDER_HREF",
    "REMINDER_LABEL",
    "RESOURCES_HREF",
    "RESOURCES_LABEL",
    "TRACKER_HREF",
    "TRACKER_LABEL",
    "Signals",
    "SupportCase",
    "detect",
    "normalise",
    "reply",
]
