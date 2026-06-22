"""Sprint S9 — Métriques Prometheus pour supervision ops.

Expose les métriques clés de l'application au format Prometheus (text-based).
Supporte deux modes d'exposition :

1. **Fichier texte** : écrit périodiquement dans un fichier `.prom` lisible
   par le ``node_exporter`` textfile collector (recommandé pour les jobs batch).
2. **Endpoint HTTP** : démarre un serveur HTTP minimal sur un port configurable
   (via ``ALPHA_TRADE_PROMETHEUS_PORT``, défaut 9090) pour scraping direct.

Métriques exposées :
- ``alpha_trade_api_errors_total`` : compteur d'erreurs API par service
- ``alpha_trade_circuit_breaker_active`` : gauge 0/1 circuit breaker
- ``alpha_trade_heartbeat_stale`` : gauge 0/1 heartbeat stale
- ``alpha_trade_empty_universe`` : gauge 0/1 univers vide
- ``alpha_trade_kill_switch_active`` : gauge 0/1 kill switch
- ``alpha_trade_model_drift_active`` : gauge 0/1 drift ML
- ``alpha_trade_cash_ledger_aligned`` : gauge 0/1 alignement cash ledger
- ``alpha_trade_execution_runs_total`` : compteur de runs d'exécution
- ``alpha_trade_alerts_total`` : compteur d'alertes émises par sévérité

Usage :
    from service.prometheus_metrics import (
        bump_api_error,
        set_circuit_breaker_active,
        set_heartbeat_stale,
        set_empty_universe,
        set_kill_switch_active,
        set_model_drift_active,
        set_cash_ledger_aligned,
        bump_execution_run,
        bump_alert,
        write_metrics_file,
        start_prometheus_server,
    )
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)

# --- Configuration ---
ENV_PROMETHEUS_PORT = "ALPHA_TRADE_PROMETHEUS_PORT"
ENV_PROMETHEUS_FILE = "ALPHA_TRADE_PROMETHEUS_FILE"
DEFAULT_PORT = 9090
DEFAULT_FILE = "artifacts/metrics/alpha_trade.prom"


@dataclass
class _MetricsRegistry:
    """Registre thread-safe des métriques Prometheus."""

    _lock: threading.Lock = field(default_factory=threading.Lock)

    # Counters
    api_errors: dict[str, int] = field(default_factory=dict)  # service -> count
    execution_runs_total: int = 0
    alerts_total: dict[str, int] = field(default_factory=dict)  # severity -> count

    # Gauges
    circuit_breaker_active: int = 0
    heartbeat_stale: int = 0
    empty_universe: int = 0
    kill_switch_active: int = 0
    model_drift_active: int = 0
    cash_ledger_aligned: int = 1  # 1 = aligné, 0 = désaligné

    # Info
    last_scrape_timestamp: float = 0.0

    def bump_api_error(self, service: str) -> None:
        with self._lock:
            self.api_errors[service] = self.api_errors.get(service, 0) + 1

    def bump_execution_run(self) -> None:
        with self._lock:
            self.execution_runs_total += 1

    def bump_alert(self, severity: str) -> None:
        with self._lock:
            self.alerts_total[severity] = self.alerts_total.get(severity, 0) + 1

    def set_gauge(self, attr: str, value: int) -> None:
        with self._lock:
            setattr(self, attr, value)

    def render(self) -> str:
        """Produit le texte Prometheus (OpenMetrics text format)."""
        now = datetime.now(timezone.utc)
        ts_ms = int(now.timestamp() * 1000)
        self.last_scrape_timestamp = now.timestamp()

        lines: list[str] = [
            "# HELP alpha_trade_api_errors_total Total API errors by service.",
            "# TYPE alpha_trade_api_errors_total counter",
        ]
        for service, count in sorted(self.api_errors.items()):
            safe_service = service.replace("-", "_").replace(".", "_").replace(" ", "_")
            lines.append(
                f'alpha_trade_api_errors_total{{service="{safe_service}"}} {count} {ts_ms}'
            )

        lines += [
            "# HELP alpha_trade_execution_runs_total Total execution runs.",
            "# TYPE alpha_trade_execution_runs_total counter",
            f"alpha_trade_execution_runs_total {self.execution_runs_total} {ts_ms}",
            "",
            "# HELP alpha_trade_alerts_total Total alerts by severity.",
            "# TYPE alpha_trade_alerts_total counter",
        ]
        for severity, count in sorted(self.alerts_total.items()):
            lines.append(
                f'alpha_trade_alerts_total{{severity="{severity}"}} {count} {ts_ms}'
            )

        lines += [
            "",
            "# HELP alpha_trade_circuit_breaker_active Circuit breaker is active (1) or not (0).",
            "# TYPE alpha_trade_circuit_breaker_active gauge",
            f"alpha_trade_circuit_breaker_active {self.circuit_breaker_active} {ts_ms}",
            "",
            "# HELP alpha_trade_heartbeat_stale Watcher heartbeat is stale (1) or fresh (0).",
            "# TYPE alpha_trade_heartbeat_stale gauge",
            f"alpha_trade_heartbeat_stale {self.heartbeat_stale} {ts_ms}",
            "",
            "# HELP alpha_trade_empty_universe Trading universe is empty (1) or populated (0).",
            "# TYPE alpha_trade_empty_universe gauge",
            f"alpha_trade_empty_universe {self.empty_universe} {ts_ms}",
            "",
            "# HELP alpha_trade_kill_switch_active Execution kill switch is active (1) or not (0).",
            "# TYPE alpha_trade_kill_switch_active gauge",
            f"alpha_trade_kill_switch_active {self.kill_switch_active} {ts_ms}",
            "",
            "# HELP alpha_trade_model_drift_active ML model drift kill switch is active (1) or not (0).",
            "# TYPE alpha_trade_model_drift_active gauge",
            f"alpha_trade_model_drift_active {self.model_drift_active} {ts_ms}",
            "",
            "# HELP alpha_trade_cash_ledger_aligned Cash ledger is aligned (1) or misaligned (0).",
            "# TYPE alpha_trade_cash_ledger_aligned gauge",
            f"alpha_trade_cash_ledger_aligned {self.cash_ledger_aligned} {ts_ms}",
            "",
            "# EOF",
        ]
        return "\n".join(lines) + "\n"


# Singleton global
_registry = _MetricsRegistry()


# --- Public API ---

def bump_api_error(service: str) -> None:
    """Incrémente le compteur d'erreurs API pour un service donné."""
    _registry.bump_api_error(service)


