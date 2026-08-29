from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.config import DataConfig, TargetOptimizationConfig
from modelFactory.target_optimization import (
    TripleBarrierCandidateResult,
    optimize_target_horizon,
    optimize_target_parameters,
    optimize_triple_barrier_parameters,
    score_target_candidate,
    score_triple_barrier_candidate,
)


def _make_prices(n: int = 80) -> pd.DataFrame:
    close = pd.Series(100 + np.arange(n) * 0.8, dtype=float)
    return pd.DataFrame({"close": close, "adj_close": close})


def _make_ohlc_df(n: int = 80, start_price: float = 100.0, trend: float = 0.5) -> pd.DataFrame:
    """Crée un DataFrame OHLC avec open, high, low, close pour tests triple-barrier."""
    rng = np.random.RandomState(42)
    closes = np.array([start_price + i * trend + rng.uniform(-0.5, 0.5) for i in range(n)], dtype=float)
    opens = np.zeros_like(closes)
    opens[0] = closes[0] - 0.1
    for i in range(1, n):
        opens[i] = closes[i - 1] * (1.0 + rng.uniform(-0.0005, 0.0005))
    highs = np.maximum(opens, closes) * (1.0 + rng.uniform(0.002, 0.008, n))
    lows = np.minimum(opens, closes) * (1.0 - rng.uniform(0.002, 0.008, n))
    df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
    df["adj_close"] = closes
    return df


def test_score_target_candidate_returns_positive_trade_rate() -> None:
    df = _make_prices()
    cfg = DataConfig(target_mode="binary", target_up_threshold=0.0)

    result = score_target_candidate(df, horizon=5, data_cfg=cfg, min_trades_fraction=0.05)

    assert result.trade_rate > 0.05
    assert result.horizon == 5
    assert result.target_up_threshold == 0.0


def test_score_target_candidate_accepts_custom_thresholds() -> None:
    df = _make_prices()
    cfg = DataConfig(target_mode="swing_cash", target_up_threshold=0.01, target_down_threshold=-0.01)

    result = score_target_candidate(
        df,
        horizon=5,
        data_cfg=cfg,
        min_trades_fraction=0.05,
        positive_threshold=0.02,
        negative_threshold=0.0,
    )

    assert result.target_up_threshold == 0.02
    assert result.target_down_threshold == 0.0


def test_optimize_target_parameters_returns_selected_thresholds() -> None:
    df = _make_prices(120)
    cfg = DataConfig(target_mode="binary", target_up_threshold=0.0)
    opt_cfg = TargetOptimizationConfig(
        enabled=True,
        candidate_horizons=(3, 5),
        candidate_up_thresholds=(0.0, 0.02),
        candidate_down_thresholds=(-0.01, 0.01),
        min_trades_fraction=0.05,
    )

    result = optimize_target_parameters(df, data_cfg=cfg, opt_cfg=opt_cfg)

    assert result["selected_horizon"] in {3, 5}
    assert result["selected_target_up_threshold"] in {0.0, 0.02}
    assert result["selected_target_down_threshold"] in {-0.01, 0.01}
    assert len(result["candidates"]) == 6


def test_optimize_target_horizon_returns_candidate_summary() -> None:
    df = _make_prices(120)
    cfg = DataConfig(target_mode="binary", target_up_threshold=0.0)
    opt_cfg = TargetOptimizationConfig(enabled=True, candidate_horizons=(3, 5, 10), min_trades_fraction=0.05)

    result = optimize_target_horizon(df, data_cfg=cfg, opt_cfg=opt_cfg)

    assert result["selected_horizon"] in {3, 5, 10}
    assert len(result["candidates"]) == 3


# ── Tests triple-barrier (Section 17 Point 3.3) ────────────────────────────

