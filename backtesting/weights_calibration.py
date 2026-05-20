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
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.conviction import ConvictionWeights, SentimentFusionWeights, fuse, fuse_sentiment

LOGGER = logging.getLogger(__name__)

ScoreMetric = Callable[[np.ndarray, np.ndarray], float]
CALIBRATION_SCHEMA_VERSION = 2
SEGMENT_DRIFT_SCHEMA_VERSION = 1
MARKET_REGIME_ALL = "all"
KNOWN_MARKET_REGIME_MODES = {
    MARKET_REGIME_ALL,
    "normal",
    "capital_preservation",
    "close_only",
    "cash_only",
}


def normalize_market_regime_mode(value: object) -> str:
    text_value = str(value or "").strip().lower()
    if not text_value:
        return MARKET_REGIME_ALL
    return text_value if text_value in KNOWN_MARKET_REGIME_MODES else MARKET_REGIME_ALL


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


def metric_strategy_sharpe(strategy_returns: np.ndarray) -> float:
    """Sharpe simplifié annualisé sur une série de rendements de stratégie."""
    if strategy_returns.size == 0:
        return float("nan")
    mean_return = float(np.mean(strategy_returns))
    std_return = float(np.std(strategy_returns, ddof=0))
    if std_return <= 0:
        return 0.0
    return float((mean_return / std_return) * np.sqrt(252.0))


def metric_strategy_log_growth(strategy_returns: np.ndarray) -> float:
    """Croissance logarithmique moyenne d'une stratégie pondérée."""
    if strategy_returns.size == 0:
        return float("nan")
    clipped = np.clip(strategy_returns, -0.999999, None)
    return float(np.mean(np.log1p(clipped)))


RISK_METRICS: dict[str, Callable[[np.ndarray], float]] = {
    "sharpe": metric_strategy_sharpe,
    "log_growth": metric_strategy_log_growth,
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
    market_regime_mode: str = MARKET_REGIME_ALL
    candidates: list[CalibrationCandidate] = field(default_factory=list)
    window_start: date | None = None
    window_end: date | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "metric_name": self.metric_name,
            "best_weights": self.best_weights,
            "metric_value": self.metric_value,
            "market_regime_mode": self.market_regime_mode,
            "candidates": [
                {"weights": c.weights, "metric_value": c.metric_value} for c in self.candidates
            ],
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "schema_version": CALIBRATION_SCHEMA_VERSION,
        }


@dataclass(frozen=True, slots=True)
class EmpiricalRiskCalibrationRun:
    start_date: date
    end_date: date
    observations_evaluated: int
    scenarios_evaluated: int
    latest_best_scenario_name: str
    metric_name: str
    metric_value: float
    final_value: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    calibration_run_id: str | None = None
    calibration_batch_id: str | None = None
    segment_key: str | None = None
    horizon_days: int = 5
    lookback_months: int | None = None
    distinct_snapshot_days: int = 0
    distinct_symbols: int = 0
    eligible_for_live: bool = False
    eligibility_reason: str | None = None
    best_weights: dict[str, float] = field(default_factory=dict)
    artifact_dir: str | None = None
    market_regime_mode: str = MARKET_REGIME_ALL


@dataclass(frozen=True, slots=True)
class CalibrationSegmentDrift:
    comparison_kind: str
    source_run_id: str | None
    target_run_id: str | None
    source_segment_key: str | None
    target_segment_key: str | None
    calibration_batch_id: str | None = None
    metric_name: str | None = None
    metric_delta: float | None = None
    final_value_drift_pct: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)


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


def _kelly_grid(
    *,
    kelly_fraction_multipliers: Sequence[float],
    min_effective_probabilities: Sequence[float],
    assumed_payoff_ratios: Sequence[float],
) -> Iterable[dict[str, float]]:
    for multiplier in kelly_fraction_multipliers:
        for min_probability in min_effective_probabilities:
            for payoff_ratio in assumed_payoff_ratios:
                yield {
                    "kelly_fraction_multiplier": float(multiplier),
                    "min_effective_probability": float(min_probability),
                    "assumed_payoff_ratio": float(payoff_ratio),
                }


def _subtract_months(reference: date, months: int) -> date:
    year = reference.year
    month = reference.month - int(months)
    while month <= 0:
        month += 12
        year -= 1
    day = min(reference.day, 28)
    return date(year, month, day)


def _build_segment_key(*, market_regime_mode: str, horizon_days: int, lookback_months: int | None) -> str:
    resolved_lookback_months = int(lookback_months or 0)
    return (
        f"regime={normalize_market_regime_mode(market_regime_mode)}"
        f"|horizon={int(horizon_days)}d"
        f"|window={resolved_lookback_months}m"
    )


def _compute_relative_drift(current: float, reference: float) -> float | None:
    if reference == 0:
        return None if current == 0 else float("inf")
    return (current - reference) / abs(reference)


def _evaluate_live_governance(
    dataset: pd.DataFrame,
    *,
    min_observations: int,
    min_snapshot_days: int,
    min_symbols: int,
) -> tuple[bool, str | None, int, int]:
    observations_evaluated = int(len(dataset))
    distinct_snapshot_days = int(dataset["snapshot_date"].nunique()) if not dataset.empty else 0
    distinct_symbols = int(dataset["symbol"].nunique()) if not dataset.empty else 0
    reasons: list[str] = []
    if observations_evaluated < int(min_observations):
        reasons.append("insufficient_observations")
    if distinct_snapshot_days < int(min_snapshot_days):
        reasons.append("insufficient_snapshot_days")
    if distinct_symbols < int(min_symbols):
        reasons.append("insufficient_symbols")
    return (not reasons), (";".join(reasons) if reasons else None), distinct_snapshot_days, distinct_symbols


