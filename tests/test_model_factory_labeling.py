"""Tests pour le triple-barrier labeling — Sprint Maître 3."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.labeling import (
    TripleBarrierConfig,
    _compute_atr,
    _deduct_costs,
    build_triple_barrier_label,
    build_triple_barrier_labels,
    build_triple_barrier_targets,
    compare_label_methods,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def flat_prices() -> dict:
    """Prix plats : pas de mouvement."""
    n = 50
    return {
        "open": np.full(n, 100.0),
        "high": np.full(n, 100.0),
        "low": np.full(n, 100.0),
        "close": np.full(n, 100.0),
    }


@pytest.fixture
def uptrend_prices() -> dict:
    """Tendance haussière régulière."""
    n = 60
    base = np.linspace(100.0, 130.0, n)
    return {
        "open": base - 0.5,
        "high": base + 1.0,
        "low": base - 1.0,
        "close": base + 0.5,
    }


@pytest.fixture
def gap_down_prices() -> dict:
    """Gap baissier à l'open le jour 6."""
    n = 60
    base = np.linspace(100.0, 130.0, n)
    opens = base - 0.5
    opens[5] = 85.0  # gap down at session 5 (0-indexed)
    return {
        "open": opens,
        "high": base + 1.0,
        "low": base - 1.0,
        "close": base + 0.5,
    }


@pytest.fixture
def ohlc_df() -> pd.DataFrame:
    """DataFrame OHLC standard."""
    n = 60
    base = np.linspace(100.0, 130.0, n)
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="B"),
        "open": base - 0.5,
        "high": base + 1.0,
        "low": base - 1.0,
        "close": base + 0.5,
        "volume": np.full(n, 1_000_000.0),
    })
    return df


# ── TripleBarrierConfig ─────────────────────────────────────────────────────

def test_config_defaults() -> None:
    cfg = TripleBarrierConfig()
    assert cfg.stop_atr_mult == 2.0
    assert cfg.tp_atr_mult == 3.0
    assert cfg.tp_max_pct == 0.0
    assert cfg.max_sessions == 20
    assert cfg.total_cost_bps > 0


def test_config_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        TripleBarrierConfig(stop_atr_mult=0)
    with pytest.raises(ValueError):
        TripleBarrierConfig(tp_atr_mult=-1)
    with pytest.raises(ValueError):
        TripleBarrierConfig(tp_max_pct=-0.01)
    with pytest.raises(ValueError):
        TripleBarrierConfig(max_sessions=0)
    with pytest.raises(ValueError):
        TripleBarrierConfig(entry_delay_sessions=-1)


def test_config_cost_pct() -> None:
    cfg = TripleBarrierConfig(spread_bps=5, commission_bps=1, slippage_bps=2)
    # total = 2 * (5+1+2) = 16 bps = 0.0016
    assert cfg.total_cost_bps == 16
    assert abs(cfg.cost_pct - 0.0016) < 1e-10


# ── ATR ─────────────────────────────────────────────────────────────────────

def test_atr_flat_prices(flat_prices) -> None:
    atr = _compute_atr(flat_prices["high"], flat_prices["low"], flat_prices["close"], 14)
    # Toutes les valeurs après warmup devraient être 0
    valid = atr[20:]
    assert np.allclose(valid, 0.0, atol=1e-10)


def test_atr_uptrend(uptrend_prices) -> None:
    atr = _compute_atr(uptrend_prices["high"], uptrend_prices["low"], uptrend_prices["close"], 14)
    valid = atr[20:]
    assert (valid > 0).all()


# ── Triple-barrier label : long ─────────────────────────────────────────────

def test_long_take_profit(uptrend_prices) -> None:
    cfg = TripleBarrierConfig(stop_atr_mult=5.0, tp_atr_mult=1.0, max_sessions=30, min_atr=0.01)
    label = build_triple_barrier_label(entry_idx=5, side="long", prices=uptrend_prices, cfg=cfg)
    assert label.side == "long"
    # Dans un uptrend avec TP serré, soit TP est touché en intraday soit à l'open (gap_tp)
    assert label.exit_reason in ("take_profit", "gap_tp")
    assert label.holding_sessions is not None and label.holding_sessions > 0
    assert label.net_return_pct is not None


def test_take_profit_percentage_cap_is_applied() -> None:
    n = 40
    prices = {
        "open": np.full(n, 100.0),
        "high": np.full(n, 106.0),
        "low": np.full(n, 99.5),
        "close": np.full(n, 100.0),
    }
    cfg = TripleBarrierConfig(
        stop_atr_mult=10.0, tp_atr_mult=10.0, tp_max_pct=0.05,
        max_sessions=5, min_atr=0.02, entry_delay_sessions=1,
    )
    label = build_triple_barrier_label(entry_idx=15, side="long", prices=prices, cfg=cfg)
    assert label.exit_reason == "take_profit"
    assert label.exit_price == pytest.approx(105.0)


