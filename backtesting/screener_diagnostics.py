"""Diagnostics PIT du screener jusqu'au portefeuille cible."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import product
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.engine import Engine

from backtesting.backfill_scores_history import BackfillScoresHistoryService
from database.connection import get_sqlalchemy_engine
from event_sentiment.signal_aggregator import SentimentBoostConfig
from risk_management.config import RiskConfig
from risk_management.models import CandidateScore, PortfolioEntry, PriceInfo
from risk_management.portfolio_builder import PortfolioBuilder
from screener.models import ScreenerConfig
from selector.alpha_scanner import AlphaScannerConfig

LOGGER = logging.getLogger(__name__)
DEFAULT_FORWARD_HORIZONS: tuple[int, ...] = (5, 10, 20)
DEFAULT_RECOMMENDATION_HORIZON = 20
DEFAULT_PILLAR_WEIGHTS: dict[str, float] = {
    "robustness": 0.40,
    "survival": 0.30,
    "forward_quality": 0.30,
}
OBJECTIVE_PROFILE_ORDER = [
    "robust",
    "offensive",
    "bear_defensive",
    "executable_compromise",
]
OBJECTIVE_PROFILES: dict[str, dict[str, object]] = {
    "robust": {
        "label": "robuste",
        "description": "Privilégie la tenue cross-régimes, la stabilité et la résilience globale.",
        "pillar_weights": {"robustness": 0.55, "survival": 0.30, "forward_quality": 0.15},
        "recommendation_label": "best_robust_objective",
    },
    "offensive": {
        "label": "offensif",
        "description": "Recherche davantage d'upside forward en acceptant un peu plus de variance.",
        "pillar_weights": {"robustness": 0.05, "survival": 0.10, "forward_quality": 0.85},
        "recommendation_label": "best_offensive_objective",
    },
    "bear_defensive": {
        "label": "défensif bear-market",
        "description": "Surpondère la survie et la robustesse sur le sous-ensemble bear quand il existe.",
        "pillar_weights": {"robustness": 0.35, "survival": 0.45, "forward_quality": 0.20},
        "recommendation_label": "best_bear_defensive_objective",
    },
    "executable_compromise": {
        "label": "meilleur compromis exécutable",
        "description": "Favorise la conversion jusqu'au portefeuille cible et la capacité d'exécution.",
        "pillar_weights": {"robustness": 0.25, "survival": 0.55, "forward_quality": 0.20},
        "recommendation_label": "best_executable_compromise_objective",
    },
}
MARKET_REGIME_ORDER = ["bull", "bear", "range", "vol"]
DEFAULT_REGIME_TREND_LOOKBACK_DAYS = 60
DEFAULT_REGIME_LONG_MA_WINDOW = 200
DEFAULT_REGIME_VOL_WINDOW = 20
DEFAULT_REGIME_VOL_LOOKBACK_WINDOW = 252
DEFAULT_REGIME_BULL_BEAR_RETURN_THRESHOLD = 0.03
DEFAULT_REGIME_VOLATILITY_MULTIPLIER = 1.35
SCENARIO_PARAMETER_COLUMNS = [
    "liquidity_threshold_usd",
    "historical_range_lookback_days",
    "min_relative_strength_index",
    "min_historical_range_score",
]
_SELECTOR_SENTIMENT_COLUMNS: dict[str, Any] = {
    "symbol": None,
    "final_score": np.nan,
    "trend_score": np.nan,
    "vcp_score": np.nan,
    "total_score": np.nan,
    "sector": None,
    "liquidity_val": np.nan,
    "relative_strength_index": np.nan,
    "historical_range_score": np.nan,
    "anomaly_count": 0,
    "missing_days_count": 0,
    "is_candidate": 0,
}


@dataclass(frozen=True, slots=True)
class ScreenerDiagnosticsScenario:
    name: str
    screener_config: ScreenerConfig
    is_baseline: bool = False
    description: str | None = None

    def parameter_dict(self) -> dict[str, float | int]:
        return {
            "liquidity_threshold_usd": float(self.screener_config.liquidity_threshold_usd),
            "historical_range_lookback_days": int(self.screener_config.historical_range_lookback_days),
            "min_relative_strength_index": float(self.screener_config.min_relative_strength_index),
            "min_historical_range_score": float(self.screener_config.min_historical_range_score),
        }

    def to_record(self) -> dict[str, object]:
        return {
            "scenario_name": self.name,
            "is_baseline": self.is_baseline,
            "description": self.description,
            **self.parameter_dict(),
        }


@dataclass(frozen=True, slots=True)
class ScreenerDiagnosticsResult:
    trading_dates: tuple[date, ...]
    scenarios: tuple[ScreenerDiagnosticsScenario, ...]
    daily_metrics: pd.DataFrame
    summary_metrics: pd.DataFrame
    baseline_name: str | None = None
    market_regimes: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary_metrics_by_regime: pd.DataFrame = field(default_factory=pd.DataFrame)

    def scenario_frame(self) -> pd.DataFrame:
        return pd.DataFrame([scenario.to_record() for scenario in self.scenarios])

    def metadata(self) -> dict[str, object]:
        return {
            "baseline_name": self.baseline_name,
            "trading_dates": [trading_day.isoformat() for trading_day in self.trading_dates],
            "scenarios": [scenario.to_record() for scenario in self.scenarios],
            "market_regime_analysis_enabled": not self.market_regimes.empty,
            "market_regimes": sorted(self.market_regimes.get("market_regime", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()),
            "market_regime_config": {
                "trend_lookback_days": DEFAULT_REGIME_TREND_LOOKBACK_DAYS,
                "long_ma_window": DEFAULT_REGIME_LONG_MA_WINDOW,
                "vol_window": DEFAULT_REGIME_VOL_WINDOW,
                "vol_lookback_window": DEFAULT_REGIME_VOL_LOOKBACK_WINDOW,
                "bull_bear_return_threshold": DEFAULT_REGIME_BULL_BEAR_RETURN_THRESHOLD,
                "volatility_multiplier": DEFAULT_REGIME_VOLATILITY_MULTIPLIER,
                "priority_order": ["vol", "bull", "bear", "range"],
            },
        }


def _dedupe_preserve_order(values: Sequence[float | int] | None) -> list[float | int]:
    if not values:
        return []
    deduped: list[float | int] = []
    seen: set[float | int] = set()
    for value in values:
        if value in seen:
            continue
        deduped.append(value)
        seen.add(value)
    return deduped


def _scenario_config_key(config: ScreenerConfig) -> tuple[float, int, float, float]:
    return (
        float(config.liquidity_threshold_usd),
        int(config.historical_range_lookback_days),
        float(config.min_relative_strength_index),
        float(config.min_historical_range_score),
    )


def _format_float_token(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value).replace(".", "_")


def _format_liquidity_token(value: float) -> str:
    if value >= 1_000_000:
        millions = value / 1_000_000.0
        suffix = _format_float_token(millions)
        return f"{suffix}m"
    if value >= 1_000:
        thousands = value / 1_000.0
        suffix = _format_float_token(thousands)
        return f"{suffix}k"
    return _format_float_token(value)


def build_screener_oat_scenarios(
    base_config: ScreenerConfig,
    *,
    rs_values: Sequence[float] | None = None,
    range_lookback_values: Sequence[int] | None = None,
    historical_range_score_values: Sequence[float] | None = None,
    liquidity_threshold_values: Sequence[float] | None = None,
) -> list[ScreenerDiagnosticsScenario]:
    """Construit un set one-at-a-time de scénarios autour d'un baseline."""
    scenarios: list[ScreenerDiagnosticsScenario] = [
        ScreenerDiagnosticsScenario(
            name="baseline",
            screener_config=base_config,
            is_baseline=True,
            description="Paramètres de référence phase 3.",
        )
    ]
    seen = {_scenario_config_key(base_config)}

    def _append(config: ScreenerConfig, *, name: str, description: str) -> None:
        key = _scenario_config_key(config)
        if key in seen:
            return
        scenarios.append(
            ScreenerDiagnosticsScenario(
                name=name,
                screener_config=config,
                is_baseline=False,
                description=description,
            )
        )
        seen.add(key)

    for value in _dedupe_preserve_order(rs_values):
        numeric = float(value)
        if numeric == base_config.min_relative_strength_index:
            continue
        config = ScreenerConfig(**{**base_config.to_dict(), "min_relative_strength_index": numeric})
        _append(
            config,
            name=f"rs_{_format_float_token(numeric)}",
            description=f"Variation OAT de RS min à {numeric}.",
        )

    for value in _dedupe_preserve_order(range_lookback_values):
        numeric = int(value)
        if numeric == base_config.historical_range_lookback_days:
            continue
        config = ScreenerConfig(**{**base_config.to_dict(), "historical_range_lookback_days": numeric})
        _append(
            config,
            name=f"range_{numeric}d",
            description=f"Variation OAT du lookback range à {numeric} jours.",
        )

    for value in _dedupe_preserve_order(historical_range_score_values):
        numeric = float(value)
        if numeric == base_config.min_historical_range_score:
            continue
        config = ScreenerConfig(**{**base_config.to_dict(), "min_historical_range_score": numeric})
        _append(
            config,
            name=f"hist_score_{_format_float_token(numeric)}",
            description=f"Variation OAT du score minimal de range à {numeric}.",
        )

    for value in _dedupe_preserve_order(liquidity_threshold_values):
        numeric = float(value)
        if numeric == base_config.liquidity_threshold_usd:
            continue
        config = ScreenerConfig(**{**base_config.to_dict(), "liquidity_threshold_usd": numeric})
        _append(
            config,
            name=f"liq_{_format_liquidity_token(numeric)}",
            description=f"Variation OAT du seuil de liquidité à {numeric} USD.",
        )

    return scenarios


def build_screener_grid_scenarios(
    base_config: ScreenerConfig,
    *,
    rs_values: Sequence[float],
    range_lookback_values: Sequence[int],
    historical_range_score_values: Sequence[float],
    liquidity_threshold_values: Sequence[float],
    max_scenarios: int | None = None,
) -> list[ScreenerDiagnosticsScenario]:
    """Construit une grille complète de scénarios."""
    rs_list = [float(value) for value in _dedupe_preserve_order(rs_values)] or [base_config.min_relative_strength_index]
    range_list = [int(value) for value in _dedupe_preserve_order(range_lookback_values)] or [base_config.historical_range_lookback_days]
    hist_list = [float(value) for value in _dedupe_preserve_order(historical_range_score_values)] or [base_config.min_historical_range_score]
    liquidity_list = [float(value) for value in _dedupe_preserve_order(liquidity_threshold_values)] or [base_config.liquidity_threshold_usd]

    total_scenarios = len(rs_list) * len(range_list) * len(hist_list) * len(liquidity_list)
    if max_scenarios is not None and total_scenarios > max_scenarios:
        raise ValueError(
            f"La grille demande {total_scenarios} scénarios, au-delà de la limite {max_scenarios}."
        )

    scenarios: list[ScreenerDiagnosticsScenario] = []
    seen: set[tuple[float, int, float, float]] = set()
    baseline_key = _scenario_config_key(base_config)
    for rs_value, range_value, hist_value, liquidity_value in product(rs_list, range_list, hist_list, liquidity_list):
        config = ScreenerConfig(
            **{
                **base_config.to_dict(),
                "min_relative_strength_index": float(rs_value),
                "historical_range_lookback_days": int(range_value),
                "min_historical_range_score": float(hist_value),
                "liquidity_threshold_usd": float(liquidity_value),
            }
        )
        key = _scenario_config_key(config)
        if key in seen:
            continue
        is_baseline = key == baseline_key
        name = (
            "baseline"
            if is_baseline
            else "grid_rs_{rs}_range_{range_days}d_hist_{hist}_liq_{liq}".format(
                rs=_format_float_token(float(rs_value)),
                range_days=int(range_value),
                hist=_format_float_token(float(hist_value)),
                liq=_format_liquidity_token(float(liquidity_value)),
            )
        )
        scenarios.append(
            ScreenerDiagnosticsScenario(
                name=name,
                screener_config=config,
                is_baseline=is_baseline,
                description=(
                    "Paramètres de référence phase 3."
                    if is_baseline
                    else "Scénario grille multi-paramètres."
                ),
            )
        )
        seen.add(key)
    return scenarios


