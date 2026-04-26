"""Utilitaires walk-forward pour charger et appliquer les meilleurs poids calibrés."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from event_sentiment.signal_aggregator import SentimentSignalAggregator

LOGGER = logging.getLogger(__name__)

_WEIGHT_FILENAMES = (
    "latest_best_weights.json",
    "walk_forward_best_weights_latest.json",
    "champion_weights.json",
)


@dataclass(frozen=True, slots=True)
class WalkForwardWeights:
    sentiment_weight: float
    macro_weight: float
    quant_weight: float
    calibration_run_id: str | None = None
    calibration_source: str | None = None
    scenario_name: str | None = None
    artifact_path: str | None = None


def _candidate_roots(search_roots: Iterable[Path] | None = None) -> list[Path]:
    roots = list(search_roots or [])
    if not roots:
        roots = [
            Path("artifacts/sentiment_walk_forward"),
            Path("artifacts/sentiment_calibration"),
            Path("artifacts"),
        ]
    return roots


def _extract_weight(payload: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = payload.get(name)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def load_walk_forward_weights(path: Path) -> WalkForwardWeights | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        LOGGER.warning("Impossible de lire les poids walk-forward depuis %s.", path, exc_info=True)
        return None
    sentiment_weight = _extract_weight(payload, "sentiment_weight", "scenario_sentiment_weight")
    macro_weight = _extract_weight(payload, "macro_weight", "scenario_macro_weight")
    quant_weight = _extract_weight(payload, "quant_weight", "scenario_quant_weight")
    if sentiment_weight is None or macro_weight is None or quant_weight is None:
        return None
    return WalkForwardWeights(
        sentiment_weight=sentiment_weight,
        macro_weight=macro_weight,
        quant_weight=quant_weight,
        calibration_run_id=str(payload.get("calibration_run_id")) if payload.get("calibration_run_id") is not None else None,
        calibration_source=str(payload.get("calibration_source") or payload.get("best_scenario_name") or "walk_forward"),
        scenario_name=str(payload.get("scenario_name") or payload.get("best_scenario_name")) if payload.get("scenario_name") or payload.get("best_scenario_name") else None,
        artifact_path=str(path),
    )


def resolve_latest_walk_forward_weights(search_roots: Iterable[Path] | None = None) -> WalkForwardWeights | None:
    candidates: list[Path] = []
    for root in _candidate_roots(search_roots):
        if not root.exists():
            continue
        for filename in _WEIGHT_FILENAMES:
            candidates.extend(root.rglob(filename))
    existing_candidates = [path for path in candidates if path.is_file()]
    if not existing_candidates:
        return None
    latest_path = max(existing_candidates, key=lambda path: path.stat().st_mtime)
    return load_walk_forward_weights(latest_path)


def apply_walk_forward_weights(scores_df: pd.DataFrame, weights: WalkForwardWeights | None) -> pd.DataFrame:
    if scores_df.empty or weights is None:
        return scores_df.copy()

    result = scores_df.copy()
    quant = pd.Series(pd.to_numeric(result.get("final_score"), errors="coerce"), index=result.index, dtype=float).fillna(0.0).clip(0.0, 1.0)

    if "company_idio_score" not in result.columns:
        result["company_idio_score"] = pd.to_numeric(result.get("sentiment_net_agg"), errors="coerce")
    if "macro_regime_score" not in result.columns:
        result["macro_regime_score"] = pd.to_numeric(result.get("sector_impact_agg"), errors="coerce")

    if "company_idio_signal_norm" in result.columns:
        company_norm = pd.Series(pd.to_numeric(result["company_idio_signal_norm"], errors="coerce"), index=result.index, dtype=float)
    else:
        company_norm = SentimentSignalAggregator._normalize_signed_signal(result.get("company_idio_score", pd.Series(index=result.index, dtype=float)))
    if "macro_regime_signal_norm" in result.columns:
        macro_norm = pd.Series(pd.to_numeric(result["macro_regime_signal_norm"], errors="coerce"), index=result.index, dtype=float)
    else:
        macro_norm = SentimentSignalAggregator._normalize_signed_signal(result.get("macro_regime_score", pd.Series(index=result.index, dtype=float)))

    company_norm = company_norm.fillna(0.5).clip(0.0, 1.0)
    macro_norm = macro_norm.fillna(0.5).clip(0.0, 1.0)

    result["company_idio_signal_norm"] = company_norm
    result["macro_regime_signal_norm"] = macro_norm
    result["company_idio_component"] = (weights.sentiment_weight * company_norm).clip(0.0, 1.0)
    result["macro_regime_component"] = (weights.macro_weight * macro_norm).clip(0.0, 1.0)
    result["quant_component"] = (weights.quant_weight * quant).clip(0.0, 1.0)
    result["final_score_walk_forward"] = (
        result["company_idio_component"] + result["macro_regime_component"] + result["quant_component"]
    ).clip(0.0, 1.0)
    result["walk_forward_sentiment_weight"] = weights.sentiment_weight
    result["walk_forward_macro_weight"] = weights.macro_weight
    result["walk_forward_quant_weight"] = weights.quant_weight
    result["calibration_run_id"] = weights.calibration_run_id
    result["calibration_source"] = weights.calibration_source or "walk_forward"
    result["score_source"] = "final_score_walk_forward"
    return result

