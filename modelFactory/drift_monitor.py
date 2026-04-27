"""Phase 7.4 — Drift monitoring ML (audit_global §7.4).

Compare la distribution des prédictions du jour vs une fenêtre de baseline
(par défaut 30 jours) via deux indicateurs :

- **KS test** (Kolmogorov-Smirnov, deux échantillons) : détecte les
  changements de distribution arbitraires. Implémenté manuellement (zéro
  dépendance scipy obligatoire) — fallback sur ``scipy.stats`` si présent
  pour la p-value précise.
- **PSI** (Population Stability Index) : ``sum((p_now - p_base) * ln(p_now / p_base))``
  sur 10 buckets équipopulés.

Seuils par défaut (configurables) :

- ``OK``     : KS p-value ≥ 0.05 ET PSI < 0.1
- ``WARN``   : KS p-value < 0.05 OU PSI ∈ [0.1, 0.25)
- ``ALERT``  : KS p-value < 0.01 OU PSI ≥ 0.25

Persistance opt-in via :func:`persist_drift_run` (table ``ml_drift_runs``).
"""
from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

import numpy as np

LOGGER = logging.getLogger(__name__)

DEFAULT_KS_WARN = 0.05
DEFAULT_KS_ALERT = 0.01
DEFAULT_PSI_WARN = 0.10
DEFAULT_PSI_ALERT = 0.25


@dataclass(frozen=True, slots=True)
class DriftReport:
    model_id: str
    n_samples: int
    n_baseline: int
    ks_stat: float | None
    ks_pvalue: float | None
    psi: float | None
    status: str  # OK | WARN | ALERT
    notes: list[str]

    def to_payload(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "n_samples": self.n_samples,
            "n_baseline": self.n_baseline,
            "ks_stat": self.ks_stat,
            "ks_pvalue": self.ks_pvalue,
            "psi": self.psi,
            "status": self.status,
            "notes": self.notes,
            "schema_version": 1,
        }


# ---------------------------------------------------------------------------
# Algorithmes
# ---------------------------------------------------------------------------

def _ks_two_sample(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """KS deux échantillons. Retourne (D, p-value approchée).

    Utilise ``scipy.stats.ks_2samp`` si disponible pour la p-value précise.
    Sinon, calcule D manuellement et applique l'approximation Smirnov
    asymptotique : p = 2 * exp(-2 * D² * n_eff).
    """
    a = np.sort(np.asarray(a, dtype=float))
    b = np.sort(np.asarray(b, dtype=float))
    if a.size == 0 or b.size == 0:
        return float("nan"), float("nan")
    try:
        from scipy.stats import ks_2samp  # type: ignore[import-not-found]

        res = ks_2samp(a, b)
        return float(res.statistic), float(res.pvalue)
    except ImportError:
        # Fallback manuel
        all_vals = np.concatenate([a, b])
        cdf_a = np.searchsorted(a, all_vals, side="right") / a.size
        cdf_b = np.searchsorted(b, all_vals, side="right") / b.size
        d = float(np.max(np.abs(cdf_a - cdf_b)))
        n_eff = (a.size * b.size) / (a.size + b.size)
        # Smirnov asymptotic: p ≈ 2 * exp(-2 * (D * sqrt(n_eff))²)
        try:
            p = 2.0 * math.exp(-2.0 * (d**2) * n_eff)
        except OverflowError:
            p = 0.0
        return d, max(0.0, min(1.0, p))


def _psi(now: np.ndarray, baseline: np.ndarray, *, buckets: int = 10) -> float:
    """Population Stability Index sur ``buckets`` buckets équipopulés baseline."""
    if now.size == 0 or baseline.size == 0:
        return float("nan")
    edges = np.quantile(baseline, np.linspace(0, 1, buckets + 1))
    edges = np.unique(edges)
    if edges.size < 2:
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf
    base_counts, _ = np.histogram(baseline, bins=edges)
    now_counts, _ = np.histogram(now, bins=edges)
    eps = 1e-6
    p_base = np.maximum(base_counts / max(baseline.size, 1), eps)
    p_now = np.maximum(now_counts / max(now.size, 1), eps)
    return float(np.sum((p_now - p_base) * np.log(p_now / p_base)))


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def compute_drift(
    today_predictions: Sequence[float],
    baseline_predictions: Sequence[float],
    *,
    model_id: str,
    ks_warn: float = DEFAULT_KS_WARN,
    ks_alert: float = DEFAULT_KS_ALERT,
    psi_warn: float = DEFAULT_PSI_WARN,
    psi_alert: float = DEFAULT_PSI_ALERT,
) -> DriftReport:
    """Calcule le drift entre les prédictions du jour et la baseline."""
    today = np.asarray(today_predictions, dtype=float)
    baseline = np.asarray(baseline_predictions, dtype=float)
    today = today[~np.isnan(today)]
    baseline = baseline[~np.isnan(baseline)]

    notes: list[str] = []
    if today.size < 5 or baseline.size < 30:
        notes.append("sample_size_too_small")
        return DriftReport(
            model_id=model_id,
            n_samples=int(today.size),
            n_baseline=int(baseline.size),
            ks_stat=None,
            ks_pvalue=None,
            psi=None,
            status="OK",
            notes=notes,
        )

    ks_stat, ks_p = _ks_two_sample(today, baseline)
    psi = _psi(today, baseline)

    status = "OK"
    if (not math.isnan(ks_p) and ks_p < ks_alert) or (not math.isnan(psi) and psi >= psi_alert):
        status = "ALERT"
    elif (not math.isnan(ks_p) and ks_p < ks_warn) or (not math.isnan(psi) and psi >= psi_warn):
        status = "WARN"

    return DriftReport(
        model_id=model_id,
        n_samples=int(today.size),
        n_baseline=int(baseline.size),
        ks_stat=float(ks_stat),
        ks_pvalue=float(ks_p),
        psi=float(psi),
        status=status,
        notes=notes,
    )


def persist_drift_run(report: DriftReport, *, engine: Any, run_id: str | None = None) -> str:
    """Insère ``report`` dans ``ml_drift_runs``. Retourne le run_id."""
    from sqlalchemy import text

    rid = run_id or f"mdr-{uuid.uuid4().hex[:12]}"
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ml_drift_runs
                    (run_id, computed_at, model_id, ks_stat, ks_pvalue, psi,
                     n_samples, n_baseline, status, payload, schema_version)
                VALUES
                    (:run_id, :computed_at, :model_id, :ks_stat, :ks_pvalue, :psi,
                     :n_samples, :n_baseline, :status, :payload, :schema_version)
                """
            ),
            {
                "run_id": rid,
                "computed_at": datetime.utcnow(),
                "model_id": report.model_id,
                "ks_stat": report.ks_stat,
                "ks_pvalue": report.ks_pvalue,
                "psi": report.psi,
                "n_samples": report.n_samples,
                "n_baseline": report.n_baseline,
                "status": report.status,
                "payload": json.dumps(report.to_payload()),
                "schema_version": 1,
            },
        )
    return rid


__all__ = [
    "DriftReport",
    "compute_drift",
    "persist_drift_run",
    "DEFAULT_KS_WARN",
    "DEFAULT_KS_ALERT",
    "DEFAULT_PSI_WARN",
    "DEFAULT_PSI_ALERT",
]

