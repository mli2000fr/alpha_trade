"""Tests de parité label/simulateur — même coûts, mêmes prix de sortie.

Section 17 Point 3 : le labeler triple-barrier et le simulateur backtest
doivent produire le même prix de sortie, la même raison de sortie,
le même rendement net et la même durée sur des fixtures OHLC déterministes,
lorsqu'ils utilisent le MÊME modèle de coûts.

Ce module teste la parité avec un simulateur minimal qui applique les
MÊMES règles que ``_resolve_exit()`` et le MÊME ``TradingCostModel``.
"""

from __future__ import annotations

import numpy as np
import pytest

from common.trading_costs import TradingCostModel, DEFAULT_COST_MODEL
from modelFactory.labeling import (
    TripleBarrierConfig,
    TripleBarrierLabel,
    build_triple_barrier_label,
    _resolve_exit,
    _compute_atr,
)


# ── Minimal simulator (same rules as labeler) ───────────────────────────────

def simulate_trade(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    entry_price: float,
    side: str,
    stop_price: float,
    tp_price: float,
    max_sessions: int,
    entry_idx: int,
    costs: TradingCostModel,
) -> dict:
    """Simule un trade barre par barre avec les MÊMES règles que _resolve_exit.

    Returns
    -------
    dict avec exit_price, exit_reason, holding_sessions, gross_return, net_return.
    """
    direction = -1 if side == "short" else 1
    exit_reason = "time_exit"
    exit_idx = min(entry_idx + max_sessions, len(closes) - 1)
    exit_price = closes[exit_idx]

    for i in range(entry_idx + 1, min(entry_idx + max_sessions + 1, len(highs))):
        if i >= len(highs):
            break

        # Gap à l'open
        if opens[i] > 0 and np.isfinite(opens[i]):
            if side == "long":
                gap_stop = opens[i] <= stop_price
                gap_tp = opens[i] >= tp_price
            else:
                gap_stop = opens[i] >= stop_price
                gap_tp = opens[i] <= tp_price

            if gap_stop:
                return _build_result(i, opens[i], "gap_stop", side,
                                     entry_price, costs, entry_idx)
            if gap_tp:
                return _build_result(i, opens[i], "gap_tp", side,
                                     entry_price, costs, entry_idx)

        # Vérification intraday
        high, low = highs[i], lows[i]
        if not (np.isfinite(high) and np.isfinite(low)):
            continue

        if side == "long":
            stop_hit = low <= stop_price
            tp_hit = high >= tp_price
        else:
            stop_hit = high >= stop_price
            tp_hit = low <= tp_price

        if stop_hit and tp_hit:
            # Conservative: stop prioritaire
            exit_price = stop_price
            exit_reason = "stop_loss"
            exit_idx = i
            break
        elif stop_hit:
            exit_price = stop_price
            exit_reason = "stop_loss"
            exit_idx = i
            break
        elif tp_hit:
            exit_price = tp_price
            exit_reason = "take_profit"
            exit_idx = i
            break

    return _build_result(exit_idx, exit_price, exit_reason, side,
                         entry_price, costs, entry_idx)


def _build_result(
    exit_idx: int, exit_price: float, exit_reason: str, side: str,
    entry_price: float, costs: TradingCostModel, entry_idx: int,
) -> dict:
    holding = exit_idx - entry_idx
    direction = -1 if side == "short" else 1
    gross_return = (exit_price - entry_price) / entry_price * direction
    net_return = costs.effective_cost_for_trade(gross_return, side, holding)
    return {
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "holding_sessions": holding,
        "gross_return": gross_return,
        "net_return": net_return,
    }


# ── OHLC fixtures ───────────────────────────────────────────────────────────

def _make_ohlc(prices: list[float]) -> tuple[np.ndarray, ...]:
    """Fabrique OHLC sans gap : open[i] ≈ close[i-1] (continuité)."""
    n = len(prices)
    opens = np.array([prices[0]] + [prices[i-1] * (1 + np.random.RandomState(i).uniform(-0.0005, 0.0005)) for i in range(1, n)], dtype=float)
    highs = np.array([p * 1.005 for p in prices], dtype=float)
    lows = np.array([p * 0.995 for p in prices], dtype=float)
    closes = np.array(prices, dtype=float)
    return opens, highs, lows, closes


