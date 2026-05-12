"""Presets de seuils de diagnostic Alpha Scanner selon style opératoire et contexte marché.

Ici, ``market_regime`` signifie seulement un **niveau de sélectivité des presets
de diagnostic** (marché normal / faible / très sélectif) utilisé pour ajuster
les seuils de fraîcheur et de couverture des dépendances de l'Alpha Scanner.

Ce n'est pas le même concept que les modes de régime market-aware d'exécution :
``normal`` / ``capital_preservation`` / ``close_only`` / ``cash_only``.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

MarketRegime = Literal["normal", "weak", "very_selective"]
PresetStyle = Literal["swing_cash_pro", "aggressive", "tolerant"]

PRESET_STYLE_LABELS: dict[PresetStyle, str] = {
    "swing_cash_pro": "Swing Cash Pro",
    "aggressive": "Agressif",
    "tolerant": "Tolérant",
}

MARKET_REGIME_LABELS: dict[MarketRegime, str] = {
    "normal": "Marché normal",
    "weak": "Marché faible",
    "very_selective": "Marché très sélectif",
}

BASE_STYLE_THRESHOLDS: dict[PresetStyle, dict[str, dict[str, float]]] = {
    "swing_cash_pro": {
        "sync_latest_quotes": {
            "coverage_warn_pct": 85.0,
            "coverage_error_pct": 60.0,
            "max_age_warn_days": 1.0,
            "max_age_error_days": 3.0,
        },
        "sync_earnings_calendar": {
            "coverage_warn_pct": 15.0,
            "coverage_error_pct": 5.0,
            "min_horizon_warn_days": 14.0,
            "min_horizon_error_days": 7.0,
        },
    },
    "aggressive": {
        "sync_latest_quotes": {
            "coverage_warn_pct": 75.0,
            "coverage_error_pct": 45.0,
            "max_age_warn_days": 2.0,
            "max_age_error_days": 5.0,
        },
        "sync_earnings_calendar": {
            "coverage_warn_pct": 10.0,
            "coverage_error_pct": 3.0,
            "min_horizon_warn_days": 10.0,
            "min_horizon_error_days": 5.0,
        },
    },
    "tolerant": {
        "sync_latest_quotes": {
            "coverage_warn_pct": 65.0,
            "coverage_error_pct": 35.0,
            "max_age_warn_days": 3.0,
            "max_age_error_days": 7.0,
        },
        "sync_earnings_calendar": {
            "coverage_warn_pct": 7.0,
            "coverage_error_pct": 2.0,
            "min_horizon_warn_days": 7.0,
            "min_horizon_error_days": 3.0,
        },
    },
}

REGIME_ADJUSTMENTS: dict[MarketRegime, dict[str, dict[str, float]]] = {
    "normal": {
        "sync_latest_quotes": {
            "coverage_warn_pct": 0.0,
            "coverage_error_pct": 0.0,
            "max_age_warn_days": 0.0,
            "max_age_error_days": 0.0,
        },
        "sync_earnings_calendar": {
            "coverage_warn_pct": 0.0,
            "coverage_error_pct": 0.0,
            "min_horizon_warn_days": 0.0,
            "min_horizon_error_days": 0.0,
        },
    },
    "weak": {
        "sync_latest_quotes": {
            "coverage_warn_pct": 5.0,
            "coverage_error_pct": 5.0,
            "max_age_warn_days": -1.0,
            "max_age_error_days": -1.0,
        },
        "sync_earnings_calendar": {
            "coverage_warn_pct": 3.0,
            "coverage_error_pct": 2.0,
            "min_horizon_warn_days": 3.0,
            "min_horizon_error_days": 2.0,
        },
    },
    "very_selective": {
        "sync_latest_quotes": {
            "coverage_warn_pct": 10.0,
            "coverage_error_pct": 10.0,
            "max_age_warn_days": -1.0,
            "max_age_error_days": -2.0,
        },
        "sync_earnings_calendar": {
            "coverage_warn_pct": 5.0,
            "coverage_error_pct": 3.0,
            "min_horizon_warn_days": 7.0,
            "min_horizon_error_days": 3.0,
        },
    },
}


def _clamp_threshold(metric_key: str, value: float) -> float:
    if metric_key.endswith("_pct"):
        return max(0.0, min(value, 100.0))
    if metric_key.endswith("_days"):
        return max(0.0, value)
    return max(0.0, value)


def get_alpha_scanner_threshold_preset(
    *,
    style: PresetStyle,
    market_regime: MarketRegime,
) -> dict[str, dict[str, float]]:
    thresholds = deepcopy(BASE_STYLE_THRESHOLDS[style])
    adjustments = REGIME_ADJUSTMENTS[market_regime]
    for step_key, metrics in thresholds.items():
        for metric_key, metric_value in metrics.items():
            adjusted_value = metric_value + adjustments.get(step_key, {}).get(metric_key, 0.0)
            thresholds[step_key][metric_key] = float(_clamp_threshold(metric_key, adjusted_value))
    return thresholds


DEFAULT_PRESET_STYLE: PresetStyle = "swing_cash_pro"
DEFAULT_MARKET_REGIME: MarketRegime = "normal"
DEFAULT_ALPHA_SCANNER_DEPENDENCY_THRESHOLDS = get_alpha_scanner_threshold_preset(
    style=DEFAULT_PRESET_STYLE,
    market_regime=DEFAULT_MARKET_REGIME,
)

