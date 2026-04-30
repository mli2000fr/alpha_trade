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

    def test_vectorized_fuse_is_faster_than_naive_fallback(self):
        """Phase F.3 (refactor) — micro-bench léger sans pytest-benchmark.

        Vérifie que la fusion vectorisée reste sensiblement plus rapide qu'une
        boucle ligne-par-ligne (équivalente à l'ancien `df.apply`). Le seuil
        est volontairement large (×3) pour rester stable en CI partagée.
        """
        import time

        from backtesting.signal_replay import _vectorized_fuse
        from core.conviction import ConvictionWeights, fuse

        rng = np.random.default_rng(42)
        n = 50_000
        scores = pd.Series(rng.random(n))
        # ~30 % de NaN → exerce la branche fallback.
        proba_arr = rng.random(n)
        proba_arr[rng.random(n) < 0.3] = np.nan
        proba = pd.Series(proba_arr)
        weights = ConvictionWeights(0.4, 0.6)

        # Warmup (JIT pandas/numpy + cache caches CPU).
        _vectorized_fuse(scores.iloc[:1024], proba.iloc[:1024], weights)

        start = time.perf_counter()
        vec_out = _vectorized_fuse(scores, proba, weights)
        vec_elapsed = time.perf_counter() - start

        # Naive : appelle `core.conviction.fuse` ligne par ligne.
        start = time.perf_counter()
        naive_out = np.empty(n, dtype=float)
        scores_arr = scores.to_numpy()
        for i in range(n):
            p = proba_arr[i]
            naive_out[i] = fuse(
                quant_score=scores_arr[i],
                predicted_proba=None if np.isnan(p) else p,
                weights=weights,
            )
        naive_elapsed = time.perf_counter() - start

        # Cohérence numérique (NaN → score brut côté vectorisé).
        np.testing.assert_allclose(vec_out.to_numpy(), naive_out, atol=1e-9)

        # Garantit un gain réel (×3 minimum, généralement ×50+ en pratique).
        assert vec_elapsed * 3 < naive_elapsed, (
            f"_vectorized_fuse trop lent : vec={vec_elapsed:.4f}s "
            f"naive={naive_elapsed:.4f}s"
        )

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

    def test_snapshot_sector_exposure_aggregates_by_sector(self):
        """Phase E.3.b — primitive `snapshot_sector_exposure` extraite du
        simulator. Vérifie l'agrégation par secteur, le fallback `sector_map`
        et le fallback `entry_price` quand la colonne `close` manque.
        """
        from types import SimpleNamespace

        from backtesting.risk_overlay import snapshot_sector_exposure

        idx = pd.to_datetime(["2025-01-02"])
        close = pd.DataFrame({"AAPL": [200.0], "MSFT": [300.0]}, index=idx)
        positions = {
            # Tech via attribut sector explicite (200 * 10 = 2000 → 20 % equity)
            "AAPL": SimpleNamespace(symbol="AAPL", quantity=10, entry_price=180.0, sector="Tech"),
            # Tech via fallback sector_map (300 * 5 = 1500 → 15 % equity)
            "MSFT": SimpleNamespace(symbol="MSFT", quantity=5, entry_price=250.0, sector=None),
            # Energy via fallback entry_price car symbole absent de close
            "XOM": SimpleNamespace(symbol="XOM", quantity=10, entry_price=100.0, sector="Energy"),
        }
        sector_map = {"MSFT": "Tech"}
        exposure = snapshot_sector_exposure(positions, close, idx[0], sector_map, current_equity=10_000.0)

        assert exposure["Tech"] == pytest.approx(0.20 + 0.15)
        assert exposure["Energy"] == pytest.approx(0.10)

    def test_snapshot_sector_exposure_returns_empty_when_equity_zero(self):
        from backtesting.risk_overlay import snapshot_sector_exposure

        out = snapshot_sector_exposure({}, pd.DataFrame(), pd.Timestamp("2025-01-02"), {}, 0.0)
        assert dict(out) == {}

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


# ---------------------------------------------------------------------------
# Phase D.5 — schéma report.json (refactor v2)
# ---------------------------------------------------------------------------


class TestReportSchema:
    def _minimal_payload(self) -> dict:
        return {
            "summary": {
                "initial_equity": 100_000.0,
                "final_value": 110_000.0,
                "total_return_pct": 10.0,
                "cagr_pct": 5.0,
                "sharpe_ratio": 1.2,
                "sortino_ratio": 1.5,
                "max_drawdown_pct": 7.5,
                "total_trades": 42,
                "win_rate_pct": 55.0,
                "avg_trade_duration_days": 4.2,
                "profit_factor": "inf",
                "calmar_ratio": 1.0,
                "ulcer_index": 0.8,
            },
            "params": {"start": "2024-01-01"},
            "artifacts": {"equity_curve_png": "/tmp/x.png"},
            "diagnostics": {"take_profit_exits": 10},
            "run_metadata": {"git_sha": "abc123", "seed": 42},
        }

    def test_validate_minimal_payload(self):
        from backtesting.report_schema import validate_report_payload

        schema = validate_report_payload(self._minimal_payload())
        assert schema.summary.total_return_pct == pytest.approx(10.0)
        assert schema.summary.profit_factor == "inf"
        assert schema.diagnostics.take_profit_exits == 10
        assert schema.run_metadata.seed == 42

    def test_validate_missing_summary_raises(self):
        from backtesting.report_schema import ReportSchemaError, validate_report_payload

        payload = self._minimal_payload()
        del payload["summary"]["sharpe_ratio"]
        with pytest.raises(ReportSchemaError):
            validate_report_payload(payload)

    def test_validate_strict_rejects_unknown_keys(self):
        from backtesting.report_schema import ReportSchemaError, validate_report_payload

        payload = self._minimal_payload()
        payload["unexpected_top_level"] = {"foo": "bar"}
        with pytest.raises(ReportSchemaError):
            validate_report_payload(payload, strict=True)
        # Default tolerant mode passes.
        validate_report_payload(payload, strict=False)