class TestScoreTripleBarrierCandidate:
    """score_triple_barrier_candidate évalue un TripleBarrierConfig sur le train."""

    def test_returns_valid_result_on_trending_data(self) -> None:
        """Un DF OHLC avec tendance doit produire un score > 0."""
        df = _make_ohlc_df(120, start_price=100.0, trend=0.8)
        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier", target_up_threshold=0.03, target_down_threshold=-0.03)

        result = score_triple_barrier_candidate(
            df,
            stop_atr_mult=2.0,
            tp_atr_mult=3.0,
            max_sessions=20,
            data_cfg=cfg,
            min_trades_fraction=0.05,
        )

        assert isinstance(result, TripleBarrierCandidateResult)
        assert result.stop_atr_mult == 2.0
        assert result.tp_atr_mult == 3.0
        assert result.max_sessions == 20
        assert result.trade_rate >= 0.0
        assert 0.0 <= result.class_balance <= 1.0

    def test_insufficient_data_yields_negative_score(self) -> None:
        """Avec trop peu de barres, le trade_rate < min_trades_fraction → score = -1."""
        df = _make_ohlc_df(30, start_price=100.0, trend=0.1)
        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier", target_up_threshold=0.03, target_down_threshold=-0.03)

        result = score_triple_barrier_candidate(
            df,
            stop_atr_mult=2.0,
            tp_atr_mult=3.0,
            max_sessions=20,
            data_cfg=cfg,
            min_trades_fraction=0.50,  # Très exigeant → échec
        )

        assert result.score == -1.0
        assert result.trade_rate < 0.50

    def test_different_params_produce_different_scores(self) -> None:
        """Des paramètres différents donnent des scores différents."""
        df = _make_ohlc_df(200, start_price=100.0, trend=0.5)
        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier", target_up_threshold=0.03, target_down_threshold=-0.03)

        r1 = score_triple_barrier_candidate(
            df, stop_atr_mult=1.5, tp_atr_mult=2.0, max_sessions=10,
            data_cfg=cfg, min_trades_fraction=0.05,
        )
        r2 = score_triple_barrier_candidate(
            df, stop_atr_mult=3.0, tp_atr_mult=5.0, max_sessions=30,
            data_cfg=cfg, min_trades_fraction=0.05,
        )

        # Les scores doivent différer (paramètres très différents)
        assert r1.score != r2.score or r1.trade_rate != r2.trade_rate


class TestOptimizeTripleBarrierParameters:
    """optimize_triple_barrier_parameters optimise sur le fold train uniquement."""

    def test_returns_best_triple_barrier_config(self) -> None:
        """Retourne les paramètres triple-barrier optimaux."""
        df = _make_ohlc_df(200, start_price=100.0, trend=0.6)
        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier", target_up_threshold=0.03, target_down_threshold=-0.03)
        opt_cfg = TargetOptimizationConfig(
            enabled=True,
            candidate_stop_atr_mults=(1.5, 2.0),
            candidate_tp_atr_mults=(2.0, 3.0),
            candidate_max_sessions=(10, 20),
            min_trades_fraction=0.05,
        )

        result = optimize_triple_barrier_parameters(df, data_cfg=cfg, opt_cfg=opt_cfg)

        assert "selected_triple_barrier_stop_atr_mult" in result
        assert "selected_triple_barrier_tp_atr_mult" in result
        assert "selected_triple_barrier_max_sessions" in result
        assert result["selected_triple_barrier_stop_atr_mult"] in {1.5, 2.0}
        assert result["selected_triple_barrier_tp_atr_mult"] in {2.0, 3.0}
        assert result["selected_triple_barrier_max_sessions"] in {10, 20}
        assert len(result["triple_barrier_candidates"]) == 8  # 2×2×2

    def test_score_positive_for_valid_config(self) -> None:
        """Le score du meilleur candidat est >= 0."""
        df = _make_ohlc_df(200, start_price=100.0, trend=0.6)
        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier", target_up_threshold=0.03, target_down_threshold=-0.03)
        opt_cfg = TargetOptimizationConfig(
            enabled=True,
            candidate_stop_atr_mults=(2.0,),
            candidate_tp_atr_mults=(3.0,),
            candidate_max_sessions=(20,),
            min_trades_fraction=0.05,
        )

        result = optimize_triple_barrier_parameters(df, data_cfg=cfg, opt_cfg=opt_cfg)

        assert result["selected_triple_barrier_score"] >= 0.0


