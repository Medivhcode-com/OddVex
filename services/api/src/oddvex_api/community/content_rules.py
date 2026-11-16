"""Automatic content rules for user text in the community. Pure: no I/O.

Every piece of free text a user can publish (pick analysis, comment, bio) goes through
:func:`check_text` before it is stored. The rules are deliberately blunt: they match
phrases, not intent. A match rejects the text and names the rule, so the author can
reword it. They are a first filter in front of reports and moderators, not a replacement
for them, and spelling tricks (``g.u.a.r.a.n.t.e.e.d``) get past them.

Three groups:

* links (``links_not_allowed``): no URLs at all, which removes most spam and every
  affiliate link;
* guaranteed-outcome and inducement language (PROJECT_CONSTITUTION §2,
  BRAND_VOICE BC-01, BC-02, BC-06, BC-07);
* selling picks and contact solicitation: payment and messaging apps, promo codes, phone
  numbers and email addresses.

Add a rule here and nowhere else, with a true positive and a near miss in
``tests/test_community_content_rules.py``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: ``http://``, ``https://`` or ``www.`` anywhere in the text.
_LINK = re.compile(r"https?://|\bwww\.", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ContentRule:
    key: str
    #: Shown to the author when the rule matches.
    message: str
    pattern: re.Pattern[str]


def _rule(key: str, message: str, pattern: str) -> ContentRule:
    return ContentRule(key, message, re.compile(pattern))


_GUARANTEE = "Do not present a result as certain. No outcome is guaranteed."
_INDUCEMENT = "Do not push other people to bet, to bet more or to win money back."
_SELLING = "Selling picks, promotions and payment or contact details are not allowed here."
_CONTACT = "Do not post contact details or ask people to contact you elsewhere."

#: Matched against the normalised text (see :func:`normalise`): lower-case, straight
#: apostrophes, single spaces. ``\b`` keeps "locker room" and "unlock" out of "lock".
RULES: tuple[ContentRule, ...] = (
    # ---- guaranteed outcomes (BC-01, BC-02)
    _rule("guaranteed_outcome", _GUARANTEE, r"\bguarantee(?:d|s)?\b"),
    _rule("guaranteed_outcome", _GUARANTEE, r"\block of the\b"),
    _rule("guaranteed_outcome", _GUARANTEE, r"\b(?:can'?t|cannot|can not) (?:lose|miss)\b"),
    _rule("guaranteed_outcome", _GUARANTEE, r"\bsure thing\b"),
    _rule("guaranteed_outcome", _GUARANTEE, r"\brisk[ -]?free\b"),
    _rule("guaranteed_outcome", _GUARANTEE, r"\bfree money\b"),
    # ---- inducement to bet, bet big or chase (BC-06, BC-07)
    _rule("inducement_to_bet", _INDUCEMENT, r"\bbet the (?:house|farm|mortgage|rent)\b"),
    _rule("inducement_to_bet", _INDUCEMENT, r"\bmax(?:imum)? bet\b"),
    _rule(
        "inducement_to_bet",
        _INDUCEMENT,
        r"\bchas(?:e|es|ed|ing)\b.*\bloss(?:es)?\b|\bloss(?:es)?\b.*\bchas(?:e|es|ed|ing)\b",
    ),
    _rule("inducement_to_bet", _INDUCEMENT, r"\bwin it (?:all )?back\b"),
    # ---- selling picks, promotions, payment apps
    _rule("selling_or_promotion", _SELLING, r"\bpromo(?:tional)? codes?\b"),
    _rule("selling_or_promotion", _SELLING, r"\bsign[ -]?up bonus(?:es)?\b"),
    _rule("selling_or_promotion", _SELLING, r"\bcash ?app\b"),
    _rule("selling_or_promotion", _SELLING, r"\bvenmo\b"),
    _rule("selling_or_promotion", _SELLING, r"\bpaypal\b"),
    # ---- contact solicitation and personal contact details
    _rule("contact_solicitation", _CONTACT, r"\bdm me\b"),
    _rule("contact_solicitation", _CONTACT, r"\btelegram\b"),
    _rule("contact_solicitation", _CONTACT, r"\bwhats ?app\b"),
    # An email address: something@something.tld
    _rule("contact_details", _CONTACT, r"[^\s@]+@[^\s@]+\.[a-z]{2,}"),
    # A phone number: 7 or more digits in a row, a US-style 3-3-4 number, or an
    # international number that starts with "+". Scores ("112-108"), lines ("224.5"),
    # seasons ("2025-26") and prices ("+150") have too few digits to match.
    _rule(
        "contact_details",
        _CONTACT,
        r"(?<!\d)\d{7,}(?!\d)"
        r"|(?<![\d.])\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)"
        r"|\+\d{1,3}[ .-]?(?:\d[ .-]?){7,}",
    ),
)

RULE_KEYS: tuple[str, ...] = tuple(dict.fromkeys(rule.key for rule in RULES))


@dataclass(frozen=True, slots=True)
class Violation:
    #: ``links_not_allowed`` or ``content_not_allowed``: the API error code.
    code: str
    #: ``links`` or one of :data:`RULE_KEYS`.
    rule: str
    message: str


#: Curly and modifier apostrophes become "'", typographic dashes become "-".
_FOLD_PUNCTUATION = str.maketrans(
    {
        **{chr(code): "'" for code in (0x2018, 0x2019, 0x02BC, 0x0060, 0x00B4)},
        **{chr(code): "-" for code in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014)},
    }
)


def normalise(text: str) -> str:
    """Lower-case, compatibility-normalised text with straight apostrophes, plain hyphens
    and single spaces, so a rule sees one spelling whatever the typography or the case."""
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_FOLD_PUNCTUATION)
    return " ".join(folded.split())


def contains_link(text: str) -> bool:
    return _LINK.search(unicodedata.normalize("NFKC", text)) is not None


def check_text(text: str | None) -> Violation | None:
    """The first rule ``text`` breaks, or ``None`` when it is acceptable.

    Links are checked first and reported as ``links_not_allowed``; everything else is
    ``content_not_allowed`` with the rule that matched.
    """
    if not text:
        return None
    if contains_link(text):
        return Violation("links_not_allowed", "links", "Links are not allowed here.")
    normalised = normalise(text)
    for rule in RULES:
        if rule.pattern.search(normalised):
            return Violation("content_not_allowed", rule.key, rule.message)
    return None
