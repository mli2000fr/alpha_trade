"""Sprint S5 — Métriques Prometheus spécifiques au pipeline Alpha Trade.

Module **opt-in** : s'appuie sur ``core.metrics`` pour le no-op fallback.
Si ``prometheus_client`` est absent, toutes les métriques deviennent des
no-op transparents.

Métriques exposées :

* ``alpha_pipeline_steps_total``      — Counter par (step, status)
* ``alpha_pipeline_duration_seconds`` — Histogram par step
* ``alpha_selections_count``          — Gauge (nombre de sélections AlphaScanner)
* ``alpha_ml_train_duration_seconds`` — Histogram par symbol
* ``alpha_db_backup_total``           — Counter par status
* ``alpha_ml_backup_total``           — Counter par status

Usage::

    from common.metrics import pipeline_steps_total, record_pipeline_step
    import time

    pipeline_steps_total.labels(step="screener", status="OK").inc()

    with record_pipeline_step("screener"):
        run_screener(date)
"""
from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Generator
from typing import Any

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import des primitives Prometheus via core.metrics (no-op fallback inclus)
# ---------------------------------------------------------------------------
try:
    # core.metrics expose déjà Counter / Gauge / Histogram no-op si absent
    from core.metrics import Counter, Gauge, Histogram, is_available  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover — cas très improbable (core toujours présent)

    def is_available() -> bool:  # type: ignore[misc]
        return False

    class _Noop:
        def labels(self, *_a: Any, **_kw: Any) -> "_Noop":
            return self

        def inc(self, *_a: Any, **_kw: Any) -> None:
            pass

        def set(self, *_a: Any, **_kw: Any) -> None:
            pass

        def observe(self, *_a: Any, **_kw: Any) -> None:
            pass

    def Counter(*_a: Any, **_kw: Any) -> _Noop:  # type: ignore[misc]
        return _Noop()

    def Gauge(*_a: Any, **_kw: Any) -> _Noop:  # type: ignore[misc]
        return _Noop()

    def Histogram(*_a: Any, **_kw: Any) -> _Noop:  # type: ignore[misc]
        return _Noop()


# ---------------------------------------------------------------------------
# Métriques pipeline
# ---------------------------------------------------------------------------

pipeline_steps_total = Counter(
    "alpha_pipeline_steps_total",
    "Nombre total d'étapes pipeline, ventilé par step et statut.",
    labelnames=("step", "status"),
)

pipeline_duration_seconds = Histogram(
    "alpha_pipeline_duration_seconds",
    "Durée (secondes) de chaque étape pipeline.",
    labelnames=("step",),
    buckets=(0.1, 0.5, 1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0),
)

selections_count = Gauge(
    "alpha_selections_count",
    "Nombre de sélections produites après AlphaScanner.",
)

ml_train_duration_seconds = Histogram(
    "alpha_ml_train_duration_seconds",
    "Durée (secondes) d'entraînement ML par symbole.",
    labelnames=("symbol",),
    buckets=(1.0, 5.0, 15.0, 30.0, 60.0, 180.0, 600.0),
)

db_backup_total = Counter(
    "alpha_db_backup_total",
    "Nombre de backups DB, ventilé par statut (OK / ERROR).",
    labelnames=("status",),
)

ml_backup_total = Counter(
    "alpha_ml_backup_total",
    "Nombre de backups artefacts ML, ventilé par statut (OK / ERROR).",
    labelnames=("status",),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def record_pipeline_step(step: str) -> Generator[None, None, None]:
    """Context-manager qui mesure la durée d'une étape et émet les métriques.

    Exemple::

        with record_pipeline_step("screener"):
            run_screener(date)

    En sortie le Counter est incrémenté avec ``status="OK"`` ou ``status="ERROR"``.
    """
    t0 = time.perf_counter()
    status = "OK"
    try:
        yield
    except Exception:
        status = "ERROR"
        raise
    finally:
        elapsed = time.perf_counter() - t0
        try:
            pipeline_steps_total.labels(step=step, status=status).inc()
            pipeline_duration_seconds.labels(step=step).observe(elapsed)
        except Exception:  # pragma: no cover — jamais bloquant
            LOGGER.debug("record_pipeline_step noop", exc_info=True)


__all__ = [
    "pipeline_steps_total",
    "pipeline_duration_seconds",
    "selections_count",
    "ml_train_duration_seconds",
    "db_backup_total",
    "ml_backup_total",
    "record_pipeline_step",
    "is_available",
]

