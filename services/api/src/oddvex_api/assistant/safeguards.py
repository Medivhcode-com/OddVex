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
remembered between messages. The only input besides the message is today's date, which
turns "I was born in 2009" into an age. Rules like these miss cases and that is a known
limit: ``KNOWN_MISSES`` in the tests lists the misses known today. Because of it, every
answer that is not a support reply ends with :data:`HELP_SENTENCE` (the gambling helpline
and the crisis line), so a message the rules miss still shows where help is. Where a
phrase could be read either way, the patterns lean towards showing help, and
``HELP_SHOWN_ANYWAY`` in the tests lists examples of help shown where none was asked for.
The tests in ``tests/test_audit_assistant_detection.py`` list what must match and, next to
it, the ordinary sports talk that must not ("the Tides can't stop the run", "under 21.5",
"I'm 15 units up", "that parlay killed me", "I think my parlay is dead"). A new wording is
added as a rule here and a message in those lists that only the new rule catches.

Most patterns name a wording or a small family of wordings. The widest is for wordings no
list has: a first-person subject joined to "die", "dead", "death", "end it", "kill" and a
few other words by filler words only (``_CHAIN``). "I just really want to be dead"
matches; "I think my parlay is dead" does not, because "my parlay is" is not filler. A few
crisis wordings have no "I" at all ("gonna end it", "might as well die", "no point
living"); they count unless the clause names somebody else first (``_SUBJECT_BEFORE_RE``).
With no "I", "end it" counts only when the clause ends there or a time, a means or a place
from a fixed list follows it ("gonna end it tonight", "gonna end it with pills"); "gonna
end it with a 3" is a game that ends.

The list is open-ended and is never finished: every review has found wordings it missed,
and every fix for a miss risked new false alarms on sports talk. The final pass on these
rules closed a fixed list of items; a wording found after it goes into ``KNOWN_MISSES`` in
the tests, and the help sentence at the end of every other answer is what covers it.

Before matching, the message is lower-cased, accents are dropped and Cyrillic or Greek
look-alike letters become Latin ones: "die" written with a Cyrillic "i" (U+0456) reads
as "die".

The reply wording is in this module too, so that a pluggable ``Explainer`` cannot reword
it. Helpline details come from ``oddvex_api.helpline``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from ..helpline import (
    CRISIS_LINE,
    CRISIS_LINE_NAME,
    CRISIS_SENTENCE,
    EMERGENCY_NUMBER,
    HELPLINE_DIGITS,
    HELPLINE_NAME,
    HELPLINE_NUMBER,
    HELPLINE_SENTENCE,
    HELPLINE_TEXT_CODE,
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
_APOSTROPHES = dict.fromkeys(map(ord, "'\u2019\u2018\u02bc`\u00b4\u2032\uff07"), None)
_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015"), "-")
#: Cyrillic and Greek letters that look like Latin ones, as used to write around a filter.
_LOOK_ALIKES = str.maketrans(
    "\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u0456\u0458\u0455\u0501\u04cf\u043a\u043c\u0442"
    "\u03bf\u03b1\u03b9\u03b5\u03ba\u03bd\u03c4\u03c1",
    "aeopcyxijsdlkmtoaiekvtp",
)


def normalise(message: str) -> str:
    """Lower case, one space between words, apostrophes removed and dashes made plain.

    "I can't stop" with a straight or a curly apostrophe and "i cant stop" all become
    ``i cant stop``, so the patterns below are written without apostrophes. Accents are
    dropped and Cyrillic or Greek look-alike letters become the Latin letter they imitate.
    """
    text = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", message).casefold())
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cf", "Mn"))
    text = text.translate(_LOOK_ALIKES)
    return " ".join(text.translate(_APOSTROPHES).translate(_DASHES).split())


def _any(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{pattern})" for pattern in patterns))


# First-person openers, after normalising ("i'm" is "im").
_IM = r"\b(?:im|i am|i m)"
#: "imma" and "ima" are "I'm going to" ("i'ma" once normalised).
_I = r"\b(?:i|im|ive|id|ill|imma|ima)"
_CANT = r"(?:cant|cannot|can not|couldnt|could not)"
_GAMBLING = r"(?:gambling|betting|sports betting|wagering|bets|parlays|sportsbooks?)"
_SELF = r"(?:my ?self|myslef|mysef|meself)"
_END = r"(?=[.,!?;]|$)"

# Words that can stand between "I" and what a sentence says without changing whose sentence
# it is: "I just really want to ...", "I think I might as well ...", "I have been thinking
# about ...". A first-person rule built on this chain matches "I want to be dead" and not
# "I think my parlay is dead", because "my parlay is" is not in the list.
_CHAIN_WORD = (
    r"(?:just|really|honestly|truly|sometimes|often|always|still|only|simply|actually|kinda|"
    r"might|may|could|would|will|should|can|do|did|have|had|was|were|am|be|been|want|wanted|"
    r"wanna|wish|wished|hope|hoped|need|must|deserve|deserved|ought|rather|going|gonna|ready|"
    r"about|plan|planning|decided|to|as|well|feel|felt|like|think|thought|thinking|keep|kept|guess|"
    r"know|if|when|i|im|id|ill|ive|my|own|not|dont|a|lot|that|soon|probably|maybe|of|on)"
)
_CHAIN = rf"{_I}(?: {_CHAIN_WORD}){{0,6}}"

# ------------------------------------------------------------------------ crisis
#: What follows "live" when it means betting during a game: "live bet", "live odds".
_LIVE_BETTING = r"(?:bet\w*|odds|lines?|markets?|games?|streams?|stream\w*|tv|scores?|wager\w*)\b"
#: Medicines and other things asked about as a way to die.
_SUBSTANCE = (
    r"pills?|tablets?|capsules?|meds|medications?|painkillers?|tylenol|acetaminophen|paracetamol|"
    r"ibuprofen|advil|aspirin|xanax|benadryl|melatonin|oxy(?!gen)\w*|fentanyl|insulin|opioids?|bleach|"
    # Prescription and over-the-counter drugs, by name.
    r"ambien|zolpidem|valium|diazepam|alprazolam|klonopin|trazodone|hydrocodone|oxycodone|"
    r"percocet|vicodin|morphine|codeine|tramadol|seroquel|lithium|"
    r"antifreeze|drugs"
)
#: "might as well", also written "might aswell" and "mightaswell".
_AS_WELL = r"(?:might|may) ?as ?well"
# Sports talk that follows "no way out of", "a way out of": a group, a parlay, a jam.
_OUT_OF_SPORT = (
    r"(?! of (?:the|this|that|my|a|his|her|their) (?:group|division|conference|bracket|pool|"
    r"parlay|bet|wager|ticket|slip|contract|deal|subscription|plan|slump|jam|inning|game|"
    r"league|trade)\b)"
)
#: A count in a game or a bet, in "how many <count> would end it": not a lethal-means question.
_NOT_A_SPORTS_COUNT = (
    r"(?!(?:more )?(?:points?|pts|runs?|goals?|games?|wins?|losses|outs?|strikes?|strikeouts?|"
    r"ks|threes?|3s|baskets?|buckets?|shots?|touchdowns?|tds?|yards?|laps?|rounds?|sets?|"
    r"innings?|legs?|units?|bets?|parlays?|picks?|minutes?|mins?|seconds?|turnovers?|fouls?)\b)"
)
#: The thing asked about in "how many <one or two words> would kill me".
_ONE_OR_TWO_WORDS = rf"{_NOT_A_SPORTS_COUNT}(?:\w+(?: \w+)?)"
#: What follows "end it" when a game or a series ends: "end it in four", "end it with a
#: walk-off" (or "walk off"), "end it in overtime", "end it in round 2", "end it with a
#: three", "end it with 2 minutes left", "end it on a high note", "end it with a Tides
#: moneyline", "end it here with one last question". A means, a time or a place ("with
#: pills", "with 3 pills", "in the morning", "on the bridge") is not on this list, so it does
#: not stop a match. A bare number counts only after "in" ("in four", "in 5"), and not
#: before minutes or days. Used after a first-person subject ("I'm going to end it ...") and
#: "time to end it"; with no subject, ``_NO_SUBJECT_END_IT_TAIL`` decides instead.
_GAME_ENDING = (
    r"game (?:\d|three|four|five|six|seven)|(?:two|three|four|five|six|seven|\d) (?:games|sets|"
    r"rounds|innings)|(?:\d+|a|one|two|three|four|five|ten) (?:minutes?|mins?|seconds?|secs?) "
    r"(?:left|to go|remaining)|round (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve)|overtime|ot|regulation|extra (?:time|innings)|straight sets|halftime|"
    r"the half|the (?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|final|"
    r"last|1st|2nd|3rd|\d+th)(?: (?:quarter|half|period|inning|round|set|frame|game|lap))?|"
    r"(?:(?:a|an|the|one|another|his|her|their|that|this) )?(?:\w+ )?(?:hedge|walk[- ]?off|"
    r"field goal|fg|touchdown|td|goal|homer|home run|three(?:-| )?pointer|three|trey|free "
    r"throws?|buzzer[- ]?beater|dunk|layup|shutout|hail mary|knockout|ko|tko|submission|sweep|"
    r"safety|pick (?:six|6)|interception|strikeout|grand slam|penalty|shootout|hat trick|cash "
    r"?out|parlay|bet|moneyline|ml|spread|prop|question|bang|whimper|win|winner|loss|w|(?:high|good|"
    r"positive|winning|strong|happy|sour|bad|low) note)"
)
_END_IT_TAIL = (
    r"(?! (?:(?:here|there) with (?:one|a|my) (?:last|final|more)\b|(?:(?:here|there|now|right "
    r"now|early) )?(?:in (?:three|four|five|six|seven|\d)(?! (?:minutes?|mins?|hours?|hrs?|"
    rf"seconds?|secs?|days?)\b)|(?:with|in|on|at|by) (?:{_GAME_ENDING}))\b))"
)
_CRISIS_RE = _any(
    # "kill myself", with the common misspellings and ways of writing around a filter.
    rf"\bk(?:i|[^a-z\s])?l{{1,3}}(?:ed|ing|in|s)? ?{_SELF}f*\b",
    rf"\bk[i1!|]?(?:[l1|]|ii){{1,2}}(?:ed|ing|in|s)? ?{_SELF}f*\b",
    r"\bk[\W_]{0,3}i[\W_]{0,3}l[\W_]{0,3}l[\W_]{0,3}my[\W_]{0,3}self\b",
    r"\bk[\W_]{0,2}m[\W_]{0,2}s\b|\bkys\b",
    r"\bkill (?:your ?self|urself)\b",
    # "suicide squeeze" is a baseball play and a "suicide pool" is a survivor contest.
    r"(?:\bs|(?<!\w)\$)u[\W_i1!|]{0,2}c[\W_i1!|]{0,2}d(?!e (?:squeeze|pools?)\b)",
    r"\bs[\W_]{1,2}i?c[\W_i]{0,2}d",
    r"\bsewer ?slide",
    r"\bunaliv",
    r"\bend(?:ing)? (?:my (?:own )?life|my (?:pain|suffering))\b",
    r"\bend(?:ing)? it all\b(?! in (?:regulation|overtime|ot|extra|the (?:first|second|third|"
    r"fourth|\d))\b)",
    # "I'm going to end it tonight", "should I just end it", "I'm going to end it with
    # pills". Not "end it here with one last question", and not a game that ends.
    rf"{_CHAIN} end(?:ing)? (?:it|things|everything)\b{_END_IT_TAIL}",
    # "end it" with a means or a place, whoever the sentence is about.
    rf"\bend(?:ing)? (?:it|it all|things|everything|my life)(?: (?:here|there|now|right now|"
    r"tonight|today))? (?:(?:with|using|by (?:taking|swallowing|using)) (?:(?:a|an|the|my|some|"
    r"all|all the|all my|all of my|those|these) )?(?:(?:\d+|few|two|three|four|five|six|seven|"
    r"eight|nine|ten|twenty|thirty|fifty|hundred|bunch of|handful of|(?:whole )?bottle of) )?"
    rf"(?:{_SUBSTANCE}|guns?|pistol|rifle|shotgun|"
    r"rope|knife|knives|blade|razor|belt|cord|bullet)|(?:in|at|on|off|from) (?:the |a |my )?"
    r"(?:bridge|garage|roof|rooftop|ledge|tracks|cliff|balcony|overpass))\b",
    r"\bshould i (?:just |maybe )?end (?:it|things|everything)\b",
    rf"{_CHAIN} end me\b",
    r"\bending (?:it|things|it all|my life) (?:would|will|might|seems|sounds|feels|is)\b",
    r"\b(?:want|wish|need) (?:my|this) life to (?:end|be over|stop)\b",
    r"\b(?:end|out of) my misery\b",
    rf"\btime (?:for me )?to end (?:it|things|everything)\b{_END_IT_TAIL}",
    r"\btak(?:e|ing) my (?:own )?life\b",
    r"\b(?:want(?:ed)? (?:to|2)|wanna|going to|gonna|ready to|rather|should just|wish i could|"
    r"hope i) d[i1!]e\b(?! (?:if (?:the|they|he|she|this|that|my)|laughing|of (?:laughter|"
    r"boredom|embarrassment))\b)",
    r"\bdeserve to (?:die|be dead)\b",
    r"\blet me die\b",
    r"\b(?:way|ways|how|take|takes|enough|pills|easiest|quickest) to die\b(?! hard)",
    r"\bbetter (?:to be|being) dead\b",
    r"\b(?:death|dying|being dead) (?:would|will|might|seems|sounds|feels|is) (?:be )?(?:a "
    r"relief|easier|better|the only|my only|the answer|peaceful|welcome)\b",
    r"\b(?:dont|do not) deserve to (?:live|be alive|be here|exist)\b",
    # First person and "die", "dead" or "death", joined only by the chain words above.
    rf"{_CHAIN} die\b(?!-hard)(?! (?:for|to (?:see|watch|get|have|know)|laughing|happy|hard|on "
    r"(?:this|"
    r"that|the|my) hill|a (?:little|\w+ fan)|of (?:laughter|boredom|embarrassment)|if (?:the|"
    r"they|he|she|this|that|my)|when (?:the|they|he|she)|every time)\b)",
    r"\b(?:if|when|before|until|once|after) i die\b",
    r"\b(?:dont|do not) care (?:if|whether) i (?:live|die)\b",
    r"\b(?:dont|do not) care what happens to me\b",
    r"\bwish i (?:was|were|am) (?:dead|gone)\b",
    r"\bworth more dead\b",
    r"\b(?:family|wife|husband|kids|children|they|she|he) (?:would|will|could|can) (?:get|"
    r"collect|have) (?:the|my) (?:life )?insurance\b",
    r"\bhope (?:i get|i am|im|to get|to be) (?:hit|run over|killed)\b(?! with)",
    r"\bhope (?:a|some) (?:car|bus|truck|train) hits me\b",
    r"\b(?:dont|do not|wont|will not|not going to|not gonna|might not|may not) (?:make it "
    r"(?:through|to|past) (?:the night|tonight|tomorrow|morning)|see tomorrow)\b",
    r"\bno tomorrow for me\b|\bwont be a tomorrow\b",
    r"\bwont matter after tonight\b|\bafter tonight (?:it|nothing) (?:wont|will not|will) "
    r"matter\b",
    rf"{_CHAIN} (?:be|was|were) dead\b(?! ?(?:wrong|right|on|serious|set|last|even|tired|"
    r"certain|sure|money|to rights|in the water|asleep|weight|after|without|lol|lmao)\b)",
    r"\b(?:when|once|after|until|till) (?:im|i am) (?:dead|gone)\b(?! (?:on|for|from|to|at)\b)",
    r"\bif i (?:was|were) (?:gone|dead)\b(?! (?:for|on|from|would my|will my|do my|does my)\b)",
    r"\bif i (?:just )?(?:wasnt|werent|was not|were not) (?:here|around|alive)\b"
    r"(?! (?:for|to|at|on|when|during)\b)",
    rf"{_CHAIN} (?<!to )death\b(?! (?:by|row|stare|trap|grip|blow|valley|spiral|march|wish)\b)",
    r"\bmy (?:own )?death\b",
    r"\b(?:dead|dying|empty|numb) inside\b",
    r"\bbetter off (?:dead|gone|without me|if i (?:was|were|wasnt|werent|am|died|die|"
    r"disappeared)|not (?:being )?(?:here|around|alive))\b",
    r"\b(?:happier|better|easier) (?:if i (?:was|were|wasnt|werent|died|die|disappeared)|"
    r"without me|with me gone|when im gone)\b",
    rf"(?:{_IM}|\bive become|\bi feel like) (?:just |such )?a burden\b",
    r"\b(?:nobody|no one|noone) (?:would|will|wouldnt|is going to) (?:even )?(?:miss me|"
    r"care (?:if|when|that) i|notice (?:if|when) i)\b",
    r"\b(?:nobody|no one|noone) cares (?:if|whether) i (?:live|die|am|was|exist)\b",
    rf"\b(?:nobody|no one|noone) (?:would|will|wouldnt) (?:even )?(?:notice|care)(?:{_END}| if i| "
    r"when i| about me)",
    r"\b(?:nobody|no one|noone) cares about me\b",
    r"\b(?:would|will|wouldnt|wont|whod)(?: (?:even|anyone|anybody|they|you|she|he|really|"
    r"ever)){0,3} miss me\b",
    r"\b(?:wont|will not|never) (?:hear from|see) me (?:again|any ?more)\b",
    rf"{_IM} (?:just |such )?a waste of (?:space|air|oxygen|life)\b",
    r"\brather be dead\b",
    r"\bfeel like dying\b",
    r"\b(?:done|finished|through) with (?:this |my )?(?:life|living)\b",
    rf"{_IM} (?:so |just )?done with (?:everything|it all|all of it)(?:{_END}| any ?more)",
    rf"\bi (?:just |really )?{_CANT} any ?more{_END}",
    rf"\b{_CANT} stand (?:being alive|living(?! (?:in|with|at|near)\b)|my life|my ?self)\b",
    r"\b(?:living|life) is too (?:hard|much|painful)\b",
    r"\blife has no (?:meaning|point|purpose)\b",
    r"\bno (?:meaning|point|purpose) (?:to|in) (?:my )?life\b",
    rf"\bnothing matters(?: any ?more\b|{_END})",
    r"\bout of this life\b|\bquit life\b",
    r"\b(?:stop|sick of|hate|done|quit|finished) living\b"
    r"(?! (?:on|in|at|with|like|off|up|for|vicariously)\b)",
    r"\b(?:dont|do not|why (?:should|do|would) i|no reason to|cant|cannot) (?:want to )?keep "
    r"living\b",
    r"\bwhy am i (?:even |still )?alive\b",
    r"\bwhy (?:even )?(?:go on|keep going|bother living)\b"
    r"(?! (?:with|to|for|at|on (?:this|the|that|a))\b)",
    r"\btired of (?:living|life|being alive|being here|existing|it all|everything)\b",
    r"\b(?:hate|sick of|stop) being alive\b",
    r"\bshouldnt be alive\b",
    r"\bwish i (?:had |was |were |d )?(?:never |not )?(?:been )?born\b",
    r"\bwish i (?:wasnt|werent|was not|were not) (?:alive|here|born|around)\b",
    r"\bnever (?:been|was) born\b",
    r"\b(?:want|wanna|wish i could|need) (?:to )?(?:just )?(?:disappear|vanish)\b",
    rf"{_CHAIN} (?:disappear|vanish)\b",
    r"\bstop existing\b|\bcease to exist\b",
    r"\bwish i (?:didnt|did not|could (?:just )?not) exist\b",
    r"\b(?:rather|wish to|want to|prefer to) not (?:be alive|exist|live|wake up)\b",
    r"\b(?:no longer|not|dont|do not) (?:want|wanna|wish|wanting|wishing) (?:to )?(?:live|be "
    r"alive|exist|do life)\b",
    r"\bgo away forever\b",
    r"\b(?:point|purpose) of (?:living|life|going on)\b",
    r"\b(?:dont|do not) (?:want|wanna) (?:to )?(?:live|be alive|be here|be around|exist|"
    r"wake up|go on(?! (?:the|a|my|this|that|tilt)\b))\b",
    r"\b(?:reason|point) (?:to|in|for) (?:keep(?:ing)? )?(?:live|living|go on|going on|"
    r"being alive|being here|stay(?:ing)? alive)\b"
    # "no reason to live bet this one": live betting is betting during the game.
    rf"(?! {_LIVE_BETTING})",
    r"\breason to keep going\b(?! (?:with|for|at|to|after|on (?:this|that|the|my|a))\b)",
    r"\bnothing (?:left )?to live for\b",
    r"\bworth living\b",
    r"\blife (?:isnt|is not|aint|is no longer) worth (?:it|living|the pain|anything)\b",
    r"\blife is (?:pointless|meaningless|hopeless)\b",
    r"\bmy life is (?:over|pointless|meaningless|worthless)\b",
    r"\b(?:give|giving|given|gave) up on (?:life|living|everything|my ?self)\b",
    rf"\bi (?:just |really )?{_CANT} go on\b"
    r"(?! (?:the|a|my|this|that|to|oddvex|air|without (?:knowing|seeing|checking))\b)",
    r"\b(?:dont|do not) think i can (?:go on|keep going|do this|take (?:it|this)|live)\b"
    r"(?! (?:the|a|my|to|with|without (?:knowing|seeing|checking))\b)",
    r"\bnothing left for me\b",
    r"\bno way forward\b",
    r"\bno hope (?:for me|left|any ?more)\b",
    r"\bi(?:ve| have)? (?:\w+ )?lost (?:all |any )?hope\b(?! (?:in|for|on) (?:the|this|that|"
    r"my (?:parlay|bet|team))\b)",
    r"\bthe end for me\b",
    r"\bend of my (?:rope|tether)\b",
    rf"\bi (?:just |really |honestly |literally )?{_CANT} keep (?:going|living|doing this)\b"
    r"(?! (?:back|with|to|for|at|in|after|on (?:this|the|that|a|my|these|those))\b)",
    rf"\bi (?:just |really |honestly |literally )?{_CANT} live (?:like this|this way|with "
    r"my ?self|with this|with it|with what i(?:ve|d)?|with the (?:shame|guilt)|any ?more|any "
    r"longer)\b",
    rf"\b{_CANT} (?:take|do|bear|stand|handle|face|cope with|deal with) (?:it|this|the pain|"
    r"life|things|everything|any of (?:it|this)) any ?more\b",
    rf"\bi (?:just |really )?{_CANT} cope\b",
    rf"\bno (?:other )?way out\b{_OUT_OF_SPORT}",
    r"\bonly way out\b",
    r"\b(?:a|any|another|an easy) way out\b(?! of (?:the|a|his|her|their|that) )"
    rf"{_OUT_OF_SPORT}",
    r"\b(?:want|wanna|need|wish) (?:it all|everything|the pain|the suffering|this all|all of "
    r"(?:it|this)) (?:to |would )(?:all )?(?:stop|end|be over|go away|disappear)\b"
    r"(?! (?:in|at|on|with|before|after|early|so|by)\b)",
    r"\bjust (?:want|wanna|need) (?:it|this) to (?:stop|end|be over)\b"
    r"(?! (?:in|at|on|with|before|after|early|so|by)\b)",
    rf"\bi (?:really )?(?:want|need|wish) (?:it|this) (?:to|would) (?:all )?(?:stop|end|be "
    rf"over){_END}",
    # Never waking up. Not "the offense may never wake up" or "I didn't wake up in time".
    r"\b(?:and|to|rather|wanna) (?:never|not) wak(?:e|ing) up\b"
    r"(?! (?:in time|early|that early|on time|for|until|till|before|to|at)\b)",
    r"\bwish i (?:wouldnt|would not|didnt|did not|dont|never) (?:have to )?wake up\b",
    rf"{_I}(?: {_CHAIN_WORD}){{0,4}} (?:dont|do not|wont|will not|never) wak(?:e|ing) up\b"
    r"(?! (?:in time|early|that early|on time|for|until|till|before|to|at)\b)",
    r"\bsleep forever\b",
    r"\b(?:please|someone|somebody) make it (?:all )?stop\b|\bmake it all stop\b",
    rf"{_IM} in (?:so much|too much|constant|unbearable) pain\b",
    r"\bpain is (?:too much|unbearable)\b",
    rf"\b(?:murder|murdering|hurt|hurting|harm|harming|cut|cutting|shoot|shooting|hang|hanging|"
    rf"drown|drowning|"
    rf"poison|poisoning|off|offing|end|ending|stab|stabbing|starve|starving|delete|deleting) "
    rf"{_SELF}\b",
    r"\b(?:slit|slitting|slash|slashing|cut|cutting) my (?:own )?(?:wrists?|throat|veins?)\b",
    r"\bblow(?:ing)? my (?:own )?(?:brains?|head) (?:out|off)\b",
    r"\b(?:bullet|gun) (?:in|to|through|against) my (?:own )?(?:head|brain|mouth|temple)\b",
    r"\b(?:i|ive) (?:just )?(?:bought|have|got|loaded|own) (?:a|my|the) (?:loaded )?(?:gun|"
    r"pistol|revolver|noose|rope)\b(?![-\w])",
    r"\bstanding on (?:a|the) (?:bridge|ledge|roof|edge)\b|\bon (?:the|a) ledge\b",
    r"\b(?:pills|rope|gun|noose|blade|razor) (?:is |are )(?:ready|loaded|in my hand|next to "
    r"me|right here)\b",
    r"\b(?:have|got) (?:the|my) (?:pills|rope|gun|noose|blade|razor) (?:ready|loaded|here|with "
    r"me)\b",
    r"\b(?:take|took|taking|swallow\w*) every (?:\w+ )?pill\b",
    r"\b(?:going to|gonna|want to|wanna|about to|might|will|ill) od\b",
    r"\b(?:rope|belt|noose|cord) around my neck\b",
    r"\beat a bullet\b",
    rf"{_CHAIN} jump{_END}",
    rf"{_CHAIN} (?:hurt|harm) (?:someone|somebody|people|him|her|them|my (?:wife|husband|kids|"
    r"family|boss|bookie|partner|girlfriend|boyfriend|parents|mom|dad))\b",
    rf"{_CHAIN} (?:go to|be in) heaven\b|\bbe with (?:my |our )?\w+ in heaven\b",
    r"\bjoin my late\b",
    r"\btell my (?:family|wife|husband|kids|mom|dad|parents|children|son|daughter) (?:that )?"
    r"(?:i love (?:them|her|him|you)|im sorry|i am sorry|goodbye)\b",
    r"\bsorry for everything\b",
    r"\bcheck(?:ing)? out (?:for good|of life|permanently)\b",
    r"\bwalk(?:ing)? into (?:traffic|the road|the sea|the ocean)\b",
    r"\bcrash(?:ing)? my car\b",
    r"\b(?:just|please|someone|somebody|god|lord) (?:shoot|end) me\b",
    r"\bself[- ]?harm",
    r"\boverdos(?:e|ed|ing)\b",
    # Pills, when the message gives a quantity. "I took my pills" is a prescription.
    r"\b(?:took|take|taking|taken|swallow\w*|down(?:ed|ing)?) (?:a (?:whole )?(?:bunch|lot|"
    r"bottle|handful|load|ton) of |all (?:of )?(?:my|the|these|those|her|his) |too many |the "
    r"(?:whole|entire) bottle of )(?:\w+ )?(?:pills|tablets|meds|medication|painkillers)\b",
    r"\b(?:jump|jumping|step|stepping|walk|walking|throw(?:ing)? my ?self) (?:in front of|off|"
    r"under) (?:a |an |the |my |oncoming |moving )?(?:train|bus|truck|car|traffic|bridge|cliff|"
    r"roof|building|balcony|overpass|ledge|subway|lorry)\b",
    r"\bdriv(?:e|ing) (?:my car )?(?:off|into) (?:a |the )?(?:bridge|cliff|wall|tree|lake|"
    r"river|oncoming)\b",
    r"\b(?:think\w*|thought|thoughts|dream\w*|fantasi\w+) (?:a lot |often |constantly |all the "
    r"time )?(?:about|of) (?:my (?:own )?)?(?:death|dying|jumping|not being (?:here|around|"
    r"alive)|not waking up|disappearing)\b",
    # "Thinking about ending it" or "... hurting myself", not "... ending my subscription".
    r"\bthink(?:ing)? (?:of|about) (?:ending|killing|hurting|harming)\b(?! (?:my|the|this|that|"
    r"a|an|our|his|her|their) (?!life\b|own\b|pain\b|suffering\b|family\b|wife\b|husband\b|"
    r"kids\b|children\b)\w)",
    r"\bdark thoughts\b|\b(?:in|into|to) a (?:very |really |pretty )?dark place\b",
    r"\bdo something (?:\w+ )?to my ?self\b",
    r"\bdanger to my ?self\b",
    r"\b(?:scared|afraid) of what i (?:might|may|could|will) do\b",
    r"\bmy life insurance\b|\blife insurance (?:would|will|pays?|payout|money|policy)\b",
    r"\b(?:wont|will not|not going to|shouldnt) be (?:around|here) (?:much longer|any ?more|"
    r"any longer)\b",
    r"\b(?:wont|will not|not going to|shouldnt|might not) be alive\b",
    rf"\b(?:{_CANT}|dont|do not) see (?:a|any|my) future\b"
    r"(?! (?:markets?|bets?|lines?|prices?|odds|props?|games?|events?)\b)",
    r"\bno future (?:for (?:me|my ?self)|left)\b",
    r"\b(?:dont|do not|cant|cannot) see (?:the|a|any) point (?:any ?more|in (?:anything|any of "
    r"(?:it|this)|living|going on|life|trying))\b",
    r"\bwhats the point (?:any ?more|of (?:anything|it all|any of (?:it|this)|trying|living|"
    r"life|going on))\b",
    r"\bthis is (?:my )?goodbye\b",
    rf"{_IM} saying (?:my )?goodbyes?\b(?! to (?:my|the|this|that|these|those)\b)",
    r"\b(?:this is|its|this will be|tonight is|today is) my last (?:message|day|night)\b"
    r"(?! (?:in|at|on|of|to)\b)|\bmy last (?:day|night) (?:on earth|alive)\b",
    r"\bgoodbye (?:everyone|everybody|all|world|forever)\b",
    # "Just kill me", as a plea. "That parlay killed me" and "these refs kill me" are slang.
    r"(?:^|[.!?;,] )(?:(?:just|please|someone|somebody|god|lord) ){0,2}kill me\b",
    r"\b(?:just|please|someone|somebody|god|lord) kill me\b",
    # Round four of the review: families rather than single wordings.
    # The will to live, and a crisis in the writer's own words. "The Tides are in crisis"
    # has no first person.
    r"\bwill to live\b",
    rf"{_IM} (?:in|having|going through) (?:a |an )?(?:real |serious |mental health |"
    r"emotional |personal )?(?:crisis|breakdown|mental breakdown|nervous breakdown)\b(?! of\b)",
    r"\bmental health (?:crisis|emergency)\b",
    # "I can't carry on", "I don't want to continue living". Not "I can't continue the
    # parlay" or "I'll carry on with this bet".
    rf"\b(?:i (?:just |really |honestly )?{_CANT}|(?:dont|do not) (?:want|wanna)(?: to)?|(?:dont|"
    rf"do not) think i can) "
    rf"(?:carry on|continue|go on)(?: (?:like this|this way|living|with (?:life|living|this "
    rf"life|my life))\b|{_END}| any ?(?:more|longer)\b)",
    # Harm to somebody else, and "... and then myself". Not "kill my parlay" or "I'd kill
    # for a cover".
    rf"{_CHAIN} kill (?:my (?:wife|husband|partner|girlfriend|boyfriend|kids|children|family|"
    r"son|daughter|mom|mum|dad|parents|boss|bookie|roommate)|him|her|them all|someone|somebody|"
    rf"everyone|everybody|people)(?:{_END}| (?:and|then|tonight|today|now|if|when)\b)",
    rf"\band (?:then )?(?:kill |shoot |hang |end )?{_SELF}(?:{_END}| too\b| after\b)",
    # More ways of writing "... myself".
    rf"\b(?:ive|i have|im|i am) (?:been |started |starting )?cutting(?: (?:again|my ?self))?{_END}",
    rf"\b(?:top|topping|gas|gassing|burn(?:ed|t|ing)?) {_SELF}\b(?! (?:out|up)\b)",
    rf"\bdo(?:ing)? {_SELF} in\b|\bfinish(?:ing)? {_SELF} off\b",
    rf"\b(?!(?:laugh|bor|bore|worr|scar|freez|stress|tir|bor)\w*\b)\w+ {_SELF} to death\b",
    # "I don't think I'll make it through the night".
    r"\b(?:(?:dont|do not) think|not sure|doubt) (?:ill|i will|i can|im going to|im gonna|i(?:ll)? "
    r"be able to) (?:make it|survive|last) (?:through|to|past|until|till) (?:the night|tonight|"
    r"tomorrow|morning)\b",
    r"\b(?:had|have had|ive had|im done having) enough of (?:life|living|being alive|this life|"
    r"my life|it all|everything)\b",
    r"\bnothing but a burden\b|\ba burden (?:to|on) (?:everyone|my family|my wife|my husband|"
    r"my kids|them|the people)\b",
    r"\bi (?:feel|felt|think)(?: like)? (?:theres|there is) (?:no|zero) hope\b"
    r"(?! (?:for|in|of|on) (?:the|this|that|a|their|his|her)\b)",
    rf"\bi (?:have|had|got) (?:no|zero) hope(?: left)?(?:{_END}| any ?more\b| for (?:me|my "
    r"?self)\b)",
    r"\b(?:happier|easier|better) (?:being |off being )?dead\b",
    r"\bworth more (?:\w+ ){0,3}?dead\b",
    rf"{_CHAIN} jump (?:off )?(?:tonight|today|right now|now)\b(?! (?:on|in|at)\b)",
    rf"\b{_CANT} bear (?:it|this)(?:(?: any)? ?(?:more|longer)\b|{_END})|\b{_CANT} bear (?:the "
    r"pain|life|living|to live|being alive|to go on)\b",
    r"\b(?:stockpil\w+|hoard\w*|sav(?:e|ed|ing) up|collect(?:ed|ing)) (?:up )?(?:my |some |a lot "
    r"of |lots of |enough )?(?:sleeping )?(?:pills|tablets|meds|medication|painkillers)\b",
    r"\bbetter off with (?:the|my) (?:life )?insurance\b",
    r"\b(?:end|stop) (?:the|this|my|all (?:the|this|my)) (?:pain|suffering|hurt|hurting)\b"
    r"(?! (?:of|for)\b)",
    r"\bmake (?:the|this|my|all the|all this) (?:pain|hurt|hurting|suffering) (?:stop|end|go "
    r"away)\b",
    r"\b(?:pills|rope|gun|noose|blade|razor|knife)(?: (?:is|are|right|sitting|lying|laid out|"
    r"all|here|now))* (?:in front of me|in my hands?|next to me|beside me|with me)\b",
    rf"{_IM} (?:on|at|standing on|standing at|up on) (?:the|a) (?:bridge|ledge|roof|rooftop)\b"
    r"(?! (?:game|club|table|tournament|bar|restaurant|party|deck|terrace|seats?|suite|top)\b)",
    r"\b(?:edge|top) of (?:the|a) (?:roof|bridge|building|cliff|balcony|platform|parking "
    r"garage)\b",
    rf"(?:{_IM} not|\bi (?:dont|do not) feel|{_IM} not feeling|\bi (?:feel|am|m) unsafe|"
    rf"\bi (?:dont|do not) think im) safe(?: (?:right now|tonight|with my ?self|around my ?self|"
    rf"alone|by my ?self|at the moment|being alone|any ?more)\b|{_END})",
    r"\b(?:suicide|goodbye|farewell) (?:note|letter)s?\b",
    rf"{_I}(?: (?:just|already|have|finally|now))* (?:wrote|written|left) (?:a|my|the) "
    rf"(?:last )?note(?:{_END}| (?:for|to) (?:my (?:family|wife|husband|kids|children|mom|dad|"
    r"parents)|everyone|them|her|him)\b)",
    r"\b(?:want|wanna|wish|need|going|gonna|ready) (?:to )?(?:be|b) gone\b"
    r"(?! (?:for|by|from|before|until|till|on|at|in|when|after)\b)",
    rf"{_CHAIN} b dead\b",
    r"\b(?:want|wanna|need|wish|ready) (?:to (?:be |get |go )?)?out of this world\b",
    # Ambiguous on its own, and common; help is shown.
    rf"{_IM} (?:just |so |finally )?ready to (?:go|leave)(?: now)?{_END}",
    # Round five of the review. Lethal means: "lethal dose", "lethal dosage", "would 20 pills
    # kill me", "how much tylenol kills you", "how many pills is lethal", "is 20 pills
    # lethal", "how to tie a noose". Not "a lethal offense" or "will this parlay kill me".
    r"\b(?:lethal|fatal|deadly) (?:doses?|dosage|amount|overdose|quantity)\b",
    r"\bld ?50\b",
    rf"\b(?:{_SUBSTANCE})\b(?: \w+){{0,4}}? (?:kills? (?:me|you|a person|someone|somebody|a "
    rf"human|{_SELF})|kills{_END}|be (?:fatal|lethal|deadly|enough to (?:kill|die))|(?:is|are|"
    rf"would be|will be|becomes?) (?:fatal|lethal|deadly)|to (?:die|end (?:it|it all|my life)|od|"
    rf"overdose|kill (?:me|{_SELF})))\b",
    # The yes/no order: "is 20 pills lethal", "is a bottle of tylenol fatal", "would 50
    # tylenol be enough".
    rf"\b(?:is|are|would|will|could|can|does|do) (?:\w+ ){{0,4}}?(?:{_SUBSTANCE})\b"
    rf"(?: \w+){{0,3}}? (?:lethal|fatal|deadly|kills?|be enough(?:{_END}| to (?:kill|die|od|"
    r"overdose|end)))\b",
    # The final pass: "how many <anything> would kill me" and "how much <anything> to die",
    # whatever the substance is called. Not "how many runs would end it".
    rf"\bhow many {_ONE_OR_TWO_WORDS} (?:to|would|will|could|(?:does|would|will) it take to) "
    rf"(?:die|kill (?:me|{_SELF})|end it|od|overdose)\b",
    rf"\bhow much {_ONE_OR_TWO_WORDS} (?:to|would|will|could) (?:kill me|die|od|overdose)\b",
    r"\bnooses?\b",
    r"\bhang (?:your ?self|urself|oneself|one ?self)\b",
    # A threat that depends on a bet: "if this parlay loses I'm done for good", "when this
    # misses I'm gone for good", "if this loses I'm jumping". Not "if this parlay loses I'm
    # done betting for the night". "Out" counts only with "for good": "if the Tides lose, I'm
    # out" is a survivor pool.
    rf"\b(?:if|when|once)\b(?: \w+){{0,6}}? (?:loses?|lost|miss(?:es)?|missed|fails?|busts?|goes "
    r"(?:bust|south|wrong)|(?:doesnt|dont|does not|do not|wont|will not) (?:hit|cash|win|cover|"
    rf"come in|come through))\b(?:,? \w+){{0,3}}?,? (?:{_IM}|\bill|\bi will|\bi(?:ll)? be|\bim "
    r"(?:gonna|going to)|\b(?:imma|ima)(?: be)?) (?:just )?(?:(?:done|finished|gone|over|ending "
    rf"(?:it|everything|things)|jumping|jump|end (?:it|everything|things))(?:{_END}| (?:for good|"
    r"forever|permanently|for real|tonight|today|off)\b)|out (?:for good|forever|permanently)\b)",
    # "I'm jumping tonight". Not "I'm jumping on the Tides tonight".
    rf"{_IM} (?:just |really )?jumping (?:off )?(?:tonight|today|right now|now|later)\b"
    r"(?! (?:on|in|at|into|over|to)\b)",
)

#: What follows "no point living" or "no point going on" in sports talk: "no point living in
#: the past", "no point going on the road with this lineup", "no point going on about the
#: refs", "no point going on to the playoffs", "no point living on the bubble". "Like this",
#: "in this pain" and "with this" are not on the list.
_NO_POINT_SPORT = (
    rf"(?! (?:{_LIVE_BETTING}|in the past|about\b|(?:on )?(?:the|a) (?:road|edge|bubble|trip|bench|"
    r"field|court|ice|clock|board|air|radio|tv|offense|defense)\b|to the (?:playoffs|postseason|"
    r"next round|finals?|championship|title game)\b|with (?:the|this|that|a|"
    r"my|these|those) (?:\w+ )?(?:bet|bets|parlay|parlays|line|lineup|roster|pick|play|team|"
    r"offense|defense|ticket|slip|game)\b))"
)
# Round five of the review: crisis wordings with no "I" ("gonna end it", "might as well
# die"). They count unless the clause names somebody else first: "the Tides are gonna end it
# tonight" and "they're going to end it" are about a team.
_NO_SUBJECT_MODAL = (
    r"gonna|going to|gon|finna|about to|bout to|abt to|ready to|want to|wanna|need to|have to|"
    rf"gotta|got to|might just|may just|should just|{_AS_WELL}"
)
# The final pass. With no "I" before it, "end it" is a crisis only when the clause ends there
# ("gonna end it", "might as well end it and ...") or a time, a means or a place from the
# lists below follows. Anything else after "with", "on", "in", "at" or "by" is a game that
# ends ("gonna end it with a 3", "gonna end it in the bottom of the ninth"); so is any word
# not on the lists ("gonna end it for the night").
_END_IT_CLAUSE_END = r"(?=[.,!?;]|$| (?:and|but|so|or|because|cause|cuz|then)\b)"
_END_IT_TIME = (
    r"(?:tonight|today|tomorrow|soon|later|forever|for good|for real|this (?:weekend|week|"
    r"morning|evening)|in the morning|before (?:the )?morning|at (?:midnight|home tonight|dawn)|"
    r"at \d{1,2}(?::\d\d)? ?(?:am|pm|oclock|tonight|today|tomorrow)|in (?:a|an|one|two|three|"
    r"a few|a couple(?: of)?|\d+) (?:minutes?|mins?|hours?|hrs?|days?)|after (?:tonight|today|"
    r"this|the game|the loss|work))\b"
)
# The lists are tuples, one entry per line, so that the tests can remove each entry on its
# own and check that a message changes (``MUTATIONS`` in tests/test_audit_assistant_detection.py).
# "noose" is not on the means list: ``\bnooses?\b`` is a crisis wherever it stands.
_END_IT_PREPOSITIONS = (
    "with",
    "using",
    "by taking",
    "by swallowing",
    "by using",
    "on",
    "in",
    "at",
    "off",
    "from",
    "in front of",
    "under",
    "by",
)
_END_IT_DETERMINERS = (
    "a",
    "an",
    "the",
    "my",
    "some",
    "all",
    "all the",
    "all my",
    "all of my",
    "those",
    "these",
)
_END_IT_COUNTS = (
    r"\d+",
    "few",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "twenty",
    "thirty",
    "fifty",
    "hundred",
    "bunch of",
    "handful of",
    "bottle of",
    "whole bottle of",
)
_END_IT_MEANS_WORDS = (
    _SUBSTANCE,
    "bottle(?! of)",
    "guns?",
    "pistol",
    "rifle",
    "shotgun",
    "rope",
    "knife",
    "knives",
    "blade",
    "razor",
    "belt",
    "cord",
    "bullets?",
    "bridge",
    "ledge",
    "roof",
    "rooftop",
    "tracks",
    "trains?",
    "cliff",
    "garage",
    "overpass",
    "balcony",
)
_END_IT_PREPOSITION = rf"(?:(?:{'|'.join(_END_IT_PREPOSITIONS)}) )?"
_END_IT_MEANS = (
    rf"(?:(?:{'|'.join(_END_IT_DETERMINERS)}) )?(?:(?:{'|'.join(_END_IT_COUNTS)}) )?"
    rf"(?:{'|'.join(_END_IT_MEANS_WORDS)})\b"
)
_NO_SUBJECT_END_IT_TAIL = (
    r"(?:(?: (?:here|there|now|right now|early|just))?"
    rf"(?:{_END_IT_CLAUSE_END}| {_END_IT_TIME}| {_END_IT_PREPOSITION}{_END_IT_MEANS}))"
)
_NO_SUBJECT_CRISIS_RE = _any(
    rf"\b(?:{_NO_SUBJECT_MODAL}) (?:just )?end (?:it|it all|things|everything)\b"
    rf"{_NO_SUBJECT_END_IT_TAIL}",
    rf"\b{_AS_WELL} (?:just )?(?:die|be dead|not (?:exist|be here|be alive|wake up)|"
    rf"kill (?:me|{_SELF}))\b(?! (?:trying|laughing|happy|on|for|in the water|money|odds|weight|"
    r"wrong|right|last|even|serious|set|certain|sure|tired|asleep)\b)",
)
#: "No point living" needs no subject check: a team is never the subject of it, so "the
#: Tides lost no point living" counts like "no point living".
_NO_POINT_RE = re.compile(
    r"\b(?:no (?:point|reason|use|sense) (?:for me )?(?:in |to |for )?|pointless |whats the "
    r"point (?:in )?|what point )(?:even )?(?:living|livin|being alive|staying alive|existing|"
    rf"live|exist|go on|going on|carry on|carrying on)\b{_NO_POINT_SPORT}"
)
#: The end of a clause that names who the sentence is about, when that is not the writer.
#: "They", "he", "she" and "we" are subjects wherever they stand. "You", "team" and "the
#: <team>" are subjects only where they open the clause or follow "and", "but", "so",
#: "because", "cause", "cuz" or "then": in "lost on the Tides again gonna end it" the team is
#: the object of "on". "The <team>" is one to three words and stops at a verb or an object:
#: in "the Tides lost gonna end it" and "the refs robbed me gonna end it" the clause says
#: what happened, not who is going to end it. "<word> is" names somebody else unless the
#: word is the writer's own loss, debt or life.
_SUBJECT_BEFORE_RE = re.compile(
    r"(?:\b(?:they|theyre|theyll|he|hes|hell|she|shes|shell|we|were|well)|(?:^|\b(?:and|but|so|"
    r"because|cause|cuz|then) )(?:you|youre|youll|u|team|the (?!(?:loss|losses|rent|money|bet|"
    r"bets|parlay|night|day|week|weekend)\b)\w+(?: (?!(?:lost|lose|loses|losing|blew|blown|"
    r"choked|missed|beat|robbed|killed|screwed|cost|ruined|took|got|again|me|my|it|so|and|but)"
    r"\b)(?!\w{3,}ed\b)\w+){0,2})|\b(?!(?:i|im|ive|id|ill|there|"
    r"here|what|whats|which|who|it|this|that|loss|losses|debt|debts|pain|life|rent|money|bet|"
    r"bets|parlay|everything|nothing)\b)\w+ (?:are|is|was|were|will)) (?:(?:just|really|probably|"
    r"definitely|all|so|still|finally) )*$"
)

# --------------------------------------------------------------------- under 21
# What follows a number when it is not an age: a record ("3-0", "10 for 12"), a count
# ("15 units", "18 bets in"), an amount ("20 dollars", "15%") or a stake ("20 on the Tides").
_NOT_AN_AGE = (
    r"(?![-:/.,]\d)(?!\s?%)(?!\s?(?:k|x|u|pts?|th|st|nd|rd)\b)"
    # "10-team parlay", but not "17-year-old".
    r"(?!-(?!years?-old|yrs?-old|yo\b)[a-z])"
    r"(?!\s(?:to|of|out of|for|from)\s\d)"
    # "10 and 2 this month" is a record; "17 and 3-0 this week" is an age and then a record.
    r"(?!\s(?:and|or)\s\d+(?![-\d]))"
    r"(?!\s(?:on|in on) (?:the|a|an|this|that|my|tonights?|both|either)\b)"
    r"(?!\s(?:units?|bets?|wagers?|picks?|plays?|games?|legs?|parlays?|props?|dollars?|bucks?"
    r"|grand|percent|points?|wins?|loss(?:es)?|for(?! sure)|of(?! age)|out|up|down|deep"
    r"|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|seasons?|straight|consecutive|under"
    r"|over|ahead|behind|times?|in a row|in the hole|in on|into|cents?|large|bands?|teams?"
    r"|teamers?|seeds?|back)\b)"
    r"(?!\s(?:years?|yrs?) (?:in|into|deep|of(?! age)|removed|away|ago|behind|sober|clean)\b)"
)
_FILLER = r"(?:(?:only|just|still|currently|like|barely|literally|actually|legally|a|an) )*"
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
_AGE = (
    r"(\d{1,2}(?!\d)|(?:twenty[- ]?one|" + "|".join(k for k in _AGE_WORDS if k.isalpha()) + r")\b)"
)
_YEARS_OLD = r"[- ]?(?:yo|y/o|years?[- ]old|yrs?[- ]old)\b"
# "twenty" followed by another number word is 21 to 29.
_NOT_TWENTIES = r"(?![- ]?(?:two|three|four|five|six|seven|eight|nine)\b)"
_21 = r"(?:21|18|twenty[- ]?one|eighteen)\b(?!\.?\d)"
# "A 20 years old veteran" is somebody else.
_NOT_A_PLAYER = (
    r"(?! (?:is|was|are|were|veteran|rookie|player|pitcher|quarterback|qb|kid|phenom|prospect|"
    r"guard|forward|center|striker|goalie|star|receiver|record|streak)\b)"
)
_SOON = (
    r"(?:next (?:week|month|year|\w+day)|tomorrow|soon|in (?:a|an|one|two|three|four|five|six|"
    r"\d+|a few|a couple(?: of)?) (?:days?|weeks?|months?|years?)|in (?:january|february|march|"
    r"april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|"
    r"aug|sep|sept|oct|nov|dec)|this (?:week|month|year|\w+day)|on (?:mon|tues|wednes|thurs|"
    r"fri|satur|sun)day)\b"
)

#: "I'm 17", "I'm17", "I am sixteen years old", "I just turned 19", "as a 17 year old",
#: "age 17": under 21 when the number is below 21.
_AGE_NOW_RE = _any(
    rf"(?:{_IM} ?(?:aged? )?|\bmy age(?: is|:)? |\bi (?:just |recently |only )?turned |"
    rf"(?:^|[.!?;] )(?:(?:just|recently) turned|being) ){_FILLER}{_AGE}"
    rf"{_NOT_TWENTIES}{_NOT_AN_AGE}",
    rf"\bas an? {_AGE}{_YEARS_OLD}",
    # "We're 17", "my friends and I are all 17": the writer is one of them.
    rf"(?:\bwe(?:re| are)|\b(?:my )?(?:friends?|buddies|brother|sister|mates) and i are)"
    rf"(?: (?:all|both|only|just|still))* {_AGE}{_NOT_TWENTIES}{_NOT_AN_AGE}{_NOT_A_PLAYER}",
    # "17 years old here", "17 here", "age 17": an age that opens the message or a sentence
    # is the writer's.
    rf"(?:^|[.!?;] ){_AGE}{_YEARS_OLD}{_NOT_A_PLAYER}",
    rf"(?:^|[.!?;] ){_AGE} here\b",
    rf"(?:^|[.!?;] )aged?:? {_AGE}{_NOT_TWENTIES}{_NOT_AN_AGE}",
    # "19M here".
    rf"(?:^|[.!?;] ){_AGE} ?[mf](?: here)?{_END}",
    rf"(?:^|[.!?;] ){_AGE} ?/? ?[mf]\b(?![-\w])(?! (?:dollars|views|contract|deal|salary|per|a "
    r"year|over|in|on|bet|bets|bucks|cap)\b)",
    # A question about someone of that age gets the same answer.
    rf"\b(?:can|could|may|should|is it (?:ok|okay|legal|allowed) for|allowed for) (?:an? |"
    rf"someone |somebody |anyone )?{_AGE}[- ]?(?:yo|y/o|years?[- ]olds?|yrs?[- ]olds?)\b"
    r"(?: \w+){0,3}? (?:bet|gamble|wager|use|sign up|join|register|download|(?:have|make|get|"
    r"open) an account)\b",
    r"\bcan (?:i|you|we|someone|anyone) (?:\w+ ){0,2}?(?:bet|gamble|use (?:this|oddvex|it|the "
    rf"app)|sign up|join|register) at (?:age )?{_AGE}{_NOT_TWENTIES}{_NOT_AN_AGE}",
)
#: "I turn 21 in March", "I'm not 21 yet", "when I'm 21", "I won't be 21 until May",
#: "I'm 21 next month": not there yet, so under 21 when the number is 21 or below.
_AGE_AHEAD_RE = _any(
    rf"(?:\bi turn|\bill (?:be|turn)|\bi will (?:be|turn)|{_IM} (?:turning|about to (?:be|turn)"
    rf"|almost|nearly|not quite|not(?: even| yet)?)|\bi aint(?: even| yet)?|\b(?:until|till|til|"
    rf"when|once|before) (?:im|i am|i turn)|(?:^|[.!?;] )(?:turning|almost|nearly|not quite)) "
    rf"{_AGE}{_NOT_TWENTIES}{_NOT_AN_AGE}",
    rf"\bi (?:havent|have not|didnt|did not|wont|will not|dont|do not) (?:even )?(?:be|turn|"
    rf"turned|hit) {_AGE}{_NOT_TWENTIES}{_NOT_AN_AGE}",
    rf"{_IM} {_AGE} {_SOON}",
)
_UNDERAGE_PHRASE_RE = _any(
    rf"{_IM} {_FILLER}(?:technically )?(?:under ?age|(?:under|below|younger than|less than|"
    rf"short of)(?: the age of)? {_21}"
    r"(?! (?:points?|pts|total|goals?|runs?))|under ?(?:21|18)\b(?!\.?\d)(?! (?:points?|pts|"
    r"total|goals?|runs?))|u ?(?:21|18)\b(?!\.?\d)|(?:under|below) the (?:(?:legal|betting|"
    r"gambling|minimum|required) ){0,2}age|too young|not old enough|not of (?:legal )?age|not "
    r"legal\b|minor\b(?! league)|kid\b"
    r"(?! at heart)|child\b|teen(?:ager)?\b|in (?:high|middle|junior high) ?school|in (?:the )?"
    r"(?:[6-9]th|1[0-2]th|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth) grade|"
    r"in grade (?:[6-9]|1[0-2])\b|"
    r"(?:[6-9]th|1[0-2]th|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)[- ]grader|"
    r"(?:high school|hs) "
    r"(?:student|kid|freshman|sophomore|junior|senior)|high ?schooler|(?:freshman|sophomore|"
    r"junior|senior) in (?:high school|hs)|(?:college|university|uni) (?:freshman|sophomore|"
    r"fresher)|(?:freshman|sophomore) (?:in|at) (?:college|university|uni))",
    r"\bi (?:still )?(?:go to|attend) (?:high|middle|junior high) ?school\b",
    r"\b(?:high ?school|hs|middle school) (?:student|kid|freshman|sophomore|junior|senior) here\b",
    r"\b(?:too young|not old enough) to (?:bet|gamble|wager|use (?:this|oddvex|it)|sign up|join)\b",
    rf"(?:\bwe(?:re| are)|\b(?:my )?(?:friends?|buddies|brother|sister|mates) and i are)"
    rf"(?: (?:all|both|only|just|still))* (?:under ?age|(?:under|below|younger than|less than) "
    rf"{_21}(?! (?:points?|pts|total|goals?|runs?))|minors|teens|teenagers|too young|not old "
    rf"enough|in (?:high|middle) ?school)",
    r"\bas an? (?:minor\b(?! league)|teen(?:ager)?\b|high ?schooler|high school (?:student|kid|"
    r"freshman|sophomore|junior|senior))",
    rf"\bnot (?:even |quite )?{_21} yet\b|\bnot yet {_21}",
    r"\b(?:\d+|a few|a couple(?: of)?|two|three|four|five|six) (?:years?|months?|weeks?|days?) "
    r"(?:away from|from|until|till|til|shy of|short of|before) "
    r"(?:im |i am |i turn |turning |being )?(?:21|twenty[- ]?one)\b",
    r"\bmy (?:1[0-9]|20)th (?:birthday|bday)\b",
    r"\b(?:until|till|til|before) my (?:21st|twenty[- ]?first)\b",
    r"\bmy (?:21st|twenty[- ]?first) (?:birthday|bday) (?:is|isnt|will be|comes)\b",
    # Asked about anyone, the answer is the same: OddVex is for adults 21 and over.
    r"\bunder ?age\b",
    r"\bfake id\b",
    r"\bi (?:just |recently )?graduated (?:from )?high ?school\b(?! in (?:19|20)\d\d| \w+ years? "
    r"ago)",
    rf"\bmy (?:little |younger )?(?:son|daughter|kid|child|nephew|niece|brother|sister|grandson|"
    rf"granddaughter|friend) is (?:only |just )?{_AGE} and (?:wants|would like|is trying|tries|"
    r"asked|asks|wanted) to (?:bet|gamble|wager|use (?:this|oddvex|the app|it)|sign up|join)\b",
    r"\bunder (?:21|18) here\b",
    r"\b(?:if youre|if you are|people|someone|anyone|users|kids|those|everyone) under "
    r"(?:21|18)\b(?!\.?\d)",
)
#: "I was born in 2009". The year is compared with today's date in ``_says_under_21``.
_BORN_RE = re.compile(
    r"(?:(?:\bi (?:was|am) |\bim |^|[.!?;] )born (?:in|on)|\bmy (?:dob|birth ?year|date of "
    r"birth)(?: is|:)?|(?:^|[.!?;] )(?:dob|birth ?year):?) (?:[\w,/]+ ){0,3}?((?:19|20)\d\d)\b"
)

# ---------------------------------------------------------------------- distress
#: Wanting to win back what was lost. Row 4 of the specification, and part of row 1.
_CHASING_RE = _any(
    r"\bwin(?:ning)? (?:(?:it|it all|everything|them|that|some|some of it|(?:my|the) (?:money|"
    r"loss|losses|rent|cash|stake|savings|bankroll|paycheck|bets?)|my \$?\d+k?|what i(?:ve| have)"
    r"? lost) )?back(?![-\w])(?! (?:the|a|their|his|her|its) (?:title|lead|belt|crown|trophy|"
    r"cup|championship|ball|possession|momentum|division|conference|job|starting|spot|fans|"
    r"serve|series|game)\b)"
    # "can the Tides win back 2 games": a count, not money.
    r"(?! (?:\d+|one|two|three|four|five|a few|some) (?:of (?:the|their|those) )?(?:games?|points?|"
    r"runs?|goals?|sets?|spots?|seats?|rounds?|strokes?|wins?|matches)\b)",
    r"\b(?:make|making|earn|earning) (?:it|it all|everything|my money|my losses|the money|"
    r"what i(?:ve| have)? lost) back\b(?! to (?:the|a) (?:playoffs|postseason|finals|top|lead|"
    r"lineup|line up|field|court|series|game|dugout|bench)\b)",
    r"\bget(?:s|ting)? (?:me )?(?:it|it all|everything|my money|my losses|the money|what i(?:ve| "
    r"have)? lost) back\b",
    r"\b(?:make|making|earn|earning|win|winning|get|getting) back (?:my|the|those|these|all|"
    r"all my|some of my) (?:\w+ )?(?:loss|losses|money|bankroll|stake)\b",
    r"\b(?:make|making|win|winning|recover|recovering|recoup|recouping|get|getting|earn|"
    r"earning) (?:back )?what i(?:ve| have)? lost\b",
    r"\b(?:recover|recoup|recovering|recouping) (?:my|the|those|these|all my|some of my) "
    r"(?:loss|losses|money|bankroll|stake)",
    r"\brecoup",
    r"\bneed (?:it|it all|the money|my money) back\b",
    r"\bchas(?:e|ed|ing) (?:my |the |these |those |all my )?loss(?:es)?\b",
    rf"{_IM} (?:just |still |always |back to )?chasing(?: again| it\b| them\b| bets\b|{_END})",
    r"\b(?:get(?:ting)? back to|back to|get(?:ting)?) even\b(?! (?:money|odds|closer|better|"
    r"more|worse|bigger|longer|shorter|higher|lower|though|if|when|in the (?:standings|series|"
    r"count|division|race|table|conference|league))\b)",
    r"\bmake up for (?:my loss|my losses|what i lost|last night|yesterday|(?:the|these|those) "
    r"losses)\b",
    r"\brecover(?:ing)? from (?:my|last nights?|yesterdays|todays|tonights) (?:\w+ )?(?:loss|"
    r"losses|bets|betting)\b",
    r"\bjust (?:want|wanna|need) to (?:get|break) even\b",
    r"\bbreak even (?:and|then) (?:quit|stop|walk away|im done|ill stop|ill quit)\b",
    r"\bdig my ?self out\b",
    r"\b(?:get|climb|dig) (?:my ?self )?out of (?:this|my) hole\b",
    rf"{_IM} (?:so |too |really |way |pretty )?(?:deep |far |far down )?in (?:a|the) hole\b",
    # A stake sized to recover: "what should I bet to break even", "best bet to recover
    # tonight". Not the break-even win rate at a price, and not a fumble recovery.
    r"\b(?:bet|stake|wager|play|parlay)\w* (?:\w+ ){0,3}?to (?:break even|get even|recover|get "
    r"(?:it |my money |everything |some )?back|make (?:it |my money |everything |some )?back|win "
    r"(?:it |some )?back)\b(?! (?:at|on|win|rate|percentage|point|odds|price|line|probability|to "
    r"(?:the|a|their|his|her)|a "
    r"fumble|the fumble|a loose|the ball|an onside)\b)(?!\s?%)",
    r"\bmake up (?:for )?(?:my|the|those|these|all my|all the|last nights?|todays?) losses\b",
    r"\b(?:i|me|im|ive)\b(?: \w+){0,4}? recover(?:ing)? from (?:a|my|this|last|the) (?:bad|rough|"
    r"losing|terrible|awful|horrible|brutal) (?:week|night|day|run|streak|month|weekend|"
    r"stretch)\b",
    r"\b(?:get(?:ting)?|me) back to zero\b",
    r"\bmoney back from (?:my|these|those|the|all|all my|all these|all the) (?:\w+ )?loss(?:es)?\b",
    r"\b(?:make|making|win|winning|get|getting|earn|earning) back (?:\S+ ){1,4}?(?:i|ive|i have|we|"
    r"weve) (?:just |already )?lost\b",
    r"\b(?:until|till|til) (?:im|i am|i get|i break|im back to|i am back to) (?:even|zero)\b",
    r"\b(?:martingale\w*|doubl(?:e|ing) (?:down|up|my (?:bets?|stakes?))) (?:\w+ )?(?:to|until|"
    r"till) (?:recover|get|win|break|make|im even)\b",
)
#: Round five of the review: an amount to win back. "I need to make back $500 tonight",
#: "have to win 2k back". Not "make back 10 points" or "win back 2 games".
_AMOUNT = (
    r"(?:\$\d[\d,]*(?:\.\d+)?k?|\d[\d,]*(?:\.\d+)?(?: ?k\b| (?:dollars|bucks|grand|thousand|"
    r"large)\b)|\d{1,3}(?:,\d{3})+\b|\d{3,}\b|(?:a|one|two|three|four|five|six|seven|eight|nine|"
    r"ten|a couple(?: of)?|a few|couple) (?:grand|thousand|hundred)\b)"
)
#: "about $500", "like 500", "almost 2k".
_ABOUT = r"(?:(?:about|around|like|over|almost|nearly|roughly|close to|at least|more than) )?"
_NOT_A_COUNT = (
    r"(?! (?:points?|pts|yards?|units?|games?|runs?|goals?|wins?|spots?|seats?|sets?|rounds?|"
    r"strokes?|minutes?|mins?|seconds?|hours?|days?|rebounds?|assists?|shots?)\b)"
)
_AMOUNT_BACK_RE = _any(
    rf"\b(?:make|making|win|winning|earn|earning|get|getting|recoup|recouping|recover|"
    rf"recovering) back (?:the |my |that |those |all |all of |all of my )?{_ABOUT}{_AMOUNT}"
    rf"{_NOT_A_COUNT}",
    rf"\b(?:make|making|win|winning|earn|earning|get|getting|need|needs) (?:the |my |that |those |"
    rf"all |all of )?{_ABOUT}{_AMOUNT} back\b",
    rf"\bmake up (?:the |my |that |those )?{_ABOUT}{_AMOUNT}{_NOT_A_COUNT}",
    # "I need to recover $500", with no "back".
    rf"\b(?:recoup|recouping|recover|recovering) (?:the |my |that |those )?{_ABOUT}{_AMOUNT}"
    rf"{_NOT_A_COUNT}",
)
#: Two digits with no sign: "I need to make back 50". Not "get 10 back", and not "the Tides
#: need to make back 21", a deficit in a game (checked in ``_chasing_losses``).
_TWO_DIGITS_BACK_RE = re.compile(
    rf"\b(?:make|making|earn|earning) back (?:the |my |that )?{_ABOUT}\d\d\b(?![.,]\d)"
    rf"{_NOT_A_COUNT}"
)
#: A refund question ("do I get my money back on a push?") is not loss chasing.
_REFUND_RE = re.compile(
    r"\b(?:push(?:es|ed)?|void(?:ed)?|refund(?:ed|s)?|cancel(?:led|ed|s)?|postponed?|"
    r"withdraw(?:al|als)?|cash ?out|abandoned|no action)\b"
)
_GET_BACK_RE = re.compile(
    r"\bget(?:s|ting)? (?:me )?(?:back )?(?:it|my money|the money)(?: back)?\b"
)
#: "Can the Tides win it back in game 7?" and "will the Tides get back to even?" are about
#: a team, not about the writer's money. "What's the play to win it back?" and "I need the
#: Tides to win it back for me" are about the writer.
_ABOUT_A_TEAM_RE = re.compile(
    r"\b(?:win(?:ning)? (?:it|it all|them|that) back|(?:get(?:ting)? back to|back to|"
    r"get(?:ting)?) even)\b"
)
_SOMEONE_ELSE_RE = re.compile(
    r"\b(?:they|he|she|team|the (?!(?:bet|bets|play|pick|move|parlay|way|loss|losses|plan|"
    r"wager|odds|price|line|stake|amount|money|best|right|only|one|chance|time|need|urge|rent|"
    r"bankroll|cash|same|next|last|first)\b)\w+(?: \w+){0,3}) "
    r"(?:(?:can|could|will|would|might|should|to|gonna|going to|ever|really|still) )*$"
    # "Can Dara Okafor win it back?": a question about somebody named.
    r"|\b(?:can|could|will|would|might|should|did|do|does) (?!i\b|we\b|you\b)\w+(?: \w+){0,3} $"
)
_MY_NEED_RE = re.compile(
    r"\b(?:i|we) (?:really |just |desperately )?(?:need|have|got|gotta|want|must)\b|\b(?:me|my)\b"
)

#: What may follow "stop" or "quit" when it is the betting that cannot be stopped: a betting
#: word, or the end of the clause. Not "stop the run" or "stop notifications".
_STOP_TAIL = (
    rf"(?= (?:{_GAMBLING}|gambl\w*|bet\w*|placing|playing|chasing|depositing|my ?self|doing "
    r"(?:it|this)|it\b|this\b)|[.,!?;]|$)"
)
_DISTRESS_RE = _any(
    # Cannot stop.
    rf"\bi (?:just |really |literally |honestly )?(?:{_CANT}|am unable to) (?:seem to )?"
    r"(?:stop|quit|control|help my ?self|walk away)\b"
    r"(?! (?:watching|laughing|smiling|cheering|reading|talking|thinking about (?:that|the)))",
    rf"\b(?:stop|quit) but (?:i )?{_CANT}\b",
    rf"\b(?:tried|trying|try) to (?:quit|stop)(?:{_STOP_TAIL}| (?:and|but|so many|before|"
    r"again|many times|several times|multiple times)\b)",
    rf"\b{_CANT} stay away\b",
    r"\b(?:back to|started|start|end up|ended up|im) (?:betting|gambling) again\b",
    r"\b(?:go|going|went|gone|im) back to (?:betting|gambling)\b",
    r"\bneed to be stopped\b|\b(?:somebody|someone|please) stop me\b",
    rf"\b(?:dont|do not) know how to (?:stop|quit){_STOP_TAIL}",
    rf"\b(?:stop|quit|quitting|stopping|give up|giving up|cut back on|cutting back on|cut down "
    rf"on|(?:a |my )?break from|time off from|time away from|step(?:ping)? (?:away|back) from|"
    rf"walk away from|stay away from) (?:my )?{_GAMBLING}"
    r"\b(?! (?:markets?|lines?|limits?|windows?)\b)",
    r"\bhelp me (?:stop|quit)\b",
    r"\bi think i need help\b|\bi need (?:serious|real|professional) help\b",
    rf"\b(?:need|want|get|getting|find|seeking) help (?:with|for|to stop|stopping|quitting) "
    rf"(?:my |the |this )?(?:{_GAMBLING}|addiction|problem)\b",
    rf"\bi(?:ve| have)? (?:lost|no) control\b|{_IM} (?:losing|out of) control\b",
    rf"\b(?:{_GAMBLING}|gambl\w+|its|it is|this is|things are) (?:(?:is|has|have|getting|"
    r"gotten|got|way|becoming|really) )*out of (?:control|hand)\b",
    r"\bfeel(?:ing)? out of control\b",
    r"\bstop (?:me|my ?self) from\b|\b(?:block|ban|exclude) (?:me|my ?self)\b",
    r"\bhelp ?line\b|\bhotline\b",
    r"\bneed help (?:quitting|stopping)\b",
    r"\b(?:need|want) (?:someone|somebody) to talk to\b|\b(?:need|want) to talk to (?:someone|"
    r"somebody)\b",
    r"\bself[- ]?exclu",
    r"\brelaps",
    r"\bgamblers? anonymous\b",
    r"\bkeep (?:on )?(?:betting|gambling|chasing|depositing)\b"
    r"(?= (?:even|although|though|when|after|despite|anyway|more|and (?:losing|cant))|[.,!?;]|$)",
    r"\b(?:promised|swore|vowed|told my ?self) (?:\w+ ){0,4}?(?:quit|stop|never|last time|no "
    r"more|not (?:to )?(?:bet|gamble))\b",
    r"\bbroke (?:my|a|the) promise\b",
    r"\b(?:one|1) (?:more|last) bet and (?:im|i am|ill) (?:done|out|finished)\b",
    r"\bthink(?:ing)? about (?:betting|gambling) (?:all the time|all day|constantly|non-?stop)\b",
    r"\ball i (?:think about|do|can think about) is (?:bet|betting|gambl\w+)\b",
    rf"\b{_CANT} think about anything (?:but|except|other than)\b",
    r"\bbet(?:ting)? on (?:everything|anything|sports i (?:dont|do not) (?:even )?(?:watch|"
    r"follow|know))\b",
    r"\b(?:betting|gambling) is my (?:only |main |sole )?(?:income|job|way out|way to (?:pay|"
    r"make))\b",
    r"\bquit my job to (?:bet|gamble)\b",
    r"\binstead of paying\b",
    r"\bskip(?:ping|ped)? (?:meals|work|class|school) to (?:bet|gamble)\b",
    r"\b(?:gambl(?:e|ing)|bet|betting|wager(?:ing)?) (?:on \w+ )?(?:every ?day|every single "
    r"day|every night|all day|all night|daily(?! fantasy)|non-?stop|constantly|at work|during "
    r"work)\b",
    # A gambling problem, in any words.
    rf"\b{_GAMBLING} (?:problem|addiction|addict|disorder)\b",
    r"\bproblem gambl",
    r"\bproblem with (?:my |the |this )?(?:gambling|betting|sports betting|wagering)\b"
    r"(?! (?:markets?|lines?|limits?|slips?|history|tracker|page|screen|tab|import|sync|odds|"
    r"board|feed)\b)",
    r"\b(?:my|the|this) (?:gambling|betting|sports betting|wagering) (?:is|has become|is "
    r"becoming|is turning into|became|has turned into|is getting to be) (?:a |an |my |the |such "
    r"a |really a |kind of a )?(?:\w+ )?(?:problem|issue|addiction|sickness|disease)\b",
    rf"\bstruggl\w+ (?:with (?:my |the |this )?(?:{_GAMBLING}|gambl\w+|addiction|debts?)|to "
    r"(?:stop|quit|control|pay))\b",
    r"\bcompulsive(?:ly)? (?:gambl|bett)",
    rf"\bhooked on (?:{_GAMBLING}|gambl\w+|this|it)\b",
    r"\baddict",
    r"\bis (?:my|this) (?:gambling|betting) (?:a|becoming a|turning into a) problem\b",
    r"\bi (?:think i |might |may |probably |really |definitely )?(?:have|ve got|got) a "
    r"(?:gambling |betting |serious |real |bad |big )?problem\b"
    r"(?! (?:with|logging|signing|on the|in the|loading|opening|seeing))",
    # Losses that hurt.
    r"\blost (?:everything|it all|all of it|too much|way too much|so much money|thousands|"
    r"more than i (?:can|could|should))\b(?! in the (?:first|second|third|fourth|1st|2nd|3rd|4th))",
    r"\blost all (?:of )?(?:my|our) (?:money|cash|winnings)\b",
    r"\b(?:lost|losing|lose|blew|blown|blowing|gambled away|gambled|bet|betting|wagered|spent|"
    r"used|using|put|putting|risked|risking|staked|cashed out|cashing out|drained|emptied|wiped "
    r"out|deposited|depositing|deposit|cleaned out|blew through|burned through) (?:all (?:of )?)?"
    r"(?:my|the|our) (?:whole |"
    r"entire |life )?(?:savings|rent|mortgage|paycheck|paycheque|tuition|bankroll|college fund|"
    r"retirement|401k|car payment|student loans?|inheritance|emergency fund|financial aid|"
    r"scholarship|unemployment|disability|pension|social security|tax refund|bank account|"
    r"account)\b(?! (?:settings?|page|screen|details|password|email|name)\b)",
    r"\ball in with (?:my|our) (?:savings|rent|paycheck|retirement|401k)\b",
    r"\b(?:bank )?account is (?:empty|overdrawn|negative|in the red)\b|\boverdr(?:ew|awn|aft)",
    r"\b(?:my|our) (?:money|paycheck|savings|rent) is (?:all )?gone\b",
    r"\b(?:have|got|with|theres) (?:nothing|no money|no cash) left\b",
    rf"{_IM} (?:completely |totally )?out of money\b",
    r"\bno money for (?:food|rent|bills|gas|groceries|my kids)\b",
    rf"\b{_CANT} (?:buy|afford) (?:food|groceries|gas|diapers)\b",
    rf"\b{_CANT} feed (?:my|our|the) (?:kids|family|children)\b",
    r"\bmissed (?:my |the |our |a )?(?:(?:car|rent|mortgage|loan|credit card) )?payments?\b",
    r"\bmissed (?:my |the |our )?rent\b",
    r"\breposs",
    r"\b(?:money|cash|\$?\d[\d,.]*k?(?: dollars| bucks)?) (?:that )?i (?:dont|do not|didnt|did "
    r"not) (?:really )?have\b",
    r"\b(?:money|cash) (?:that )?i need(?:ed)? (?:for|to pay)\b",
    r"\b(?:used?|using|spent|spend|spending|took|taking|blew|lost|bet|betting|gambled|"
    r"gambling) (?:all (?:of )?)?(?:my|our) (?:kids?|childs|childrens|sons|daughters|wifes|"
    r"husbands|familys|parents|moms|mums|dads|partners) (?:\w+ )?(?:fund|tuition|savings|money|"
    r"account|card|inheritance|rent|paycheck|allowance|piggy bank|college)\b",
    r"\blost (?:my|our|the) (?:job|house|car|marriage|family|wife|husband|kids|business)\b",
    r"\b(?:lose|losing) (?:my|our) (?:job|house|home\b(?! (?:opener|game|team|bet|pick|field))|"
    r"car|marriage|family|wife|husband|kids|business|apartment)\b",
    r"\bcost(?:s|ing)? me (?:my (?:marriage|family|job|house|home|savings|relationship|wife|"
    r"husband|kids|friends|life|sanity|health|career|business)|everything)\b",
    # A loss of a thousand or more, in the writer's own words.
    rf"(?:\bi(?:ve| have)? (?:just |already |now )?(?:lost|blew|blown|dropped)|{_IM} (?:now |"
    r"already )?down) (?:over |about |around |almost |nearly |like |more than )?\$?"
    r"(?:\d{1,3},\d{3}|\d{4,}|\d+(?:\.\d+)?k|\d+ (?:grand|thousand))\b"
    r"(?! (?:points?|pts|yards?|units?)\b)",
    r"\b(?:gambl|bett)ing with (?:my|our|the) (?:kids|rent|savings|mortgage|retirement|tuition|"
    r"bill|paycheck|last)",
    r"\b(?:bet|betting|gamble|gambling|spend|spending|staking|wagering)\b(?: \w+){0,3}? (?:too "
    r"much(?! time)|more than i (?:should|can|could|want|meant|planned))\b",
    r"\b(?:rent|mortgage|bill|grocery|tuition) money\b",
    r"\bmore than i (?:can|could) afford\b",
    r"\b(?:losing|lost|lose) everything to (?:betting|gambling|sports betting|bets|the "
    r"sportsbooks?|sportsbooks?)\b",
    r"\bmoney (?:meant |needed |set aside |saved |that was )?for (?:the |my |our )?(?:bills|rent|"
    r"food|groceries|mortgage|kids)\b(?! (?:is|was) (?:safe|paid|covered|fine)\b)",
    r"\bdouble (?:my|the|our) money to (?:pay|cover|make rent|get out)\b",
    # Warning signs RESPONSIBLE_GAMBLING.md section 7 publishes.
    r"\b(?:gambl\w*|bet|bets|betting) to (?:escape|cope|forget|numb|deal with|feel better|get "
    r"away from|feel something)\b",
    r"\b(?:anxious|restless|irritable|on edge|edgy|antsy|agitated) when (?:im |i am |i )?(?:not "
    r"betting|not gambling|cant bet|cant gamble|dont bet|dont gamble|stop betting|try to stop|"
    r"am not betting)\b",
    r"\b(?:missed|miss|missing|skipped|skip|skipping) (?:work|my shift|class|school|my kids|"
    r"family) (?:because of|for|to) (?:betting|gambling|bet|gamble|my bets)\b",
    r"\bcall(?:ed|ing)? (?:in )?sick to (?:bet|gamble|watch my bets)\b",
    # Betting for money that is needed.
    r"\b(?:need|have|got) to make (?:rent|my rent|the rent|my bills|the mortgage|my mortgage|my "
    r"car payment)(?=[.,!?;]|$| (?:by|this|next|tonight|today|on time|or|and|before|until|so|with|"
    r"from)\b)",
    r"\bbet (?:will|would|can|could|to) (?:pay|cover) (?:my|the|our) (?:bills|rent|mortgage|"
    r"debts?|loans?)\b",
    r"\bneed (?:money|cash) (?:fast|quick|quickly|now|today|tonight|asap)\b",
    # A big loss with no "I": "lost 4k today", "down 12k lifetime". Not a year.
    r"(?:^|[.!?;,] )(?:just |already )?(?:lost|down|blew|dropped) (?:over |about |around |almost "
    r"|nearly |like |more than )?(?!(?:19|20)\d\d\b)\$?(?:\d{1,3},\d{3}|\d{4,}|\d+(?:\.\d+)?k|"
    r"\d+ (?:grand|thousand))\b(?! (?:points?|pts|yards?|units?)\b)",
    rf"\b{_CANT} (?:pay|cover|make) (?:(?:my|the|our|this months?|next months?) )?(?:rent|"
    r"bills?|mortgage|debts?)\b",
    r"\bbehind on (?:my |the |our )?(?:rent|bills|mortgage|payments)\b",
    r"\bdebts?\b(?! (?:to|of gratitude)\b)",
    # Not "the best bet to cover the spread" or "to make the playoffs".
    r"\b(?:gambl\w+|bet|betting) to (?:pay|afford|get out of)\b|\b(?:gambl\w+|bet|betting) to "
    r"(?:cover|make) (?:(?:my|our|the|this months?|next months?) )?(?:rent|bills?|mortgage|debts?|"
    r"loans?|losses|car payment|tuition|ends meet|payroll)\b",
    r"\bpay(?:ing)? off (?:my |the |our |this |some )?(?:debts?|loans?|credit cards?|bills|"
    r"mortgage)\b",
    r"\bbankrupt",
    r"\bevict",
    r"\bforeclos",
    r"\bbet (?:it all|everything|(?:the|my|our) house)\b(?! (?:edge|always|wins))",
    r"\bi owe (?:my|a|the|people|everyone|him|her|them|\$?\d|money|so much|too much|thousands)"
    r"(?!.{0,20}\b(?:beer|drink|thank|thanks|apology|favor|favour)\b)",
    # Not "the Tides need a big win".
    r"(?<![a-z]s )\bneed (?:to win big|a big win)\b",
    r"\b(?:i|we) (?:just |only |really )?need one big win\b",
    r"\bone big win (?:and i|to (?:fix|pay|get|make|cover|clear)|would (?:fix|solve|cover))\b",
    r"\bpay (?:everyone|everybody|people|them|him|her|it all) back\b",
    r"\b(?:have|has|need|needs|got) to (?:win|hit|cash)\b.{0,30}?\bor (?:im|i am|i|ill|my|we)\b",
    r"\bmy last (?:\$\d|\d+ ?(?:dollars|bucks)|(?:few |hundred |thousand |couple (?:of )?)?"
    r"(?:dollars?|bucks)|money|paycheck|dime|cent|penny)",
    r"\ball i have left\b|\beverything i have (?:left|on)\b",
    # Borrowed money, or money that was not for betting.
    r"\bborrow(?:ed|ing|s)?(?: (?:money|cash|\$?\d[\d,.]*k?|from|against|more|some|a (?:few|"
    r"couple|lot|bit|grand)|to (?:bet|gamble|cover|pay|keep))\b|(?=[.,!?]|$))",
    r"\b(?:took|take|taking|get|got|getting) (?:out )?(?:a|another|a second|a personal|a title|"
    r"a home equity) (?:payday )?(?:loan|mortgage|line of credit|cash advance)\b",
    r"\b(?:second|2nd|reverse) mortgage\b|\bremortgag",
    r"\bpayday loan",
    r"\bloan shark",
    r"\bmaxed (?:out )?(?:my|the|our|a|another)? ?(?:credit )?cards?\b",
    r"\b(?:credit cards?|overdraft|cash advance|line of credit) (?:to|for) (?:bet|gambl|wager|"
    r"deposit|fund|cover|chase|keep|parlay)",
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
    r"\b(?:wife|husband|partner|girlfriend|boyfriend|fiance|fiancee|spouse|family) (?:left"
    r"(?! (?:the (?:game|room|house|bar|stadium|party)|early|for (?:work|the)|a (?:message|"
    r"note))\b)|is leaving|will leave|is going to leave|threatened to leave|found out|finds "
    r"out|kicked me out)\b",
    r"\b(?:wife|husband|partner|girlfriend|boyfriend|fiance|fiancee|spouse|family|parents|mom|"
    r"mum|dad|kids) (?:has|have) no idea\b",
    r"\b(?:havent|have not|didnt|did not|cant|cannot|never|afraid to|scared to) (?:told|tell) "
    r"(?:my (?:wife|husband|partner|girlfriend|boyfriend|fiance|fiancee|spouse|family|parents|"
    r"mom|mum|dad|kids)|anyone|anybody|her|him|them)\b",
    r"\b(?:nobody|no one) knows (?:how much|about my|that i|i)\b",
    r"\bl(?:ie|ied|ying) about how much\b",
    r"\b(?:gambl\w+|bet|betting) in secret\b|\bsecret(?:ly)? (?:gambl|bett)",
    r"\bso (?:she|he|they|my \w+) (?:wont|doesnt|dont|cant) (?:see|know|find out)\b",
    r"\bdivorce",
    r"\b(?:marriage|family|relationship|life) is falling apart\b",
    r"\b(?:taken|took|takes) everything\b",
    rf"\bl(?:ie|ied|ying) (?:to (?:my|everyone|people)|about (?:my |the )?(?:{_GAMBLING}|losses|"
    r"money))\b",
    rf"\bkeep(?:ing)? (?:it|this|my (?:{_GAMBLING})) (?:a )?secret(?: from\b|(?=[.,!?]|$))",
    r"\bbehind (?:my|her|his|their) (?:wifes |husbands |partners )?back\b",
    # What it is doing to the person.
    rf"\b(?:{_GAMBLING}|losing|losses) (?:is|are|has|have) (?:(?:ruin|destroy|wreck|kill|"
    r"consum|control|hurt|stress)\w* (?:my|me|our)|tak\w* over)\b",
    rf"\b(?:scared|worried|afraid|anxious|stressed|ashamed|embarrassed|guilty|sick|concerned|"
    rf"depressed|upset|miserable|devastated|panicking|panicked|freaking out|crying|terrified) "
    rf"(?:about|of|over|by) (?:how much i|how much im|how much ive|my (?:{_GAMBLING}|losses|"
    rf"debts?)|what i(?:ve| have)? lost|money|(?:{_GAMBLING}|gambl\w+))\b",
    r"\bregret (?:betting|gambling|ever (?:betting|gambling|starting))\b",
    rf"\b(?:{_CANT} sleep|not sleeping|lost sleep|up all night) (?:because of|over|about|"
    rf"thinking about|from) (?:my |the |this )?(?:{_GAMBLING}|losses|loss|debts?|money|bets?)\b",
    r"\bi(?:ve| have)? (?:ruined|destroyed|wrecked|messed up|screwed up) (?:everything|my life|"
    r"it all)\b",
    rf"\b(?:messed|screwed) up (?:\w+ ){{0,3}}?(?:with|by|from|on) (?:{_GAMBLING}|gambl\w+)\b",
    r"\b(?:its|it is|thats|this is) (?:ruin|destroy|wreck)\w* (?:me|my|us|our)\b",
    rf"{_IM} in (?:deep |big |serious |real |so much )?trouble\b",
    rf"\bin over my head\b|{_IM} in (?:way )?too deep\b|{_IM} (?:so )?underwater\b",
    rf"{_IM} (?:over |about |around |almost |nearly |like |more than )?\$?\d[\d,.]*k?(?: "
    r"dollars| bucks| grand| thousand)? (?:deep )?in (?:the|a) hole\b"
    r"(?! (?:on|in) (?:\w+ )?(?:points|units|pts|fantasy|dfs)\b)",
    r"\bdo something (?:stupid|drastic|desperate|i(?:ll| will)? regret)\b",
    r"\bits over for me\b",
    rf"\bi (?:just |really )?{_CANT} do this(?:{_END}| any ?more| alone)",
    r"\b(?:ruin|destroy|wreck)(?:ed|ing|s)? my (?:life|marriage|family|finances|credit|"
    r"relationship)\b",
    rf"(?:{_IM}|\bi feel|\bi felt) (?:so |really |just |completely |totally )?(?:hopeless|"
    r"desperate|worthless|ashamed|ruined|trapped|depressed|guilty|panicking|terrified|drowning|a "
    r"failure|like (?:such )?a (?:failure|loser|fraud)|disgusted with my ?self|sick about)\b",
    rf"{_IM} (?:flat |dead |completely |totally |so )?broke\b",
    r"\bhate (?:my ?self|my life)\b",
    r"\b(?:i|ive|im|we|weve|my|me)(?: \w+){0,4}? rock bottom\b|\brock bottom for me\b",
    r"\bdesperately need\b",
    r"\bon tilt\b",
    rf"\blosing sleep over (?:my |the |this )?(?:{_GAMBLING}|losses|loss|debt)\b",
    rf"\bi {_CANT} (?:afford to )?lose (?:any ?more|another|again|this one|the rent)\b",
    r"\bneed(?:ed)? (?:to win|a win|this (?:one |bet )?to (?:hit|win|cash))\b.{0,40}?\b"
    r"(?:rent|mortgage|pay|debt|or im|or else|or my)\b",
)
#: "I have a problem with gambling" is about the writer; "I have a problem with the app" is
#: about the product and is left to the lookahead in the rule above.
_MY_PROBLEM_RE = re.compile(
    r"\bproblem with (?:my |the |this )?(?:money|debts?|addiction|losing|stopping|chasing)\b"
)
#: "I can't afford this" is the writer; "the Tides can't afford to lose this one" is a team.
_AFFORD_RE = re.compile(
    rf"\b{_CANT} afford\b(?! (?:the |a |to pay for )?(?:premium|plan|subscription|upgrade))"
)
_TEAM_SUBJECT_RE = re.compile(
    r"\b(?:(?:they|he|she|team) |the (?:(?!(?:and|but|so|now|i|we|im)\b)\w+ ){1,4})"
    r"(?:(?:just|really|simply) )?$"
)
#: "... and can't stop", "... but I just can't quit": the subject is earlier in the sentence.
_AND_CANT_STOP_RE = re.compile(
    rf"\b(?:and|but|just|still|simply|really) (?:i )?(?:just |still )?{_CANT} (?:stop|quit)"
    rf"{_STOP_TAIL}"
)
_FIRST_PERSON_RE = re.compile(r"\b(?:i|im|ive|id|ill|we)\b")

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
    r"\b100 ?(?:%|percent) (?:sure (?:thing|bet|win|winner)|certain to|safe|chance|going to|"
    r"win|winner|to (?:win|hit|cash))",
    r"\bcertain (?:to win|winner|win)\b",
    r"\b(?:safe|safest) bets?\b",
    r"\b(?:never|cant|cannot) loses?\b",
    r"\bwin either way\b",
    r"\bdefinitely (?:going to |gonna |will )?(?:win|hit|cash)\b",
    r"\b(?:fixed|rigged) (?:game|match|fight)\b",
    r"\b(?:game|match|fight|games|matches|fights) (?:(?:is|are|was|were|being) )?(?:fixed|"
    r"rigged)\b",
)


def _age(token: str) -> int:
    return int(token) if token.isdigit() else _AGE_WORDS[token.replace("-", " ")]


def _says_under_21(text: str, today: date) -> bool:
    if _UNDERAGE_PHRASE_RE.search(text):
        return True
    for pattern, limit in ((_AGE_NOW_RE, 20), (_AGE_AHEAD_RE, 21)):
        for match in pattern.finditer(text):
            token = next(group for group in match.groups() if group is not None)
            # Nobody younger than ten is typing here; a smaller number is something else.
            if 10 <= _age(token) <= limit:
                return True
    # Twenty or younger whatever the birthday; a year that leaves it open is not used.
    return any(10 <= today.year - int(born.group(1)) <= 20 for born in _BORN_RE.finditer(text))


def _in_crisis(text: str) -> bool:
    if _CRISIS_RE.search(text) or _NO_POINT_RE.search(text):
        return True
    for match in _NO_SUBJECT_CRISIS_RE.finditer(text):
        clause = re.split(r"[.!?;,] ", text[: match.start()])[-1]
        if not _SUBJECT_BEFORE_RE.search(clause):
            return True
    return False


def _chasing_losses(text: str) -> bool:
    for match in _AMOUNT_BACK_RE.finditer(text):
        # "do I get $50 back on a push?" is a refund question.
        if not (match.group(0).startswith(("get", "need")) and _REFUND_RE.search(text)):
            return True
    for match in _TWO_DIGITS_BACK_RE.finditer(text):
        if not _SOMEONE_ELSE_RE.search(text[: match.start()]):
            return True
    for match in _CHASING_RE.finditer(text):
        found, before = match.group(0), text[: match.start()]
        if _GET_BACK_RE.fullmatch(found) and _REFUND_RE.search(text):
            continue
        if (
            _ABOUT_A_TEAM_RE.fullmatch(found)
            and _SOMEONE_ELSE_RE.search(before)
            and not _MY_NEED_RE.search(before)
        ):
            continue
        return True
    return False


def _in_distress(text: str) -> bool:
    if _DISTRESS_RE.search(text) or _MY_PROBLEM_RE.search(text):
        return True
    for match in _AFFORD_RE.finditer(text):
        if not _TEAM_SUBJECT_RE.search(text[: match.start()]):
            return True
    for match in _AND_CANT_STOP_RE.finditer(text):
        sentence = re.split(r"[.!?;] ", text[: match.start()])[-1]
        if _FIRST_PERSON_RE.search(sentence):
            return True
    return False


def detect(message: str, today: date | None = None) -> Signals:
    """Every group of patterns ``message`` matches. Deterministic.

    ``today`` is only used to turn "I was born in 2009" into an age; it defaults to the
    current date.
    """
    text = normalise(message)
    chasing = _chasing_losses(text)
    return Signals(
        crisis=_in_crisis(text),
        underage=_says_under_21(text, today or datetime.now(UTC).date()),
        distress=chasing or _in_distress(text),
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


#: The sentence that ends every answer that is not a support reply: ordinary answers, the
#: fallback, the refusal below and every "couldn't find" answer. The rules above are a fixed
#: list and miss some wordings; a message they miss still gets the helpline and the crisis
#: line in the answer itself. Support replies keep their own wording and do not get it.
HELP_SENTENCE = (
    f"If gambling is causing problems, call the {HELPLINE_NAME} at {HELPLINE_NUMBER} "
    f"({HELPLINE_DIGITS}) or text {HELPLINE_TEXT_CODE}; in a crisis, call or text {CRISIS_LINE} "
    f"(the {CRISIS_LINE_NAME})."
)

#: Kept next to the support wording because the same review covers it.
NO_CERTAINTY_REPLY = (
    "I can't answer that with a pick. No result in sports is certain, and I don't make picks "
    "or predictions. I can show market data instead: the best current price for a team, a "
    "player's recent prop results, line movement, or EV and no-vig math."
)

__all__ = [
    "HELP_SENTENCE",
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
