from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.cross_sectional import CROSS_SECTIONAL_FEATURE_COLUMNS, build_cross_sectional_features, merge_cross_sectional_features
from modelFactory.cross_sectional import (
    GLOBAL_PRED_FEATURE_COLUMNS,
    SECTOR_FEATURE_COLUMNS,
    _compute_sector_features,
    _load_sector_mapping,
)


def _make_symbol_bars(symbol: str, base: float, n: int = 90) -> pd.DataFrame:
	close = pd.Series(np.linspace(base, base + 20.0, n), dtype=float)
	return pd.DataFrame(
		{
			"symbol": [symbol] * n,
			"date": pd.date_range("2020-01-01", periods=n, freq="D"),
			"open": close * 0.99,
			"high": close * 1.01,
			"low": close * 0.98,
			"close": close,
			"volume": np.linspace(1_000_000, 1_100_000, n),
			"adj_close": close,
			"vwap": close,
			"daily_return": 0.0,
			"is_filled": 0,
		}
	)


def test_build_cross_sectional_features_returns_rank_columns() -> None:
	universe = pd.concat([
		_make_symbol_bars("AAPL", 100.0),
		_make_symbol_bars("MSFT", 120.0),
		_make_symbol_bars("NVDA", 140.0),
	], ignore_index=True)
	benchmark = _make_symbol_bars("SPY", 90.0)

	result, diagnostics = build_cross_sectional_features(universe, benchmark_df=benchmark, min_universe_size=2)

	assert not result.empty
	for col in CROSS_SECTIONAL_FEATURE_COLUMNS:
		assert col in result.columns
	assert diagnostics["enabled"] is True
	assert diagnostics["unique_symbols"] == 3


def test_merge_cross_sectional_features_fills_missing_columns_with_neutral_values() -> None:
	symbol_df = pd.DataFrame(
		{
			"symbol": ["AAPL"],
			"date": [pd.Timestamp("2020-01-01")],
			"daily_return": [0.01],
		}
	)

	merged = merge_cross_sectional_features(symbol_df, pd.DataFrame(columns=["symbol", "date"]))

	for col in CROSS_SECTIONAL_FEATURE_COLUMNS:
		assert merged[col].iloc[0] == 0.5


# ═══════════════════════════════════════════════════════════════════════════
# Sector feature tests
# ═══════════════════════════════════════════════════════════════════════════

def _make_raw_panel() -> pd.DataFrame:
    """Build a minimal raw_panel mimicking _compute_symbol_raw_values output."""
    symbols = ["AAPL", "MSFT", "JPM", "BAC", "XOM", "CVX"]
    dates = pd.date_range("2020-01-15", periods=60, freq="D")
    rows: list[dict] = []
    for sym in symbols:
        for i, d in enumerate(dates):
            rows.append({
                "symbol": sym,
                "date": d,
                "ret_20": 0.02 + 0.01 * i + hash(sym) % 5 * 0.005,
                "ret_60": 0.05 + 0.005 * i,
                "volatility_20": 0.15 + 0.01 * (i % 10),
                "dollar_volume_20": 1e9 + 1e8 * (i % 5),
                "benchmark_return_20": 0.01 + 0.002 * i,
                "benchmark_return_60": 0.03 + 0.001 * i,
            })
    return pd.DataFrame(rows)


def test_sector_feature_columns_defined() -> None:
    """SECTOR_FEATURE_COLUMNS must contain the expected columns."""
    expected = [
        "sector_ret_20",
        "sector_ret_60",
        "sector_vol_20",
        "sector_relative_strength_20",
        "sector_dollar_volume_20",
        "sector_symbol_count",
        "stock_vs_sector_ret_20",
        "stock_vs_sector_ret_60",
    ]
    assert SECTOR_FEATURE_COLUMNS == expected


