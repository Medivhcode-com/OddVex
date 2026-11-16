"""Case-insensitive text keys computed in Python, the same way on every database.

``lower()`` in SQL only folds ASCII on SQLite and on PostgreSQL with the ``C`` locale, so
"ÉCLAIR" and "éclair" would not match there. Anything that has to be compared without
regard to case is folded here instead, stored next to the original value and compared as
plain text.
"""

from __future__ import annotations

import unicodedata


def fold(value: str | None) -> str:
    """A caseless key: NFKC, ``str.casefold()``, NFKC again, whitespace collapsed.

    The second normalisation is needed because case folding can produce characters that
    are not in normal form. The result is stable: ``fold(fold(x)) == fold(x)``.
    """
    if not value:
        return ""
    folded = unicodedata.normalize("NFKC", unicodedata.normalize("NFKC", value).casefold())
    return " ".join(folded.split())


def user_search_key(email: str | None, display_name: str | None) -> str:
    """What the admin user search matches against: folded email and display name, on two
    lines so that a search term can never match across the two."""
    return f"{fold(email)}\n{fold(display_name)}"
