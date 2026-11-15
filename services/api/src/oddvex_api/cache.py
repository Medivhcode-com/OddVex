"""Tiny cache abstraction so Redis can be slotted in later."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, Protocol


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: float) -> None: ...

    def delete(self, key: str) -> None: ...

    def clear(self) -> None: ...


class InMemoryTTLCache:
    """Process-local TTL cache. Thread-safe, bounded, not shared between workers."""

    def __init__(
        self, max_entries: int = 2048, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= self._clock():
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            return
        with self._lock:
            now = self._clock()
            if len(self._data) >= self._max_entries:
                expired = [k for k, (exp, _) in self._data.items() if exp <= now]
                for k in expired:
                    del self._data[k]
                while len(self._data) >= self._max_entries:
                    del self._data[next(iter(self._data))]
            self._data[key] = (now + ttl_seconds, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


def cached[T](cache: Cache, key: str, ttl_seconds: float, compute: Callable[[], T]) -> T:
    """Return the cached value for ``key`` or compute and store it."""
    hit = cache.get(key)
    if hit is not None:
        return hit  # type: ignore[no-any-return]
    value = compute()
    cache.set(key, value, ttl_seconds)
    return value