def test_compute_sector_features_empty_map_returns_empty() -> None:
    """With empty sector_map, return empty DataFrame with correct columns."""
    raw = _make_raw_panel()
    result = _compute_sector_features(raw, {})
    assert result.empty
    for col in SECTOR_FEATURE_COLUMNS:
        assert col in result.columns


def test_compute_sector_features_aggregates_by_sector() -> None:
    """Sector aggregates should be computed per (date, sector)."""
    raw = _make_raw_panel()
    sector_map = {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "JPM": "Financials",
        "BAC": "Financials",
        "XOM": "Energy",
        "CVX": "Energy",
    }
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    assert not result.empty
    for col in SECTOR_FEATURE_COLUMNS:
        assert col in result.columns

    # Same sector, same date → same sector_ret_20
    tech_date = result[(result["symbol"] == "AAPL") & (result["date"] == pd.Timestamp("2020-01-20"))]
    msft_date = result[(result["symbol"] == "MSFT") & (result["date"] == pd.Timestamp("2020-01-20"))]
    if not tech_date.empty and not msft_date.empty:
        assert abs(tech_date["sector_ret_20"].iloc[0] - msft_date["sector_ret_20"].iloc[0]) < 0.01


def test_compute_sector_features_stock_vs_sector() -> None:
    """stock_vs_sector_ret_20 should equal ret_20 - sector_ret_20."""
    raw = _make_raw_panel()
    sector_map = {"AAPL": "Technology", "MSFT": "Technology"}
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    sample = result[result["symbol"] == "AAPL"].iloc[0]
    # ret_20 is from the raw_panel merged in; stock_vs_sector = ret_20 - sector_ret_20
    assert "sector_ret_20" in result.columns
    assert "stock_vs_sector_ret_20" in result.columns
    # stock_vs_sector should be near 0 on average (same-sector stocks move together)
    mean_alpha = result[result["symbol"] == "AAPL"]["stock_vs_sector_ret_20"].mean()
    assert abs(mean_alpha) < 0.1  # should be small


def test_compute_sector_features_handles_small_sectors() -> None:
    """Sectors with < min_symbols_per_sector should get NaN → ffill → 0."""
    raw = _make_raw_panel()
    sector_map = {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "JPM": "Financials",  # only 1 symbol in Financials
    }
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    # Financials (JPM) should have 0 or NaN values since sector has < 2 symbols
    jpm_rows = result[result["symbol"] == "JPM"]
    if not jpm_rows.empty:
        # After ffill+fillna(0), values should be 0 (no prior data for this sector)
        assert jpm_rows["sector_ret_20"].iloc[0] == 0.0 or pd.isna(jpm_rows["sector_ret_20"].iloc[0])


def test_compute_sector_features_symbol_not_in_map() -> None:
    """Symbols not in sector_map should get fillna(0) for sector features."""
    raw = _make_raw_panel()
    sector_map = {"AAPL": "Technology"}  # MSFT not mapped
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    msft_rows = result[result["symbol"] == "MSFT"]
    if not msft_rows.empty:
        assert msft_rows["sector_ret_20"].iloc[0] == 0.0


def test_merge_cross_sectional_features_handles_sector_columns() -> None:
    """merge_cross_sectional_features should fill missing sector columns with 0.0."""
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2020-01-01")],
        "daily_return": [0.01],
    })
    merged = merge_cross_sectional_features(symbol_df, None)

    # Cross-sectional columns → 0.5
    for col in CROSS_SECTIONAL_FEATURE_COLUMNS:
        assert merged[col].iloc[0] == 0.5
    # Sector columns → 0.0
    for col in SECTOR_FEATURE_COLUMNS:
        assert merged[col].iloc[0] == 0.0