def test_long_time_exit(flat_prices) -> None:
    cfg = TripleBarrierConfig(stop_atr_mult=5.0, tp_atr_mult=5.0, max_sessions=5)
    label = build_triple_barrier_label(entry_idx=5, side="long", prices=flat_prices, cfg=cfg)
    assert label.exit_reason == "time_exit"
    assert label.holding_sessions == 5


def test_long_stop_loss() -> None:
    """Simule un stop loss : prix qui montent puis chutent."""
    n = 50
    prices = {
        "open": np.full(n, 100.0),
        "high": np.full(n, 100.0),
        "low": np.full(n, 100.0),
        "close": np.full(n, 100.0),
    }
    # Entrée à 100, puis chute à 90 (10% drop)
    for i in range(10, 30):
        prices["low"][i] = 90.0
        prices["close"][i] = 92.0
    cfg = TripleBarrierConfig(stop_atr_mult=2.0, tp_atr_mult=10.0, max_sessions=20, min_atr=0.02)
    label = build_triple_barrier_label(entry_idx=5, side="long", prices=prices, cfg=cfg)
    assert label.exit_reason in ("stop_loss", "gap_stop")
    assert label.net_return_pct is not None and label.net_return_pct < 0


# ── Triple-barrier label : short ────────────────────────────────────────────

def test_short_take_profit() -> None:
    """Short avec baisse des prix → TP touché."""
    n = 50
    prices = {
        "open": np.full(n, 100.0),
        "high": np.full(n, 100.0),
        "low": np.full(n, 100.0),
        "close": np.full(n, 100.0),
    }
    for i in range(10, 30):
        prices["low"][i] = 88.0
        prices["close"][i] = 90.0
    cfg = TripleBarrierConfig(stop_atr_mult=10.0, tp_atr_mult=0.5, max_sessions=20, min_atr=0.05)
    label = build_triple_barrier_label(entry_idx=5, side="short", prices=prices, cfg=cfg)
    assert label.exit_reason == "take_profit"
    assert label.gross_return is not None and label.gross_return > 0


def test_short_stop_loss() -> None:
    """Short avec hausse des prix → stop touché."""
    n = 50
    prices = {
        "open": np.full(n, 100.0),
        "high": np.full(n, 100.0),
        "low": np.full(n, 100.0),
        "close": np.full(n, 100.0),
    }
    # Prix grimpent après entrée → short perd
    for i in range(10, 30):
        prices["high"][i] = 115.0
        prices["close"][i] = 112.0
    cfg = TripleBarrierConfig(stop_atr_mult=2.0, tp_atr_mult=10.0, max_sessions=20, min_atr=0.02)
    label = build_triple_barrier_label(entry_idx=5, side="short", prices=prices, cfg=cfg)
    assert label.exit_reason in ("stop_loss", "gap_stop")
    assert label.net_return_pct is not None and label.net_return_pct < 0


# ── Gap handling ────────────────────────────────────────────────────────────

def test_gap_stop_long(gap_down_prices) -> None:
    """Gap down traverse le stop → exécuté au prix open disponible."""
    cfg = TripleBarrierConfig(stop_atr_mult=2.0, tp_atr_mult=10.0, max_sessions=10, min_atr=0.02, entry_delay_sessions=0)
    label = build_triple_barrier_label(entry_idx=4, side="long", prices=gap_down_prices, cfg=cfg)
    # Gap à 85 traverse le stop → gap_stop
    assert label.exit_reason == "gap_stop"
    assert label.exit_price is not None


# ── Coûts transforment un gain brut en perte nette ──────────────────────────

def test_costs_turn_gain_into_flat() -> None:
    """Un petit gain brut devient non significatif après coûts."""
    cfg = TripleBarrierConfig(spread_bps=50, commission_bps=25, slippage_bps=25)
    # total_cost = 2 * (50+25+25) = 200 bps = 2%
    gross_return = 0.015  # 1.5% brut
    net = _deduct_costs(gross_return, cfg, holding_sessions=1)
    assert net < 0  # 1.5% - 2% = -0.5%


def test_costs_dont_increase_with_more_costs() -> None:
    """Plus de coûts → rendement net plus faible."""
    cfg_low = TripleBarrierConfig(spread_bps=1, commission_bps=1, slippage_bps=1)
    cfg_high = TripleBarrierConfig(spread_bps=10, commission_bps=10, slippage_bps=10)
    gross = 0.02
    net_low = _deduct_costs(gross, cfg_low, holding_sessions=1)
    net_high = _deduct_costs(gross, cfg_high, holding_sessions=1)
    assert net_high < net_low


# ── build_triple_barrier_labels (vectorisé) ─────────────────────────────────

