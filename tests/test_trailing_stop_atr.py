"""Tests pour le trailing stop ATR dynamique (Axe F)."""
from __future__ import annotations

from execution_engine.config import ExecutionConfig, TrailingStopConfig
from execution_engine.order_intents import build_manual_buy_initial_stop_intent
from execution_engine.models import OrderIntent
from service.market.volatility import OHLCBar, compute_atr_from_bars


def _parent(symbol="AAPL") -> OrderIntent:
    return OrderIntent(
        intent_id="i1",
        risk_run_id="r1",
        exec_run_id="e1",
        symbol=symbol,
        side="buy",
        qty=10,
        order_type="market",
        limit_price=None,
        trail_percent=None,
        broker_mode="paper",
        parent_intent_id=None,
        intent_role="ENTRY",
        idempotency_key="k",
        decision_price=100.0,
    )


def test_compute_atr_from_bars_returns_positive_value():
    bars = [
        OHLCBar(high=h, low=l, close=c)
        for h, l, c in [
            (10, 9, 9.5), (10.5, 9.5, 10), (11, 10, 10.7), (11.5, 10.5, 11),
            (12, 11, 11.8), (12.5, 11.5, 12), (13, 12, 12.6), (13.5, 12.5, 13),
            (14, 13, 13.7), (14.5, 13.5, 14), (15, 14, 14.6), (15.5, 14.5, 15),
            (16, 15, 15.6), (16.5, 15.5, 16), (17, 16, 16.6), (17.5, 16.5, 17),
        ]
    ]
    atr = compute_atr_from_bars(bars, period=14)
    assert atr is not None
    assert atr > 0


def test_compute_atr_returns_none_when_insufficient_bars():
    bars = [OHLCBar(10, 9, 9.5), OHLCBar(10.5, 9.5, 10)]
    assert compute_atr_from_bars(bars, period=14) is None


def test_manual_buy_initial_stop_dynamic_atr_mode():
    cfg = ExecutionConfig(
        manual_buy_stop_loss_pct=0.05,
        trailing_stop=TrailingStopConfig(
            enabled=True, mode="dynamic_atr", atr_multiplier=2.5, fallback_fixed_pct=5.0,
            apply_to_manual_orphan_buys=True,
        ),
    )
    intent = build_manual_buy_initial_stop_intent(_parent(), 10, 100.0, cfg, atr_value=2.0)
    assert intent is not None
    # stop = 100 - 2.5 * 2 = 95.0
    assert intent.stop_price == 95.0


def test_manual_buy_initial_stop_fallback_fixed_pct_when_atr_missing():
    cfg = ExecutionConfig(
        manual_buy_stop_loss_pct=0.05,
        trailing_stop=TrailingStopConfig(
            enabled=True, mode="dynamic_atr", atr_multiplier=2.5, fallback_fixed_pct=5.0,
            apply_to_manual_orphan_buys=True,
        ),
    )
    intent = build_manual_buy_initial_stop_intent(_parent(), 10, 100.0, cfg, atr_value=None)
    assert intent is not None
    # fallback fixed 5% -> stop 95.0
    assert intent.stop_price == 95.0


def test_manual_buy_initial_stop_legacy_when_trailing_disabled():
    cfg = ExecutionConfig(
        manual_buy_stop_loss_pct=0.10,
        trailing_stop=TrailingStopConfig(enabled=False),
    )
    intent = build_manual_buy_initial_stop_intent(_parent(), 10, 100.0, cfg, atr_value=5.0)
    assert intent is not None
    # comportement historique : 100 * (1 - 0.10) = 90
    assert intent.stop_price == 90.0


def test_execution_config_blocks_new_entries_for_close_or_cash_only():
    assert ExecutionConfig(entry_mode="normal").blocks_new_entries is False
    assert ExecutionConfig(entry_mode="close_only").blocks_new_entries is True
    assert ExecutionConfig(entry_mode="cash_only").blocks_new_entries is True
    assert ExecutionConfig(entry_mode="capital_preservation").blocks_new_entries is False