def test_merge_cross_sectional_features_preserves_sector_values() -> None:
    """When sector columns are present in cross_sectional_df, they should be preserved."""
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2020-01-15")],
        "daily_return": [0.01],
    })
    cs_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2020-01-15")],
        "sector_ret_20": [0.035],
        "sector_vol_20": [0.18],
        "stock_vs_sector_ret_20": [-0.005],
    })
    merged = merge_cross_sectional_features(symbol_df, cs_df)

    assert merged["sector_ret_20"].iloc[0] == 0.035
    assert merged["sector_vol_20"].iloc[0] == 0.18
    assert merged["stock_vs_sector_ret_20"].iloc[0] == -0.005
    # Missing sector columns should get default 0.0
    for col in SECTOR_FEATURE_COLUMNS:
        if col not in cs_df.columns:
            assert merged[col].iloc[0] == 0.0


def test_compute_sector_features_relative_strength() -> None:
    """sector_relative_strength_20 = sector_ret_20 - benchmark_return_20."""
    raw = _make_raw_panel()
    sector_map = {"AAPL": "Technology", "MSFT": "Technology"}
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    assert "sector_relative_strength_20" in result.columns
    assert "sector_ret_20" in result.columns
    # Should not be all zeros
    assert result["sector_relative_strength_20"].abs().max() > 0.001


def test_compute_sector_features_sector_symbol_count() -> None:
    """sector_symbol_count should reflect the number of symbols in the sector."""
    raw = _make_raw_panel()
    sector_map = {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "JPM": "Financials",
        "BAC": "Financials",
    }
    result = _compute_sector_features(raw, sector_map, min_symbols_per_sector=2)

    tech_count = result[result["symbol"] == "AAPL"]["sector_symbol_count"].iloc[-1]
    fin_count = result[result["symbol"] == "JPM"]["sector_symbol_count"].iloc[-1]
    assert tech_count == 2.0
    assert fin_count == 2.0


# ─────────────────────────────────────────────────────────────────────
# Approche 2 — Stacking : GLOBAL_PRED_FEATURE_COLUMNS
# ─────────────────────────────────────────────────────────────────────

def test_global_pred_feature_columns_defined() -> None:
    """GLOBAL_PRED_FEATURE_COLUMNS must contain the expected column."""
    assert GLOBAL_PRED_FEATURE_COLUMNS == ["global_pred_long"]


def test_merge_cross_sectional_features_handles_global_pred() -> None:
    """merge_cross_sectional_features should handle global_pred_long if present in cache."""
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "date": [pd.Timestamp("2022-06-15"), pd.Timestamp("2022-06-15")],
        "daily_return": [0.01, -0.005],
    })
    cs_df = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "date": [pd.Timestamp("2022-06-15"), pd.Timestamp("2022-06-15")],
        "ret_20_rank": [0.65, 0.45],
        "global_pred_long": [0.72, 0.48],
    })
    merged = merge_cross_sectional_features(symbol_df, cs_df)

    assert "global_pred_long" in merged.columns
    assert merged.loc[merged["symbol"] == "AAPL", "global_pred_long"].iloc[0] == 0.72
    assert merged.loc[merged["symbol"] == "MSFT", "global_pred_long"].iloc[0] == 0.48


def test_merge_cross_sectional_features_fills_missing_global_pred() -> None:
    """When global_pred_long is NOT in cache, it should default to 0.5 (neutral)."""
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2022-01-01")],
        "daily_return": [0.01],
    })
    # Cache without global_pred_long
    cs_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2022-01-01")],
        "ret_20_rank": [0.55],
    })
    merged = merge_cross_sectional_features(symbol_df, cs_df)

    assert "global_pred_long" in merged.columns
    assert merged["global_pred_long"].iloc[0] == 0.5


def test_merge_cross_sectional_features_global_pred_no_cache() -> None:
    """When cache is None, global_pred_long defaults to 0.5 like other rank columns."""
    symbol_df = pd.DataFrame({
        "symbol": ["AAPL"],
        "date": [pd.Timestamp("2022-01-01")],
        "daily_return": [0.01],
    })
    merged = merge_cross_sectional_features(symbol_df, None)

    assert "global_pred_long" in merged.columns
    assert merged["global_pred_long"].iloc[0] == 0.5
