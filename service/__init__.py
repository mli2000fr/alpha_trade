"""Package ``service`` — clients HTTP unifiés (Alpaca, Finnhub, news...).

Phase 2.3 du refactor (`prompt/refactor/plan.md`).

Re-exporte les utilitaires transverses pour faciliter l'import :

    from service import (
        RetryPolicy, CircuitBreaker, request_with_retry,
        get_telemetry, bump,
    )
"""
from __future__ import annotations

from service._http_retry import (
    DEFAULT_CIRCUIT_BREAKER,
    CircuitBreaker,
    CircuitOpenError,
    RetryPolicy,
    request_with_retry,
)
from service._telemetry import bump, get_telemetry, reset_telemetry

__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "DEFAULT_CIRCUIT_BREAKER",
    "RetryPolicy",
    "bump",
    "get_telemetry",
    "request_with_retry",
    "reset_telemetry",
]

