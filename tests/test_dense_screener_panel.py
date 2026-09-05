from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.dense_screener_panel import (
    _calendar_window_return, build_quality_report, compute_dense_panel)
from screener.models import ScreenerConfig


def test_calendar_window_return_uses_first_observation_inside_calendar_window() -> None:
    dates = pd.Series(pd.to_datetime(["2024-01-01", "2024-01-05", "2024-01-10"]))
    result = _calendar_window_return(dates, pd.Series([100.0, 110.0, 121.0]), 6)
    assert np.allclose(result, [0.0, 0.1, 0.1])


def _bars() -> pd.DataFrame:
    rows = []
    for symbol, multiplier in (("AAA", 1.02), ("BBB", 0.99), ("SPY", 1.005)):
        close = 10.0
        for date in pd.bdate_range("2024-01-01", periods=12):
            close *= multiplier
            rows.append({"date": date, "symbol": symbol, "close": close,
                         "high": close * 1.01, "low": close * 0.99,
                         "volume": 1_000_000, "is_filled": 0})
    return pd.DataFrame(rows)


def _config() -> ScreenerConfig:
    return ScreenerConfig(
        min_history_days=2, min_close_price=1.0, lookback_liquidity_bars=3,
        lookback_relative_days=6, historical_range_lookback_days=6,
        liquidity_threshold_usd=0.0, min_relative_strength_index=100.0,
        min_historical_range_score=0.0, first_pass_window_days=6)


def test_dense_panel_keeps_rejected_rows_and_marks_oracle_top_pool() -> None:
    date = pd.bdate_range("2024-01-01", periods=12)[-1]
    oracle = pd.DataFrame({"date": [date, date], "symbol": ["AAA", "BBB"],
        "oracle_oof_available": [True, True], "oracle_percentile": [0.9, 0.2],
        "oracle_top_pool": [True, False]})
    panel = compute_dense_panel(oracle, _bars(), _config())
    by_symbol = panel.set_index("symbol")
    assert len(panel) == 2 and panel["oracle_top_pool"].sum() == 1
    assert by_symbol.loc["AAA", "filter_all_pass"]
    assert not by_symbol.loc["BBB", "filter_relative_strength_pass"]
    assert by_symbol.loc["BBB", "rejection_reasons"] == "relative_strength"
    assert panel["total_score_dense"].notna().all()
    assert panel.loc[~panel["filter_all_pass"], "total_score_survivors"].isna().all()


def test_filled_bar_is_retained_but_fails_data_quality() -> None:
    bars = _bars()
    index = bars[bars["symbol"].eq("AAA")].index[-1]
    bars.loc[index, "is_filled"] = 1
    oracle = pd.DataFrame({"date": [bars.loc[index, "date"]], "symbol": ["AAA"],
        "oracle_oof_available": [True], "oracle_percentile": [0.9],
        "oracle_top_pool": [True]})
    panel = compute_dense_panel(oracle, bars, _config())
    assert not bool(panel.loc[0, "data_quality_valid"])
    assert pd.notna(panel.loc[0, "historical_range_score"])
    assert "data_quality_valid" in set(build_quality_report(panel)["metric"])