def _safe_divide(numerator: float | int, denominator: float | int) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _safe_numeric_mean(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return float("nan")
    series = pd.to_numeric(frame[column], errors="coerce")
    if series.notna().sum() == 0:
        return float("nan")
    return float(series.mean())


def summarize_screener_diagnostics(
    daily_metrics: pd.DataFrame,
    *,
    baseline_name: str | None = None,
) -> pd.DataFrame:
    """Agrège les métriques journalières par scénario et calcule les deltas baseline."""
    if daily_metrics.empty:
        return pd.DataFrame()

    group_columns = ["scenario_name", "is_baseline", *SCENARIO_PARAMETER_COLUMNS]
    numeric_columns = [
        column
        for column in daily_metrics.select_dtypes(include=[np.number]).columns
        if column not in SCENARIO_PARAMETER_COLUMNS and column != "is_baseline"
    ]
    aggregate_map: dict[str, Any] = {column: "mean" for column in numeric_columns}
    aggregate_map["trade_date"] = "count"
    aggregate_map["status"] = lambda values: int((pd.Series(values) != "ok").sum())

    summary = (
        daily_metrics.groupby(group_columns, dropna=False, as_index=False)
        .agg(aggregate_map)
        .rename(columns={"trade_date": "days_evaluated", "status": "days_failed"})
    )

    renamed_columns: dict[str, str] = {}
    for column in numeric_columns:
        renamed_columns[column] = f"{column}_mean"
    summary = summary.rename(columns=renamed_columns)

    if baseline_name is None:
        baseline_rows = summary[summary["is_baseline"] == 1]
        baseline_name = str(baseline_rows.iloc[0]["scenario_name"]) if not baseline_rows.empty else None

    if baseline_name:
        baseline_row = summary[summary["scenario_name"] == baseline_name]
        if not baseline_row.empty:
            baseline_series = baseline_row.iloc[0]
            excluded = set(group_columns) | {"days_evaluated", "days_failed"}
            numeric_summary_columns = [
                column
                for column in summary.select_dtypes(include=[np.number]).columns
                if column not in excluded
            ]
            for column in numeric_summary_columns:
                delta_column = f"delta_{column}"
                summary[delta_column] = pd.to_numeric(summary[column], errors="coerce") - float(
                    pd.to_numeric(pd.Series([baseline_series[column]]), errors="coerce").iloc[0]
                )

    numeric_output_columns = [
        column
        for column in summary.select_dtypes(include=[np.number]).columns
        if column not in {"is_baseline", "days_evaluated", "days_failed"}
    ]
    if numeric_output_columns:
        summary.loc[:, numeric_output_columns] = summary.loc[:, numeric_output_columns].round(10)

    return summary.sort_values(["is_baseline", "scenario_name"], ascending=[False, True]).reset_index(drop=True)


def classify_market_regimes(
    benchmark_history: pd.DataFrame,
    *,
    benchmark_symbol: str,
    trade_dates: Sequence[date] | None = None,
    trend_lookback_days: int = DEFAULT_REGIME_TREND_LOOKBACK_DAYS,
    long_ma_window: int = DEFAULT_REGIME_LONG_MA_WINDOW,
    vol_window: int = DEFAULT_REGIME_VOL_WINDOW,
    vol_lookback_window: int = DEFAULT_REGIME_VOL_LOOKBACK_WINDOW,
    bull_bear_return_threshold: float = DEFAULT_REGIME_BULL_BEAR_RETURN_THRESHOLD,
    volatility_multiplier: float = DEFAULT_REGIME_VOLATILITY_MULTIPLIER,
) -> pd.DataFrame:
    """Classe les séances benchmark en régimes bull / bear / range / vol."""
    columns = [
        "trade_date",
        "benchmark_symbol",
        "benchmark_close",
        f"benchmark_return_{trend_lookback_days}d",
        f"benchmark_sma_{long_ma_window}",
        f"benchmark_sma_{long_ma_window}_gap",
        f"benchmark_vol_{vol_window}d",
        f"benchmark_vol_{vol_window}d_median_{vol_lookback_window}d",
        "market_regime",
    ]
    if benchmark_history.empty:
        return pd.DataFrame(columns=columns)

    history = benchmark_history.copy()
    if "symbol" in history.columns:
        history = history[history["symbol"].astype(str) == str(benchmark_symbol)].copy()
    if history.empty:
        return pd.DataFrame(columns=columns)

    date_column = "bar_date" if "bar_date" in history.columns else "trade_date" if "trade_date" in history.columns else None
    price_column = "close_price" if "close_price" in history.columns else "close" if "close" in history.columns else None
    if date_column is None or price_column is None:
        return pd.DataFrame(columns=columns)

    history[date_column] = pd.to_datetime(history[date_column], utc=False)
    history = history.sort_values(date_column).drop_duplicates(subset=[date_column], keep="last").copy()
    history["benchmark_close"] = pd.to_numeric(history[price_column], errors="coerce")
    history = history[history["benchmark_close"].notna()].copy()
    if history.empty:
        return pd.DataFrame(columns=columns)

    close_series = history["benchmark_close"]
    returns_1d = close_series.pct_change(fill_method=None)
    history[f"benchmark_return_{trend_lookback_days}d"] = close_series / close_series.shift(trend_lookback_days) - 1.0
    history[f"benchmark_sma_{long_ma_window}"] = close_series.rolling(long_ma_window, min_periods=max(2, min(long_ma_window, 20))).mean()
    history[f"benchmark_sma_{long_ma_window}_gap"] = close_series / history[f"benchmark_sma_{long_ma_window}"] - 1.0
    history[f"benchmark_vol_{vol_window}d"] = returns_1d.rolling(vol_window, min_periods=max(2, min(vol_window, 5))).std(ddof=0) * np.sqrt(252)
    history[f"benchmark_vol_{vol_window}d_median_{vol_lookback_window}d"] = history[f"benchmark_vol_{vol_window}d"].rolling(
        vol_lookback_window,
        min_periods=max(3, min(vol_lookback_window, 20)),
    ).median()

    vol_series = pd.to_numeric(history[f"benchmark_vol_{vol_window}d"], errors="coerce")
    vol_median_series = pd.to_numeric(history[f"benchmark_vol_{vol_window}d_median_{vol_lookback_window}d"], errors="coerce")
    return_series = pd.to_numeric(history[f"benchmark_return_{trend_lookback_days}d"], errors="coerce")
    gap_series = pd.to_numeric(history[f"benchmark_sma_{long_ma_window}_gap"], errors="coerce")

    vol_condition = (
        vol_series.notna()
        & vol_median_series.notna()
        & (vol_median_series > 0)
        & (vol_series > vol_median_series * float(volatility_multiplier))
    )
    bull_condition = gap_series.gt(0.0) & return_series.gt(float(bull_bear_return_threshold))
    bear_condition = gap_series.lt(0.0) & return_series.lt(-float(bull_bear_return_threshold))

    history["market_regime"] = np.where(
        vol_condition,
        "vol",
        np.where(bull_condition, "bull", np.where(bear_condition, "bear", "range")),
    )
    history["benchmark_symbol"] = str(benchmark_symbol)
    history["trade_date"] = history[date_column].dt.date

    regime_frame = history.loc[:, columns].copy()
    if trade_dates is not None:
        trade_date_frame = pd.DataFrame({"trade_date": list(trade_dates)})
        regime_frame = trade_date_frame.merge(regime_frame, on="trade_date", how="left")
        regime_frame["benchmark_symbol"] = regime_frame["benchmark_symbol"].fillna(str(benchmark_symbol))
        regime_frame["market_regime"] = regime_frame["market_regime"].fillna("range")

    return regime_frame.reset_index(drop=True)


def summarize_screener_diagnostics_by_regime(
    daily_metrics: pd.DataFrame,
    *,
    baseline_name: str | None = None,
) -> pd.DataFrame:
    """Agrège les diagnostics par scénario et par régime de marché."""
    if daily_metrics.empty or "market_regime" not in daily_metrics.columns:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    available_regimes = [regime for regime in MARKET_REGIME_ORDER if regime in set(daily_metrics["market_regime"].dropna().astype(str))]
    for regime in available_regimes:
        regime_daily = daily_metrics[daily_metrics["market_regime"].astype(str) == regime].copy()
        if regime_daily.empty:
            continue
        regime_summary = summarize_screener_diagnostics(regime_daily, baseline_name=baseline_name)
        if regime_summary.empty:
            continue
        regime_summary.insert(0, "market_regime", regime)
        frames.append(regime_summary)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _pick_first_available_column(frame: pd.DataFrame, candidates: Sequence[str]) -> str | None:
    for column in candidates:
        if column not in frame.columns:
            continue
        series = pd.to_numeric(frame[column], errors="coerce")
        if series.notna().any():
            return column
    return None


def _winsorize_series(series: pd.Series, *, quantile: float = 0.05) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if len(valid) < 4:
        return numeric
    lower = float(valid.quantile(quantile))
    upper = float(valid.quantile(1.0 - quantile))
    return numeric.clip(lower=lower, upper=upper)


def _normalize_metric_series(series: pd.Series, *, higher_is_better: bool) -> pd.Series:
    numeric = _winsorize_series(series)
    result = pd.Series(0.5, index=series.index, dtype=float)
    valid = numeric.dropna()
    if valid.empty:
        return result
    min_value = float(valid.min())
    max_value = float(valid.max())
    if np.isclose(max_value, min_value):
        result.loc[valid.index] = 0.5
        return result
    scaled = (numeric - min_value) / (max_value - min_value)
    if not higher_is_better:
        scaled = 1.0 - scaled
    scaled = scaled.clip(lower=0.0, upper=1.0)
    result.loc[scaled.dropna().index] = scaled.dropna()
    return result


def _weighted_average_columns(frame: pd.DataFrame, columns_with_weights: Sequence[tuple[str, float]]) -> pd.Series:
    if not columns_with_weights:
        return pd.Series(0.5, index=frame.index, dtype=float)
    weighted_sum = pd.Series(0.0, index=frame.index, dtype=float)
    total_weight = 0.0
    for column, weight in columns_with_weights:
        weighted_sum = weighted_sum + pd.to_numeric(frame[column], errors="coerce").fillna(0.5) * float(weight)
        total_weight += float(weight)
    if total_weight <= 0:
        return pd.Series(0.5, index=frame.index, dtype=float)
    return weighted_sum / total_weight


def _weighted_confidence(frame: pd.DataFrame, columns_with_weights: Sequence[tuple[str, float]]) -> pd.Series:
    if not columns_with_weights:
        return pd.Series(0.0, index=frame.index, dtype=float)
    weighted_sum = pd.Series(0.0, index=frame.index, dtype=float)
    total_weight = 0.0
    for column, weight in columns_with_weights:
        weighted_sum = weighted_sum + pd.to_numeric(frame[column], errors="coerce").fillna(0.0) * float(weight)
        total_weight += float(weight)
    if total_weight <= 0:
        return pd.Series(0.0, index=frame.index, dtype=float)
    return weighted_sum / total_weight


def _weighted_geometric_mean(frame: pd.DataFrame, columns_with_weights: Sequence[tuple[str, float]]) -> pd.Series:
    if not columns_with_weights:
        return pd.Series(0.5, index=frame.index, dtype=float)
    clipped_columns = [
        pd.to_numeric(frame[column], errors="coerce").fillna(0.5).clip(lower=1e-6, upper=1.0)
        for column, _ in columns_with_weights
    ]
    weights = np.array([float(weight) for _, weight in columns_with_weights], dtype=float)
    total_weight = float(weights.sum())
    if total_weight <= 0:
        return pd.Series(0.5, index=frame.index, dtype=float)
    log_terms = sum(np.log(series) * weight for series, weight in zip(clipped_columns, weights, strict=False))
    return np.exp(log_terms / total_weight)


def _candidate_mean_columns(prefix: str, metric: str, target_horizon: int) -> list[str]:
    horizons = [target_horizon, *[h for h in DEFAULT_FORWARD_HORIZONS if h != target_horizon]]
    return [f"{prefix}_{metric}_{horizon}d_mean" for horizon in horizons]


def _candidate_daily_columns(prefix: str, metric: str, target_horizon: int) -> list[str]:
    horizons = [target_horizon, *[h for h in DEFAULT_FORWARD_HORIZONS if h != target_horizon]]
    return [f"{prefix}_{metric}_{horizon}d" for horizon in horizons]


def _enrich_summary_with_daily_stability(
    summary_metrics: pd.DataFrame,
    daily_metrics: pd.DataFrame | None,
    *,
    target_horizon: int,
) -> pd.DataFrame:
    if daily_metrics is None or daily_metrics.empty or summary_metrics.empty:
        return summary_metrics.copy()

    daily = daily_metrics.copy()
    group_column = "scenario_name"
    if group_column not in daily.columns:
        return summary_metrics.copy()

    survival_std_column = _pick_first_available_column(daily, ["portfolio_survival_ratio", "selector_to_portfolio_survival_ratio"])
    forward_daily_column = _pick_first_available_column(
        daily,
        _candidate_daily_columns("portfolio", "excess_return", target_horizon)
        + _candidate_daily_columns("portfolio", "forward_return", target_horizon)
        + _candidate_daily_columns("selector", "excess_return", target_horizon)
        + _candidate_daily_columns("selector", "forward_return", target_horizon),
    )

    if not survival_std_column and not forward_daily_column:
        return summary_metrics.copy()

    records: list[dict[str, object]] = []
    for scenario_name, group in daily.groupby(group_column, dropna=False):
        record: dict[str, object] = {"scenario_name": scenario_name}
        if survival_std_column:
            survival_series = pd.to_numeric(group[survival_std_column], errors="coerce")
            record["portfolio_survival_ratio_std"] = float(survival_series.std(ddof=0)) if survival_series.notna().any() else float("nan")
        if forward_daily_column:
            forward_series = pd.to_numeric(group[forward_daily_column], errors="coerce")
            record["forward_return_consistency_std"] = float(forward_series.std(ddof=0)) if forward_series.notna().any() else float("nan")
            positive_mask = forward_series.dropna() > 0
            record["forward_return_positive_day_share"] = float(positive_mask.mean()) if not positive_mask.empty else float("nan")
        records.append(record)

    enriched = pd.DataFrame(records)
    return summary_metrics.merge(enriched, on="scenario_name", how="left")


def _build_recommendation_text(row: pd.Series, *, forward_column: str | None) -> str:
    parts = [
        f"robustesse={float(row['robustness_score']):.3f}",
        f"survie={float(row['survival_score']):.3f}",
        f"forward={float(row['forward_quality_score']):.3f}",
    ]
    if "portfolio_survival_ratio_mean" in row.index and pd.notna(row.get("portfolio_survival_ratio_mean")):
        parts.append(f"portfolio_survival_ratio_mean={float(row['portfolio_survival_ratio_mean']):.3f}")
    if forward_column and forward_column in row.index and pd.notna(row.get(forward_column)):
        parts.append(f"{forward_column}={float(row[forward_column]):.4f}")
    if "success_rate" in row.index and pd.notna(row.get("success_rate")):
        parts.append(f"success_rate={float(row['success_rate']):.3f}")
    return " | ".join(parts)


def _build_objective_reason(
    row: pd.Series,
    *,
    objective_name: str,
    objective_label: str,
) -> str:
    parts = [f"objectif={objective_label}"]
    if pd.notna(row.get("objective_score")):
        parts.append(f"objective_score={float(row['objective_score']):.3f}")
    if pd.notna(row.get("overall_score")):
        parts.append(f"overall={float(row['overall_score']):.3f}")
    if objective_name == "robust" and pd.notna(row.get("cross_regime_overall_score")):
        parts.append(f"cross_regime={float(row['cross_regime_overall_score']):.3f}")
    if objective_name == "robust" and pd.notna(row.get("worst_regime_overall_score")):
        parts.append(f"worst_regime={float(row['worst_regime_overall_score']):.3f}")
    if objective_name == "bear_defensive" and pd.notna(row.get("bear_overall_score")):
        parts.append(f"bear_overall={float(row['bear_overall_score']):.3f}")
    if objective_name == "bear_defensive" and pd.notna(row.get("bear_survival_score")):
        parts.append(f"bear_survival={float(row['bear_survival_score']):.3f}")
    base_reason = str(row.get("recommendation_reason") or "")
    if base_reason:
        parts.append(base_reason)
    return " | ".join(parts)


def _empty_objective_summary(
    *,
    baseline_name: str | None,
    message: str,
) -> dict[str, object]:
    return {
        "status": "empty",
        "message": message,
        "baseline_name": baseline_name,
        "objectives": {},
    }


def _resolve_objective_summary_by_regime(
    *,
    summary_metrics_by_regime: pd.DataFrame | None,
    daily_metrics: pd.DataFrame | None,
    baseline_name: str | None,
) -> pd.DataFrame:
    if summary_metrics_by_regime is not None and not summary_metrics_by_regime.empty:
        return summary_metrics_by_regime.copy()
    if daily_metrics is None or daily_metrics.empty or "market_regime" not in daily_metrics.columns:
        return pd.DataFrame()
    return summarize_screener_diagnostics_by_regime(daily_metrics, baseline_name=baseline_name)


def recommend_screener_scenarios(
    summary_metrics: pd.DataFrame,
    *,
    daily_metrics: pd.DataFrame | None = None,
    baseline_name: str | None = None,
    target_horizon: int = DEFAULT_RECOMMENDATION_HORIZON,
    pillar_weights: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Classe les scénarios en meilleur compromis robustesse / survie / qualité forward."""
    if summary_metrics.empty:
        return pd.DataFrame(), {
            "status": "empty",
            "message": "Aucune métrique de synthèse disponible à analyser.",
            "baseline_name": baseline_name,
        }

    weights = {**DEFAULT_PILLAR_WEIGHTS, **(pillar_weights or {})}
    analysis = _enrich_summary_with_daily_stability(summary_metrics, daily_metrics, target_horizon=target_horizon).copy()

    if baseline_name is None and "is_baseline" in analysis.columns:
        baseline_rows = analysis[pd.to_numeric(analysis["is_baseline"], errors="coerce").fillna(0).astype(int) == 1]
        if not baseline_rows.empty:
            baseline_name = str(baseline_rows.iloc[0]["scenario_name"])

    if {"days_evaluated", "days_failed"}.issubset(analysis.columns):
        evaluated = pd.to_numeric(analysis["days_evaluated"], errors="coerce").replace(0, np.nan)
        failed = pd.to_numeric(analysis["days_failed"], errors="coerce").fillna(0.0)
        analysis["success_rate"] = (1.0 - failed / evaluated).clip(lower=0.0, upper=1.0)
        analysis["success_rate"] = analysis["success_rate"].fillna(0.0)
    else:
        analysis["success_rate"] = np.nan

    portfolio_forward_column = _pick_first_available_column(
        analysis,
        _candidate_mean_columns("portfolio", "excess_return", target_horizon)
        + _candidate_mean_columns("portfolio", "forward_return", target_horizon),
    )
    selector_forward_column = _pick_first_available_column(
        analysis,
        _candidate_mean_columns("selector", "excess_return", target_horizon)
        + _candidate_mean_columns("selector", "forward_return", target_horizon),
    )
    coverage_column = _pick_first_available_column(
        analysis,
        _candidate_mean_columns("portfolio", "coverage", target_horizon)
        + _candidate_mean_columns("selector", "coverage", target_horizon),
    )
    positive_share_column = _pick_first_available_column(
        analysis,
        _candidate_mean_columns("portfolio", "positive_share", target_horizon)
        + _candidate_mean_columns("selector", "positive_share", target_horizon),
    )
    stability_cost_column = _pick_first_available_column(
        analysis,
        ["forward_return_consistency_std", "portfolio_survival_ratio_std"],
    )

    metric_definitions: list[dict[str, object]] = [
        {
            "label": "success_rate",
            "candidates": ["success_rate"],
            "higher_is_better": True,
            "pillar": "robustness",
            "weight": 0.50,
        },
        {
            "label": "coverage",
            "candidates": [coverage_column] if coverage_column else [],
            "higher_is_better": True,
            "pillar": "robustness",
            "weight": 0.20,
        },
        {
            "label": "stability",
            "candidates": [stability_cost_column] if stability_cost_column else [],
            "higher_is_better": False,
            "pillar": "robustness",
            "weight": 0.30,
        },
        {
            "label": "portfolio_survival_ratio",
            "candidates": ["portfolio_survival_ratio_mean"],
            "higher_is_better": True,
            "pillar": "survival",
            "weight": 0.45,
        },
        {
            "label": "selector_to_portfolio_survival_ratio",
            "candidates": ["selector_to_portfolio_survival_ratio_mean"],
            "higher_is_better": True,
            "pillar": "survival",
            "weight": 0.35,
        },
        {
            "label": "portfolio_target_count",
            "candidates": ["portfolio_target_count_mean", "selector_candidate_count_mean"],
            "higher_is_better": True,
            "pillar": "survival",
            "weight": 0.20,
        },
        {
            "label": "portfolio_forward_quality",
            "candidates": [portfolio_forward_column] if portfolio_forward_column else [],
            "higher_is_better": True,
            "pillar": "forward_quality",
            "weight": 0.50,
        },
        {
            "label": "selector_forward_quality",
            "candidates": [selector_forward_column] if selector_forward_column else [],
            "higher_is_better": True,
            "pillar": "forward_quality",
            "weight": 0.20,
        },
        {
            "label": "positive_share",
            "candidates": [positive_share_column] if positive_share_column else [],
            "higher_is_better": True,
            "pillar": "forward_quality",
            "weight": 0.20,
        },
        {
            "label": "delta_forward_vs_baseline",
            "candidates": [
                f"delta_{portfolio_forward_column}" if portfolio_forward_column else None,
                f"delta_{selector_forward_column}" if selector_forward_column else None,
            ],
            "higher_is_better": True,
            "pillar": "forward_quality",
            "weight": 0.10,
        },
    ]

    metric_sources: dict[str, str | None] = {}
    pillar_metric_columns: dict[str, list[tuple[str, float]]] = {pillar: [] for pillar in weights}
    pillar_confidence_columns: dict[str, list[tuple[str, float]]] = {pillar: [] for pillar in weights}
    missing_metrics: list[str] = []

    for definition in metric_definitions:
        label = str(definition["label"])
        candidates = [str(candidate) for candidate in definition["candidates"] if candidate]
        pillar = str(definition["pillar"])
        weight = float(definition["weight"])
        source_column = _pick_first_available_column(analysis, candidates)
        metric_sources[label] = source_column
        score_column = f"metric_{label}_score"
        confidence_column = f"metric_{label}_confidence"
        if source_column is None:
            analysis[score_column] = 0.5
            analysis[confidence_column] = 0.0
            missing_metrics.append(label)
        else:
            numeric_series = pd.to_numeric(analysis[source_column], errors="coerce")
            analysis[score_column] = _normalize_metric_series(
                numeric_series,
                higher_is_better=bool(definition["higher_is_better"]),
            )
            analysis[confidence_column] = numeric_series.notna().astype(float)
        pillar_metric_columns[pillar].append((score_column, weight))
        pillar_confidence_columns[pillar].append((confidence_column, weight))

    for pillar_name in weights:
        analysis[f"{pillar_name}_score"] = _weighted_average_columns(analysis, pillar_metric_columns[pillar_name]).clip(0.0, 1.0)
        analysis[f"{pillar_name}_confidence"] = _weighted_confidence(analysis, pillar_confidence_columns[pillar_name]).clip(0.0, 1.0)

    overall_columns = [(f"{pillar}_score", float(weight)) for pillar, weight in weights.items()]
    confidence_columns = [(f"{pillar}_confidence", float(weight)) for pillar, weight in weights.items()]
    analysis["confidence_score"] = _weighted_confidence(analysis, confidence_columns).clip(0.0, 1.0)
    analysis["overall_score_raw"] = _weighted_geometric_mean(analysis, overall_columns)
    analysis["overall_score"] = (analysis["overall_score_raw"] * (0.80 + 0.20 * analysis["confidence_score"])).clip(0.0, 1.0)
    analysis["forward_metric_source"] = portfolio_forward_column or selector_forward_column
    analysis["recommendation_reason"] = analysis.apply(
        lambda row: _build_recommendation_text(row, forward_column=portfolio_forward_column or selector_forward_column),
        axis=1,
    )
    analysis["recommendation_warnings"] = ""
    if "days_failed" in analysis.columns:
        failed_mask = pd.to_numeric(analysis["days_failed"], errors="coerce").fillna(0.0) > 0
        analysis.loc[failed_mask, "recommendation_warnings"] = "jours en échec détectés"
    low_confidence_mask = analysis["confidence_score"] < 0.60
    analysis.loc[low_confidence_mask, "recommendation_warnings"] = analysis.loc[low_confidence_mask, "recommendation_warnings"].replace(
        "",
        "couverture métrique partielle",
    )
    analysis.loc[
        low_confidence_mask & analysis["recommendation_warnings"].ne("couverture métrique partielle"),
        "recommendation_warnings",
    ] = analysis.loc[
        low_confidence_mask & analysis["recommendation_warnings"].ne("couverture métrique partielle"),
        "recommendation_warnings",
    ] + "; couverture métrique partielle"

    analysis = analysis.sort_values(
        ["overall_score", "confidence_score", "scenario_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    analysis.insert(0, "rank", np.arange(1, len(analysis) + 1))

    leader_overall = analysis.iloc[0]
    leader_robustness = analysis.sort_values(["robustness_score", "overall_score"], ascending=[False, False]).iloc[0]
    leader_survival = analysis.sort_values(["survival_score", "overall_score"], ascending=[False, False]).iloc[0]
    leader_forward = analysis.sort_values(["forward_quality_score", "overall_score"], ascending=[False, False]).iloc[0]

    viable_mask = pd.to_numeric(
        analysis.get("portfolio_target_count_mean", pd.Series(0.0, index=analysis.index)),
        errors="coerce",
    ).fillna(0.0) > 0.0
    viable_candidates = analysis[viable_mask].copy()
    if viable_candidates.empty:
        selective_viable = leader_overall
    else:
        selective_viable = viable_candidates.sort_values(
            ["portfolio_target_count_mean", "overall_score"],
            ascending=[True, False],
        ).iloc[0]

    analysis["recommendation_label"] = ""
    analysis.loc[analysis["scenario_name"] == leader_overall["scenario_name"], "recommendation_label"] = "best_compromise"

    summary: dict[str, object] = {
        "status": "ok",
        "baseline_name": baseline_name,
        "target_horizon_days": target_horizon,
        "analyzed_scenarios": int(len(analysis)),
        "metric_sources": metric_sources,
        "missing_metrics": missing_metrics,
        "pillar_weights": weights,
        "recommended_scenario": {
            "scenario_name": str(leader_overall["scenario_name"]),
            "rank": int(leader_overall["rank"]),
            "overall_score": float(leader_overall["overall_score"]),
            "robustness_score": float(leader_overall["robustness_score"]),
            "survival_score": float(leader_overall["survival_score"]),
            "forward_quality_score": float(leader_overall["forward_quality_score"]),
            "confidence_score": float(leader_overall["confidence_score"]),
            "reason": str(leader_overall["recommendation_reason"]),
        },
        "category_leaders": {
            "best_compromise": str(leader_overall["scenario_name"]),
            "best_robustness": str(leader_robustness["scenario_name"]),
            "best_survival": str(leader_survival["scenario_name"]),
            "best_forward_quality": str(leader_forward["scenario_name"]),
            "most_selective_viable": str(selective_viable["scenario_name"]),
        },
    }
    return analysis, summary


def build_cross_regime_recommendations(
    regime_recommendations: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Construit un classement de robustesse cross-régimes à partir des recommandations par régime."""
    if regime_recommendations.empty or "market_regime" not in regime_recommendations.columns:
        return pd.DataFrame(), {
            "status": "empty",
            "message": "Aucune recommandation par régime disponible.",
        }

    total_regimes = int(regime_recommendations["market_regime"].dropna().astype(str).nunique())
    scenario_meta_columns = [
        column
        for column in ["scenario_name", "is_baseline", *SCENARIO_PARAMETER_COLUMNS]
        if column in regime_recommendations.columns
    ]
    scenario_meta = regime_recommendations.loc[:, scenario_meta_columns].drop_duplicates(subset=["scenario_name"])
    grouped = (
        regime_recommendations.groupby("scenario_name", as_index=False)
        .agg(
            regimes_covered=("market_regime", lambda values: int(pd.Series(values).dropna().astype(str).nunique())),
            mean_regime_overall_score=("overall_score", "mean"),
            worst_regime_overall_score=("overall_score", "min"),
            regime_overall_score_std=("overall_score", lambda values: float(pd.to_numeric(pd.Series(values), errors="coerce").std(ddof=0))),
            mean_regime_confidence_score=("confidence_score", "mean"),
            mean_regime_robustness_score=("robustness_score", "mean"),
            mean_regime_survival_score=("survival_score", "mean"),
            mean_regime_forward_quality_score=("forward_quality_score", "mean"),
        )
        .merge(scenario_meta, on="scenario_name", how="left")
    )
    grouped["regime_coverage_ratio"] = pd.to_numeric(grouped["regimes_covered"], errors="coerce").fillna(0.0) / max(total_regimes, 1)

    metric_specs = [
        ("mean_regime_overall_score", True, 0.35),
        ("worst_regime_overall_score", True, 0.35),
        ("regime_coverage_ratio", True, 0.15),
        ("regime_overall_score_std", False, 0.10),
        ("mean_regime_confidence_score", True, 0.05),
    ]
    weighted_columns: list[tuple[str, float]] = []
    for column, higher_is_better, weight in metric_specs:
        score_column = f"cross_metric_{column}_score"
        grouped[score_column] = _normalize_metric_series(
            pd.to_numeric(grouped[column], errors="coerce"),
            higher_is_better=higher_is_better,
        )
        weighted_columns.append((score_column, weight))

    grouped["cross_regime_overall_score"] = _weighted_geometric_mean(grouped, weighted_columns).clip(0.0, 1.0)
    grouped = grouped.sort_values(
        ["cross_regime_overall_score", "mean_regime_overall_score", "scenario_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    grouped.insert(0, "cross_regime_rank", np.arange(1, len(grouped) + 1))
    grouped["recommendation_label"] = ""
    if not grouped.empty:
        grouped.loc[grouped.index[0], "recommendation_label"] = "best_cross_regime_compromise"

    leader = grouped.iloc[0]
    summary = {
        "status": "ok",
        "regimes_evaluated": total_regimes,
        "recommended_scenario": {
            "scenario_name": str(leader["scenario_name"]),
            "cross_regime_rank": int(leader["cross_regime_rank"]),
            "cross_regime_overall_score": float(leader["cross_regime_overall_score"]),
            "mean_regime_overall_score": float(leader["mean_regime_overall_score"]),
            "worst_regime_overall_score": float(leader["worst_regime_overall_score"]),
            "regime_coverage_ratio": float(leader["regime_coverage_ratio"]),
        },
    }
    return grouped, summary


def recommend_screener_scenarios_by_regime(
    summary_metrics_by_regime: pd.DataFrame,
    *,
    daily_metrics: pd.DataFrame | None = None,
    baseline_name: str | None = None,
    target_horizon: int = DEFAULT_RECOMMENDATION_HORIZON,
    pillar_weights: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, dict[str, object], pd.DataFrame, dict[str, object]]:
    """Produit les recommandations phase 6 par régime puis un score cross-régimes."""
    if summary_metrics_by_regime.empty or "market_regime" not in summary_metrics_by_regime.columns:
        empty_summary = {
            "status": "empty",
            "message": "Aucune synthèse par régime disponible.",
            "baseline_name": baseline_name,
        }
        return pd.DataFrame(), empty_summary, pd.DataFrame(), {"status": "empty", "message": "Aucune synthèse par régime disponible."}

    regime_frames: list[pd.DataFrame] = []
    per_regime_summary: dict[str, object] = {}
    available_regimes = [regime for regime in MARKET_REGIME_ORDER if regime in set(summary_metrics_by_regime["market_regime"].dropna().astype(str))]
    for regime in available_regimes:
        regime_summary_df = summary_metrics_by_regime[summary_metrics_by_regime["market_regime"].astype(str) == regime].copy()
        if regime_summary_df.empty:
            continue
        regime_daily = None
        if daily_metrics is not None and not daily_metrics.empty and "market_regime" in daily_metrics.columns:
            regime_daily = daily_metrics[daily_metrics["market_regime"].astype(str) == regime].copy()
        recommendations, summary = recommend_screener_scenarios(
            regime_summary_df.drop(columns=["market_regime"], errors="ignore"),
            daily_metrics=regime_daily,
            baseline_name=baseline_name,
            target_horizon=target_horizon,
            pillar_weights=pillar_weights,
        )
        if recommendations.empty:
            continue
        recommendations.insert(0, "market_regime", regime)
        regime_frames.append(recommendations)
        per_regime_summary[regime] = summary

    if not regime_frames:
        empty_summary = {
            "status": "empty",
            "message": "Aucune recommandation calculée par régime.",
            "baseline_name": baseline_name,
        }
        return pd.DataFrame(), empty_summary, pd.DataFrame(), {"status": "empty", "message": "Aucune recommandation calculée par régime."}

    combined = pd.concat(regime_frames, ignore_index=True)
    cross_regime_recommendations, cross_regime_summary = build_cross_regime_recommendations(combined)
    summary = {
        "status": "ok",
        "baseline_name": baseline_name,
        "regimes": available_regimes,
        "per_regime": per_regime_summary,
        "cross_regime": cross_regime_summary,
    }
    return combined, summary, cross_regime_recommendations, cross_regime_summary


def recommend_screener_scenarios_by_objective(
    summary_metrics: pd.DataFrame,
    *,
    daily_metrics: pd.DataFrame | None = None,
    summary_metrics_by_regime: pd.DataFrame | None = None,
    baseline_name: str | None = None,
    target_horizon: int = DEFAULT_RECOMMENDATION_HORIZON,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Construit des recommandations alternatives selon plusieurs objectifs opérationnels."""
    if summary_metrics.empty:
        return pd.DataFrame(), _empty_objective_summary(
            baseline_name=baseline_name,
            message="Aucune métrique de synthèse disponible à analyser.",
        )

    resolved_summary_by_regime = _resolve_objective_summary_by_regime(
        summary_metrics_by_regime=summary_metrics_by_regime,
        daily_metrics=daily_metrics,
        baseline_name=baseline_name,
    )
    regime_recommendations = pd.DataFrame()
    cross_regime_recommendations = pd.DataFrame()
    cross_regime_summary: dict[str, object] = {"status": "empty", "message": "Aucune analyse cross-régimes disponible."}
    if not resolved_summary_by_regime.empty and "market_regime" in resolved_summary_by_regime.columns:
        regime_recommendations, _, cross_regime_recommendations, cross_regime_summary = recommend_screener_scenarios_by_regime(
            resolved_summary_by_regime,
            daily_metrics=daily_metrics,
            baseline_name=baseline_name,
            target_horizon=target_horizon,
        )

    objective_frames: list[pd.DataFrame] = []
    objective_summaries: dict[str, object] = {}
    available_regimes = [
        regime
        for regime in MARKET_REGIME_ORDER
        if regime in set(resolved_summary_by_regime.get("market_regime", pd.Series(dtype=str)).dropna().astype(str))
    ]

    bear_summary = pd.DataFrame()
    bear_daily = pd.DataFrame()
    if not resolved_summary_by_regime.empty and "market_regime" in resolved_summary_by_regime.columns:
        bear_summary = resolved_summary_by_regime[resolved_summary_by_regime["market_regime"].astype(str) == "bear"].copy()
    if daily_metrics is not None and not daily_metrics.empty and "market_regime" in daily_metrics.columns:
        bear_daily = daily_metrics[daily_metrics["market_regime"].astype(str) == "bear"].copy()

    for objective_priority, objective_name in enumerate(OBJECTIVE_PROFILE_ORDER, start=1):
        profile = OBJECTIVE_PROFILES[objective_name]
        objective_label = str(profile["label"])
        objective_description = str(profile["description"])
        pillar_weights = dict(profile["pillar_weights"])

        objective_summary_input = summary_metrics
        objective_daily_input = daily_metrics if daily_metrics is not None and not daily_metrics.empty else None
        objective_scope = "global"
        scope_regime = None

        if objective_name == "bear_defensive" and not bear_summary.empty:
            objective_summary_input = bear_summary.drop(columns=["market_regime"], errors="ignore")
            objective_daily_input = bear_daily if not bear_daily.empty else None
            objective_scope = "bear_regime"
            scope_regime = "bear"
        elif objective_name == "bear_defensive":
            objective_scope = "global_fallback"

        objective_frame, objective_phase_summary = recommend_screener_scenarios(
            objective_summary_input,
            daily_metrics=objective_daily_input,
            baseline_name=baseline_name,
            target_horizon=target_horizon,
            pillar_weights=pillar_weights,
        )
        if objective_frame.empty:
            continue

        objective_frame = objective_frame.copy()
        objective_frame.insert(0, "objective_priority", objective_priority)
        objective_frame.insert(1, "objective", objective_name)
        objective_frame.insert(2, "objective_label", objective_label)
        objective_frame.insert(3, "objective_scope", objective_scope)
        objective_frame.insert(4, "objective_scope_regime", scope_regime)
        objective_frame["objective_score"] = pd.to_numeric(objective_frame.get("overall_score"), errors="coerce")

        if objective_name == "robust" and not cross_regime_recommendations.empty:
            cross_columns = [
                column
                for column in [
                    "scenario_name",
                    "cross_regime_rank",
                    "cross_regime_overall_score",
                    "mean_regime_overall_score",
                    "worst_regime_overall_score",
                    "regime_coverage_ratio",
                ]
                if column in cross_regime_recommendations.columns
            ]
            objective_frame = objective_frame.merge(
                cross_regime_recommendations.loc[:, cross_columns],
                on="scenario_name",
                how="left",
            )
            base_score = pd.to_numeric(objective_frame["overall_score"], errors="coerce").fillna(0.0)
            cross_score = pd.to_numeric(objective_frame.get("cross_regime_overall_score"), errors="coerce")
            objective_frame["objective_score"] = (
                cross_score.fillna(base_score) * 0.65 + base_score * 0.35
            ).clip(lower=0.0, upper=1.0)
            objective_frame = objective_frame.sort_values(
                [
                    "objective_score",
                    "worst_regime_overall_score",
                    "cross_regime_overall_score",
                    "overall_score",
                    "confidence_score",
                    "scenario_name",
                ],
                ascending=[False, False, False, False, False, True],
            ).reset_index(drop=True)
            objective_scope = "cross_regime"
            objective_frame["objective_scope"] = objective_scope

        if objective_name == "offensive":
            offensive_columns = [
                ("metric_portfolio_forward_quality_score", 0.45),
                ("metric_selector_forward_quality_score", 0.15),
                ("metric_positive_share_score", 0.10),
                ("metric_delta_forward_vs_baseline_score", 0.20),
                ("forward_quality_score", 0.10),
            ]
            objective_frame["objective_score"] = _weighted_average_columns(
                objective_frame,
                [(column, weight) for column, weight in offensive_columns if column in objective_frame.columns],
            ).clip(lower=0.0, upper=1.0)

        if objective_name == "executable_compromise":
            executable_columns = [
                ("metric_portfolio_survival_ratio_score", 0.30),
                ("metric_selector_to_portfolio_survival_ratio_score", 0.25),
                ("metric_portfolio_target_count_score", 0.20),
                ("metric_success_rate_score", 0.15),
                ("survival_score", 0.10),
            ]
            objective_frame["objective_score"] = _weighted_average_columns(
                objective_frame,
                [(column, weight) for column, weight in executable_columns if column in objective_frame.columns],
            ).clip(lower=0.0, upper=1.0)

        if objective_name == "bear_defensive" and objective_scope == "bear_regime":
            objective_frame = objective_frame.rename(
                columns={
                    "overall_score": "bear_overall_score",
                    "robustness_score": "bear_robustness_score",
                    "survival_score": "bear_survival_score",
                    "forward_quality_score": "bear_forward_quality_score",
                    "confidence_score": "bear_confidence_score",
                    "rank": "bear_rank",
                }
            )
            global_frame, _ = recommend_screener_scenarios(
                summary_metrics,
                daily_metrics=daily_metrics,
                baseline_name=baseline_name,
                target_horizon=target_horizon,
            )
            if not global_frame.empty:
                objective_frame = objective_frame.merge(
                    global_frame.loc[:, [column for column in ["scenario_name", "overall_score", "robustness_score", "survival_score", "forward_quality_score", "confidence_score"] if column in global_frame.columns]],
                    on="scenario_name",
                    how="left",
                    suffixes=("", "_global"),
                )
            else:
                for column in ["overall_score", "robustness_score", "survival_score", "forward_quality_score", "confidence_score"]:
                    objective_frame[column] = np.nan
            objective_frame["rank"] = np.arange(1, len(objective_frame) + 1)
            objective_frame["objective_score"] = pd.to_numeric(objective_frame["bear_overall_score"], errors="coerce").fillna(
                pd.to_numeric(objective_frame.get("overall_score"), errors="coerce").fillna(0.0)
            )
            objective_frame = objective_frame.sort_values(
                ["objective_score", "bear_survival_score", "bear_robustness_score", "scenario_name"],
                ascending=[False, False, False, True],
            ).reset_index(drop=True)
            objective_frame["rank"] = np.arange(1, len(objective_frame) + 1)

        if objective_name != "bear_defensive":
            objective_frame = objective_frame.sort_values(
                ["objective_score", "forward_quality_score", "overall_score", "confidence_score", "scenario_name"],
                ascending=[False, False, False, False, True],
            ).reset_index(drop=True)
            objective_frame["rank"] = np.arange(1, len(objective_frame) + 1)

        objective_frame["objective_recommendation_label"] = ""
        objective_frame.loc[objective_frame.index[0], "objective_recommendation_label"] = str(profile["recommendation_label"])
        objective_frame["objective_reason"] = objective_frame.apply(
            lambda row: _build_objective_reason(row, objective_name=objective_name, objective_label=objective_label),
            axis=1,
        )
        objective_frames.append(objective_frame)

        leader = objective_frame.iloc[0]
        objective_summaries[objective_name] = {
            "label": objective_label,
            "description": objective_description,
            "scope": objective_scope,
            "scope_regime": scope_regime,
            "pillar_weights": pillar_weights,
            "analyzed_scenarios": int(len(objective_frame)),
            "recommended_scenario": {
                "scenario_name": str(leader["scenario_name"]),
                "rank": int(leader["rank"]),
                "objective_score": float(pd.to_numeric(pd.Series([leader.get("objective_score")]), errors="coerce").fillna(0.0).iloc[0]),
                "reason": str(leader["objective_reason"]),
                "overall_score": float(pd.to_numeric(pd.Series([leader.get("overall_score")]), errors="coerce").fillna(0.0).iloc[0]),
                "robustness_score": float(pd.to_numeric(pd.Series([leader.get("robustness_score")]), errors="coerce").fillna(0.0).iloc[0]),
                "survival_score": float(pd.to_numeric(pd.Series([leader.get("survival_score")]), errors="coerce").fillna(0.0).iloc[0]),
                "forward_quality_score": float(pd.to_numeric(pd.Series([leader.get("forward_quality_score")]), errors="coerce").fillna(0.0).iloc[0]),
                "confidence_score": float(pd.to_numeric(pd.Series([leader.get("confidence_score")]), errors="coerce").fillna(0.0).iloc[0]),
            },
            "metric_sources": objective_phase_summary.get("metric_sources", {}),
            "missing_metrics": objective_phase_summary.get("missing_metrics", []),
        }
        if objective_name == "robust" and cross_regime_summary.get("status") == "ok":
            objective_summaries[objective_name]["cross_regime_summary"] = cross_regime_summary

    if not objective_frames:
        return pd.DataFrame(), _empty_objective_summary(
            baseline_name=baseline_name,
            message="Aucune recommandation par objectif calculée.",
        )

    combined = pd.concat(objective_frames, ignore_index=True)
    combined = combined.sort_values(["objective_priority", "rank", "scenario_name"], ascending=[True, True, True]).reset_index(drop=True)
    return combined, {
        "status": "ok",
        "baseline_name": baseline_name,
        "target_horizon_days": target_horizon,
        "available_regimes": available_regimes,
        "available_objectives": OBJECTIVE_PROFILE_ORDER,
        "bear_market_data_available": not bear_summary.empty,
        "cross_regime_analysis_available": cross_regime_summary.get("status") == "ok",
        "objectives": objective_summaries,
    }


class ScreenerDiagnosticsService:
    """Rejoue screener → selector → portefeuille cible pour comparer des paramètres."""

    def __init__(
        self,
        engine: Engine | None = None,
        *,
        base_screener_config: ScreenerConfig | None = None,
        scanner_config: AlphaScannerConfig | None = None,
        sentiment_config: SentimentBoostConfig | None = None,
        risk_config: RiskConfig | None = None,
        screener_max_workers: int | None = None,
        forward_return_horizons: Sequence[int] = DEFAULT_FORWARD_HORIZONS,
    ) -> None:
        self.engine = engine or get_sqlalchemy_engine()
        self.base_screener_config = base_screener_config or ScreenerConfig()
        self.scanner_config = scanner_config or AlphaScannerConfig.strict_swing_cash()
        self.sentiment_config = sentiment_config or SentimentBoostConfig()
        self.risk_config = risk_config or RiskConfig()
        self.screener_max_workers = screener_max_workers
        self.forward_return_horizons = tuple(sorted({int(value) for value in forward_return_horizons if int(value) > 0}))
        if not self.forward_return_horizons:
            raise ValueError("Au moins un horizon forward positif est requis.")
        self._stock_bars_layout: tuple[str, str] | None = None

    def _build_market_regime_frame(self, trading_dates: Sequence[date]) -> pd.DataFrame:
        if not trading_dates:
            return pd.DataFrame()
        benchmark_symbol = self.base_screener_config.benchmark_symbol
        warmup_days = max(
            DEFAULT_REGIME_LONG_MA_WINDOW * 4,
            DEFAULT_REGIME_VOL_LOOKBACK_WINDOW * 3,
            DEFAULT_REGIME_TREND_LOOKBACK_DAYS * 4,
            365,
        )
        benchmark_history = self._load_price_history(
            [benchmark_symbol],
            start_date=min(trading_dates) - timedelta(days=warmup_days),
            end_date=max(trading_dates),
            include_volume=False,
        )
        return classify_market_regimes(
            benchmark_history,
            benchmark_symbol=benchmark_symbol,
            trade_dates=trading_dates,
        )

    def _resolve_stock_bars_layout(self) -> tuple[str, str]:
        if self._stock_bars_layout is not None:
            return self._stock_bars_layout
        columns = {str(col["name"]) for col in inspect(self.engine).get_columns("stock_bars_daily")}
        date_column = "date" if "date" in columns else "trade_date" if "trade_date" in columns else None
        if date_column is None:
            raise RuntimeError("Impossible de localiser une colonne date compatible dans stock_bars_daily.")
        close_expression = "COALESCE(adj_close, `close`)" if "adj_close" in columns else "`close`"
        self._stock_bars_layout = (date_column, close_expression)
        return self._stock_bars_layout

    def list_trading_dates(self, start_date: date, end_date: date) -> list[date]:
        date_column, _ = self._resolve_stock_bars_layout()
        stmt = text(
            f"""
            SELECT DISTINCT `{date_column}` AS trade_date
            FROM stock_bars_daily
            WHERE `{date_column}` BETWEEN :start_date AND :end_date
            ORDER BY `{date_column}`
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, {"start_date": start_date, "end_date": end_date}).scalars().all()
        return [pd.Timestamp(value).date() for value in rows]

    def analyze_period(
        self,
        *,
        start_date: date,
        end_date: date,
        scenarios: Sequence[ScreenerDiagnosticsScenario],
        limit_days: int | None = None,
    ) -> ScreenerDiagnosticsResult:
        trading_dates = self.list_trading_dates(start_date, end_date)
        if limit_days is not None:
            trading_dates = trading_dates[:limit_days]
        scenario_list = list(scenarios)
        if not scenario_list:
            raise ValueError("Aucun scénario fourni.")

        market_regimes = self._build_market_regime_frame(trading_dates)

        daily_rows: list[dict[str, object]] = []
        for scenario in scenario_list:
            LOGGER.info("Diagnostic screener | scénario=%s baseline=%s", scenario.name, scenario.is_baseline)
            snapshot_service = self._make_snapshot_service(scenario.screener_config)
            for as_of_date in trading_dates:
                daily_rows.append(self._evaluate_scenario_on_date(snapshot_service, scenario, as_of_date))

        daily_df = pd.DataFrame(daily_rows)
        if not daily_df.empty:
            if not market_regimes.empty:
                daily_df = daily_df.merge(market_regimes, on="trade_date", how="left")
            daily_df = daily_df.sort_values(["scenario_name", "trade_date"]).reset_index(drop=True)
        baseline_name = next((scenario.name for scenario in scenario_list if scenario.is_baseline), scenario_list[0].name)
        summary_df = summarize_screener_diagnostics(daily_df, baseline_name=baseline_name)
        summary_by_regime_df = summarize_screener_diagnostics_by_regime(daily_df, baseline_name=baseline_name)
        return ScreenerDiagnosticsResult(
            trading_dates=tuple(trading_dates),
            scenarios=tuple(scenario_list),
            daily_metrics=daily_df,
            summary_metrics=summary_df,
            baseline_name=baseline_name,
            market_regimes=market_regimes,
            summary_metrics_by_regime=summary_by_regime_df,
        )

    def _make_snapshot_service(self, screener_config: ScreenerConfig) -> BackfillScoresHistoryService:
        return BackfillScoresHistoryService(
            engine=self.engine,
            screener_config=screener_config,
            scanner_config=self.scanner_config,
            sentiment_config=self.sentiment_config,
            screener_max_workers=self.screener_max_workers,
        )

    def _evaluate_scenario_on_date(
        self,
        snapshot_service: BackfillScoresHistoryService,
        scenario: ScreenerDiagnosticsScenario,
        as_of_date: date,
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "trade_date": as_of_date,
            "scenario_name": scenario.name,
            "is_baseline": int(scenario.is_baseline),
            "status": "ok",
            "error_message": None,
            **scenario.parameter_dict(),
        }
        for prefix in ("selector", "portfolio"):
            for horizon in self.forward_return_horizons:
                row.setdefault(f"{prefix}_forward_return_{horizon}d", float("nan"))
                row.setdefault(f"{prefix}_excess_return_{horizon}d", float("nan"))
                row.setdefault(f"{prefix}_positive_share_{horizon}d", float("nan"))
                row.setdefault(f"{prefix}_coverage_{horizon}d", 0.0)
            row.setdefault(f"{prefix}_mean_score", float("nan"))
        for horizon in self.forward_return_horizons:
            row.setdefault(f"benchmark_forward_return_{horizon}d", float("nan"))

        try:
            screener_df, selector_df, history_df = self._build_pit_frames(snapshot_service, as_of_date)
            selector_candidates = self._extract_selector_candidates(history_df)
            portfolio_entries = self._build_portfolio_entries(selector_candidates, as_of_date)
            target_entries = [entry for entry in portfolio_entries if entry.approved_shares > 0]
            accepted_entries = [entry for entry in target_entries if str(entry.decision).upper() == "ACCEPTED"]
            reduced_entries = [entry for entry in target_entries if str(entry.decision).upper() == "REDUCED"]
            rejected_entries = [entry for entry in portfolio_entries if entry.approved_shares <= 0]

            screener_count = len(screener_df)
            selector_filtered_count = len(history_df)
            selector_candidate_count = len(selector_candidates)
            portfolio_target_count = len(target_entries)

            row.update(
                {
                    "screener_count": screener_count,
                    "selector_filtered_count": selector_filtered_count,
                    "selector_candidate_count": selector_candidate_count,
                    "portfolio_target_count": portfolio_target_count,
                    "portfolio_accepted_count": len(accepted_entries),
                    "portfolio_reduced_count": len(reduced_entries),
                    "portfolio_rejected_count": len(rejected_entries),
                    "selector_survival_ratio": _safe_divide(selector_candidate_count, screener_count),
                    "portfolio_survival_ratio": _safe_divide(portfolio_target_count, screener_count),
                    "selector_to_portfolio_survival_ratio": _safe_divide(portfolio_target_count, selector_candidate_count),
                    "selector_selection_ratio": _safe_divide(selector_candidate_count, selector_filtered_count),
                    "screener_mean_total_score": _safe_numeric_mean(screener_df, "total_score"),
                    "screener_mean_relative_strength_index": _safe_numeric_mean(screener_df, "relative_strength_index"),
                    "screener_mean_historical_range_score": _safe_numeric_mean(screener_df, "historical_range_score"),
                    "selector_mean_final_score": _safe_numeric_mean(history_df, "final_score"),
                    "selector_mean_final_score_sentiment": _safe_numeric_mean(history_df, "final_score_sentiment"),
                    "selector_mean_total_score": _safe_numeric_mean(history_df, "total_score"),
                    "selector_mean_score": _safe_numeric_mean(selector_candidates, "final_score_sentiment"),
                    "portfolio_mean_score": self._mean_entry_score(target_entries),
                }
            )

            benchmark_returns = self._compute_benchmark_forward_returns(as_of_date)
            row.update(benchmark_returns)
            row.update(self._compute_symbol_set_forward_metrics(
                selector_candidates["symbol"].astype(str).tolist(),
                weights=None,
                as_of_date=as_of_date,
                benchmark_returns=benchmark_returns,
                prefix="selector",
            ))
            row.update(self._compute_symbol_set_forward_metrics(
                [entry.symbol for entry in target_entries],
                weights={entry.symbol: float(entry.target_weight) for entry in target_entries},
                as_of_date=as_of_date,
                benchmark_returns=benchmark_returns,
                prefix="portfolio",
            ))
        except Exception as exc:
            LOGGER.exception(
                "Diagnostic screener en échec | scénario=%s date=%s",
                scenario.name,
                as_of_date,
            )
            row.update(
                {
                    "status": "error",
                    "error_message": str(exc),
                    "screener_count": 0,
                    "selector_filtered_count": 0,
                    "selector_candidate_count": 0,
                    "portfolio_target_count": 0,
                    "portfolio_accepted_count": 0,
                    "portfolio_reduced_count": 0,
                    "portfolio_rejected_count": 0,
                    "selector_survival_ratio": 0.0,
                    "portfolio_survival_ratio": 0.0,
                    "selector_to_portfolio_survival_ratio": 0.0,
                    "selector_selection_ratio": 0.0,
                    "screener_mean_total_score": float("nan"),
                    "screener_mean_relative_strength_index": float("nan"),
                    "screener_mean_historical_range_score": float("nan"),
                    "selector_mean_final_score": float("nan"),
                    "selector_mean_final_score_sentiment": float("nan"),
                    "selector_mean_total_score": float("nan"),
                    "selector_mean_score": float("nan"),
                    "portfolio_mean_score": float("nan"),
                }
            )
        return row

    def _build_pit_frames(
        self,
        snapshot_service: BackfillScoresHistoryService,
        as_of_date: date,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        screener_df = snapshot_service._compute_screener_snapshot(as_of_date)
        if screener_df.empty:
            return screener_df, pd.DataFrame(), snapshot_service._empty_history_frame()

        selector_df = snapshot_service._compute_selector_snapshot(screener_df, as_of_date)
        if selector_df.empty:
            return screener_df, selector_df, snapshot_service._empty_history_frame()

        sentiment_input = selector_df.copy()
        for column, default in _SELECTOR_SENTIMENT_COLUMNS.items():
            if column not in sentiment_input.columns:
                sentiment_input[column] = default
        sentiment_input = sentiment_input[list(_SELECTOR_SENTIMENT_COLUMNS.keys())].copy()
        enriched = snapshot_service.aggregator.merge(sentiment_input, trade_date=as_of_date)
        history_df = snapshot_service._to_history_snapshot(enriched, as_of_date)
        return screener_df, selector_df, history_df

    @staticmethod
    def _extract_selector_candidates(history_df: pd.DataFrame) -> pd.DataFrame:
        if history_df.empty or "is_candidate" not in history_df.columns:
            return pd.DataFrame()
        candidates = history_df[pd.to_numeric(history_df["is_candidate"], errors="coerce").fillna(0).astype(int) == 1].copy()
        if candidates.empty:
            return candidates
        def _as_series(col_name: str) -> pd.Series:
            col = candidates.get(col_name)
            if col is None:
                return pd.Series([pd.NA] * len(candidates), index=candidates.index, dtype="Float64")
            return pd.to_numeric(col, errors="coerce")

        score_series = _as_series("final_score_sentiment")
        walk_forward_series = _as_series("final_score_walk_forward")
        fallback_final = _as_series("final_score")
        fallback_total = _as_series("total_score")
        candidates["score_for_portfolio"] = walk_forward_series
        candidates["score_for_portfolio_source"] = pd.NA
        candidates.loc[walk_forward_series.notna(), "score_for_portfolio_source"] = "final_score_walk_forward"
        missing_mask = candidates["score_for_portfolio"].isna()
        candidates.loc[missing_mask, "score_for_portfolio"] = score_series
        candidates.loc[missing_mask & score_series.notna(), "score_for_portfolio_source"] = "final_score_sentiment"
        missing_mask = candidates["score_for_portfolio"].isna()
        candidates.loc[missing_mask, "score_for_portfolio"] = fallback_final
        candidates.loc[missing_mask & fallback_final.notna(), "score_for_portfolio_source"] = "final_score"
        missing_mask = candidates["score_for_portfolio"].isna()
        candidates.loc[missing_mask, "score_for_portfolio"] = fallback_total
        candidates.loc[missing_mask & fallback_total.notna(), "score_for_portfolio_source"] = "total_score"
        candidates = candidates[candidates["score_for_portfolio"].notna()].copy()
        return candidates

    def _build_portfolio_entries(self, selector_candidates: pd.DataFrame, as_of_date: date) -> list[PortfolioEntry]:
        if selector_candidates.empty:
            return []
        candidates = [
            CandidateScore(
                symbol=str(row["symbol"]),
                sector=str(row.get("sector") or "UNKNOWN"),
                score_used=float(row["score_for_portfolio"]),
                score_source=str(row.get("score_for_portfolio_source") or "final_score_sentiment"),
                company_idio_score=float(row["company_idio_score"]) if row.get("company_idio_score") is not None else None,
                macro_regime_score=float(row["macro_regime_score"]) if row.get("macro_regime_score") is not None else None,
                company_idio_signal_norm=float(row["company_idio_signal_norm"]) if row.get("company_idio_signal_norm") is not None else None,
                macro_regime_signal_norm=float(row["macro_regime_signal_norm"]) if row.get("macro_regime_signal_norm") is not None else None,
                company_idio_component=float(row["company_idio_component"]) if row.get("company_idio_component") is not None else None,
                macro_regime_component=float(row["macro_regime_component"]) if row.get("macro_regime_component") is not None else None,
                quant_component=float(row["quant_component"]) if row.get("quant_component") is not None else None,
                walk_forward_sentiment_weight=float(row["walk_forward_sentiment_weight"]) if row.get("walk_forward_sentiment_weight") is not None else None,
                walk_forward_macro_weight=float(row["walk_forward_macro_weight"]) if row.get("walk_forward_macro_weight") is not None else None,
                walk_forward_quant_weight=float(row["walk_forward_quant_weight"]) if row.get("walk_forward_quant_weight") is not None else None,
                calibration_run_id=str(row["calibration_run_id"]) if row.get("calibration_run_id") is not None else None,
                calibration_source=str(row["calibration_source"]) if row.get("calibration_source") is not None else None,
            )
            for row in selector_candidates.to_dict(orient="records")
        ]
        symbols = [candidate.symbol for candidate in candidates]
        prices = self._load_pit_prices(symbols, as_of_date=as_of_date, atr_window=self.risk_config.atr_window)
        return_matrix = self._load_pit_return_matrix(
            symbols,
            as_of_date=as_of_date,
            lookback_days=self.risk_config.correlation_lookback_days,
        )
        builder = PortfolioBuilder(self.risk_config)
        return builder.build(candidates, prices, predictions=None, win_rates=None, return_matrix=return_matrix)

    def _load_price_history(
        self,
        symbols: Sequence[str],
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        include_volume: bool = True,
    ) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame()
        date_column, close_expression = self._resolve_stock_bars_layout()
        select_columns = [
            "symbol",
            f"`{date_column}` AS bar_date",
            f"{close_expression} AS close_price",
            "`high` AS high_price",
            "`low` AS low_price",
        ]
        if include_volume:
            select_columns.append("volume")

        query = [
            f"SELECT {', '.join(select_columns)}",
            "FROM stock_bars_daily",
            "WHERE symbol IN :symbols",
        ]
        params: dict[str, Any] = {"symbols": list(symbols)}
        if start_date is not None:
            query.append(f"AND `{date_column}` >= :start_date")
            params["start_date"] = start_date
        if end_date is not None:
            query.append(f"AND `{date_column}` <= :end_date")
            params["end_date"] = end_date
        query.append(f"ORDER BY symbol, `{date_column}`")
        stmt = text("\n".join(query)).bindparams(bindparam("symbols", expanding=True))
        with self.engine.connect() as conn:
            history = pd.read_sql_query(stmt, conn, params=params)
        if history.empty:
            return history
        history["bar_date"] = pd.to_datetime(history["bar_date"], utc=False)
        return history

    def _load_pit_prices(self, symbols: Sequence[str], *, as_of_date: date, atr_window: int) -> dict[str, PriceInfo]:
        history = self._load_price_history(
            symbols,
            start_date=as_of_date - timedelta(days=max(atr_window * 5, 90)),
            end_date=as_of_date,
            include_volume=False,
        )
        if history.empty:
            return {}

        result: dict[str, PriceInfo] = {}
        for symbol, group in history.groupby("symbol"):
            ordered = group.sort_values("bar_date").tail(atr_window + 1).copy()
            if ordered.empty:
                continue
            last_close = float(pd.to_numeric(ordered["close_price"], errors="coerce").iloc[-1])
            prev_close = pd.to_numeric(ordered["close_price"], errors="coerce").shift(1)
            high = pd.to_numeric(ordered["high_price"], errors="coerce")
            low = pd.to_numeric(ordered["low_price"], errors="coerce")
            tr_components = pd.concat(
                [
                    high - low,
                    (high - prev_close).abs(),
                    (low - prev_close).abs(),
                ],
                axis=1,
            )
            true_range = tr_components.max(axis=1, skipna=True)
            atr_value = true_range.dropna().tail(atr_window).mean()
            result[str(symbol)] = PriceInfo(
                symbol=str(symbol),
                last_close=last_close,
                atr_20=float(atr_value) if pd.notna(atr_value) else None,
            )
        return result

    def _load_pit_return_matrix(
        self,
        symbols: Sequence[str],
        *,
        as_of_date: date,
        lookback_days: int,
    ) -> pd.DataFrame:
        history = self._load_price_history(
            symbols,
            start_date=as_of_date - timedelta(days=max(lookback_days * 3, 90)),
            end_date=as_of_date,
            include_volume=False,
        )
        if history.empty:
            return pd.DataFrame()

        trimmed = (
            history.sort_values(["symbol", "bar_date"])
            .groupby("symbol", group_keys=False)
            .tail(lookback_days + 1)
            .copy()
        )
        pivot = trimmed.pivot_table(index="bar_date", columns="symbol", values="close_price")
        returns = pivot.sort_index().pct_change(fill_method=None)
        return returns.iloc[1:]

    def _compute_benchmark_forward_returns(self, as_of_date: date) -> dict[str, float]:
        symbol_returns = self._compute_symbol_forward_returns(
            [self.base_screener_config.benchmark_symbol],
            as_of_date=as_of_date,
        )
        benchmark = symbol_returns.get(self.base_screener_config.benchmark_symbol, {})
        return {
            f"benchmark_forward_return_{horizon}d": float(benchmark.get(horizon, float("nan")))
            for horizon in self.forward_return_horizons
        }

    def _compute_symbol_set_forward_metrics(
        self,
        symbols: Sequence[str],
        *,
        weights: dict[str, float] | None,
        as_of_date: date,
        benchmark_returns: dict[str, float],
        prefix: str,
    ) -> dict[str, float]:
        metrics: dict[str, float] = {}
        for horizon in self.forward_return_horizons:
            metrics[f"{prefix}_forward_return_{horizon}d"] = float("nan")
            metrics[f"{prefix}_excess_return_{horizon}d"] = float("nan")
            metrics[f"{prefix}_positive_share_{horizon}d"] = float("nan")
            metrics[f"{prefix}_coverage_{horizon}d"] = 0.0

        clean_symbols = [str(symbol) for symbol in symbols if symbol]
        if not clean_symbols:
            return metrics

        symbol_returns = self._compute_symbol_forward_returns(clean_symbols, as_of_date=as_of_date)
        for horizon in self.forward_return_horizons:
            horizon_returns = {
                symbol: float(return_map[horizon])
                for symbol, return_map in symbol_returns.items()
                if horizon in return_map and pd.notna(return_map[horizon])
            }
            metrics[f"{prefix}_coverage_{horizon}d"] = float(len(horizon_returns))
            if not horizon_returns:
                continue
            weights_for_horizon = self._normalize_weights(horizon_returns, weights)
            weighted_return = sum(horizon_returns[symbol] * weights_for_horizon[symbol] for symbol in horizon_returns)
            metrics[f"{prefix}_forward_return_{horizon}d"] = float(weighted_return)
            metrics[f"{prefix}_positive_share_{horizon}d"] = float(
                np.mean([1.0 if value > 0.0 else 0.0 for value in horizon_returns.values()])
            )
            benchmark_value = benchmark_returns.get(f"benchmark_forward_return_{horizon}d", float("nan"))
            if pd.notna(benchmark_value):
                metrics[f"{prefix}_excess_return_{horizon}d"] = float(weighted_return - float(benchmark_value))
        return metrics

    def _compute_symbol_forward_returns(self, symbols: Sequence[str], *, as_of_date: date) -> dict[str, dict[int, float]]:
        max_horizon = max(self.forward_return_horizons)
        history = self._load_price_history(
            symbols,
            start_date=as_of_date,
            end_date=as_of_date + timedelta(days=max(max_horizon * 4, 30)),
            include_volume=False,
        )
        if history.empty:
            return {}

        symbol_returns: dict[str, dict[int, float]] = {}
        for symbol, group in history.groupby("symbol"):
            ordered = group.sort_values("bar_date").copy()
            ordered = ordered[ordered["bar_date"].dt.date >= as_of_date]
            if ordered.empty or ordered.iloc[0]["bar_date"].date() != as_of_date:
                continue
            close_series = pd.to_numeric(ordered["close_price"], errors="coerce").dropna().reset_index(drop=True)
            if close_series.empty:
                continue
            base_close = float(close_series.iloc[0])
            if base_close <= 0:
                continue
            returns_by_horizon: dict[int, float] = {}
            for horizon in self.forward_return_horizons:
                if len(close_series) <= horizon:
                    returns_by_horizon[horizon] = float("nan")
                    continue
                returns_by_horizon[horizon] = float(close_series.iloc[horizon] / base_close - 1.0)
            symbol_returns[str(symbol)] = returns_by_horizon
        return symbol_returns

    @staticmethod
    def _normalize_weights(
        horizon_returns: dict[str, float],
        weights: dict[str, float] | None,
    ) -> dict[str, float]:
        if not horizon_returns:
            return {}
        symbols = list(horizon_returns.keys())
        if not weights:
            equal_weight = 1.0 / len(symbols)
            return {symbol: equal_weight for symbol in symbols}
        valid_weights = {symbol: max(float(weights.get(symbol, 0.0)), 0.0) for symbol in symbols}
        total_weight = sum(valid_weights.values())
        if total_weight <= 0:
            equal_weight = 1.0 / len(symbols)
            return {symbol: equal_weight for symbol in symbols}
        return {symbol: weight / total_weight for symbol, weight in valid_weights.items()}

    @staticmethod
    def _mean_entry_score(entries: Sequence[PortfolioEntry]) -> float:
        if not entries:
            return float("nan")
        return float(np.mean([float(entry.score_used) for entry in entries]))


def export_screener_diagnostics(result: ScreenerDiagnosticsResult, output_dir: str | Path) -> dict[str, Path]:
    """Exporte les artefacts diagnostics au format CSV/JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    daily_path = output_path / "daily_metrics.csv"
    summary_path = output_path / "summary_metrics.csv"
    scenarios_path = output_path / "scenarios.csv"
    metadata_path = output_path / "metadata.json"
    market_regimes_path = output_path / "market_regimes.csv"
    summary_by_regime_path = output_path / "summary_metrics_by_regime.csv"

    result.daily_metrics.to_csv(daily_path, index=False)
    result.summary_metrics.to_csv(summary_path, index=False)
    result.scenario_frame().to_csv(scenarios_path, index=False)
    if not result.market_regimes.empty:
        result.market_regimes.to_csv(market_regimes_path, index=False)
    if not result.summary_metrics_by_regime.empty:
        result.summary_metrics_by_regime.to_csv(summary_by_regime_path, index=False)
    metadata_path.write_text(json.dumps(result.metadata(), ensure_ascii=False, indent=2), encoding="utf-8")

    artifacts = {
        "daily_metrics": daily_path,
        "summary_metrics": summary_path,
        "scenarios": scenarios_path,
        "metadata": metadata_path,
    }
    if not result.market_regimes.empty:
        artifacts["market_regimes"] = market_regimes_path
    if not result.summary_metrics_by_regime.empty:
        artifacts["summary_metrics_by_regime"] = summary_by_regime_path
    return artifacts


def export_screener_recommendations(
    recommendations: pd.DataFrame,
    recommendation_summary: dict[str, object],
    output_dir: str | Path,
) -> dict[str, Path]:
    """Exporte le classement phase 5 et le résumé JSON associé."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    recommendations_path = output_path / "scenario_recommendations.csv"
    summary_path = output_path / "recommendation_summary.json"

    recommendations.to_csv(recommendations_path, index=False)
    summary_path.write_text(json.dumps(recommendation_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "scenario_recommendations": recommendations_path,
        "recommendation_summary": summary_path,
    }


def export_screener_regime_recommendations(
    regime_recommendations: pd.DataFrame,
    regime_summary: dict[str, object],
    cross_regime_recommendations: pd.DataFrame,
    cross_regime_summary: dict[str, object],
    output_dir: str | Path,
) -> dict[str, Path]:
    """Exporte les recommandations détaillées de phase 6 par régime et cross-régimes."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    by_regime_path = output_path / "scenario_recommendations_by_regime.csv"
    by_regime_summary_path = output_path / "recommendation_summary_by_regime.json"
    cross_regime_path = output_path / "cross_regime_recommendations.csv"
    cross_regime_summary_path = output_path / "cross_regime_recommendation_summary.json"

    regime_recommendations.to_csv(by_regime_path, index=False)
    by_regime_summary_path.write_text(json.dumps(regime_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    cross_regime_recommendations.to_csv(cross_regime_path, index=False)
    cross_regime_summary_path.write_text(json.dumps(cross_regime_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "scenario_recommendations_by_regime": by_regime_path,
        "recommendation_summary_by_regime": by_regime_summary_path,
        "cross_regime_recommendations": cross_regime_path,
        "cross_regime_recommendation_summary": cross_regime_summary_path,
    }


def export_screener_objective_recommendations(
    objective_recommendations: pd.DataFrame,
    objective_summary: dict[str, object],
    output_dir: str | Path,
) -> dict[str, Path]:
    """Exporte les recommandations phase 7 adaptées à l'objectif opérationnel."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    recommendations_path = output_path / "scenario_recommendations_by_objective.csv"
    summary_path = output_path / "recommendation_summary_by_objective.json"

    objective_recommendations.to_csv(recommendations_path, index=False)
    summary_path.write_text(json.dumps(objective_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "scenario_recommendations_by_objective": recommendations_path,
        "recommendation_summary_by_objective": summary_path,
    }


def validate_recommendations_holdout(
    daily_metrics: pd.DataFrame,
    *,
    train_end,
    test_end,
    train_start=None,
    test_start=None,
    metric_column: str = "portfolio_forward_return_20d",
    scenario_column: str = "scenario_name",
    date_column: str = "trade_date",
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Phase 6.1.d — validation hold-out du diagnostic screener (phase 5-7).

    Compare le rang des scénarios sur la fenêtre **train** (≤ ``train_end``)
    et sur la fenêtre **test** (``test_start`` exclus de train, ≤ ``test_end``).
    Retourne un DataFrame trié par ``rank_train`` avec :

    - ``rank_train``, ``rank_test`` (1 = meilleur)
    - ``score_train``, ``score_test`` (moyenne du metric sur la fenêtre)
    - ``rank_delta`` = rank_test - rank_train (positif = dégrade)
    - ``score_delta``

    et un dict de résumé (``stable_top_k_ratio``, ``avg_rank_delta``, 
    ``status``).
    """
    summary: dict[str, object] = {"status": "empty", "message": "No data."}
    if daily_metrics is None or daily_metrics.empty:
        return pd.DataFrame(), summary
    if metric_column not in daily_metrics.columns:
        summary = {"status": "missing_metric", "message": f"colonne {metric_column} absente"}
        return pd.DataFrame(), summary
    if scenario_column not in daily_metrics.columns or date_column not in daily_metrics.columns:
        summary = {"status": "missing_columns", "message": "scenario_name/trade_date manquants"}
        return pd.DataFrame(), summary

    df = daily_metrics.copy()
    df[date_column] = pd.to_datetime(df[date_column])
    train_end_ts = pd.to_datetime(train_end)
    test_end_ts = pd.to_datetime(test_end)
    train_start_ts = pd.to_datetime(train_start) if train_start else df[date_column].min()
    test_start_ts = pd.to_datetime(test_start) if test_start else (train_end_ts + pd.Timedelta(days=1))

    train_mask = (df[date_column] >= train_start_ts) & (df[date_column] <= train_end_ts)
    test_mask = (df[date_column] >= test_start_ts) & (df[date_column] <= test_end_ts)
    if not train_mask.any() or not test_mask.any():
        summary = {"status": "empty_window", "message": "fenêtre train ou test vide"}
        return pd.DataFrame(), summary

    train_scores = (
        df.loc[train_mask].groupby(scenario_column)[metric_column].mean().rename("score_train")
    )
    test_scores = (
        df.loc[test_mask].groupby(scenario_column)[metric_column].mean().rename("score_test")
    )
    merged = pd.concat([train_scores, test_scores], axis=1).dropna()
    if merged.empty:
        summary = {"status": "empty_intersection", "message": "Aucun scénario commun train/test"}
        return pd.DataFrame(), summary

    merged["rank_train"] = merged["score_train"].rank(ascending=False, method="min").astype(int)
    merged["rank_test"] = merged["score_test"].rank(ascending=False, method="min").astype(int)
    merged["rank_delta"] = merged["rank_test"] - merged["rank_train"]
    merged["score_delta"] = merged["score_test"] - merged["score_train"]
    merged = merged.sort_values("rank_train").reset_index()

    top_k = max(min(5, len(merged) // 2), 1)
    train_top = set(merged.nsmallest(top_k, "rank_train")[scenario_column])
    test_top = set(merged.nsmallest(top_k, "rank_test")[scenario_column])
    stable_ratio = len(train_top & test_top) / float(top_k) if top_k else 0.0

    summary = {
        "status": "ok",
        "metric_column": metric_column,
        "train_start": str(train_start_ts.date()),
        "train_end": str(train_end_ts.date()),
        "test_start": str(test_start_ts.date()),
        "test_end": str(test_end_ts.date()),
        "scenarios_evaluated": int(len(merged)),
        "stable_top_k": int(top_k),
        "stable_top_k_ratio": float(stable_ratio),
        "avg_rank_delta": float(merged["rank_delta"].mean()),
        "avg_score_delta": float(merged["score_delta"].mean()),
    }
    return merged, summary


def export_holdout_validation(
    holdout_df: pd.DataFrame,
    holdout_summary: dict[str, object],
    output_dir: str | Path,
) -> dict[str, Path]:
    """Exporte les artefacts de la validation hold-out (Phase 6.1.d)."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    csv_path = output_path / "holdout_validation_recommendations.csv"
    json_path = output_path / "holdout_summary.json"
    holdout_df.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(holdout_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "holdout_validation_recommendations": csv_path,
        "holdout_summary": json_path,
    }
