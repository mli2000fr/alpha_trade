from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.cross_sectional import CROSS_SECTIONAL_FEATURE_COLUMNS, build_cross_sectional_features, merge_cross_sectional_features


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


