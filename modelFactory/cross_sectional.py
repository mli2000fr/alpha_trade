"""modelFactory/cross_sectional.py — Features cross-sectionnelles PIT-safe.

Refactored to load bars symbol-by-symbol instead of all at once,
avoiding massive MySQL queries that exceed max_allowed_packet.
"""
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

RAW_CROSS_SECTIONAL_COLUMNS_MAP: dict[str, str] = {
    "ret_20": "ret_20_rank",
    "ret_60": "ret_60_rank",
    "relative_strength_20_value": "relative_strength_20_rank",
    "relative_strength_60_value": "relative_strength_60_rank",
    "volatility_20": "volatility_20_rank",
    "dollar_volume_20": "dollar_volume_20_rank",
    "volume_ratio_20": "volume_ratio_20_rank_xs",
    "range_position_20": "range_position_20_rank",
}

RAW_CROSS_SECTIONAL_COLS = list(RAW_CROSS_SECTIONAL_COLUMNS_MAP.keys())


def _compute_symbol_raw_values(
    sym_df: pd.DataFrame,
    benchmark_returns: pd.DataFrame | None,
) -> pd.DataFrame:
    """Compute raw cross-sectional values for a single symbol (all dates)."""
    sym_sorted = sym_df.sort_values("date").reset_index(drop=True)
    prices = _build_adjusted_price_frame(sym_sorted)
    close = prices["close"]
    volume = pd.to_numeric(sym_sorted["volume"], errors="coerce").astype(float)
    daily_return = close.pct_change(fill_method=None)
    dollar_volume = close * volume

    part = pd.DataFrame(
        {
            "symbol": sym_sorted["symbol"].iloc[0] if "symbol" in sym_sorted.columns else "?",
            "date": pd.to_datetime(sym_sorted["date"]),
            "ret_20": close / close.shift(20) - 1.0,
            "ret_60": close / close.shift(60) - 1.0,
            "volatility_20": daily_return.rolling(20).std(),
            "dollar_volume_20": dollar_volume.rolling(20).mean(),
            "volume_ratio_20": volume / volume.rolling(20).mean().clip(lower=1.0),
            "range_position_20": _range_position(close, 20),
        }
    )
    if benchmark_returns is not None and not benchmark_returns.empty:
        part = part.merge(benchmark_returns, on="date", how="left")
        part["relative_strength_20_value"] = part["ret_20"] - part["benchmark_return_20"]
        part["relative_strength_60_value"] = part["ret_60"] - part["benchmark_return_60"]
    else:
        part["relative_strength_20_value"] = part["ret_20"]
        part["relative_strength_60_value"] = part["ret_60"]
    return part


