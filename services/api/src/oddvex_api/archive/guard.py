"""The append-only rule of the snapshot archive, enforced on every ORM flush.

No code path updates an archive row. A ``before_flush`` listener on every SQLAlchemy
session refuses a flush that would update or delete an archive model instance. The only
deletions are the retention prune's bulk ``DELETE`` statements (``archive/prune.py``),
which do not go through the unit of work.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from ..db import ARCHIVE_MODELS


class ArchiveIsAppendOnly(RuntimeError):
    """An archive row was changed or deleted through the ORM."""


def _refuse_changes(session: Session, _context: Any, _instances: Any) -> None:
    for instance in session.deleted:
        if isinstance(instance, ARCHIVE_MODELS):
            raise ArchiveIsAppendOnly(
                f"{type(instance).__name__} rows are append-only; only the retention "
                "prune deletes them"
            )
    for instance in session.dirty:
        if isinstance(instance, ARCHIVE_MODELS) and session.is_modified(instance):
            raise ArchiveIsAppendOnly(f"{type(instance).__name__} rows are append-only")


def install_archive_guard() -> None:
    """Install the listener on every session. Safe to call more than once."""
    if not event.contains(Session, "before_flush", _refuse_changes):
        event.listen(Session, "before_flush", _refuse_changes)