def _make_trend_ohlc(
    start: float, step: float, n: int, noise: float = 0.0,
) -> tuple[np.ndarray, ...]:
    """OHLC en tendance : start, start+step, start+2*step, ..."""
    rng = np.random.RandomState(42)
    prices = [start]
    for i in range(1, n):
        prices.append(prices[-1] + step + rng.uniform(-noise, noise))
    return _make_ohlc(prices)


# ── Parity tests ────────────────────────────────────────────────────────────

class TestLabelSimulatorParity:
    """Le labeler et le simulateur minimal doivent produire le MÊME résultat."""

    def test_long_tp_parity(self):
        """Long take-profit : labeler == simulateur."""
        # Assez de barres pour que l'ATR ait 14 barres d'historique
        opens, highs, lows, closes = _make_trend_ohlc(100.0, 1.0, 40, noise=0.1)
        prices = {"open": opens, "high": highs, "low": lows, "close": closes}
        entry_idx = 13  # 14 barres d'historique pour l'ATR
        entry_price_label = float(opens[entry_idx + 1])

        cfg = TripleBarrierConfig(
            stop_atr_mult=2.0, tp_atr_mult=2.0, max_sessions=20,
            entry_delay_sessions=1,
        )
        costs = DEFAULT_COST_MODEL

        label: TripleBarrierLabel = build_triple_barrier_label(
            entry_idx=entry_idx, side="long", prices=prices, cfg=cfg,
        )

        # Calculer stop/TP avec les MÊMES paramètres que le labeler
        atr = _compute_atr(highs[:entry_idx+2], lows[:entry_idx+2], closes[:entry_idx+2], cfg.atr_window)
        atr_val = max(float(atr[entry_idx + 1]), cfg.min_atr * entry_price_label)
        stop_price = entry_price_label - cfg.stop_atr_mult * atr_val
        tp_price = entry_price_label + cfg.tp_atr_mult * atr_val

        sim = simulate_trade(
            opens, highs, lows, closes,
            entry_price=entry_price_label, side="long",
            stop_price=stop_price, tp_price=tp_price,
            max_sessions=cfg.max_sessions, entry_idx=entry_idx + 1, costs=costs,
        )

        assert label.exit_reason == sim["exit_reason"], \
            f"exit_reason: label={label.exit_reason} sim={sim['exit_reason']}"
        assert label.exit_price == pytest.approx(sim["exit_price"], rel=1e-10), \
            f"exit_price: label={label.exit_price} sim={sim['exit_price']}"
        assert label.holding_sessions == sim["holding_sessions"], \
            f"holding: label={label.holding_sessions} sim={sim['holding_sessions']}"
        assert label.net_return == pytest.approx(sim["net_return"], rel=1e-10), \
            f"net_return: label={label.net_return} sim={sim['net_return']}"

    def test_long_stop_parity(self):
        """Long stop-loss : labeler == simulateur."""
        opens, highs, lows, closes = _make_trend_ohlc(100.0, -0.8, 40, noise=0.1)
        prices = {"open": opens, "high": highs, "low": lows, "close": closes}
        entry_idx = 13
        entry_price_label = float(opens[entry_idx + 1])

        cfg = TripleBarrierConfig(
            stop_atr_mult=1.5, tp_atr_mult=4.0, max_sessions=20,
            entry_delay_sessions=1,
        )
        costs = DEFAULT_COST_MODEL

        label = build_triple_barrier_label(
            entry_idx=entry_idx, side="long", prices=prices, cfg=cfg,
        )

        atr = _compute_atr(highs[:entry_idx+2], lows[:entry_idx+2], closes[:entry_idx+2], cfg.atr_window)
        atr_val = max(float(atr[entry_idx + 1]), cfg.min_atr * entry_price_label)
        stop_price = entry_price_label - cfg.stop_atr_mult * atr_val
        tp_price = entry_price_label + cfg.tp_atr_mult * atr_val

        sim = simulate_trade(
            opens, highs, lows, closes,
            entry_price=entry_price_label, side="long",
            stop_price=stop_price, tp_price=tp_price,
            max_sessions=cfg.max_sessions, entry_idx=entry_idx + 1, costs=costs,
        )

        assert label.exit_reason == sim["exit_reason"]
        assert label.exit_price == pytest.approx(sim["exit_price"], rel=1e-10)
        assert label.holding_sessions == sim["holding_sessions"]
        assert label.net_return == pytest.approx(sim["net_return"], rel=1e-10)

    def test_short_tp_parity(self):
        """Short take-profit : labeler == simulateur."""
        opens, highs, lows, closes = _make_trend_ohlc(100.0, -1.0, 40, noise=0.1)
        prices = {"open": opens, "high": highs, "low": lows, "close": closes}
        entry_idx = 13
        entry_price_label = float(opens[entry_idx + 1])

        cfg = TripleBarrierConfig(
            stop_atr_mult=2.0, tp_atr_mult=2.0, max_sessions=20,
            entry_delay_sessions=1,
        )
        costs = DEFAULT_COST_MODEL

        label = build_triple_barrier_label(
            entry_idx=entry_idx, side="short", prices=prices, cfg=cfg,
        )

        atr = _compute_atr(highs[:entry_idx+2], lows[:entry_idx+2], closes[:entry_idx+2], cfg.atr_window)
        atr_val = max(float(atr[entry_idx + 1]), cfg.min_atr * entry_price_label)
        stop_price = entry_price_label + cfg.stop_atr_mult * atr_val
        tp_price = entry_price_label - cfg.tp_atr_mult * atr_val

        sim = simulate_trade(
            opens, highs, lows, closes,
            entry_price=entry_price_label, side="short",
            stop_price=stop_price, tp_price=tp_price,
            max_sessions=cfg.max_sessions, entry_idx=entry_idx + 1, costs=costs,
        )

        assert label.exit_reason == sim["exit_reason"], \
            f"exit_reason: label={label.exit_reason} sim={sim['exit_reason']}"
        assert label.exit_price == pytest.approx(sim["exit_price"], rel=1e-10)
        assert label.holding_sessions == sim["holding_sessions"]
        assert label.net_return == pytest.approx(sim["net_return"], rel=1e-10)

    def test_short_stop_parity(self):
        """Short stop-loss : labeler == simulateur."""
        opens, highs, lows, closes = _make_trend_ohlc(100.0, 0.8, 40, noise=0.1)
        prices = {"open": opens, "high": highs, "low": lows, "close": closes}
        entry_idx = 13
        entry_price_label = float(opens[entry_idx + 1])

        cfg = TripleBarrierConfig(
            stop_atr_mult=1.5, tp_atr_mult=4.0, max_sessions=20,
            entry_delay_sessions=1,
        )
        costs = DEFAULT_COST_MODEL

        label = build_triple_barrier_label(
            entry_idx=entry_idx, side="short", prices=prices, cfg=cfg,
        )

        atr = _compute_atr(highs[:entry_idx+2], lows[:entry_idx+2], closes[:entry_idx+2], cfg.atr_window)
        atr_val = max(float(atr[entry_idx + 1]), cfg.min_atr * entry_price_label)
        stop_price = entry_price_label + cfg.stop_atr_mult * atr_val
        tp_price = entry_price_label - cfg.tp_atr_mult * atr_val

        sim = simulate_trade(
            opens, highs, lows, closes,
            entry_price=entry_price_label, side="short",
            stop_price=stop_price, tp_price=tp_price,
            max_sessions=cfg.max_sessions, entry_idx=entry_idx + 1, costs=costs,
        )

        assert label.exit_reason == sim["exit_reason"]
        assert label.exit_price == pytest.approx(sim["exit_price"], rel=1e-10)
        assert label.holding_sessions == sim["holding_sessions"]
        assert label.net_return == pytest.approx(sim["net_return"], rel=1e-10)

    def test_time_exit_parity(self):
        """Time exit (pas de barrier touché) : labeler == simulateur."""
        opens, highs, lows, closes = _make_trend_ohlc(100.0, 0.1, 40, noise=0.05)
        prices = {"open": opens, "high": highs, "low": lows, "close": closes}
        entry_idx = 13
        entry_price_label = float(opens[entry_idx + 1])

        cfg = TripleBarrierConfig(
            stop_atr_mult=5.0, tp_atr_mult=5.0, max_sessions=10,
            entry_delay_sessions=1,
        )
        costs = DEFAULT_COST_MODEL

        label = build_triple_barrier_label(
            entry_idx=entry_idx, side="long", prices=prices, cfg=cfg,
        )

        atr = _compute_atr(highs[:entry_idx+2], lows[:entry_idx+2], closes[:entry_idx+2], cfg.atr_window)
        atr_val = max(float(atr[entry_idx + 1]), cfg.min_atr * entry_price_label)
        stop_price = entry_price_label - cfg.stop_atr_mult * atr_val
        tp_price = entry_price_label + cfg.tp_atr_mult * atr_val

        sim = simulate_trade(
            opens, highs, lows, closes,
            entry_price=entry_price_label, side="long",
            stop_price=stop_price, tp_price=tp_price,
            max_sessions=cfg.max_sessions, entry_idx=entry_idx + 1, costs=costs,
        )

        assert label.exit_reason == sim["exit_reason"]
        assert label.exit_price == pytest.approx(sim["exit_price"], rel=1e-10)
        assert label.holding_sessions == sim["holding_sessions"]
        assert label.net_return == pytest.approx(sim["net_return"], rel=1e-10)

    def test_gap_stop_parity(self):
        """Gap à travers le stop : labeler == simulateur."""
        # Construction d'un gap réel : prix qui chute brutalement du jour au lendemain
        raw_prices = [100.0] * 14 + [100.5, 101.0, 101.5, 88.0]  # gap à 88!
        opens_arr, highs_arr, lows_arr, closes_arr = _make_ohlc(raw_prices)
        # Force le gap: opens[17] (le jour du gap) = 88.0 au lieu de ~101.5
        opens_arr = opens_arr.copy()
        opens_arr[16] = 88.0  # gap down à l'open
        prices = {"open": opens_arr, "high": highs_arr, "low": lows_arr, "close": closes_arr}
        entry_idx = 13
        entry_price_label = float(opens_arr[entry_idx + 1])

        cfg = TripleBarrierConfig(
            stop_atr_mult=1.0, tp_atr_mult=5.0, max_sessions=20,
            entry_delay_sessions=1,
        )

        label = build_triple_barrier_label(
            entry_idx=entry_idx, side="long", prices=prices, cfg=cfg,
        )

        if label.exit_reason == "gap_stop":
            costs = DEFAULT_COST_MODEL
            atr = _compute_atr(highs_arr[:entry_idx+2], lows_arr[:entry_idx+2], closes_arr[:entry_idx+2], cfg.atr_window)
            atr_val = max(float(atr[entry_idx + 1]), cfg.min_atr * entry_price_label)
            stop_price = entry_price_label - cfg.stop_atr_mult * atr_val
            tp_price = entry_price_label + cfg.tp_atr_mult * atr_val

            sim = simulate_trade(
                opens_arr, highs_arr, lows_arr, closes_arr,
                entry_price=entry_price_label, side="long",
                stop_price=stop_price, tp_price=tp_price,
                max_sessions=cfg.max_sessions, entry_idx=entry_idx + 1, costs=costs,
            )

            assert label.exit_reason == sim["exit_reason"]
            assert label.exit_price == pytest.approx(sim["exit_price"], rel=1e-10)
            assert label.holding_sessions == sim["holding_sessions"]
            assert label.net_return == pytest.approx(sim["net_return"], rel=1e-10)
        else:
            pytest.fail(f"Expected gap_stop, got {label.exit_reason}")