def bump_execution_run() -> None:
    """Incrémente le compteur de runs d'exécution."""
    _registry.bump_execution_run()


def bump_alert(severity: str) -> None:
    """Incrémente le compteur d'alertes pour une sévérité donnée."""
    _registry.bump_alert(severity)


def set_circuit_breaker_active(active: bool) -> None:
    """Met à jour la gauge circuit breaker (1 = actif)."""
    _registry.set_gauge("circuit_breaker_active", 1 if active else 0)


def set_heartbeat_stale(stale: bool) -> None:
    """Met à jour la gauge heartbeat stale (1 = stale)."""
    _registry.set_gauge("heartbeat_stale", 1 if stale else 0)


def set_empty_universe(empty: bool) -> None:
    """Met à jour la gauge univers vide (1 = vide)."""
    _registry.set_gauge("empty_universe", 1 if empty else 0)


def set_kill_switch_active(active: bool) -> None:
    """Met à jour la gauge kill switch exécution (1 = actif)."""
    _registry.set_gauge("kill_switch_active", 1 if active else 0)


def set_model_drift_active(active: bool) -> None:
    """Met à jour la gauge drift ML (1 = drift détecté)."""
    _registry.set_gauge("model_drift_active", 1 if active else 0)


def set_cash_ledger_aligned(aligned: bool) -> None:
    """Met à jour la gauge alignement cash ledger (1 = aligné)."""
    _registry.set_gauge("cash_ledger_aligned", 1 if aligned else 0)


def render_metrics() -> str:
    """Retourne le texte Prometheus complet."""
    return _registry.render()


def write_metrics_file(filepath: str | Path | None = None) -> Path:
    """Écrit les métriques dans un fichier (pour node_exporter textfile collector).

    Le fichier est écrit atomiquement (write temp + rename) pour éviter
    que Prometheus ne lise un fichier partiel.
    """
    target = Path(filepath) if filepath else Path(
        os.environ.get(ENV_PROMETHEUS_FILE, DEFAULT_FILE)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")

    content = render_metrics()
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(target)

    LOGGER.debug("Prometheus metrics written to %s (%d bytes)", target, len(content))
    return target


def start_prometheus_server(
    port: int | None = None,
    *,
    blocking: bool = False,
) -> Optional[threading.Thread]:
    """Démarre un serveur HTTP minimal exposant ``/metrics``.

    Parameters
    ----------
    port:
        Port d'écoute (défaut : ``ALPHA_TRADE_PROMETHEUS_PORT`` ou 9090).
    blocking:
        Si ``True``, bloque le thread courant. Sinon démarre un daemon thread.

    Returns
    -------
    Optional[threading.Thread]
        Le thread du serveur, ou ``None`` si le serveur n'a pas pu démarrer.
    """
    resolved_port = port or int(os.environ.get(ENV_PROMETHEUS_PORT, str(DEFAULT_PORT)))

    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _MetricsHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/metrics":
                content = render_metrics()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            elif self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK\n")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt: str, *args: object) -> None:
            # Silence les logs HTTP pour ne pas polluer
            pass

    try:
        server = HTTPServer(("0.0.0.0", resolved_port), _MetricsHandler)
    except OSError as exc:
        LOGGER.error("Cannot start Prometheus server on port %d: %s", resolved_port, exc)
        return None

    LOGGER.info("Prometheus metrics server started on 0.0.0.0:%d/metrics", resolved_port)

    if blocking:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
        return None

    thread = threading.Thread(target=server.serve_forever, daemon=True, name="prometheus-server")
    thread.start()
    return thread


__all__ = [
    "bump_api_error",
    "bump_execution_run",
    "bump_alert",
    "set_circuit_breaker_active",
    "set_heartbeat_stale",
    "set_empty_universe",
    "set_kill_switch_active",
    "set_model_drift_active",
    "set_cash_ledger_aligned",
    "render_metrics",
    "write_metrics_file",
    "start_prometheus_server",
]