def compute_segment_drifts(
    runs: Sequence[EmpiricalRiskCalibrationRun],
    *,
    reference_horizon_days: int | None = None,
    reference_lookback_months: int | None = None,
) -> list[CalibrationSegmentDrift]:
    if not runs:
        return []
    run_by_segment = {
        str(run.segment_key or _build_segment_key(
            market_regime_mode=run.market_regime_mode,
            horizon_days=run.horizon_days,
            lookback_months=run.lookback_months,
        )): run
        for run in runs
    }
    baseline_by_horizon_window = {
        (int(run.horizon_days), int(run.lookback_months or 0)): run
        for run in runs
        if normalize_market_regime_mode(run.market_regime_mode) == MARKET_REGIME_ALL
    }
    resolved_reference_horizon = int(reference_horizon_days or min(int(run.horizon_days) for run in runs))
    lookback_candidates = [int(run.lookback_months or 0) for run in runs]
    resolved_reference_lookback = int(reference_lookback_months or max(lookback_candidates))
    reference_segment_key = _build_segment_key(
        market_regime_mode=MARKET_REGIME_ALL,
        horizon_days=resolved_reference_horizon,
        lookback_months=resolved_reference_lookback,
    )
    reference_run = run_by_segment.get(reference_segment_key)
    drifts: list[CalibrationSegmentDrift] = []
    for run in runs:
        source_segment_key = str(run.segment_key or "").strip() or _build_segment_key(
            market_regime_mode=run.market_regime_mode,
            horizon_days=run.horizon_days,
            lookback_months=run.lookback_months,
        )
        if normalize_market_regime_mode(run.market_regime_mode) != MARKET_REGIME_ALL:
            baseline_run = baseline_by_horizon_window.get((int(run.horizon_days), int(run.lookback_months or 0)))
            if baseline_run is not None and baseline_run.calibration_run_id != run.calibration_run_id:
                drifts.append(
                    CalibrationSegmentDrift(
                        comparison_kind="vs_all_same_horizon_window",
                        source_run_id=run.calibration_run_id,
                        target_run_id=baseline_run.calibration_run_id,
                        source_segment_key=source_segment_key,
                        target_segment_key=baseline_run.segment_key,
                        calibration_batch_id=run.calibration_batch_id,
                        metric_name=run.metric_name,
                        metric_delta=float(run.metric_value - baseline_run.metric_value),
                        final_value_drift_pct=_compute_relative_drift(run.final_value, baseline_run.final_value),
                        payload={
                            "source_market_regime_mode": run.market_regime_mode,
                            "target_market_regime_mode": baseline_run.market_regime_mode,
                            "horizon_days": int(run.horizon_days),
                            "lookback_months": int(run.lookback_months or 0),
                        },
                    )
                )
        if reference_run is not None and reference_run.calibration_run_id != run.calibration_run_id:
            drifts.append(
                CalibrationSegmentDrift(
                    comparison_kind="vs_reference_live_segment",
                    source_run_id=run.calibration_run_id,
                    target_run_id=reference_run.calibration_run_id,
                    source_segment_key=source_segment_key,
                    target_segment_key=reference_run.segment_key,
                    calibration_batch_id=run.calibration_batch_id,
                    metric_name=run.metric_name,
                    metric_delta=float(run.metric_value - reference_run.metric_value),
                    final_value_drift_pct=_compute_relative_drift(run.final_value, reference_run.final_value),
                    payload={
                        "reference_horizon_days": resolved_reference_horizon,
                        "reference_lookback_months": resolved_reference_lookback,
                    },
                )
            )
    return drifts


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
    market_regime_mode: str = MARKET_REGIME_ALL,
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
            [fuse(quant_score=q, predicted_proba=float(p), weights=w) for q, p in zip(quant_v, proba_v, strict=False)],
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
        market_regime_mode=normalize_market_regime_mode(market_regime_mode),
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
    market_regime_mode: str = MARKET_REGIME_ALL,
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
        market_regime_mode=normalize_market_regime_mode(market_regime_mode),
        candidates=candidates,
        window_start=start,
        window_end=end,
    )


def _compute_kelly_fraction(
    predicted_proba: np.ndarray,
    historical_win_rate: np.ndarray,
    *,
    kelly_fraction_multiplier: float,
    min_effective_probability: float,
    assumed_payoff_ratio: float,
    prediction_confidence_weight: float = 0.60,
    historical_win_rate_weight: float = 0.40,
    max_position_weight: float = 0.10,
) -> np.ndarray:
    p_eff = (prediction_confidence_weight * predicted_proba) + (historical_win_rate_weight * historical_win_rate)
    p_eff = np.clip(p_eff, 0.001, 0.999)
    raw_kelly = p_eff - ((1.0 - p_eff) / assumed_payoff_ratio)
    kelly_fraction = np.maximum(raw_kelly, 0.0) * float(kelly_fraction_multiplier)
    kelly_fraction = np.where(p_eff >= float(min_effective_probability), kelly_fraction, 0.0)
    return np.minimum(kelly_fraction, float(max_position_weight))


