"""The community guidelines: one source of truth for every client.

Wording follows docs/compliance/RESPONSIBLE_GAMBLING.md (the community row of the product
commitments) and docs/marketing/BRAND_VOICE.md. It is a product draft: the public wording
needs the same counsel review as the other policy pages before the flag is turned on.
"""

from __future__ import annotations

GUIDELINES_VERSION = "2026-11-16"

INTRO = (
    "The community is for discussing research. Picks are structured, posted before the "
    "game and graded automatically from the final score."
)

#: (key, title, text). The keys are stable; clients may use them for icons or anchors.
RULES: tuple[tuple[str, str, str], ...] = (
    (
        "be_civil",
        "Be civil",
        "Discuss the pick, not the person. No harassment, no hate speech and no mocking "
        "of anyone's losses.",
    ),
    (
        "no_guarantees_or_inducements",
        "No guarantees and no pressure to bet",
        "Do not present any result as certain or without risk, and do not push anyone to "
        "bet, to bet more or to win money back.",
    ),
    (
        "no_selling_or_links",
        "No selling picks and no links",
        "No paid picks, promotions, promo codes, affiliate offers or links of any kind. "
        "Do not ask people to contact you elsewhere.",
    ),
    (
        "no_personal_information",
        "No personal information",
        "Do not post phone numbers, email addresses, payment details or anything else "
        "that identifies you or another person.",
    ),
    (
        "adults_only",
        "21 and over only",
        "OddVex is for adults aged 21 or older. Accounts identified as under 21 are closed.",
    ),
    (
        "opinions_not_advice",
        "Picks are opinions, not advice",
        "A pick is one person's opinion about a game. It is not betting advice and not a "
        "prediction from OddVex. A record describes past picks and does not predict "
        "future ones.",
    ),
)

ENFORCEMENT = (
    "Text that breaks these rules can be rejected automatically. Anyone can report a "
    "pick, a comment or a profile. Moderators can hide or remove content and suspend "
    "accounts."
)

HELP = (
    "21+. OddVex does not accept wagers. Gambling problem? Call 1-800-GAMBLER. Free, "
    "confidential help is available."
)

#: Shown wherever a record or a ranking appears.
RECORD_CAVEAT = (
    "A record describes picks that were already graded. Past results do not predict future results."
)

LEADERBOARD_CAVEAT = (
    "This ranking describes graded picks from the past. Past results do not predict "
    "future results, a ranking is not a recommendation to follow anyone's picks, and "
    "sports betting involves risk of financial loss."
)

LEADERBOARD_METHOD = (
    "Profiles with at least {minimum} graded picks in the window, ordered by the lower "
    "bound of the Wilson 95% interval of their win rate (wins divided by wins plus "
    "losses). The lower bound is used instead of the raw win rate so that a small "
    "sample cannot rank first, and return on stake is not used for ranking at all."
)

#: What an author sees in place of their own text after a moderator hid or removed it.
MODERATED_PLACEHOLDER = "Removed by moderators."
