"""In-process summary cache. TTL comes from settings; writes discard the entry."""

from __future__ import annotations

import copy
import time
from typing import Any, Callable

from utility_assets.config import get_settings

SUMMARY_CACHE_KEY = "reports.summary"


class InMemoryTtlCache:
    """Single-process dict with a wall-clock TTL. Tests may replace `clock`."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self.clock = clock or time.monotonic
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if self.clock() >= expires_at:
            self._store.pop(key, None)
            return None
        return copy.deepcopy(value)

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        ttl = (
            get_settings().summary_cache_ttl_seconds
            if ttl_seconds is None
            else ttl_seconds
        )
        if ttl <= 0:
            return
        self._store[key] = (self.clock() + float(ttl), copy.deepcopy(value))

    def invalidate(self, key: str | None = None) -> None:
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)


summary_cache = InMemoryTtlCache()


def invalidate_summary_cache() -> None:
    """Drop the cached summary so the next read rebuilds from the database."""
    summary_cache.invalidate(SUMMARY_CACHE_KEY)
