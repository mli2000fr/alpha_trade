"""Compteurs de télémétrie pour les clients HTTP du module ``service``.

Phase 2.3 du refactor (`prompt/refactor/plan.md`, audit_service §observabilité).

Compteurs en mémoire processus, sans dépendance externe (pas de
Prometheus / OpenTelemetry à ce stade ; cf. Phase 7 pour le dashboard).

Usage :

    from service._telemetry import bump, get_telemetry

    bump("alpaca", "requests_total")
    bump("alpaca", "5xx_total")
    snapshot = get_telemetry("alpaca")  # -> dict
"""
from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Mapping

_LOCK = Lock()
_COUNTERS: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

#: Métriques standard publiées par ``request_with_retry`` (cf. wrapper
#: dans ``service/_http_retry.py`` ou les call-sites clients).
STANDARD_METRICS: tuple[str, ...] = (
    "requests_total",
    "success_total",
    "retry_total",
    "429_total",
    "5xx_total",
    "circuit_open_total",
    "timeout_total",
)


def bump(client: str, metric: str, *, by: int = 1) -> None:
    """Incrémente atomiquement ``counters[client][metric]`` de ``by``."""
    if not client or not metric:
        return
    with _LOCK:
        _COUNTERS[client][metric] += int(by)


def get_telemetry(client: str | None = None) -> Mapping[str, Mapping[str, int]] | Mapping[str, int]:
    """Retourne un snapshot immuable.

    - Si ``client`` est ``None`` : ``{client: {metric: value}}`` global.
    - Sinon : ``{metric: value}`` pour le client demandé.
    """
    with _LOCK:
        if client is None:
            return {c: dict(metrics) for c, metrics in _COUNTERS.items()}
        return dict(_COUNTERS.get(client, {}))


def reset_telemetry() -> None:
    """Réinitialise tous les compteurs (utile en fixtures pytest)."""
    with _LOCK:
        _COUNTERS.clear()


__all__ = ["STANDARD_METRICS", "bump", "get_telemetry", "reset_telemetry"]