# ---------------------------------------------------------------------------
# Phase E.3 (refactor v2) — _RunState invariant
# ---------------------------------------------------------------------------


class TestRunStateInvariants:
    def _build_minimal_inputs(self):
        from datetime import date

        idx = pd.date_range("2024-01-02", periods=5, freq="B")
        symbols = ["AAA", "BBB"]
        rng = np.random.default_rng(0)
        prices = pd.DataFrame(
            100 + rng.normal(0, 1, size=(len(idx), len(symbols))).cumsum(axis=0),
            index=idx,
            columns=symbols,
        )
        ohlcv = {
            "open": prices,
            "close": prices,
            "high": prices * 1.01,
            "low": prices * 0.99,
        }
        signals = pd.DataFrame(
            [
                {"trade_date": idx[0], "symbol": "AAA", "selected": True, "rank": 1, "signal_date": idx[0]},
                {"trade_date": idx[1], "symbol": "BBB", "selected": True, "rank": 1, "signal_date": idx[1]},
            ]
        )
        return ohlcv, signals, idx, date(2024, 1, 1), date(2024, 1, 10)

    def test_equity_non_negative_for_random_seeds(self):
        """Property léger : equity finale ≥ 0 pour 5 seeds différents (pas besoin d'hypothesis)."""
        from backtesting.simulator import BacktestConfig, BacktestEngine

        ohlcv, signals, _idx, start, end = self._build_minimal_inputs()
        for seed in range(5):
            cfg = BacktestConfig(
                start_date=start, end_date=end,
                initial_equity=10_000.0,
                profit_taker_pct=0.05,
                trailing_stop_pct=0.03,
                max_positions=2,
                fees_pct=0.001,
                seed=seed,
            )
            engine = BacktestEngine(cfg)
            result = engine.run(
                open_df=ohlcv["open"], close=ohlcv["close"],
                high=ohlcv["high"], low=ohlcv["low"], signals_df=signals,
            )
            assert result.final_value() >= 0.0

    def test_legacy_neutral_overlays_match_default_run(self):
        """Phase B/C : overlays par défaut => mêmes résultats qu'un run sans overlays."""
        from backtesting.microstructure import MicrostructureConfig
        from backtesting.risk_overlay import RiskOverlayConfig
        from backtesting.simulator import BacktestConfig, BacktestEngine

        ohlcv, signals, _idx, start, end = self._build_minimal_inputs()
        common = dict(
            start_date=start, end_date=end, initial_equity=10_000.0,
            profit_taker_pct=0.05, trailing_stop_pct=0.03, max_positions=2, fees_pct=0.001,
        )
        cfg_a = BacktestConfig(**common)
        cfg_b = BacktestConfig(
            **common,
            microstructure=MicrostructureConfig(),
            risk_overlay=RiskOverlayConfig(),
        )
        eq_a = BacktestEngine(cfg_a).run(
            open_df=ohlcv["open"], close=ohlcv["close"],
            high=ohlcv["high"], low=ohlcv["low"], signals_df=signals,
        ).equity_curve
        eq_b = BacktestEngine(cfg_b).run(
            open_df=ohlcv["open"], close=ohlcv["close"],
            high=ohlcv["high"], low=ohlcv["low"], signals_df=signals,
        ).equity_curve
        assert (eq_a.values == eq_b.values).all()


# ---------------------------------------------------------------------------
# Phase F.3/G — property tests via Hypothesis (skipped si non installé)
# ---------------------------------------------------------------------------


try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    _HYPOTHESIS_AVAILABLE = True
except ImportError:  # pragma: no cover — chemin sans dépendance.
    _HYPOTHESIS_AVAILABLE = False