# ── TradingCostModel contract tests ─────────────────────────────────────────

class TestTradingCostModel:
    def test_defaults(self):
        c = DEFAULT_COST_MODEL
        assert c.spread_bps == 5.0
        assert c.commission_bps == 1.0
        assert c.slippage_bps == 2.0
        assert c.per_leg_cost_bps == 8.0
        assert c.round_trip_cost_bps == 16.0
        assert c.per_leg_cost_pct == 0.0008
        assert c.round_trip_cost_pct == 0.0016

    def test_deduct_round_trip(self):
        c = DEFAULT_COST_MODEL
        assert c.deduct_round_trip(0.02) == 0.02 - 0.0016
        assert c.deduct_round_trip(0.001) == 0.001 - 0.0016  # négatif → perte

    def test_borrow_cost_zero_when_no_fee(self):
        c = TradingCostModel(borrow_fee_annual=0.0)
        assert c.borrow_cost_for_holding(20) == 0.0

    def test_borrow_cost_proportional(self):
        c = TradingCostModel(borrow_fee_annual=0.003)
        cost_10d = c.borrow_cost_for_holding(10)
        cost_20d = c.borrow_cost_for_holding(20)
        assert cost_20d == pytest.approx(2.0 * cost_10d)

    def test_effective_cost_long(self):
        c = DEFAULT_COST_MODEL
        net = c.effective_cost_for_trade(0.02, "long", holding_sessions=10)
        expected = 0.02 - 0.0016  # no borrow for longs
        assert net == pytest.approx(expected)

    def test_effective_cost_short(self):
        c = DEFAULT_COST_MODEL
        net = c.effective_cost_for_trade(0.02, "short", holding_sessions=10)
        expected = 0.02 - 0.0016 - c.borrow_cost_for_holding(10)
        assert net == pytest.approx(expected)

    def test_to_dict_from_dict_roundtrip(self):
        c = TradingCostModel(spread_bps=3.0, commission_bps=2.0, slippage_bps=4.0)
        d = c.to_dict()
        c2 = TradingCostModel.from_dict(d)
        assert c2.spread_bps == 3.0
        assert c2.commission_bps == 2.0
        assert c2.slippage_bps == 4.0
        assert c2.round_trip_cost_bps == 2 * (3 + 2 + 4)

    def test_immutable(self):
        c = DEFAULT_COST_MODEL
        with pytest.raises(Exception):
            c.spread_bps = 10.0  # type: ignore[misc]

    def test_custom_costs(self):
        c = TradingCostModel(spread_bps=10.0, commission_bps=0.0, slippage_bps=0.0)
        assert c.round_trip_cost_bps == 20.0
        assert c.round_trip_cost_pct == 0.002


