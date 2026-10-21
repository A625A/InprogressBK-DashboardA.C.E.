"""Process-local cache for validated dashboard aggregates only."""

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Literal

from fastapi import Request

from app.schemas.dashboard import MonthlyValues, TopFive, Totals

Endpoint = Literal["totals", "top-5", "valor-por-mes"]
KPIValue = Totals | TopFive | MonthlyValues
CacheKey = tuple[Endpoint, tuple[tuple[str, int], ...]]


@dataclass
class Entry:
    value: KPIValue
    expires_at: float


class DashboardCache:
    def __init__(self, ttl_seconds: float, *, clock: Callable[[], float] = monotonic):
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[CacheKey, Entry] = {}
        self._generation = 0
        self._lock = Lock()

    def get_or_load[T: KPIValue](
        self, endpoint: Endpoint, loader: Callable[[], T], **parameters: int
    ) -> T:
        # Callers pass only validated KPI parameters, never raw requests or JWTs.
        key = (endpoint, tuple(sorted(parameters.items())))
        with self._lock:
            now = self._clock()
            self._entries = {
                key: entry for key, entry in self._entries.items() if entry.expires_at > now
            }
            if key in self._entries:
                return self._entries[key].value.model_copy(deep=True)
            generation = self._generation

        # Exceptions propagate without being cached. Do not lock during SQL work.
        value = loader()
        with self._lock:
            # A concurrent COMMIT must not let an older read repopulate the cache.
            if generation == self._generation:
                # Bound memory even if clients request many different years.
                if len(self._entries) >= 256:
                    del self._entries[next(iter(self._entries))]
                self._entries[key] = Entry(
                    value.model_copy(deep=True), self._clock() + self._ttl_seconds
                )
        return value

    def invalidate_policy(self, year: int | None) -> None:
        with self._lock:
            self._generation += 1
            self._entries.pop(("totals", ()), None)
            self._entries.pop(("top-5", ()), None)
            if year is not None:
                self._entries.pop(("valor-por-mes", (("year", year),)), None)


def get_dashboard_cache(request: Request) -> DashboardCache:
    return request.app.state.dashboard_cache
