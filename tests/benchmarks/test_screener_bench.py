"""Benchmarks screener — Sprint S14.

Usage:
    pytest tests/benchmarks/test_screener_bench.py --benchmark-only
"""
from __future__ import annotations

import pytest
import pandas as pd

from screener.models import ScreenerConfig
from screener.pipeline import screen_recent_prices


def _prices() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=130)
    rows = []
    for idx in range(500):
        base = 20.0 + idx / 10.0
        rows.extend(
            {
                "symbol": f"S{idx:04d}",
                "timestamp": day,
                "close_price": base * (1.0 + offset / 1000.0),
                "volume": 1_000_000.0,
            }
            for offset, day in enumerate(dates)
        )
    return pd.DataFrame(rows)


@pytest.mark.benchmark(group="screener")
def test_screener_liquidity_pass_benchmark(benchmark) -> None:
    """Benchmark : passe de liquidité sur un univers synthétique de 500 symboles."""
    prices = _prices()
    config = ScreenerConfig(min_history_days=100, min_relative_strength_index=0.01)
    result, metrics = benchmark(screen_recent_prices, prices, 0.0, config)
    assert metrics["symbols_pass_liquidity"] == 500
    assert not result.empty


@pytest.mark.benchmark(group="screener")
def test_screener_relative_strength_benchmark(benchmark) -> None:
    """Benchmark : calcul force relative 6m vs SPY."""
    prices = _prices()
    config = ScreenerConfig(min_history_days=100, min_relative_strength_index=0.01)
    result, metrics = benchmark(screen_recent_prices, prices, 0.0, config)
    assert metrics["symbols_pass_relative_strength"] == 500
    assert "relative_strength_index" in result