# ── Cost consistency: labeler vs edge ───────────────────────────────────────

class TestCostConsistency:
    """Le labeler et l'EdgeCalculator doivent utiliser les MÊMES coûts."""

    def test_labeler_defaults_match_cost_model(self):
        """TripleBarrierConfig doit avoir les mêmes défauts que TradingCostModel."""
        cfg = TripleBarrierConfig()
        costs = DEFAULT_COST_MODEL

        assert cfg.spread_bps == costs.spread_bps
        assert cfg.commission_bps == costs.commission_bps
        assert cfg.slippage_bps == costs.slippage_bps
        assert cfg.borrow_fee_annual == costs.borrow_fee_annual
        assert cfg.total_cost_bps == costs.round_trip_cost_bps
        assert cfg.cost_pct == costs.round_trip_cost_pct

    def test_edge_calculator_defaults_match_cost_model(self):
        """EdgeCalculator doit avoir les mêmes défauts que TradingCostModel."""
        from risk_management.edge import EdgeCalculator
        edge = EdgeCalculator()
        costs = DEFAULT_COST_MODEL

        assert edge.spread_bps == costs.spread_bps
        assert edge.commission_bps == costs.commission_bps
        assert edge.slippage_bps == costs.slippage_bps
        assert edge.borrow_fee_annual == costs.borrow_fee_annual
        assert edge.total_cost_bps == costs.round_trip_cost_bps
        assert edge.cost_pct == costs.round_trip_cost_pct
