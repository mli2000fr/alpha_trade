"""Phase 7.5 — Métriques Prometheus minimales (audit_global §7.5).

Module **opt-in** : la dépendance ``prometheus_client`` est dans l'extra
``[observability]`` du ``pyproject.toml``. Si elle est absente, les helpers
deviennent des no-op pour ne pas casser les CLI batch standards.

Usage type :

    from core.metrics import (
        run_summary_total,
        watcher_heartbeat_age_seconds,
        start_metrics_server,
    )

    run_summary_total.labels(module="risk_management", status="OK").inc()
    start_metrics_server(port=9100)  # daemons uniquement (watcher, IHM)

Les CLI batch courts peuvent utiliser ``push_to_gateway`` (cf. doc).
"""
from __future__ import annotations

import logging
import os
from typing import Any

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - importé dynamiquement, testé via mock dans tests/
    from prometheus_client import (  # type: ignore[import-not-found]
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        REGISTRY,
        start_http_server,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback no-op
    _PROMETHEUS_AVAILABLE = False
    CollectorRegistry = object  # type: ignore[assignment,misc]
    REGISTRY = None  # type: ignore[assignment]

    class _NoopMetric:
        def labels(self, *_args: Any, **_kwargs: Any) -> "_NoopMetric":
            return self

        def inc(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def dec(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def set(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def observe(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    def Counter(*_args: Any, **_kwargs: Any) -> _NoopMetric:  # type: ignore[no-redef]
        return _NoopMetric()

    def Gauge(*_args: Any, **_kwargs: Any) -> _NoopMetric:  # type: ignore[no-redef]
        return _NoopMetric()

    def Histogram(*_args: Any, **_kwargs: Any) -> _NoopMetric:  # type: ignore[no-redef]
        return _NoopMetric()

    def start_http_server(*_args: Any, **_kwargs: Any) -> None:  # type: ignore[no-redef]
        LOGGER.warning("prometheus_client absent : start_metrics_server() est no-op.")


def is_available() -> bool:
    """Retourne True si ``prometheus_client`` est installé."""
    return _PROMETHEUS_AVAILABLE


# ---------------------------------------------------------------------------
# Métriques canoniques (registry par défaut Prometheus)
# ---------------------------------------------------------------------------

run_summary_total = Counter(
    "alpha_trade_run_summary_total",
    "Nombre de run_summary publiés, ventilé par module et statut.",
    labelnames=("module", "status"),
)

data_freshness_hours = Gauge(
    "alpha_trade_data_freshness_hours",
    "Âge (heures) des dernières données par table.",
    labelnames=("table",),
)

iex_stale_quote_pct = Gauge(
    "alpha_trade_iex_stale_quote_pct",
    "Pourcentage de quotes considérées stale (audit IEX).",
)

iex_zero_volume_count = Gauge(
    "alpha_trade_iex_zero_volume_count",
    "Nombre de symboles à volume zéro sur 30j (audit IEX).",
)

watcher_heartbeat_age_seconds = Gauge(
    "alpha_trade_watcher_heartbeat_age_seconds",
    "Âge (secondes) du dernier heartbeat watcher par compte.",
    labelnames=("account_id",),
)

ml_drift_status = Gauge(
    "alpha_trade_ml_drift_status",
    "État du drift monitoring ML (0=OK, 1=WARN, 2=ALERT).",
    labelnames=("model_id",),
)


_SERVER_STARTED = False


def start_metrics_server(port: int | None = None, *, addr: str = "0.0.0.0") -> bool:
    """Démarre l'endpoint HTTP ``/metrics`` (idempotent).

    - ``port`` : si ``None``, lit ``ALPHA_TRADE_METRICS_PORT`` (env). Si l'env
      est lui-même vide ou non numérique, ne fait rien (opt-in strict).
    - ``addr`` : adresse de bind. **Garder ``localhost``** en prod si IHM
      exposée hors VPN (cf. ``doc/ihm.md`` §sécurité).
    - Idempotent : un second appel ne tente pas de re-binder.

    Retourne ``True`` si le serveur a été démarré (ou l'était déjà).
    """
    global _SERVER_STARTED
    if _SERVER_STARTED:
        return True
    if port is None:
        env_port = os.environ.get("ALPHA_TRADE_METRICS_PORT", "").strip()
        if not env_port:
            return False
        try:
            port = int(env_port)
        except ValueError:
            LOGGER.warning("ALPHA_TRADE_METRICS_PORT invalide (%r), ignoré.", env_port)
            return False
    if not _PROMETHEUS_AVAILABLE:
        LOGGER.warning(
            "prometheus_client absent : endpoint /metrics non démarré "
            "(installer via pip install 'alpha-trade[observability]')."
        )
        return False
    try:
        start_http_server(port, addr=addr)
        _SERVER_STARTED = True
        LOGGER.info("Metrics endpoint /metrics démarré sur %s:%d", addr, port)
        return True
    except OSError as exc:  # pragma: no cover - dépend de l'env
        LOGGER.warning("Impossible de démarrer /metrics sur %s:%d : %s", addr, port, exc)
        return False


def record_run_summary(module: str, status: str = "OK") -> None:
    """Helper appelé après publication d'un run_summary (cf. core.run_summary)."""
    try:
        run_summary_total.labels(module=module, status=status).inc()
    except Exception:  # pragma: no cover - jamais bloquant
        LOGGER.debug("record_run_summary noop", exc_info=True)


__all__ = [
    "is_available",
    "run_summary_total",
    "data_freshness_hours",
    "iex_stale_quote_pct",
    "iex_zero_volume_count",
    "watcher_heartbeat_age_seconds",
    "ml_drift_status",
    "start_metrics_server",
    "record_run_summary",
]