def test_build_labels_long(ohlc_df) -> None:
    cfg = TripleBarrierConfig(stop_atr_mult=2.0, tp_atr_mult=1.5, max_sessions=15)
    result = build_triple_barrier_labels(ohlc_df, cfg, side="long")
    assert "label" in result.columns
    assert "net_return_pct" in result.columns
    assert "exit_reason" in result.columns
    assert "mae" in result.columns
    assert "mfe" in result.columns
    # Les premières lignes doivent avoir des labels valides
    early = result.iloc[:20]
    assert early["label"].notna().any()


def test_build_labels_short(ohlc_df) -> None:
    cfg = TripleBarrierConfig(stop_atr_mult=2.0, tp_atr_mult=1.5, max_sessions=15)
    result = build_triple_barrier_labels(ohlc_df, cfg, side="short")
    assert "label" in result.columns
    # Distribution short/flat
    labels = result["label"].dropna().astype(int)
    assert set(labels.unique()).issubset({-1, 0})


def test_build_triple_barrier_targets_returns_ternary_target(ohlc_df) -> None:
    result = build_triple_barrier_targets(ohlc_df, TripleBarrierConfig(max_sessions=5))

    assert {"target", "future_return", "long_net_return", "short_net_return"}.issubset(result.columns)
    assert set(result["target"].dropna().astype(int).unique()).issubset({-1, 0, 1})


# ── Symétrie long/short ─────────────────────────────────────────────────────

def test_long_short_symmetry() -> None:
    """Sur une série inversée, le long et le short devraient être symétriques
    (hors coûts asymétriques comme le borrow fee)."""
    n = 50
    uptrend = np.linspace(100, 120, n)
    downtrend = np.linspace(120, 100, n)

    prices_up = {
        "open": uptrend - 0.5,
        "high": uptrend + 1,
        "low": uptrend - 1,
        "close": uptrend + 0.5,
    }
    prices_down = {
        "open": downtrend - 0.5,
        "high": downtrend + 1,
        "low": downtrend - 1,
        "close": downtrend + 0.5,
    }

    cfg = TripleBarrierConfig(stop_atr_mult=2.0, tp_atr_mult=1.5, max_sessions=20, borrow_fee_annual=0.0)
    label_long_up = build_triple_barrier_label(entry_idx=5, side="long", prices=prices_up, cfg=cfg)
    label_short_down = build_triple_barrier_label(entry_idx=5, side="short", prices=prices_down, cfg=cfg)

    # Miroir : long sur une hausse ≈ short sur une baisse
    # Les signes devraient être opposés
    if label_long_up.net_return is not None and label_short_down.net_return is not None:
        # Les deux devraient être gagnants (long up, short down)
        assert label_long_up.net_return > 0 or label_long_up.exit_reason == "time_exit"
        assert label_short_down.net_return > 0 or label_short_down.exit_reason == "time_exit"


# ── Pas de fuite inter-fold ──────────────────────────────────────────────────

def test_no_lookahead() -> None:
    """Le label à l'index i n'utilise que les prix à partir de i+entry_delay."""
    n = 50
    prices = {
        "open": np.linspace(100, 120, n),
        "high": np.linspace(101, 121, n),
        "low": np.linspace(99, 119, n),
        "close": np.linspace(100.5, 120.5, n),
    }
    cfg = TripleBarrierConfig(stop_atr_mult=2.0, tp_atr_mult=1.5, max_sessions=10, entry_delay_sessions=1)
    label = build_triple_barrier_label(entry_idx=5, side="long", prices=prices, cfg=cfg)
    # Le label doit utiliser entry_bar_idx >= 6 (5+1)
    assert label.entry_price is not None
    # L'entrée est à entry_idx + entry_delay
    assert label.barrier_touched_at is None or label.barrier_touched_at > 5


# ── compare_label_methods ────────────────────────────────────────────────────

def test_compare_label_methods(ohlc_df) -> None:
    cfg = TripleBarrierConfig(stop_atr_mult=2.0, tp_atr_mult=1.5, max_sessions=10)
    report = compare_label_methods(ohlc_df, cfg, fixed_horizon=10)
    assert "fixed_target" in report
    assert "triple_barrier_long" in report
    assert "triple_barrier_short" in report
    assert "distribution" in report["fixed_target"]


# ── Insufficient data ───────────────────────────────────────────────────────

def test_insufficient_data_returns_flat() -> None:
    """Pas assez de données forward → flat."""
    prices = {
        "open": np.array([100.0, 101.0, 102.0]),
        "high": np.array([101.0, 102.0, 103.0]),
        "low": np.array([99.0, 100.0, 101.0]),
        "close": np.array([100.5, 101.5, 102.5]),
    }
    # max_sessions=20, entry_delay=1, 3 barres → l'entrée est à l'index 2+1=3 >= 3
    cfg = TripleBarrierConfig(max_sessions=20, entry_delay_sessions=2)
    label = build_triple_barrier_label(entry_idx=1, side="long", prices=prices, cfg=cfg)
    assert label.side == "flat"
    assert label.exit_reason == "insufficient_data"
