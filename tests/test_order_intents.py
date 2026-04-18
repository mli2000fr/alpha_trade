"""Tests for execution_engine.order_intents."""
from __future__ import annotations

from datetime import date

import pytest
from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionTarget, IntentRole
from execution_engine.order_intents import (
    build_entry_intents,
    build_take_profit_intent,
    build_trailing_stop_intent,
    intent_to_alpaca_payload,
)


def _target(symbol: str = "AAPL", shares: int = 100, price: float = 150.0) -> ExecutionTarget:
    return ExecutionTarget(
        risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol=symbol,
        target_shares=shares, entry_price=price, target_weight=0.05,
        sector="Tech", conviction_score=0.8, sizing_method="atr", kelly_fraction=0.1,
    )


class TestBuildEntryIntents:
    def test_market(self) -> None:
        cfg = ExecutionConfig(broker_mode="paper", entry_order_type="market")
        intents = build_entry_intents([_target()], cfg, "run1")
        assert len(intents) == 1
        assert intents[0].order_type == "market"
        assert intents[0].limit_price is None
        assert intents[0].side == "buy"
        assert intents[0].intent_role == IntentRole.ENTRY

    def test_limit(self) -> None:
        cfg = ExecutionConfig(broker_mode="paper", entry_order_type="limit", limit_price_buffer_bps=10)
        intents = build_entry_intents([_target(price=100.0)], cfg, "run1")
        assert intents[0].order_type == "limit"
        assert intents[0].limit_price == pytest.approx(100.10, abs=0.01)

    def test_skip_zero_shares(self) -> None:
        cfg = ExecutionConfig()
        intents = build_entry_intents([_target(shares=0)], cfg, "run1")
        assert intents == []

    def test_idempotency_key_stable(self) -> None:
        cfg = ExecutionConfig()
        i1 = build_entry_intents([_target()], cfg, "run1")
        i2 = build_entry_intents([_target()], cfg, "run1")
        assert i1[0].idempotency_key == i2[0].idempotency_key

    def test_idempotency_key_unique_across_symbols(self) -> None:
        cfg = ExecutionConfig()
        intents = build_entry_intents([_target("AAPL"), _target("MSFT")], cfg, "run1")
        assert intents[0].idempotency_key != intents[1].idempotency_key


class TestBuildChildren:
    def test_take_profit(self) -> None:
        cfg = ExecutionConfig(profit_taker_pct=0.08)
        parent = build_entry_intents([_target()], cfg, "run1")[0]
        tp = build_take_profit_intent(parent, 100.0, 150.0, cfg)
        assert tp.side == "sell"
        assert tp.order_type == "limit"
        assert tp.limit_price == pytest.approx(162.0, abs=0.01)
        assert tp.intent_role == IntentRole.TAKE_PROFIT
        assert tp.parent_intent_id == parent.intent_id

    def test_trailing_stop(self) -> None:
        cfg = ExecutionConfig(trailing_stop_pct=0.05)
        parent = build_entry_intents([_target()], cfg, "run1")[0]
        ts = build_trailing_stop_intent(parent, 100.0, cfg)
        assert ts.side == "sell"
        assert ts.order_type == "trailing_stop"
        assert ts.trail_percent == pytest.approx(5.0)
        assert ts.intent_role == IntentRole.TRAILING_STOP


class TestIntentToPayload:
    def test_market(self) -> None:
        cfg = ExecutionConfig()
        intent = build_entry_intents([_target()], cfg, "run1")[0]
        p = intent_to_alpaca_payload(intent)
        assert p["type"] == "market"
        assert p["time_in_force"] == "day"
        assert p["qty"] == "100"
        assert "limit_price" not in p

    def test_limit(self) -> None:
        cfg = ExecutionConfig(entry_order_type="limit")
        intent = build_entry_intents([_target()], cfg, "run1")[0]
        p = intent_to_alpaca_payload(intent)
        assert p["type"] == "limit"
        assert "limit_price" in p

    def test_trailing_stop_payload(self) -> None:
        cfg = ExecutionConfig(trailing_stop_pct=0.05)
        parent = build_entry_intents([_target()], cfg, "run1")[0]
        ts = build_trailing_stop_intent(parent, 100.0, cfg)
        p = intent_to_alpaca_payload(ts)
        assert p["type"] == "trailing_stop"
        assert p["trail_percent"] == "5.0"
        assert p["time_in_force"] == "gtc"

    def test_time_in_force_day_for_entry_gtc_for_children(self) -> None:
        cfg = ExecutionConfig(profit_taker_pct=0.08)
        parent = build_entry_intents([_target()], cfg, "run1")[0]
        tp = build_take_profit_intent(parent, 100.0, 150.0, cfg)
        assert intent_to_alpaca_payload(parent)["time_in_force"] == "day"
        assert intent_to_alpaca_payload(tp)["time_in_force"] == "gtc"