def _weighted_daily_strategy_returns(
    snapshot_dates: Sequence[date | datetime | str],
    conviction_scores: np.ndarray,
    kelly_fractions: np.ndarray,
    forward_returns: np.ndarray,
    *,
    top_n: int,
) -> np.ndarray:
    dates = pd.to_datetime(pd.Series(snapshot_dates), errors="coerce")
    work = pd.DataFrame(
        {
            "snapshot_date": dates,
            "conviction": conviction_scores,
            "kelly_fraction": kelly_fractions,
            "forward_return": forward_returns,
        }
    ).dropna(subset=["snapshot_date", "conviction", "kelly_fraction", "forward_return"])
    if work.empty:
        return np.asarray([], dtype=float)
    work = work.sort_values(["snapshot_date", "conviction"], ascending=[True, False]).reset_index(drop=True)
    daily_returns: list[float] = []
    for _, group in work.groupby("snapshot_date", sort=True):
        selected = group.head(max(int(top_n), 1)).copy()
        position_weight = selected["conviction"].clip(lower=0.0) * selected["kelly_fraction"].clip(lower=0.0)
        gross_weight = float(position_weight.sum())
        if gross_weight <= 0:
            daily_returns.append(0.0)
            continue
        portfolio_return = float(np.average(selected["forward_return"], weights=position_weight))
        daily_returns.append(portfolio_return)
    return np.asarray(daily_returns, dtype=float)


def calibrate_conviction_kelly(
    *,
    snapshot_dates: Sequence[date | datetime | str],
    quant_scores: Sequence[float],
    predicted_proba: Sequence[float | None],
    historical_win_rate: Sequence[float | None],
    forward_returns: Sequence[float],
    metric_name: str = "sharpe",
    conviction_grid_step: float = 0.05,
    kelly_fraction_multipliers: Sequence[float] = (0.10, 0.25, 0.50),
    min_effective_probabilities: Sequence[float] = (0.50, 0.52, 0.55),
    assumed_payoff_ratios: Sequence[float] = (1.0, 1.5, 2.0),
    top_n: int = 20,
    max_position_weight: float = 0.10,
    window: tuple[date, date] | None = None,
    market_regime_mode: str = MARKET_REGIME_ALL,
) -> CalibrationResult:
    """Calibre conjointement les poids de conviction et les paramètres Kelly.

    La boucle évalue une stratégie cross-sectionnelle simple : top-N par date,
    pondérée par ``conviction * kelly_fraction`` puis scorée via une métrique de
    rendement de stratégie (Sharpe ou log-growth).
    """
    if metric_name not in RISK_METRICS:
        raise ValueError(f"Métrique risque inconnue : {metric_name!r} (attendu: {list(RISK_METRICS)}).")
    metric_fn = RISK_METRICS[metric_name]
    quant = np.asarray(quant_scores, dtype=float)
    proba = np.asarray([p if p is not None else np.nan for p in predicted_proba], dtype=float)
    hist_wr = np.asarray([p if p is not None else np.nan for p in historical_win_rate], dtype=float)
    fwd = np.asarray(forward_returns, dtype=float)
    if len({len(snapshot_dates), len(quant), len(proba), len(hist_wr), len(fwd)}) != 1:
        raise ValueError("calibrate_conviction_kelly : longueurs incohérentes.")
    mask = ~(np.isnan(quant) | np.isnan(proba) | np.isnan(hist_wr) | np.isnan(fwd))
    if int(mask.sum()) < 10:
        raise ValueError("calibrate_conviction_kelly : moins de 10 observations valides.")

    filtered_dates = list(pd.to_datetime(pd.Series(snapshot_dates), errors="coerce")[mask])
    quant_v = quant[mask]
    proba_v = proba[mask]
    hist_wr_v = hist_wr[mask]
    fwd_v = fwd[mask]

    candidates: list[CalibrationCandidate] = []
    best: CalibrationCandidate | None = None
    for conviction_weights in _conviction_grid(conviction_grid_step):
        fused = np.asarray(
            [
                fuse(quant_score=float(q), predicted_proba=float(p), weights=conviction_weights)
                for q, p in zip(quant_v, proba_v, strict=False)
            ],
            dtype=float,
        )
        for kelly_params in _kelly_grid(
            kelly_fraction_multipliers=kelly_fraction_multipliers,
            min_effective_probabilities=min_effective_probabilities,
            assumed_payoff_ratios=assumed_payoff_ratios,
        ):
            kelly_fraction = _compute_kelly_fraction(
                proba_v,
                hist_wr_v,
                kelly_fraction_multiplier=kelly_params["kelly_fraction_multiplier"],
                min_effective_probability=kelly_params["min_effective_probability"],
                assumed_payoff_ratio=kelly_params["assumed_payoff_ratio"],
                max_position_weight=max_position_weight,
            )
            strategy_returns = _weighted_daily_strategy_returns(
                filtered_dates,
                fused,
                kelly_fraction,
                fwd_v,
                top_n=top_n,
            )
            metric_value = metric_fn(strategy_returns)
            if not np.isfinite(metric_value):
                continue
            candidate_weights = {
                "score_weight": float(conviction_weights.score_weight),
                "prediction_weight": float(conviction_weights.prediction_weight),
                "kelly_fraction_multiplier": float(kelly_params["kelly_fraction_multiplier"]),
                "min_effective_probability": float(kelly_params["min_effective_probability"]),
                "assumed_payoff_ratio": float(kelly_params["assumed_payoff_ratio"]),
                "top_n": float(top_n),
            }
            candidate = CalibrationCandidate(weights=candidate_weights, metric_value=float(metric_value))
            candidates.append(candidate)
            if best is None or candidate.metric_value > best.metric_value:
                best = candidate
    if best is None:
        raise RuntimeError("calibrate_conviction_kelly : aucun candidat évaluable.")
    start, end = (window if window else (None, None))
    return CalibrationResult(
        scope="risk",
        metric_name=metric_name,
        best_weights=best.weights,
        metric_value=best.metric_value,
        market_regime_mode=normalize_market_regime_mode(market_regime_mode),
        candidates=candidates,
        window_start=start,
        window_end=end,
    )


