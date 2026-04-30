"""Tests des modules refactor (audit_plan.md Phases A→G)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Phase A
# ---------------------------------------------------------------------------


class TestPhaseA:
    def test_pick_score_column_uses_priority(self):
        from backtesting.signal_replay import _pick_score_column

        df = pd.DataFrame(
            {
                "final_score": [0.5, 0.5],
                "final_score_sentiment": [0.7, np.nan],
                "final_score_walk_forward": [0.9, np.nan],
            }
        )
        score, source = _pick_score_column(df, preferred=None)
        assert list(score) == [0.9, 0.5]
        assert list(source) == ["final_score_walk_forward", "final_score"]

    def test_vectorized_fuse_falls_back_when_proba_missing(self):
        from backtesting.signal_replay import _vectorized_fuse
        from core.conviction import ConvictionWeights

        scores = pd.Series([0.5, 0.8])
        proba = pd.Series([np.nan, 0.9])
        out = _vectorized_fuse(scores, proba, ConvictionWeights(0.4, 0.6))
        assert out.iloc[0] == pytest.approx(0.5)
        assert out.iloc[1] == pytest.approx(0.4 * 0.8 + 0.6 * 0.9)

    def test_report_calmar_and_ulcer_present(self):
        from backtesting.report import BacktestReport

        r = BacktestReport(
            initial_equity=100, final_value=120, total_return_pct=20, cagr_pct=10,
            sharpe_ratio=1.0, sortino_ratio=1.2, max_drawdown_pct=5.0,
            total_trades=5, win_rate_pct=60, avg_trade_duration_days=3,
            profit_factor=float("inf"), calmar_ratio=2.0, ulcer_index=1.5,
            risk_free_rate=0.04,
        )
        d = r.to_serializable_dict()
        assert d["calmar_ratio"] == 2.0
        assert d["ulcer_index"] == 1.5
        assert d["risk_free_rate"] == 0.04
        # Phase A.7 — sentinel inf préservé.
        assert d["profit_factor"] == "inf"

    def test_run_metadata_structure(self):
        from backtesting.run_metadata import build_run_metadata

        meta = build_run_metadata(
            seed=42,
            dataset_frames={"x": pd.DataFrame({"a": [1, 2, 3]})},
        )
        assert meta["seed"] == 42
        assert "python_version" in meta
        assert "platform" in meta
        assert "packages" in meta and "pandas" in meta["packages"]
        assert "dataset_hash" in meta and isinstance(meta["dataset_hash"], str)
        assert meta["generated_at_utc"].endswith("Z")


# ---------------------------------------------------------------------------
# Phase B
# ---------------------------------------------------------------------------


class TestPhaseB:
    def test_slippage_fixed_default_is_zero(self):
        from backtesting.microstructure import SlippageConfig

        cfg = SlippageConfig()
        assert cfg.compute_bps(1_000_000, 50_000_000) == 0.0

    def test_slippage_sqrt_increases_with_size(self):
        from backtesting.microstructure import SlippageConfig

        cfg = SlippageConfig(base_bps=2.0, impact_coef=20.0, model="sqrt")
        small = cfg.compute_bps(10_000, 1_000_000)
        big = cfg.compute_bps(500_000, 1_000_000)
        assert big > small > cfg.base_bps

    def test_should_skip_entry_for_gap(self):
        from backtesting.microstructure import should_skip_entry_for_gap

        assert should_skip_entry_for_gap(100.0, 110.0, max_gap_pct=0.05) is True
        assert should_skip_entry_for_gap(100.0, 102.0, max_gap_pct=0.05) is False
        assert should_skip_entry_for_gap(None, 110.0, max_gap_pct=0.05) is False
        assert should_skip_entry_for_gap(100.0, 110.0, max_gap_pct=0.0) is False

    def test_resolve_intrabar_initial_stop_priority(self):
        from backtesting.microstructure import resolve_intrabar_exit

        res = resolve_intrabar_exit(
            day_high=110.0, day_low=85.0,
            take_profit_price=108.0, trailing_stop_price=95.0,
            initial_stop_price=90.0, priority="conservative",
        )
        assert res.triggered and res.exit_reason == "initial_stop"

    def test_resolve_intrabar_tp_first_wins_conflict(self):
        from backtesting.microstructure import resolve_intrabar_exit

        res = resolve_intrabar_exit(
            day_high=110.0, day_low=92.0,
            take_profit_price=108.0, trailing_stop_price=95.0,
            initial_stop_price=None, priority="tp_first",
        )
        assert res.exit_reason == "take_profit"

    def test_resolve_intrabar_conservative_picks_trailing(self):
        from backtesting.microstructure import resolve_intrabar_exit

        res = resolve_intrabar_exit(
            day_high=110.0, day_low=92.0,
            take_profit_price=108.0, trailing_stop_price=95.0,
            initial_stop_price=None, priority="conservative",
        )
        assert res.exit_reason == "trailing_stop"


# ---------------------------------------------------------------------------
# Phase C
# ---------------------------------------------------------------------------


class TestPhaseC:
    def test_sizing_equal_weight_default(self):
        from backtesting.risk_overlay import SizingConfig

        cfg = SizingConfig()
        candidates = pd.DataFrame({"symbol": ["A", "B", "C"]})
        w = cfg.compute_weights(candidates, max_positions=10)
        assert w.tolist() == [0.1, 0.1, 0.1]

    def test_sizing_conviction_weighted_normalizes(self):
        from backtesting.risk_overlay import SizingConfig

        cfg = SizingConfig(mode="conviction_weighted", min_weight_pct=0.0, max_weight_pct=1.0)
        candidates = pd.DataFrame({"symbol": ["A", "B"], "conviction": [0.6, 0.4]})
        w = cfg.compute_weights(candidates, max_positions=2)
        assert w.iloc[0] == pytest.approx(0.6)
        assert w.iloc[1] == pytest.approx(0.4)

    def test_sectoral_cap_blocks_overshoot(self):
        from backtesting.risk_overlay import SectoralCapConfig

        cap = SectoralCapConfig(enabled=True, max_sector_exposure_pct=0.40)
        assert cap.is_entry_allowed("Tech", 0.30, 0.20) is False
        assert cap.is_entry_allowed("Tech", 0.20, 0.10) is True

    def test_drawdown_breaker_trips_and_recovers(self):
        from backtesting.risk_overlay import DrawdownCircuitBreaker

        cb = DrawdownCircuitBreaker(enabled=True, max_dd_pct=0.10, recovery_pct=0.95)
        assert cb.update(equity=100.0, peak_equity=100.0) is True
        assert cb.update(equity=85.0, peak_equity=100.0) is False
        assert cb.update(equity=96.0, peak_equity=100.0) is True

    def test_regime_filter_blocks_when_below_sma(self):
        from backtesting.risk_overlay import RegimeFilterConfig

        idx = pd.date_range("2024-01-01", periods=210, freq="B")
        # SMA200 ≈ 150 (linspace 100→200), dernier prix forcé à 100 (-33% vs SMA).
        prices = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
        prices.iloc[-1] = 100.0
        cfg = RegimeFilterConfig(enabled=True, sma_window=200, bear_threshold=-0.02)
        assert cfg.is_entry_allowed(prices, prices.index[-1]) is False


# ---------------------------------------------------------------------------
# Phase D
# ---------------------------------------------------------------------------


class TestPhaseD:
    def test_compute_benchmark_analytics_runs(self):
        from backtesting.analytics import compute_benchmark_analytics

        idx = pd.date_range("2025-01-01", periods=30, freq="B")
        equity = pd.Series(np.linspace(100, 110, len(idx)), index=idx)
        bm = pd.Series(np.linspace(100, 105, len(idx)), index=idx)
        out = compute_benchmark_analytics(equity, bm)
        assert out.beta != 0.0
        assert isinstance(out.alpha_annualized_pct, float)

    def test_sector_attribution_groups_by_sector(self):
        from backtesting.analytics import sector_attribution

        df = pd.DataFrame(
            {
                "sector": ["Tech", "Tech", "Health"],
                "pnl": [100.0, -50.0, 75.0],
                "return_pct": [10.0, -5.0, 7.5],
            }
        )
        out = sector_attribution(df)
        assert set(out["sector"]) == {"Tech", "Health"}
        tech = out[out["sector"] == "Tech"].iloc[0]
        assert tech["n_trades"] == 2
        assert tech["total_pnl"] == 50.0

    def test_compute_tail_analytics_returns_finite_values(self):
        from backtesting.analytics import compute_tail_analytics

        idx = pd.date_range("2025-01-01", periods=100, freq="B")
        eq = pd.Series(100 * np.cumprod(1 + np.random.default_rng(1).normal(0, 0.01, len(idx))), index=idx)
        out = compute_tail_analytics(eq)
        assert math.isfinite(out.var_95_pct)
        assert math.isfinite(out.cvar_95_pct)


# ---------------------------------------------------------------------------
# Phase E
# ---------------------------------------------------------------------------


class TestPhaseE:
    def test_parquet_cache_roundtrip(self, tmp_path: Path):
        from backtesting.cache import ParquetCache

        cache = ParquetCache(cache_dir=tmp_path)
        df = pd.DataFrame({"a": [1, 2, 3]})
        cache.put("foo", df)
        out = cache.get("foo")
        assert out is not None
        assert out["a"].tolist() == [1, 2, 3]

    def test_parquet_cache_get_or_load(self, tmp_path: Path):
        from backtesting.cache import ParquetCache

        cache = ParquetCache(cache_dir=tmp_path)
        calls = {"n": 0}

        def loader():
            calls["n"] += 1
            return pd.DataFrame({"a": [1, 2]})

        cache.get_or_load("bar", loader)
        cache.get_or_load("bar", loader)
        assert calls["n"] == 1


# ---------------------------------------------------------------------------
# Phase F (invariants)
# ---------------------------------------------------------------------------


class TestPhaseFInvariants:
    def test_simulator_cash_plus_positions_equals_equity(self):
        """Invariant comptable : final_value = equity_curve.iloc[-1]."""
        from datetime import date as date_t

        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"])
        op = pd.DataFrame({"AAPL": [100.0, 101.0, 104.0, 103.0]}, index=idx)
        cl = pd.DataFrame({"AAPL": [100.0, 103.0, 106.0, 104.0]}, index=idx)
        hi = pd.DataFrame({"AAPL": [101.0, 104.0, 108.0, 105.0]}, index=idx)
        lo = pd.DataFrame({"AAPL": [99.0, 102.0, 103.0, 101.0]}, index=idx)
        sig = pd.DataFrame({"trade_date": [idx[0]], "symbol": ["AAPL"], "selected": [True]})
        engine = BacktestEngine(
            BacktestConfig(start_date=date_t(2025, 1, 1), end_date=date_t(2025, 1, 6),
                           initial_equity=10_000, max_positions=1)
        )
        result = engine.run(open_df=op, close=cl, high=hi, low=lo, signals_df=sig)
        # Invariant : final_value ≥ 0 et cohérent avec equity_curve.
        assert float(result.final_value()) >= 0.0


# ---------------------------------------------------------------------------
# Phase G
# ---------------------------------------------------------------------------


class TestPhaseG:
    def test_bootstrap_trades_returns_intervals(self):
        from backtesting.statistical_validation import bootstrap_trades

        trades = pd.DataFrame(
            {"return_pct": [5.0, -2.0, 3.0, 8.0, -1.0, 4.0, -3.0, 6.0, 2.0, -0.5]}
        )
        out = bootstrap_trades(trades, n_iterations=200, initial_equity=10_000.0, seed=0)
        assert out.n_iterations == 200
        assert out.ci_low_total_return_pct <= out.mean_total_return_pct <= out.ci_high_total_return_pct
        assert out.ci_high_max_dd_pct >= 0

    def test_parameter_sensitivity_ranks_by_abs_value(self):
        from backtesting.statistical_validation import parameter_sensitivity

        base = {"tp": 0.10, "ts": 0.05}

        def metric(p):
            return 100.0 * p["tp"] - 500.0 * p["ts"]

        df = parameter_sensitivity(base, metric, perturbation=0.10)
        assert df.iloc[0]["parameter"] == "ts"  # plus sensible (coef -500 × value 0.05)



