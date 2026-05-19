"""Helpers partagés d'explicabilité candidat pour le module ``selector``.

Le but est de figer un contrat unique réutilisable par :
- le ``run_summary`` live/CLI ;
- la persistance / lecture IHM depuis ``stock_scores`` ;
- les futurs endpoints/API sans dupliquer la logique de formatage.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import pandas as pd


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (str, bytes, dict, list, tuple, set)):
        return False
    try:
        return bool(pd.isna(cast(Any, value)))
    except Exception:
        return False


def _clean_text(value: object) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _clean_int(value: object) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _clean_float(value: object, *, digits: int = 4) -> float | None:
    if _is_missing(value):
        return None
    try:
        return round(float(str(value)), digits)
    except (TypeError, ValueError):
        return None


def _clean_date(value: object) -> str | None:
    if _is_missing(value):
        return None
    timestamp = pd.to_datetime(cast(Any, value), errors="coerce", utc=False)
    if not isinstance(timestamp, pd.Timestamp) or pd.isna(timestamp):
        return None
    return timestamp.date().isoformat()


def build_candidate_explainability_payload(row: Mapping[str, object]) -> dict[str, object]:
    """Construit un payload canonique d'explicabilité pour un candidat selector."""
    return {
        "identity": {
            "symbol": _clean_text(row.get("symbol")),
            "sector": _clean_text(row.get("sector")),
            "rank": _clean_int(row.get("rank")),
            "candidate_rank": _clean_int(row.get("candidate_rank")),
        },
        "score_inputs": {
            "trend_score": _clean_float(row.get("trend_score")),
            "vcp_score": _clean_float(row.get("vcp_score")),
            "total_score": _clean_float(row.get("total_score")),
            "relative_strength_index": _clean_float(row.get("relative_strength_index")),
        },
        "score_components": {
            "trend_vcp_component": _clean_float(row.get("trend_vcp_component")),
            "total_score_component": _clean_float(row.get("total_score_component")),
            "rsi_component": _clean_float(row.get("rsi_component")),
        },
        "score_outputs": {
            "raw_final_score": _clean_float(row.get("raw_final_score")),
            "final_score": _clean_float(row.get("final_score")),
            "normalized_total_score": _clean_float(row.get("normalized_total_score")),
            "normalized_rsi": _clean_float(row.get("normalized_rsi")),
            "total_score_neutralized": _clean_float(row.get("total_score_neutralized")),
            "relative_strength_index_neutralized": _clean_float(row.get("relative_strength_index_neutralized")),
        },
        "technical_context": {
            "latest_close": _clean_float(row.get("latest_close")),
            "avg_dollar_volume_20d": _clean_float(row.get("avg_dollar_volume_20d")),
            "liquidity_val": _clean_float(row.get("liquidity_val")),
            "atr_pct_20": _clean_float(row.get("atr_pct_20")),
            "weekly_trend_score": _clean_float(row.get("weekly_trend_score")),
            "high_52w_proximity": _clean_float(row.get("high_52w_proximity")),
            "volatility_ratio": _clean_float(row.get("volatility_ratio")),
            "history_days": _clean_int(row.get("history_days")),
        },
        "risk_context": {
            "market_cap": _clean_float(row.get("market_cap")),
            "beta_126": _clean_float(row.get("beta_126")),
            "spread_bps": _clean_float(row.get("spread_bps")),
        },
        "earnings_context": {
            "earnings_date": _clean_date(row.get("earnings_date")),
            "days_to_earnings": _clean_int(row.get("days_to_earnings")),
            "earnings_blackout": _clean_int(row.get("earnings_blackout")),
        },
        "quality_context": {
            "anomaly_count": _clean_int(row.get("anomaly_count")),
            "missing_days_count": _clean_int(row.get("missing_days_count")),
            "sanitizer_status": _clean_text(row.get("sanitizer_status")),
        },
        "selection_context": {
            "selector_signal_mode": _clean_text(row.get("selector_signal_mode")),
            "selection_explanation": _clean_text(row.get("selection_explanation")),
        },
    }


__all__ = ["build_candidate_explainability_payload"]