def _build_benchmark_returns(
    benchmark_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Build benchmark return columns for relative strength computation."""
    if benchmark_df is None or benchmark_df.empty:
        return pd.DataFrame()
    bench = benchmark_df.copy()
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.sort_values("date").reset_index(drop=True)
    prices = _build_adjusted_price_frame(bench)
    close = prices["close"]
    out = pd.DataFrame({"date": bench["date"]})
    out["benchmark_return_20"] = close / close.shift(20) - 1.0
    out["benchmark_return_60"] = close / close.shift(60) - 1.0
    return out


def build_cross_sectional_features_from_db(
    engine,
    symbols: list[str],
    *,
    benchmark_df: pd.DataFrame | None = None,
    min_universe_size: int = 20,
    start_date=None,
    end_date=None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build cross-sectional features by loading bars symbol-by-symbol.

    Avoids loading all symbols at once -- queries one symbol's bars at a time,
    accumulates raw values, then computes percentile ranks per date.

    This replaces the old approach of loading all universe bars in a single
    massive MySQL query that exceeded max_allowed_packet.
    """
    from modelFactory.data_loader import load_symbol_bars

    if not symbols:
        return pd.DataFrame(columns=["symbol", "date", *CROSS_SECTIONAL_FEATURE_COLUMNS]), {
            "enabled": False,
            "reason": "empty_symbols_list",
            "feature_columns": list(CROSS_SECTIONAL_FEATURE_COLUMNS),
        }

    benchmark_returns = _build_benchmark_returns(benchmark_df)

    all_raw_parts: list[pd.DataFrame] = []
    loaded_count = 0
    skipped_count = 0

    for symbol in symbols:
        try:
            sym_df = load_symbol_bars(engine, symbol, end_date=end_date, start_date=start_date)
        except Exception:
            skipped_count += 1
            continue
        if sym_df.empty or len(sym_df) < 60:
            skipped_count += 1
            continue
        raw_part = _compute_symbol_raw_values(sym_df, benchmark_returns)
        raw_part["symbol"] = symbol
        if not raw_part.empty:
            all_raw_parts.append(raw_part)
        loaded_count += 1

    if not all_raw_parts:
        return pd.DataFrame(columns=["symbol", "date", *CROSS_SECTIONAL_FEATURE_COLUMNS]), {
            "enabled": True,
            "reason": "no_valid_symbols",
            "feature_columns": list(CROSS_SECTIONAL_FEATURE_COLUMNS),
            "loaded_count": loaded_count,
            "skipped_count": skipped_count,
        }

    raw_panel = pd.concat(all_raw_parts, ignore_index=True)
    raw_panel["universe_symbol_count"] = raw_panel.groupby("date")["symbol"].transform("nunique")

    for raw_col, rank_col in RAW_CROSS_SECTIONAL_COLUMNS_MAP.items():
        if raw_col not in raw_panel.columns:
            raw_panel[rank_col] = 0.5
            continue
        rank_series = raw_panel.groupby("date")[raw_col].rank(method="average", pct=True)
        rank_series = rank_series.where(raw_panel["universe_symbol_count"] >= min_universe_size, 0.5)
        raw_panel[rank_col] = rank_series.astype(float)

    feature_frame = raw_panel[["symbol", "date", *CROSS_SECTIONAL_FEATURE_COLUMNS]].copy()
    diagnostics = {
        "enabled": True,
        "feature_columns": list(CROSS_SECTIONAL_FEATURE_COLUMNS),
        "output_rows": int(len(feature_frame)),
        "unique_symbols": int(raw_panel["symbol"].nunique()),
        "unique_dates": int(raw_panel["date"].nunique()),
        "min_universe_size": int(min_universe_size),
        "dates_below_min_universe": int((raw_panel.groupby("date")["universe_symbol_count"].first() < min_universe_size).sum()),
        "loaded_count": loaded_count,
        "skipped_count": skipped_count,
    }
    return feature_frame, diagnostics


# ---------------------------------------------------------------------------
# Legacy wrapper -- accepts a pre-loaded DataFrame (backward compat)
# ---------------------------------------------------------------------------

def build_cross_sectional_features(
    universe_df: pd.DataFrame | None,
    *,
    benchmark_df: pd.DataFrame | None = None,
    min_universe_size: int = 20,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build cross-sectional features from a pre-loaded DataFrame.

    Prefer ``build_cross_sectional_features_from_db`` which loads bars
    symbol-by-symbol and avoids massive MySQL queries.
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
        raw_part = _compute_symbol_raw_values(sym_df, benchmark_returns)
        if not raw_part.empty:
            parts.append(raw_part)

    raw_panel = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["symbol", "date", *RAW_CROSS_SECTIONAL_COLS])
    raw_panel["universe_symbol_count"] = raw_panel.groupby("date")["symbol"].transform("nunique")

    for raw_col, rank_col in RAW_CROSS_SECTIONAL_COLUMNS_MAP.items():
        if raw_col not in raw_panel.columns:
            raw_panel[rank_col] = 0.5
            continue
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
    """Merge cross-sectional features on (symbol, date) PIT-safe."""
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
