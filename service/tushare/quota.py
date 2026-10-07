from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from service.tushare.errors import TushareQuotaError


class QuotaBudget:
    """Budget local borné par minute et par run, indépendant des points Tushare."""

    def __init__(
        self,
        *,
        max_calls_per_minute: int = 180,
        max_calls_per_run: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_calls_per_minute = max(1, int(max_calls_per_minute))
        self.max_calls_per_run = max(1, int(max_calls_per_run))
        self._clock = clock
        self._sleeper = sleeper
        self._recent: deque[float] = deque()
        self._calls = 0
        self._lock = threading.Lock()

    @property
    def calls(self) -> int:
        return self._calls

    def acquire(self) -> None:
        with self._lock:
            if self._calls >= self.max_calls_per_run:
                raise TushareQuotaError(
                    f"Budget du run atteint : {self._calls}/{self.max_calls_per_run} appels"
                )
            now = self._clock()
            while self._recent and now - self._recent[0] >= 60.0:
                self._recent.popleft()
            if len(self._recent) >= self.max_calls_per_minute:
                wait = max(0.0, 60.0 - (now - self._recent[0]))
                self._sleeper(wait)
                now = self._clock()
                while self._recent and now - self._recent[0] >= 60.0:
                    self._recent.popleft()
            self._recent.append(now)
            self._calls += 1


__all__ = ["QuotaBudget"]
