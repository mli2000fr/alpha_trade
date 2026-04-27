"""Phase 7.2 — Calibration empirique des poids conviction / sentiment.

Réf. ``prompt/refactor/plan.md`` Phase 7 + ``audit_global.md §7.2``.

Approche minimale et déterministe :

- Grille discrète sur l'espace des poids (pas 0.05 par défaut).
- Pour chaque jeu de poids, calcule une métrique d'évaluation (Sharpe, hit
  rate, ou IC) sur un panneau de signaux fournis par l'appelant.
- Retourne le meilleur jeu + l'ensemble des candidats évalués.
- La persistance en DB (table ``weights_calibration_runs``, migration 0020)
  est offerte par :func:`persist_calibration_run`, **opt-in** (le moteur de
  calcul est totalement découplé de la DB).

L'intégration au pipeline complet (`signal_replay` glissant 6 mois) est laissée
au sub-command CLI ``backtesting calibrate-weights`` (à câbler ultérieurement) :
ce module fournit l'API noyau testable.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

from core.conviction import ConvictionWeights, SentimentFusionWeights, fuse, fuse_sentiment

LOGGER = logging.getLogger(__name__)

ScoreMetric = Callable[[np.ndarray, np.ndarray], float]


# ---------------------------------------------------------------------------
# Métriques disponibles
# ---------------------------------------------------------------------------

def metric_information_coefficient(predictions: np.ndarray, forward_returns: np.ndarray) -> float:
    """IC = corrélation Spearman simplifiée (Pearson sur ranks)."""
    if predictions.size == 0 or forward_returns.size == 0:
        return float("nan")
    a = np.argsort(np.argsort(predictions))
    b = np.argsort(np.argsort(forward_returns))
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def metric_hit_rate(predictions: np.ndarray, forward_returns: np.ndarray, *, threshold: float = 0.5) -> float:
    """Hit rate = % de cas où ``prediction > threshold`` ET ``forward_return > 0``."""
    if predictions.size == 0:
        return float("nan")
    long_mask = predictions > threshold
    if long_mask.sum() == 0:
        return 0.0
    wins = (forward_returns[long_mask] > 0).sum()
    return float(wins / long_mask.sum())


METRICS: dict[str, ScoreMetric] = {
    "ic": metric_information_coefficient,
    "hit_rate": metric_hit_rate,
}


# ---------------------------------------------------------------------------
# Résultat
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CalibrationCandidate:
    weights: dict[str, float]
    metric_value: float


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    scope: str
    metric_name: str
    best_weights: dict[str, float]
    metric_value: float
    candidates: list[CalibrationCandidate] = field(default_factory=list)
    window_start: date | None = None
    window_end: date | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "metric_name": self.metric_name,
            "best_weights": self.best_weights,
            "metric_value": self.metric_value,
            "candidates": [
                {"weights": c.weights, "metric_value": c.metric_value} for c in self.candidates
            ],
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "schema_version": 1,
        }


# ---------------------------------------------------------------------------
# Grilles
# ---------------------------------------------------------------------------

def _conviction_grid(step: float = 0.05) -> Iterable[ConvictionWeights]:
    grid = np.round(np.arange(0.0, 1.0 + step, step), 6)
    for s in grid:
        p = round(1.0 - float(s), 6)
        if p < 0.0:
            continue
        yield ConvictionWeights(score_weight=float(s), prediction_weight=p)


def _sentiment_grid(step: float = 0.05) -> Iterable[SentimentFusionWeights]:
    vals = np.round(np.arange(0.0, 1.0 + step, step), 6)
    for q in vals:
        for s in vals:
            m = round(1.0 - float(q) - float(s), 6)
            if m < 0.0 or m > 1.0:
                continue
            try:
                yield SentimentFusionWeights(
                    quant_weight=float(q),
                    sentiment_weight=float(s),
                    macro_weight=float(m),
                )
            except ValueError:
                continue


# ---------------------------------------------------------------------------
# Calibrations
# ---------------------------------------------------------------------------

def calibrate_conviction(
    *,
    quant_scores: Sequence[float],
    predicted_proba: Sequence[float | None],
    forward_returns: Sequence[float],
    metric_name: str = "ic",
    grid_step: float = 0.05,
    window: tuple[date, date] | None = None,
) -> CalibrationResult:
    """Calibre ``ConvictionWeights`` sur l'historique fourni.

    Tous les vecteurs doivent avoir la même longueur N. Les positions où
    ``predicted_proba[i] is None`` sont ignorées pour le calcul.
    """
    if metric_name not in METRICS:
        raise ValueError(f"Métrique inconnue : {metric_name!r} (attendu: {list(METRICS)}).")
    metric_fn = METRICS[metric_name]
    quant = np.asarray(quant_scores, dtype=float)
    proba = np.asarray([p if p is not None else np.nan for p in predicted_proba], dtype=float)
    fwd = np.asarray(forward_returns, dtype=float)
    if not (len(quant) == len(proba) == len(fwd)):
        raise ValueError("calibrate_conviction : longueurs incohérentes.")
    mask = ~(np.isnan(quant) | np.isnan(proba) | np.isnan(fwd))
    if mask.sum() < 5:
        raise ValueError("calibrate_conviction : moins de 5 observations valides.")
    quant_v, proba_v, fwd_v = quant[mask], proba[mask], fwd[mask]

    candidates: list[CalibrationCandidate] = []
    best: CalibrationCandidate | None = None
    for w in _conviction_grid(grid_step):
        fused = np.asarray(
            [fuse(quant_score=q, predicted_proba=float(p), weights=w) for q, p in zip(quant_v, proba_v)],
            dtype=float,
        )
        m = metric_fn(fused, fwd_v)
        if not np.isfinite(m):
            continue
        cand = CalibrationCandidate(
            weights={"score_weight": w.score_weight, "prediction_weight": w.prediction_weight},
            metric_value=float(m),
        )
        candidates.append(cand)
        if best is None or m > best.metric_value:
            best = cand
    if best is None:
        raise RuntimeError("calibrate_conviction : aucun candidat évaluable.")
    start, end = (window if window else (None, None))
    return CalibrationResult(
        scope="conviction",
        metric_name=metric_name,
        best_weights=best.weights,
        metric_value=best.metric_value,
        candidates=candidates,
        window_start=start,
        window_end=end,
    )


def calibrate_sentiment(
    *,
    quant_scores: Sequence[float],
    sentiment_signal: Sequence[float],
    macro_signal: Sequence[float],
    forward_returns: Sequence[float],
    metric_name: str = "ic",
    grid_step: float = 0.1,
    window: tuple[date, date] | None = None,
) -> CalibrationResult:
    """Calibre ``SentimentFusionWeights`` (triplet quant/sentiment/macro)."""
    if metric_name not in METRICS:
        raise ValueError(f"Métrique inconnue : {metric_name!r}.")
    metric_fn = METRICS[metric_name]
    arrs = [np.asarray(x, dtype=float) for x in (quant_scores, sentiment_signal, macro_signal, forward_returns)]
    if len({len(a) for a in arrs}) != 1:
        raise ValueError("calibrate_sentiment : longueurs incohérentes.")
    quant_v, sent_v, macro_v, fwd_v = arrs
    mask = ~(np.isnan(quant_v) | np.isnan(sent_v) | np.isnan(macro_v) | np.isnan(fwd_v))
    if mask.sum() < 5:
        raise ValueError("calibrate_sentiment : moins de 5 observations valides.")
    quant_v, sent_v, macro_v, fwd_v = quant_v[mask], sent_v[mask], macro_v[mask], fwd_v[mask]

    candidates: list[CalibrationCandidate] = []
    best: CalibrationCandidate | None = None
    for w in _sentiment_grid(grid_step):
        fused = fuse_sentiment(
            quant_score=quant_v,
            sentiment_signal_norm=sent_v,
            macro_signal_norm=macro_v,
            weights=w,
        )
        if isinstance(fused, float):
            fused = np.asarray([fused])
        m = metric_fn(np.asarray(fused), fwd_v)
        if not np.isfinite(m):
            continue
        cand = CalibrationCandidate(
            weights={
                "quant_weight": w.quant_weight,
                "sentiment_weight": w.sentiment_weight,
                "macro_weight": w.macro_weight,
            },
            metric_value=float(m),
        )
        candidates.append(cand)
        if best is None or m > best.metric_value:
            best = cand
    if best is None:
        raise RuntimeError("calibrate_sentiment : aucun candidat évaluable.")
    start, end = (window if window else (None, None))
    return CalibrationResult(
        scope="sentiment",
        metric_name=metric_name,
        best_weights=best.weights,
        metric_value=best.metric_value,
        candidates=candidates,
        window_start=start,
        window_end=end,
    )


# ---------------------------------------------------------------------------
# Persistance (opt-in, ne dépend pas du moteur de calcul)
# ---------------------------------------------------------------------------

def persist_calibration_run(
    result: CalibrationResult,
    *,
    engine: Any,
    git_sha: str | None = None,
    run_id: str | None = None,
) -> str:
    """Insère ``result`` dans ``weights_calibration_runs``.

    ``engine`` doit être un SQLAlchemy ``Engine`` ; isolation explicite afin
    de garder le module testable sans DB.
    """
    from sqlalchemy import text  # import paresseux

    rid = run_id or f"wcr-{uuid.uuid4().hex[:12]}"
    payload = result.to_payload()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO weights_calibration_runs
                    (run_id, calibrated_at, scope, window_start, window_end,
                     metric_name, metric_value, best_weights, candidates,
                     git_sha, schema_version)
                VALUES
                    (:run_id, :calibrated_at, :scope, :window_start, :window_end,
                     :metric_name, :metric_value, :best_weights, :candidates,
                     :git_sha, :schema_version)
                """
            ),
            {
                "run_id": rid,
                "calibrated_at": datetime.utcnow(),
                "scope": result.scope,
                "window_start": result.window_start,
                "window_end": result.window_end,
                "metric_name": result.metric_name,
                "metric_value": result.metric_value,
                "best_weights": json.dumps(result.best_weights),
                "candidates": json.dumps(payload["candidates"]),
                "git_sha": git_sha,
                "schema_version": 1,
            },
        )
    return rid


__all__ = [
    "CalibrationResult",
    "CalibrationCandidate",
    "METRICS",
    "calibrate_conviction",
    "calibrate_sentiment",
    "metric_information_coefficient",
    "metric_hit_rate",
    "persist_calibration_run",
]