class EmpiricalRiskCalibrator:
    """Calibrateur batch conviction/Kelly à partir de la base PIT."""

    def __init__(self, engine: Any | None = None) -> None:
        if engine is None:
            from database.connection import get_sqlalchemy_engine

            engine = get_sqlalchemy_engine()
        self.engine = engine

    def _get_table_columns(self, table_name: str) -> set[str]:
        try:
            from sqlalchemy import inspect

            return {str(column["name"]) for column in inspect(self.engine).get_columns(table_name)}
        except Exception:
            LOGGER.debug("Impossible d'inspecter la table %s pour calibration risque.", table_name, exc_info=True)
            return set()

    def _resolve_market_regime_modes(self, snapshot_dates: Sequence[pd.Timestamp]) -> dict[date, str]:
        unique_dates = sorted({ts.date() for ts in snapshot_dates if not pd.isna(ts)})
        if not unique_dates:
            return {}
        try:
            from common.config_loader import load_config
            from service.market import (
                DbSentimentScoreProvider,
                build_default_macro_provider,
                build_snapshot,
                parse_market_regimes,
            )

            yaml_cfg = load_config() or {}
            market_regimes_cfg = parse_market_regimes(yaml_cfg.get("market_regimes"))
            if not getattr(market_regimes_cfg, "enabled", False):
                return {}
            macro_provider = build_default_macro_provider(yaml_cfg)
        except Exception:
            LOGGER.info("Segmentation par régime indisponible : fallback `all`.", exc_info=True)
            return {}

        resolved: dict[date, str] = {}
        for snapshot_date in unique_dates:
            try:
                snapshot = build_snapshot(
                    snapshot_date,
                    config=market_regimes_cfg,
                    execution_context="backtest",
                    macro_provider=macro_provider,
                    sentiment_score_provider=DbSentimentScoreProvider(snapshot_date, engine=self.engine),
                )
            except Exception:
                LOGGER.debug("Snapshot de régime introuvable pour %s ; fallback `all`.", snapshot_date, exc_info=True)
                continue
            resolved[snapshot_date] = normalize_market_regime_mode(getattr(snapshot, "mode", MARKET_REGIME_ALL))
        return resolved

    def load_dataset(
        self,
        *,
        start_date: date,
        end_date: date,
        horizon_days: int = 5,
        candidates_only: bool = True,
        include_market_regime: bool = True,
    ) -> pd.DataFrame:
        from sqlalchemy import text

        score_columns = self._get_table_columns("stock_scores_history")
        if not score_columns:
            return pd.DataFrame()
        score_expr = (
            "COALESCE(final_score_walk_forward, final_score_sentiment, final_score)"
            if "final_score_walk_forward" in score_columns
            else "COALESCE(final_score_sentiment, final_score)"
        )
        candidate_clause = "AND is_candidate = 1" if candidates_only else ""
        scores_query = text(
            f"""
            SELECT snapshot_date, symbol, {score_expr} AS quant_score
            FROM stock_scores_history
            WHERE snapshot_date BETWEEN :start_date AND :end_date
              {candidate_clause}
              AND {score_expr} IS NOT NULL
            ORDER BY snapshot_date ASC, symbol ASC
            """
        )
        predictions_query = text(
            """
            SELECT symbol, prediction_date, predicted_proba, created_at
            FROM model_predictions
            WHERE prediction_date <= :end_date
              AND predicted_proba IS NOT NULL
            ORDER BY symbol ASC, prediction_date ASC, created_at ASC
            """
        )
        win_rates_query = text(
            """
            SELECT m.symbol, t.finished_at AS asof_date, m.directional_accuracy
            FROM model_metrics m
            JOIN model_training_run t ON m.run_id = t.run_id
            WHERE t.status = 'completed'
              AND m.directional_accuracy IS NOT NULL
              AND DATE(t.finished_at) <= :end_date
            ORDER BY m.symbol ASC, t.finished_at ASC, m.run_id ASC
            """
        )
        bars_query = text(
            """
            SELECT symbol, date AS bar_date, close AS close_price
            FROM stock_bars_daily
            WHERE date BETWEEN :start_date AND :end_date_plus_buffer
            ORDER BY symbol ASC, date ASC
            """
        )
        with self.engine.connect() as conn:
            scores = pd.read_sql_query(scores_query, conn, params={"start_date": start_date, "end_date": end_date})
            predictions = pd.read_sql_query(predictions_query, conn, params={"end_date": end_date})
            win_rates = pd.read_sql_query(win_rates_query, conn, params={"end_date": end_date})
            bars = pd.read_sql_query(
                bars_query,
                conn,
                params={
                    "start_date": start_date,
                    "end_date_plus_buffer": end_date + pd.Timedelta(days=max(int(horizon_days) * 4, 20)),
                },
            )
        if scores.empty or predictions.empty or win_rates.empty or bars.empty:
            return pd.DataFrame()

        scores = scores.copy()
        scores["snapshot_date"] = pd.to_datetime(scores["snapshot_date"])
        predictions = predictions.copy()
        predictions["prediction_date"] = pd.to_datetime(predictions["prediction_date"])
        win_rates = win_rates.copy()
        win_rates["asof_date"] = pd.to_datetime(win_rates["asof_date"])
        bars = bars.copy()
        bars["bar_date"] = pd.to_datetime(bars["bar_date"])
        bars = bars.sort_values(["symbol", "bar_date"]).reset_index(drop=True)
        bars["future_close_price"] = bars.groupby("symbol")["close_price"].shift(-int(horizon_days))
        bars["forward_return"] = (bars["future_close_price"] / bars["close_price"]) - 1.0
        bars = bars[["symbol", "bar_date", "forward_return"]].dropna(subset=["forward_return"])

        predictions = predictions.sort_values(["symbol", "prediction_date", "created_at"]).reset_index(drop=True)
        predictions = predictions.groupby(["symbol", "prediction_date"], as_index=False).last()
        win_rates = win_rates.sort_values(["symbol", "asof_date"]).reset_index(drop=True)
        win_rates = win_rates.groupby(["symbol", "asof_date"], as_index=False).last()
        scores = scores.sort_values(["symbol", "snapshot_date"]).reset_index(drop=True)

        enriched = pd.merge_asof(
            scores,
            predictions[["symbol", "prediction_date", "predicted_proba"]],
            by="symbol",
            left_on="snapshot_date",
            right_on="prediction_date",
            direction="backward",
        )
        enriched = pd.merge_asof(
            enriched.sort_values(["symbol", "snapshot_date"]),
            win_rates[["symbol", "asof_date", "directional_accuracy"]],
            by="symbol",
            left_on="snapshot_date",
            right_on="asof_date",
            direction="backward",
        )
        dataset = enriched.merge(
            bars,
            left_on=["symbol", "snapshot_date"],
            right_on=["symbol", "bar_date"],
            how="left",
        )
        dataset = dataset.rename(columns={"directional_accuracy": "historical_win_rate"})
        dataset = dataset[[
            "snapshot_date",
            "symbol",
            "quant_score",
            "predicted_proba",
            "historical_win_rate",
            "forward_return",
        ]].dropna()
        dataset = dataset.reset_index(drop=True)
        dataset["market_regime_mode"] = MARKET_REGIME_ALL
        if include_market_regime and not dataset.empty:
            resolved_modes = self._resolve_market_regime_modes(dataset["snapshot_date"].tolist())
            if resolved_modes:
                dataset["market_regime_mode"] = (
                    dataset["snapshot_date"].dt.date.map(resolved_modes).fillna("normal")
                )
        return dataset

    def _build_run_summary(
        self,
        *,
        calibration: CalibrationResult,
        dataset: pd.DataFrame,
        daily_returns: np.ndarray,
        best_weights: dict[str, float],
        output_path: Path,
        horizon_days: int,
        lookback_months: int | None,
        calibration_batch_id: str | None,
        min_live_observations: int,
        min_live_snapshot_days: int,
        min_live_symbols: int,
    ) -> EmpiricalRiskCalibrationRun:
        eligible_for_live, eligibility_reason, distinct_snapshot_days, distinct_symbols = _evaluate_live_governance(
            dataset,
            min_observations=min_live_observations,
            min_snapshot_days=min_live_snapshot_days,
            min_symbols=min_live_symbols,
        )
        equity_curve = 100_000.0 * np.cumprod(1.0 + daily_returns)
        final_value = float(equity_curve[-1]) if equity_curve.size else 100_000.0
        peak = np.maximum.accumulate(equity_curve) if equity_curve.size else np.asarray([100_000.0])
        drawdowns = (equity_curve / peak) - 1.0 if equity_curve.size else np.asarray([0.0])
        return EmpiricalRiskCalibrationRun(
            start_date=calibration.window_start or pd.Timestamp(dataset["snapshot_date"].min()).date(),
            end_date=calibration.window_end or pd.Timestamp(dataset["snapshot_date"].max()).date(),
            observations_evaluated=len(dataset),
            scenarios_evaluated=len(calibration.candidates),
            latest_best_scenario_name=(
                f"score_{best_weights['score_weight']:.2f}_pred_{best_weights['prediction_weight']:.2f}"
                f"__kelly_{best_weights['kelly_fraction_multiplier']:.2f}"
                f"__minp_{best_weights['min_effective_probability']:.2f}"
                f"__payoff_{best_weights['assumed_payoff_ratio']:.2f}"
            ),
            metric_name=calibration.metric_name,
            metric_value=float(calibration.metric_value),
            final_value=final_value,
            total_return_pct=((final_value / 100_000.0) - 1.0) * 100.0,
            sharpe_ratio=metric_strategy_sharpe(daily_returns),
            max_drawdown_pct=float(np.min(drawdowns) * 100.0) if drawdowns.size else 0.0,
            calibration_batch_id=calibration_batch_id,
            segment_key=_build_segment_key(
                market_regime_mode=calibration.market_regime_mode,
                horizon_days=horizon_days,
                lookback_months=lookback_months,
            ),
            horizon_days=int(horizon_days),
            lookback_months=lookback_months,
            distinct_snapshot_days=distinct_snapshot_days,
            distinct_symbols=distinct_symbols,
            eligible_for_live=eligible_for_live,
            eligibility_reason=eligibility_reason,
            best_weights={key: float(value) for key, value in best_weights.items()},
            artifact_dir=str(output_path),
            market_regime_mode=normalize_market_regime_mode(calibration.market_regime_mode),
        )

    def walk_forward_backtest(
        self,
        *,
        start_date: date,
        end_date: date,
        output_dir: str | Path,
        top_n: int = 20,
        horizon_days: int = 5,
        metric_name: str = "sharpe",
        conviction_grid_step: float = 0.1,
        kelly_fraction_multipliers: Sequence[float] = (0.10, 0.25, 0.50),
        min_effective_probabilities: Sequence[float] = (0.50, 0.52, 0.55),
        assumed_payoff_ratios: Sequence[float] = (1.0, 1.5, 2.0),
        candidates_only: bool = True,
        market_regime_mode: str = MARKET_REGIME_ALL,
        dataset: pd.DataFrame | None = None,
        lookback_months: int | None = None,
        calibration_batch_id: str | None = None,
        min_live_observations: int = 250,
        min_live_snapshot_days: int = 20,
        min_live_symbols: int = 10,
    ) -> tuple[EmpiricalRiskCalibrationRun, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        resolved_market_regime_mode = normalize_market_regime_mode(market_regime_mode)
        work_dataset = dataset.copy() if dataset is not None else self.load_dataset(
            start_date=start_date,
            end_date=end_date,
            horizon_days=horizon_days,
            candidates_only=candidates_only,
        )
        if resolved_market_regime_mode != MARKET_REGIME_ALL and "market_regime_mode" in work_dataset.columns:
            work_dataset = work_dataset.loc[
                work_dataset["market_regime_mode"].astype(str).str.lower() == resolved_market_regime_mode
            ].reset_index(drop=True)
        if work_dataset.empty:
            raise ValueError(
                "EmpiricalRiskCalibrator : dataset vide, calibration impossible"
                f" pour le segment régime `{resolved_market_regime_mode}`."
            )

        calibration = calibrate_conviction_kelly(
            snapshot_dates=work_dataset["snapshot_date"].tolist(),
            quant_scores=work_dataset["quant_score"].tolist(),
            predicted_proba=work_dataset["predicted_proba"].tolist(),
            historical_win_rate=work_dataset["historical_win_rate"].tolist(),
            forward_returns=work_dataset["forward_return"].tolist(),
            metric_name=metric_name,
            conviction_grid_step=conviction_grid_step,
            kelly_fraction_multipliers=kelly_fraction_multipliers,
            min_effective_probabilities=min_effective_probabilities,
            assumed_payoff_ratios=assumed_payoff_ratios,
            top_n=top_n,
            window=(start_date, end_date),
            market_regime_mode=resolved_market_regime_mode,
        )

        best_weights = calibration.best_weights
        fused = np.asarray(
            [
                fuse(
                    quant_score=float(row.quant_score),
                    predicted_proba=float(row.predicted_proba),
                    weights=ConvictionWeights(
                        score_weight=float(best_weights["score_weight"]),
                        prediction_weight=float(best_weights["prediction_weight"]),
                    ),
                )
                for row in work_dataset.itertuples(index=False)
            ],
            dtype=float,
        )
        kelly_fraction = _compute_kelly_fraction(
            work_dataset["predicted_proba"].to_numpy(dtype=float),
            work_dataset["historical_win_rate"].to_numpy(dtype=float),
            kelly_fraction_multiplier=float(best_weights["kelly_fraction_multiplier"]),
            min_effective_probability=float(best_weights["min_effective_probability"]),
            assumed_payoff_ratio=float(best_weights["assumed_payoff_ratio"]),
        )
        daily_returns = _weighted_daily_strategy_returns(
            work_dataset["snapshot_date"].tolist(),
            fused,
            kelly_fraction,
            work_dataset["forward_return"].to_numpy(dtype=float),
            top_n=int(best_weights.get("top_n", top_n)),
        )
        run_summary = self._build_run_summary(
            calibration=calibration,
            dataset=work_dataset,
            daily_returns=daily_returns,
            best_weights=best_weights,
            output_path=output_path,
            horizon_days=horizon_days,
            lookback_months=lookback_months,
            calibration_batch_id=calibration_batch_id,
            min_live_observations=min_live_observations,
            min_live_snapshot_days=min_live_snapshot_days,
            min_live_symbols=min_live_symbols,
        )
        calibration_run_id = persist_calibration_run(calibration, engine=self.engine, run_summary=run_summary)
        daily_returns_df = pd.DataFrame(
            {
                "snapshot_date": sorted(pd.to_datetime(pd.Series(work_dataset["snapshot_date"]).dropna().unique())),
                "strategy_return": daily_returns,
            }
        )
        candidates_df = pd.DataFrame(
            {
                "metric_value": [candidate.metric_value for candidate in calibration.candidates],
                **{
                    key: [candidate.weights.get(key) for candidate in calibration.candidates]
                    for key in calibration.best_weights
                },
            }
        )
        dataset_csv = output_path / "conviction_kelly_dataset.csv"
        candidates_csv = output_path / "conviction_kelly_candidates.csv"
        daily_returns_csv = output_path / "conviction_kelly_daily_returns.csv"
        work_dataset.to_csv(dataset_csv, index=False)
        candidates_df.to_csv(candidates_csv, index=False)
        daily_returns_df.to_csv(daily_returns_csv, index=False)
        artifacts = {
            "dataset_csv": str(dataset_csv),
            "candidates_csv": str(candidates_csv),
            "daily_returns_csv": str(daily_returns_csv),
        }
        run_summary = EmpiricalRiskCalibrationRun(
            **{
                **run_summary.__dict__,
                "calibration_run_id": calibration_run_id,
            }
        )
        return run_summary, candidates_df, daily_returns_df, work_dataset, artifacts

    def walk_forward_backtests_by_regime(
        self,
        *,
        start_date: date,
        end_date: date,
        output_dir: str | Path,
        top_n: int = 20,
        horizon_days: int = 5,
        metric_name: str = "sharpe",
        conviction_grid_step: float = 0.1,
        kelly_fraction_multipliers: Sequence[float] = (0.10, 0.25, 0.50),
        min_effective_probabilities: Sequence[float] = (0.50, 0.52, 0.55),
        assumed_payoff_ratios: Sequence[float] = (1.0, 1.5, 2.0),
        candidates_only: bool = True,
    ) -> dict[str, tuple[EmpiricalRiskCalibrationRun, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]]:
        dataset = self.load_dataset(
            start_date=start_date,
            end_date=end_date,
            horizon_days=horizon_days,
            candidates_only=candidates_only,
        )
        if dataset.empty:
            raise ValueError("EmpiricalRiskCalibrator : dataset vide, calibration impossible.")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        regime_modes = [
            mode
            for mode in sorted({normalize_market_regime_mode(value) for value in dataset.get("market_regime_mode", pd.Series(dtype=str)).tolist()})
            if mode != MARKET_REGIME_ALL
        ]
        results: dict[str, tuple[EmpiricalRiskCalibrationRun, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]] = {}
        for regime_mode in [MARKET_REGIME_ALL, *regime_modes]:
            segment_output = output_path if regime_mode == MARKET_REGIME_ALL else output_path / regime_mode
            try:
                results[regime_mode] = self.walk_forward_backtest(
                    start_date=start_date,
                    end_date=end_date,
                    output_dir=segment_output,
                    top_n=top_n,
                    horizon_days=horizon_days,
                    metric_name=metric_name,
                    conviction_grid_step=conviction_grid_step,
                    kelly_fraction_multipliers=kelly_fraction_multipliers,
                    min_effective_probabilities=min_effective_probabilities,
                    assumed_payoff_ratios=assumed_payoff_ratios,
                    candidates_only=candidates_only,
                    market_regime_mode=regime_mode,
                    dataset=dataset,
                )
            except ValueError:
                if regime_mode == MARKET_REGIME_ALL:
                    raise
                LOGGER.info("Segment régime `%s` ignoré : dataset insuffisant.", regime_mode, exc_info=True)
        return results

    def walk_forward_backtests_by_segment(
        self,
        *,
        end_date: date,
        output_dir: str | Path,
        horizon_days_values: Sequence[int],
        lookback_months_values: Sequence[int],
        top_n: int = 20,
        metric_name: str = "sharpe",
        conviction_grid_step: float = 0.1,
        kelly_fraction_multipliers: Sequence[float] = (0.10, 0.25, 0.50),
        min_effective_probabilities: Sequence[float] = (0.50, 0.52, 0.55),
        assumed_payoff_ratios: Sequence[float] = (1.0, 1.5, 2.0),
        candidates_only: bool = True,
        min_live_observations: int = 250,
        min_live_snapshot_days: int = 20,
        min_live_symbols: int = 10,
        calibration_batch_id: str | None = None,
    ) -> dict[str, tuple[EmpiricalRiskCalibrationRun, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        resolved_batch_id = calibration_batch_id or f"wcb-{uuid.uuid4().hex[:12]}"
        results: dict[str, tuple[EmpiricalRiskCalibrationRun, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]] = {}
        for lookback_months in sorted({int(value) for value in lookback_months_values if int(value) > 0}):
            segment_start_date = _subtract_months(end_date, lookback_months)
            for horizon_days in sorted({int(value) for value in horizon_days_values if int(value) > 0}):
                dataset = self.load_dataset(
                    start_date=segment_start_date,
                    end_date=end_date,
                    horizon_days=horizon_days,
                    candidates_only=candidates_only,
                )
                if dataset.empty:
                    LOGGER.info(
                        "Segment horizon=%sd window=%sm ignoré : dataset vide.",
                        horizon_days,
                        lookback_months,
                    )
                    continue
                regime_modes = [
                    mode
                    for mode in sorted(
                        {
                            normalize_market_regime_mode(value)
                            for value in dataset.get("market_regime_mode", pd.Series(dtype=str)).tolist()
                        }
                    )
                    if mode != MARKET_REGIME_ALL
                ]
                for regime_mode in [MARKET_REGIME_ALL, *regime_modes]:
                    segment_key = _build_segment_key(
                        market_regime_mode=regime_mode,
                        horizon_days=horizon_days,
                        lookback_months=lookback_months,
                    )
                    segment_output = output_path / f"window_{lookback_months}m" / f"horizon_{horizon_days}d" / regime_mode
                    try:
                        results[segment_key] = self.walk_forward_backtest(
                            start_date=segment_start_date,
                            end_date=end_date,
                            output_dir=segment_output,
                            top_n=top_n,
                            horizon_days=horizon_days,
                            metric_name=metric_name,
                            conviction_grid_step=conviction_grid_step,
                            kelly_fraction_multipliers=kelly_fraction_multipliers,
                            min_effective_probabilities=min_effective_probabilities,
                            assumed_payoff_ratios=assumed_payoff_ratios,
                            candidates_only=candidates_only,
                            market_regime_mode=regime_mode,
                            dataset=dataset,
                            lookback_months=lookback_months,
                            calibration_batch_id=resolved_batch_id,
                            min_live_observations=min_live_observations,
                            min_live_snapshot_days=min_live_snapshot_days,
                            min_live_symbols=min_live_symbols,
                        )
                    except ValueError:
                        if regime_mode == MARKET_REGIME_ALL:
                            raise
                        LOGGER.info(
                            "Segment régime `%s` / horizon=%sd / fenêtre=%sm ignoré : dataset insuffisant.",
                            regime_mode,
                            horizon_days,
                            lookback_months,
                            exc_info=True,
                        )
        if not results:
            raise ValueError("EmpiricalRiskCalibrator : aucun segment exploitable pour la calibration multi-horizon/fenêtre.")
        return results


# ---------------------------------------------------------------------------
# Persistance (opt-in, ne dépend pas du moteur de calcul)
# ---------------------------------------------------------------------------

def persist_calibration_run(
    result: CalibrationResult,
    *,
    engine: Any,
    git_sha: str | None = None,
    run_id: str | None = None,
    run_summary: EmpiricalRiskCalibrationRun | None = None,
) -> str:
    """Insère ``result`` dans ``weights_calibration_runs``.

    ``engine`` doit être un SQLAlchemy ``Engine`` ; isolation explicite afin
    de garder le module testable sans DB.
    """
    from sqlalchemy import (
        inspect,
        text,  # import paresseux
    )

    rid = run_id or f"wcr-{uuid.uuid4().hex[:12]}"
    payload = result.to_payload()
    try:
        available_columns = {str(column["name"]) for column in inspect(engine).get_columns("weights_calibration_runs")}
    except Exception:
        available_columns = {
            "run_id",
            "calibrated_at",
            "scope",
            "window_start",
            "window_end",
            "metric_name",
            "metric_value",
            "best_weights",
            "candidates",
            "git_sha",
            "schema_version",
            "market_regime_mode",
            "calibration_batch_id",
            "segment_key",
            "horizon_days",
            "lookback_months",
            "distinct_snapshot_days",
            "distinct_symbols",
            "eligible_for_live",
            "eligibility_reason",
            "observations_evaluated",
            "scenarios_evaluated",
            "latest_best_scenario_name",
            "final_value",
            "total_return_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
            "artifact_dir",
        }
    values: dict[str, Any] = {
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
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "market_regime_mode": normalize_market_regime_mode(result.market_regime_mode),
    }
    if run_summary is not None:
        values.update(
            {
                "calibration_batch_id": run_summary.calibration_batch_id,
                "segment_key": run_summary.segment_key,
                "horizon_days": int(run_summary.horizon_days),
                "lookback_months": int(run_summary.lookback_months) if run_summary.lookback_months is not None else None,
                "distinct_snapshot_days": int(run_summary.distinct_snapshot_days),
                "distinct_symbols": int(run_summary.distinct_symbols),
                "eligible_for_live": bool(run_summary.eligible_for_live),
                "eligibility_reason": run_summary.eligibility_reason,
                "observations_evaluated": int(run_summary.observations_evaluated),
                "scenarios_evaluated": int(run_summary.scenarios_evaluated),
                "latest_best_scenario_name": run_summary.latest_best_scenario_name,
                "final_value": float(run_summary.final_value),
                "total_return_pct": float(run_summary.total_return_pct),
                "sharpe_ratio": float(run_summary.sharpe_ratio),
                "max_drawdown_pct": float(run_summary.max_drawdown_pct),
                "artifact_dir": run_summary.artifact_dir,
            }
        )
    insert_columns = [column for column in values if column in available_columns]
    insert_params = {column: values[column] for column in insert_columns}
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO weights_calibration_runs
                    ({columns})
                VALUES
                    ({placeholders})
                """
                .format(
                    columns=", ".join(insert_columns),
                    placeholders=", ".join(f":{column}" for column in insert_columns),
                )
            ),
            insert_params,
        )
    return rid


def persist_segment_drifts(drifts: Sequence[CalibrationSegmentDrift], *, engine: Any) -> int:
    if not drifts:
        return 0
    from sqlalchemy import inspect, text

    try:
        available_columns = {
            str(column["name"]) for column in inspect(engine).get_columns("weights_calibration_segment_drifts")
        }
    except Exception:
        available_columns = {
            "run_id",
            "compared_at",
            "comparison_kind",
            "calibration_batch_id",
            "source_run_id",
            "target_run_id",
            "source_segment_key",
            "target_segment_key",
            "metric_name",
            "metric_delta",
            "final_value_drift_pct",
            "payload",
            "schema_version",
        }
    rows: list[dict[str, Any]] = []
    for drift in drifts:
        payload = {
            "run_id": f"wcsd-{uuid.uuid4().hex[:12]}",
            "compared_at": datetime.utcnow(),
            "comparison_kind": drift.comparison_kind,
            "calibration_batch_id": drift.calibration_batch_id,
            "source_run_id": drift.source_run_id,
            "target_run_id": drift.target_run_id,
            "source_segment_key": drift.source_segment_key,
            "target_segment_key": drift.target_segment_key,
            "metric_name": drift.metric_name,
            "metric_delta": drift.metric_delta,
            "final_value_drift_pct": drift.final_value_drift_pct,
            "payload": json.dumps(drift.payload),
            "schema_version": SEGMENT_DRIFT_SCHEMA_VERSION,
        }
        rows.append({column: payload[column] for column in payload if column in available_columns})
    if not rows:
        return 0
    insert_columns = list(rows[0])
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO weights_calibration_segment_drifts
                    ({columns})
                VALUES
                    ({placeholders})
                """.format(
                    columns=", ".join(insert_columns),
                    placeholders=", ".join(f":{column}" for column in insert_columns),
                )
            ),
            rows,
        )
    return len(rows)


__all__ = [
    "CalibrationResult",
    "CalibrationCandidate",
    "EmpiricalRiskCalibrationRun",
    "CalibrationSegmentDrift",
    "EmpiricalRiskCalibrator",
    "MARKET_REGIME_ALL",
    "METRICS",
    "RISK_METRICS",
    "calibrate_conviction",
    "calibrate_conviction_kelly",
    "calibrate_sentiment",
    "compute_segment_drifts",
    "metric_information_coefficient",
    "metric_hit_rate",
    "metric_strategy_log_growth",
    "metric_strategy_sharpe",
    "normalize_market_regime_mode",
    "persist_calibration_run",
    "persist_segment_drifts",
]

