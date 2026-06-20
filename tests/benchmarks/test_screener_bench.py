"""Benchmarks screener — Sprint S14.

Usage:
    pytest tests/benchmarks/test_screener_bench.py --benchmark-only
"""
from __future__ import annotations

import pytest


@pytest.mark.benchmark(group="screener")
def test_screener_liquidity_pass_benchmark(benchmark) -> None:
    """Benchmark : passe de liquidité sur un univers synthétique de 500 symboles."""
    from screener.stock_screener import StockScreener

    screener = StockScreener()
    # Warm-up
    benchmark(lambda: screener._compute_liquidity_pass(None))


@pytest.mark.benchmark(group="screener")
def test_screener_relative_strength_benchmark(benchmark) -> None:
    """Benchmark : calcul force relative 6m vs SPY."""
    from screener.stock_screener import StockScreener

    screener = StockScreener()
    benchmark(lambda: screener._compute_relative_strength(None))
