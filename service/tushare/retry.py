from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import requests

from service.tushare.errors import TushareQuotaError, TushareResponseError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 4
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 15.0


def with_retry[T](
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    sleeper: Callable[[float], None] = time.sleep,
) -> T:
    last_error: Exception | None = None
    for attempt in range(max(1, policy.attempts)):
        try:
            return operation()
        except (requests.Timeout, requests.ConnectionError, TushareQuotaError) as exc:
            last_error = exc
            if attempt + 1 >= policy.attempts:
                break
            delay = min(policy.max_delay_seconds, policy.base_delay_seconds * (2**attempt))
            sleeper(delay)
    if isinstance(last_error, TushareQuotaError):
        raise last_error
    raise TushareResponseError(f"Tushare indisponible après retry : {last_error}") from last_error


__all__ = ["RetryPolicy", "with_retry"]
