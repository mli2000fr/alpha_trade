"""modelFactory/cross_sectional.py — Features cross-sectionnelles PIT-safe à partir des barres historiques."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from modelFactory.features import _build_adjusted_price_frame, _range_position

CROSS_SECTIONAL_FEATURE_COLUMNS: list[str] = [
    "ret_20_rank",
    "ret_60_rank",
    "relative_strength_20_rank",
    "relative_strength_60_rank",
    "volatility_20_rank",
    "dollar_volume_20_rank",
    "volume_ratio_20_rank_xs",
    "range_position_20_rank",
]


RAW_CROSS_SECTIONAL_COLUMNS: dict[str, str] = {
    "ret_20": "ret_20_rank",
    "ret_60": "ret_60_rank",
    "relative_strength_20_value": "relative_strength_20_rank",
    "relative_strength_60_value": "relative_strength_60_rank",
    "volatility_20": "volatility_20_rank",
    "dollar_volume_20": "dollar_volume_20_rank",
    "volume_ratio_20": "volume_ratio_20_rank_xs",
    "range_position_20": "range_position_20_rank",
}


def build_cross_sectional_features(
    universe_df: pd.DataFrame | None,
    *,
    benchmark_df: pd.DataFrame | None = None,
    min_universe_size: int = 20,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Construit des features cross-sectionnelles par `(symbol, date)`.

    Les features sont calculées uniquement depuis les barres historiques disponibles,
    puis transformées en ranks journaliers percentile au sein de l'univers.
    """
    if universe_df is None or universe_df.empty:
        return pd.DataFrame(columns=["symbol", "date", *CROSS_SECTIONAL_FEATURE_COLUMNS]), {
            "enabled": False,
            "reason": "empty_universe",
            "feature_columns": list(CROSS_SECTIONAL_FEATURE_COLUMNS),
        }

    required_cols = {"symbol", "date", "close", "adj_close", "volume"}
    missing = required_cols.difference(universe_df.columns)
    if missing:
        raise ValueError(f"build_cross_sectional_features missing required columns: {sorted(missing)}")

    panel = universe_df.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)

    benchmark_returns = _build_benchmark_returns(benchmark_df)
    parts: list[pd.DataFrame] = []
    for symbol, sym_df in panel.groupby("symbol", sort=False):
        sym_sorted = sym_df.sort_values("date").reset_index(drop=True)
        prices = _build_adjusted_price_frame(sym_sorted)
        close = prices["close"]
        volume = pd.to_numeric(sym_sorted["volume"], errors="coerce").astype(float)
        daily_return = close.pct_change(fill_method=None)
        dollar_volume = close * volume

        part = pd.DataFrame(
            {
                "symbol": symbol,
                "date": pd.to_datetime(sym_sorted["date"]),
                "ret_20": close / close.shift(20) - 1.0,
                "ret_60": close / close.shift(60) - 1.0,
                "volatility_20": daily_return.rolling(20).std(),
                "dollar_volume_20": dollar_volume.rolling(20).mean(),
                "volume_ratio_20": volume / volume.rolling(20).mean().clip(lower=1.0),
                "range_position_20": _range_position(close, 20),
            }
        )
        if not benchmark_returns.empty:
            part = part.merge(benchmark_returns, on="date", how="left")
            part["relative_strength_20_value"] = part["ret_20"] - part["benchmark_return_20"]
            part["relative_strength_60_value"] = part["ret_60"] - part["benchmark_return_60"]
        else:
            part["relative_strength_20_value"] = part["ret_20"]
            part["relative_strength_60_value"] = part["ret_60"]
        parts.append(part)

    raw_panel = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["symbol", "date", *RAW_CROSS_SECTIONAL_COLUMNS])
    raw_panel["universe_symbol_count"] = raw_panel.groupby("date")["symbol"].transform("nunique")

    for raw_col, rank_col in RAW_CROSS_SECTIONAL_COLUMNS.items():
        rank_series = raw_panel.groupby("date")[raw_col].rank(method="average", pct=True)
        rank_series = rank_series.where(raw_panel["universe_symbol_count"] >= min_universe_size, 0.5)
        raw_panel[rank_col] = rank_series.astype(float)

    feature_frame = raw_panel[["symbol", "date", *CROSS_SECTIONAL_FEATURE_COLUMNS]].copy()
    diagnostics = {
        "enabled": True,
        "feature_columns": list(CROSS_SECTIONAL_FEATURE_COLUMNS),
        "input_rows": int(len(universe_df)),
        "output_rows": int(len(feature_frame)),
        "unique_symbols": int(panel["symbol"].nunique()),
        "unique_dates": int(panel["date"].nunique()),
        "min_universe_size": int(min_universe_size),
        "dates_below_min_universe": int((raw_panel.groupby("date")["universe_symbol_count"].first() < min_universe_size).sum()),
    }
    return feature_frame, diagnostics


def merge_cross_sectional_features(
    symbol_df: pd.DataFrame,
    cross_sectional_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Merge les features cross-sectionnelles sur `(symbol, date)` de façon PIT-safe."""
    if cross_sectional_df is None or cross_sectional_df.empty:
        merged = symbol_df.copy()
        for col in CROSS_SECTIONAL_FEATURE_COLUMNS:
            if col not in merged.columns:
                merged[col] = 0.5
        return merged

    merged = symbol_df.merge(cross_sectional_df, on=["symbol", "date"], how="left")
    for col in CROSS_SECTIONAL_FEATURE_COLUMNS:
        if col not in merged.columns:
            merged[col] = 0.5
    return merged


def _build_benchmark_returns(benchmark_df: pd.DataFrame | None) -> pd.DataFrame:
    if benchmark_df is None or benchmark_df.empty:
        return pd.DataFrame(columns=["date", "benchmark_return_20", "benchmark_return_60"])
    bench = benchmark_df.copy().sort_values("date").reset_index(drop=True)
    bench["date"] = pd.to_datetime(bench["date"])
    prices = _build_adjusted_price_frame(bench)
    close = prices["close"]
    return pd.DataFrame(
        {
            "date": bench["date"],
            "benchmark_return_20": close / close.shift(20) - 1.0,
            "benchmark_return_60": close / close.shift(60) - 1.0,
        }
    )

