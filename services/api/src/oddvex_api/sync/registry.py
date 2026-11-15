from __future__ import annotations

from .base import SyncProvider
from .mock import MockSyncProvider


class SyncRegistry:
    def __init__(self, providers: list[SyncProvider]) -> None:
        self._providers = {p.info.key: p for p in providers}

    def list(self) -> list[SyncProvider]:
        return list(self._providers.values())

    def get(self, key: str) -> SyncProvider | None:
        return self._providers.get(key)


def default_registry() -> SyncRegistry:
    return SyncRegistry([MockSyncProvider()])