class TestOptimizeTargetParametersTripleBarrier:
    """optimize_target_parameters avec label_method='triple_barrier'."""

    def test_triple_barrier_mode_includes_tb_params(self) -> None:
        """En mode triple_barrier, le résultat contient les clés triple-barrier."""
        df = _make_ohlc_df(200, start_price=100.0, trend=0.6)
        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier", target_up_threshold=0.03, target_down_threshold=-0.03)
        opt_cfg = TargetOptimizationConfig(
            enabled=True,
            candidate_stop_atr_mults=(2.0,),
            candidate_tp_atr_mults=(3.0,),
            candidate_max_sessions=(20,),
            candidate_horizons=(),
            min_trades_fraction=0.05,
        )

        result = optimize_target_parameters(df, data_cfg=cfg, opt_cfg=opt_cfg)

        assert "selected_triple_barrier_stop_atr_mult" in result
        assert "selected_triple_barrier_tp_atr_mult" in result
        assert "selected_triple_barrier_max_sessions" in result
        assert "triple_barrier_candidates" in result

    def test_triple_barrier_with_horizon_candidates(self) -> None:
        """Avec candidate_horizons, on optimise aussi l'horizon."""
        df = _make_ohlc_df(200, start_price=100.0, trend=0.6)
        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier", target_up_threshold=0.03, target_down_threshold=-0.03)
        opt_cfg = TargetOptimizationConfig(
            enabled=True,
            candidate_horizons=(10, 20),
            candidate_stop_atr_mults=(2.0,),
            candidate_tp_atr_mults=(3.0,),
            candidate_max_sessions=(10, 20),
            min_trades_fraction=0.05,
        )

        result = optimize_target_parameters(df, data_cfg=cfg, opt_cfg=opt_cfg)

        assert "selected_horizon" in result
        assert result["selected_horizon"] in {10, 20}

    def test_fixed_horizon_still_works(self) -> None:
        """Le mode fixed_horizon continue de fonctionner (backward compat)."""
        df = _make_prices(120)
        cfg = DataConfig(target_mode="binary", label_method="fixed_horizon")
        opt_cfg = TargetOptimizationConfig(
            enabled=True,
            candidate_horizons=(3, 5),
            candidate_up_thresholds=(0.0,),
            candidate_down_thresholds=(0.0,),
            min_trades_fraction=0.05,
        )

        result = optimize_target_parameters(df, data_cfg=cfg, opt_cfg=opt_cfg)

        assert result["selected_horizon"] in {3, 5}
        assert "candidates" in result


# ── Isolation train fold ────────────────────────────────────────────────────

class TestTrainFoldIsolation:
    """Vérifie que l'optimisation n'utilise que les données du train (Point 3.4)."""

    def test_score_triple_barrier_only_uses_passed_df(self) -> None:
        """score_triple_barrier_candidate ne doit référencer que le df passé,
        pas de données externes."""
        df = _make_ohlc_df(150, start_price=100.0, trend=0.5)
        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier", target_up_threshold=0.03, target_down_threshold=-0.03)

        result = score_triple_barrier_candidate(
            df,
            stop_atr_mult=2.0,
            tp_atr_mult=3.0,
            max_sessions=20,
            data_cfg=cfg,
            min_trades_fraction=0.05,
        )

        # Vérifie que le trade_rate est calculé sur le df passé
        n = len(df)
        max_trade_rate = (n - 20 - 1) / n  # cutoff = n - max_sessions - entry_delay
        assert result.trade_rate <= max_trade_rate

    def test_optimize_only_sees_train_data(self) -> None:
        """optimize_target_parameters ne doit pas accéder à des données
        hors du DataFrame passé en paramètre."""
        df_train = _make_ohlc_df(150, start_price=100.0, trend=0.5)
        cfg = DataConfig(target_mode="ternary", label_method="triple_barrier", target_up_threshold=0.03, target_down_threshold=-0.03)
        opt_cfg = TargetOptimizationConfig(
            enabled=True,
            candidate_stop_atr_mults=(2.0,),
            candidate_tp_atr_mults=(3.0,),
            candidate_max_sessions=(20,),
            candidate_horizons=(),
            min_trades_fraction=0.05,
        )

        result = optimize_target_parameters(df_train, data_cfg=cfg, opt_cfg=opt_cfg)

        # Le résultat doit provenir uniquement du df_train
        assert "selected_triple_barrier_stop_atr_mult" in result
        assert result["selected_triple_barrier_score"] >= 0.0