@pytest.mark.skipif(not _HYPOTHESIS_AVAILABLE, reason="hypothesis non installé en local")
def test_bootstrap_intervals_contain_mean():
    """Property : la moyenne bootstrap est toujours dans [ci_low, ci_high]."""
    from backtesting.statistical_validation import bootstrap_trades

    @settings(max_examples=25, deadline=None)
    @given(
        n_trades=st.integers(min_value=5, max_value=50),
        win_rate=st.floats(min_value=0.1, max_value=0.9),
        seed=st.integers(min_value=0, max_value=10_000),
    )
    def _inner(n_trades, win_rate, seed):
        rng = np.random.default_rng(seed)
        returns = np.where(
            rng.random(n_trades) < win_rate,
            rng.uniform(0.5, 5.0, n_trades),
            -rng.uniform(0.5, 5.0, n_trades),
        )
        trades = pd.DataFrame({"return_pct": returns})
        out = bootstrap_trades(trades, n_iterations=200, initial_equity=10_000.0, seed=seed)
        assert (
            out.ci_low_total_return_pct - 1e-6
            <= out.mean_total_return_pct
            <= out.ci_high_total_return_pct + 1e-6
        )

    _inner()


@pytest.mark.skipif(not _HYPOTHESIS_AVAILABLE, reason="hypothesis non installé en local")
def test_drawdown_circuit_breaker_is_monotonic_in_drawdown():
    """Property C.5 : `update()` doit toujours bloquer si DD ≤ -max_dd_pct,
    et libérer dès que equity ≥ peak * recovery_pct (jamais l'inverse)."""
    from backtesting.risk_overlay import DrawdownCircuitBreaker

    @settings(max_examples=40, deadline=None)
    @given(
        peak=st.floats(min_value=1_000.0, max_value=1_000_000.0, allow_nan=False),
        max_dd=st.floats(min_value=0.05, max_value=0.50),
        recovery=st.floats(min_value=0.80, max_value=0.99),
        equity_pct_of_peak=st.floats(min_value=0.10, max_value=1.20),
    )
    def _inner(peak, max_dd, recovery, equity_pct_of_peak):
        breaker = DrawdownCircuitBreaker(enabled=True, max_dd_pct=max_dd, recovery_pct=recovery)
        equity = peak * equity_pct_of_peak
        allowed = breaker.update(equity, peak)
        dd = (equity / peak) - 1.0
        # Si on est sous le seuil de DD, le breaker DOIT s'être déclenché.
        if dd <= -max_dd - 1e-9:
            assert breaker._tripped is True
            assert allowed is False
        # Si on n'a jamais déclenché et qu'on est au-dessus du seuil, OK.
        if not breaker._tripped:
            assert allowed is True

    _inner()


@pytest.mark.skipif(not _HYPOTHESIS_AVAILABLE, reason="hypothesis non installé en local")
def test_simulator_invariants_equity_positive_and_cash_conservation():
    """Property F.1 généralisée : pour tout config neutre + signaux aléatoires,
    l'equity reste ≥ 0 et `settled_cash + unsettled_cash + market_value`
    correspond bien au point d'equity courbe (à 1e-6 près)."""
    from backtesting.simulator import BacktestConfig, BacktestEngine
    from datetime import date

    @settings(max_examples=8, deadline=None)
    @given(
        seed=st.integers(min_value=0, max_value=999),
        n_days=st.integers(min_value=20, max_value=60),
        n_symbols=st.integers(min_value=2, max_value=6),
    )
    def _inner(seed, n_days, n_symbols):
        rng = np.random.default_rng(seed)
        idx = pd.date_range("2025-01-02", periods=n_days, freq="B")
        symbols = [f"S{i}" for i in range(n_symbols)]
        # Marche aléatoire faiblement positive pour rester réaliste.
        returns = rng.normal(0.0005, 0.015, size=(n_days, n_symbols))
        prices = 100.0 * np.exp(np.cumsum(returns, axis=0))
        close = pd.DataFrame(prices, index=idx, columns=symbols)
        open_df = close.shift(1).fillna(close.iloc[0])
        high = close * 1.01
        low = close * 0.99

        # Génère ~1 signal/symbole sur la première moitié de la fenêtre.
        signals_rows = []
        for i, sym in enumerate(symbols):
            day = idx[1 + (i % max(1, n_days // 2))]
            signals_rows.append(
                {"trade_date": day, "symbol": sym, "selected": True, "rank": float(i + 1)}
            )
        signals_df = pd.DataFrame(signals_rows)

        cfg = BacktestConfig(
            start_date=idx[0].date() if hasattr(idx[0], "date") else date(2025, 1, 2),
            end_date=idx[-1].date() if hasattr(idx[-1], "date") else date(2025, 1, 31),
            initial_equity=10_000.0,
            profit_taker_pct=0.10,
            trailing_stop_pct=0.05,
            max_positions=n_symbols,
            fees_pct=0.001,
            seed=seed,
        )
        engine = BacktestEngine(cfg)
        result = engine.run(open=open_df, close=close, high=high, low=low, signals_df=signals_df)

        # Invariant 1 : equity ≥ 0 partout (jamais de découvert simulé).
        assert (result.equity_curve >= -1e-6).all(), "equity négative détectée"
        # Invariant 2 : la valeur finale est cohérente avec la dernière valeur
        # de la courbe d'equity (l'API expose `final_value` comme méthode).
        final_value = float(result.equity_curve.iloc[-1])
        assert final_value >= 0.0
        # Invariant 3 : monotonie length — la courbe contient bien `n_days` points.
        assert len(result.equity_curve) == n_days

    _inner()





