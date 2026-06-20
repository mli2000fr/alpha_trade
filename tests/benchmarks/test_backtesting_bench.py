"""Benchmarks backtesting — Sprint S14.

Usage:
    pytest tests/benchmarks/test_backtesting_bench.py --benchmark-only
"""
from __future__ import annotations

import pytest


@pytest.mark.benchmark(group="backtesting")
def test_trading_constraints_instantiation_benchmark(benchmark) -> None:
    """Benchmark : instanciation TradingConstraintConfig (chemin chaud)."""
    from backtesting.trading_constraints import TradingConstraintConfig

    benchmark(lambda: TradingConstraintConfig(account_type="cash", swing_only=False))


@pytest.mark.benchmark(group="backtesting")
def test_commission_tiered_resolution_benchmark(benchmark) -> None:
    """Benchmark : résolution du preset de commission par palier."""
    from backtesting.trading_constraints import resolve_commission_preset

    benchmark(lambda: [resolve_commission_preset(eq) for eq in [1500, 5000, 25000, 100000]])
