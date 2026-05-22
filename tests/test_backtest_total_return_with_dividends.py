"""Sprint S3 / A-006 — convention canonique total_return = MTM + dividendes.

Vérifie que :
- ``compute_total_return_with_dividends`` applique bien
  ``total_return = mtm_return + dividend_yield`` (convention README §15-16).
- Différence ``total - mtm`` = `dividend_yield` exactement.
- ``load_dividends_received`` est défensif (DB indispo → 0.0).
- Le module backtesting expose bien la métrique
  ``total_return_with_dividends_pct`` dans ``BacktestReport``.
"""
from __future__ import annotations

import pytest

from backtesting.analytics import compare_total_return_to_oracle, compute_total_return_with_dividends
from backtesting.report import BacktestReport, load_dividends_received


def test_total_return_equals_mtm_plus_dividends():
    out = compute_total_return_with_dividends(
        initial_equity=10_000.0,
        final_value_mtm=10_500.0,  # +5 % MTM
        dividends_received=100.0,  # +1 % yield
    )
    assert out["mtm_return_pct"] == pytest.approx(5.0, abs=1e-6)
    assert out["dividend_yield_pct"] == pytest.approx(1.0, abs=1e-6)
    assert out["total_return_pct"] == pytest.approx(6.0, abs=1e-6)
    assert (out["total_return_pct"] - out["mtm_return_pct"]) == pytest.approx(
        out["dividend_yield_pct"], abs=1e-6
    )


def test_dividends_only_no_mtm_change():
    out = compute_total_return_with_dividends(
        initial_equity=5_000.0,
        final_value_mtm=5_000.0,
        dividends_received=10.0,
    )
    assert out["mtm_return_pct"] == 0.0
    assert out["dividend_yield_pct"] == pytest.approx(0.2, abs=1e-6)
    assert out["total_return_pct"] == pytest.approx(0.2, abs=1e-6)


def test_no_dividends_total_equals_mtm():
    out = compute_total_return_with_dividends(
        initial_equity=10_000.0,
        final_value_mtm=12_000.0,
        dividends_received=0.0,
    )
    assert out["total_return_pct"] == pytest.approx(out["mtm_return_pct"], abs=1e-9)
    assert out["dividend_yield_pct"] == 0.0


def test_zero_initial_equity_returns_zeros():
    out = compute_total_return_with_dividends(0.0, 100.0, 10.0)
    assert out == {"mtm_return_pct": 0.0, "dividend_yield_pct": 0.0, "total_return_pct": 0.0}


def test_load_dividends_received_defensive_when_engine_broken():
    class _BrokenEngine:
        def connect(self):
            raise RuntimeError("db down")

    out = load_dividends_received("2026-01-01", "2026-12-31", engine=_BrokenEngine())
    assert out == 0.0


def test_backtest_report_exposes_total_return_with_dividends():
    rep = BacktestReport(
        initial_equity=10_000.0,
        final_value=10_500.0,
        total_return_pct=5.0,
        cagr_pct=5.0,
        sharpe_ratio=1.0,
        sortino_ratio=1.0,
        max_drawdown_pct=2.0,
        total_trades=10,
        win_rate_pct=60.0,
        avg_trade_duration_days=5.0,
        profit_factor=1.5,
        dividends_received=100.0,
        total_return_with_dividends_pct=6.0,
    )
    serialized = rep.to_serializable_dict()
    assert "total_return_with_dividends_pct" in serialized
    assert "dividends_received" in serialized
    assert serialized["total_return_with_dividends_pct"] == pytest.approx(6.0)
    assert serialized["dividends_received"] == pytest.approx(100.0)
    # Conformité : total_return - mtm == dividend_yield (1 %).
    expected_yield_pct = (rep.dividends_received / rep.initial_equity) * 100.0
    assert (rep.total_return_with_dividends_pct - rep.total_return_pct) == pytest.approx(
        expected_yield_pct, abs=1e-6
    )


def test_compare_total_return_to_oracle_accepts_small_difference() -> None:
    result = compare_total_return_to_oracle(
        initial_equity=10_000.0,
        final_value_mtm=10_500.0,
        dividends_received=100.0,
        oracle_total_return_pct=6.02,
        tolerance_bps=5.0,
    )
    assert result["delta_bps"] == pytest.approx(-2.0, abs=1e-6)
    assert result["within_tolerance"] is True


def test_compare_total_return_to_oracle_flags_large_divergence() -> None:
    result = compare_total_return_to_oracle(
        initial_equity=10_000.0,
        final_value_mtm=10_500.0,
        dividends_received=100.0,
        oracle_total_return_pct=5.0,
        tolerance_bps=25.0,
    )
    assert result["delta_bps"] == pytest.approx(100.0, abs=1e-6)
    assert result["within_tolerance"] is False


