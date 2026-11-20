"""Structured JSON logging.

A failed database statement is logged without what was bound to it. The engines hide
the parameter list (``db/session.py``), and the tracebacks written here leave out the
message of every exception in a chain that contains a database error: the driver's own
text can name a key value (``Key (email)=(...) already exists``) or a whole row
(``Failing row contains (...)``, password hash included). What stays is each
exception's class, where it was raised, the SQLSTATE, the table, column and constraint
names the driver reports, and the statement with its placeholders.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import UTC, datetime
from types import TracebackType
from typing import Any

from sqlalchemy.exc import StatementError

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}

#: Top-level packages of database drivers. Their errors carry text from the database.
_DRIVER_PACKAGES = frozenset({"psycopg", "psycopg2", "psycopg_pool", "sqlite3", "asyncpg"})
#: Names the driver reports about a failed statement (psycopg ``Diagnostic``). They are
#: identifiers from the schema, never values.
_DIAGNOSTIC_NAMES = ("schema_name", "table_name", "column_name", "constraint_name")
_WITHHELD = "message withheld (database error in this chain)"
_STATEMENT_LIMIT = 500


def _class_name(exc: BaseException) -> str:
    cls = type(exc)
    if cls.__module__ == "builtins":
        return cls.__qualname__
    return f"{cls.__module__}.{cls.__qualname__}"


def _is_database_error(exc: BaseException) -> bool:
    return (
        isinstance(exc, StatementError)
        or type(exc).__module__.partition(".")[0] in _DRIVER_PACKAGES
    )


def _chain(exc: BaseException) -> list[BaseException]:
    """``exc`` and the exceptions it was raised from or during, the first raised last,
    following the links the standard traceback follows. A group's members are added."""
    found: list[BaseException] = []
    seen: set[int] = set()
    pending = [exc]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        found.append(current)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        elif current.__context__ is not None and not current.__suppress_context__:
            pending.append(current.__context__)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(current.exceptions)
    return found


def _database_facts(exc: BaseException) -> list[str]:
    """What may be said about a database error: codes and names, no text from the data."""
    facts: list[str] = []
    driver_error = getattr(exc, "orig", None) if isinstance(exc, StatementError) else exc
    if driver_error is not None and driver_error is not exc:
        facts.append(f"({_class_name(driver_error)})")
    sqlstate = getattr(driver_error, "sqlstate", None) or getattr(driver_error, "pgcode", None)
    if isinstance(sqlstate, str) and sqlstate.isalnum():
        facts.append(f"SQLSTATE {sqlstate}")
    diagnostics = getattr(driver_error, "diag", None)
    for name in _DIAGNOSTIC_NAMES:
        value = getattr(diagnostics, name, None)
        if isinstance(value, str) and value:
            facts.append(f"{name}={value}")
    statement = getattr(exc, "statement", None) if isinstance(exc, StatementError) else None
    if isinstance(statement, str) and statement:
        shown = " ".join(statement.split())
        if len(shown) > _STATEMENT_LIMIT:
            shown = shown[:_STATEMENT_LIMIT] + " ..."
        facts.append(f"[SQL: {shown}]")
    return facts


def _withheld_line(exc: BaseException) -> str:
    facts = _database_facts(exc) if _is_database_error(exc) else []
    return f"{_class_name(exc)}: {' '.join([*facts, _WITHHELD])}"


def _render(exc: BaseException, seen: set[int], indent: str = "") -> list[str]:
    """The traceback of ``exc`` and its chain in the standard order, messages withheld."""
    links: list[tuple[BaseException, str]] = []
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if current.__cause__ is not None:
            links.append((current, "The above exception was the direct cause of the following"))
            current = current.__cause__
        elif current.__context__ is not None and not current.__suppress_context__:
            links.append((current, "During handling of the above exception, another"))
            current = current.__context__
        else:
            links.append((current, ""))
            current = None
    lines: list[str] = []
    for position, (link, _) in enumerate(reversed(links)):
        if position:
            # The sentence belongs to the link that points at the exception shown before.
            sentence = links[len(links) - position - 1][1]
            suffix = " exception:" if sentence.endswith("following") else " exception occurred:"
            lines.append(f"\n{indent}{sentence}{suffix}\n")
        trace: TracebackType | None = link.__traceback__
        if trace is not None:
            lines.append(f"{indent}Traceback (most recent call last):")
            for frame in traceback.format_tb(trace):
                lines.extend(indent + row for row in frame.rstrip("\n").split("\n"))
        lines.append(indent + _withheld_line(link))
        if isinstance(link, BaseExceptionGroup):
            for number, member in enumerate(link.exceptions, start=1):
                lines.append(f"{indent}  Member {number} of the group:")
                lines.extend(_render(member, seen, indent + "    "))
    return lines


def database_safe_traceback(exc: BaseException) -> str | None:
    """The traceback of ``exc`` for the log when a database error is anywhere in its
    chain, else None (the standard traceback is then fine).

    Every exception of the chain is named with the place it was raised, like the
    standard traceback, but no exception's message is printed: a wrapper often repeats
    the text of what it wraps. Database errors get their codes and names instead.
    """
    if not any(_is_database_error(link) for link in _chain(exc)):
        return None
    return "\n".join(_render(exc, set()))


class DatabaseErrorFilter(logging.Filter):
    """Gives a record whose exception involves a database error its safe traceback.

    The standard formatter prints ``exc_text`` when it is already set, so this works
    with any formatter. It is put on uvicorn's error logger, which writes the errors
    that get past the application: a failed batch of a streamed response, a background
    task.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        if exc is not None and not record.exc_text:
            safe = database_safe_traceback(exc)
            if safe is not None:
                record.exc_text = safe
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

    def formatException(self, ei: Any) -> str:
        exc = ei[1] if isinstance(ei, tuple) else None
        safe = database_safe_traceback(exc) if isinstance(exc, BaseException) else None
        return safe if safe is not None else super().formatException(ei)


def configure_logging(level: str = "INFO") -> None:
    server_errors = logging.getLogger("uvicorn.error")
    if not any(isinstance(f, DatabaseErrorFilter) for f in server_errors.filters):
        server_errors.addFilter(DatabaseErrorFilter())
    root = logging.getLogger("oddvex")
    if any(getattr(h, "_oddvex", False) for h in root.handlers):
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._oddvex = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level.upper())
    root.propagate = False
