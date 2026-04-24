from datetime import datetime, timezone

import numpy as np
import pandas as pd

from screener.models import ScreenerConfig
from screener import RESULT_COLUMNS, compute_scores_from_prices


def _make_symbol_frame(symbol: str, base_price: float, drift: float, volume: float, rows: int = 2600) -> pd.DataFrame:
    dates = pd.bdate_range(end=datetime.now(timezone.utc), periods=rows)
    trend = np.linspace(0.0, drift, rows)
    close = base_price * (1.0 + trend)
    high = close * 1.01
    low = close * 0.99

    return pd.DataFrame(
        {
            "symbol": symbol,
            "timestamp": dates,
            "close_price": close,
            "high_price": high,
            "low_price": low,
            "volume": np.full(rows, volume),
        }
    )


def test_compute_scores_filters_illiquid_symbols_and_sorts_descending() -> None:
    config = ScreenerConfig(liquidity_threshold_usd=500_000.0)
    prices = pd.concat(
        [
            _make_symbol_frame("AAA", base_price=50.0, drift=0.30, volume=25_000),
            _make_symbol_frame("BBB", base_price=20.0, drift=0.02, volume=2_000),
            _make_symbol_frame("CCC", base_price=100.0, drift=-0.05, volume=12_000),
        ],
        ignore_index=True,
    )

    scores = compute_scores_from_prices(prices, spy_return_6m=0.06, config=config)

    assert list(scores.columns) == RESULT_COLUMNS
    assert "BBB" not in set(scores["symbol"])
    assert list(scores["total_score"]) == sorted(scores["total_score"], reverse=True)
    assert scores["total_score"].between(0.0, 100.0).all()
    assert scores.iloc[0]["symbol"] == "AAA"
    assert set(scores["is_candidate"]) == {0}
    assert scores["sector"].isna().all()
    assert scores["last_updated_score"].notna().all()
    assert scores["last_updated_scan"].notna().all()
    assert (scores["last_updated_score"] == scores["last_updated_scan"]).all()


def test_compute_scores_returns_empty_frame_when_benchmark_is_invalid() -> None:
    config = ScreenerConfig(liquidity_threshold_usd=100.0)
    prices = _make_symbol_frame("AAA", base_price=50.0, drift=0.10, volume=1_000)

    scores = compute_scores_from_prices(prices, spy_return_6m=-1.0, config=config)

    assert scores.empty
    assert list(scores.columns) == RESULT_COLUMNS


def test_compute_scores_returns_empty_frame_for_empty_input() -> None:
    scores = compute_scores_from_prices(pd.DataFrame(), spy_return_6m=0.05, config=ScreenerConfig())

    assert scores.empty
    assert list(scores.columns) == RESULT_COLUMNS


def test_compute_scores_excludes_symbols_with_insufficient_history() -> None:
    config = ScreenerConfig(liquidity_threshold_usd=100.0, min_history_days=252)
    prices = _make_symbol_frame("NEW", base_price=30.0, drift=0.15, volume=20_000, rows=120)

    scores = compute_scores_from_prices(prices, spy_return_6m=0.03, config=config)

    assert scores.empty
    assert list(scores.columns) == RESULT_COLUMNS


def test_compute_scores_excludes_symbols_below_min_close_price() -> None:
    config = ScreenerConfig(liquidity_threshold_usd=100.0, min_close_price=5.0)
    prices = _make_symbol_frame("PENNY", base_price=2.0, drift=0.05, volume=100_000, rows=400)

    scores = compute_scores_from_prices(prices, spy_return_6m=0.03, config=config)

    assert scores.empty
    assert list(scores.columns) == RESULT_COLUMNS


