"""Tests for execution_engine.order_intents."""
from __future__ import annotations

from datetime import date

import pytest
from execution_engine.config import ExecutionConfig
from execution_engine.models import ExecutionTarget, IntentRole
from execution_engine.order_intents import (
    build_oco_protection_payload,
    build_entry_intents,
    build_initial_stop_intent,
    build_take_profit_intent,
    build_trailing_stop_intent,
    filter_targets_by_live_regime_guards,
    intent_to_alpaca_payload,
    resolve_initial_stop_price,
    resolve_trailing_activation_price,
)


def _target(symbol: str = "AAPL", shares: float = 100.0, price: float = 150.0) -> ExecutionTarget:
    return ExecutionTarget(
        risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol=symbol,
        target_shares=shares, entry_price=price, target_weight=0.05,
        sector="Tech", conviction_score=0.8, sizing_method="atr", kelly_fraction=0.1,
        stop_price_initial=140.0, risk_per_share=10.0, risk_budget_dollars=1_000.0,
        initial_risk_dollars=1_000.0, target_notional=15_000.0,
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

    def test_submission_key_unique_per_exec_run_while_business_key_stays_stable(self) -> None:
        cfg = ExecutionConfig()
        i1 = build_entry_intents([_target()], cfg, "run1")[0]
        i2 = build_entry_intents([_target()], cfg, "run2")[0]
        assert i1.idempotency_key == i2.idempotency_key
        assert i1.submission_key != i2.submission_key

    def test_filter_targets_by_live_regime_guards_blocks_oversized_position_weight(self) -> None:
        cfg = ExecutionConfig(regime_max_position_weight=0.20)
        oversized_target = ExecutionTarget(
            risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="AAPL",
            target_shares=100, entry_price=150.0, target_weight=0.25,
            sector="Tech", conviction_score=0.8, sizing_method="atr", kelly_fraction=0.1,
        )

        kept, blocked = filter_targets_by_live_regime_guards(
            targets=[oversized_target],
            config=cfg,
        )

        assert kept == []
        assert len(blocked) == 1
        assert blocked[0]["reason"] == "regime_max_position_weight"

    def test_filter_targets_by_live_regime_guards_enforces_sector_cap_and_max_positions_by_rank(self) -> None:
        cfg = ExecutionConfig(
            regime_max_sector_weight=0.30,
            regime_max_positions=2,
        )
        targets = [
            ExecutionTarget(
                risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="AAPL",
                target_shares=100, entry_price=150.0, target_weight=0.20,
                sector="Tech", conviction_score=0.8, sizing_method="atr", kelly_fraction=0.1,
                candidate_rank=1,
            ),
            ExecutionTarget(
                risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="MSFT",
                target_shares=90, entry_price=140.0, target_weight=0.15,
                sector="Tech", conviction_score=0.7, sizing_method="atr", kelly_fraction=0.1,
                candidate_rank=2,
            ),
            ExecutionTarget(
                risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="JPM",
                target_shares=80, entry_price=120.0, target_weight=0.12,
                sector="Financials", conviction_score=0.75, sizing_method="atr", kelly_fraction=0.1,
                candidate_rank=3,
            ),
            ExecutionTarget(
                risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="XOM",
                target_shares=70, entry_price=100.0, target_weight=0.10,
                sector="Energy", conviction_score=0.65, sizing_method="atr", kelly_fraction=0.1,
                candidate_rank=4,
            ),
        ]

        kept, blocked = filter_targets_by_live_regime_guards(targets=targets, config=cfg)

        assert [target.symbol for target in kept] == ["AAPL", "JPM"]
        assert {entry["symbol"] for entry in blocked} == {"MSFT", "XOM"}
        assert any(entry["reason"] == "regime_max_sector_weight" and entry["symbol"] == "MSFT" for entry in blocked)
        assert any(entry["reason"] == "regime_max_positions" and entry["symbol"] == "XOM" for entry in blocked)

    def test_filter_targets_by_live_regime_guards_enforces_gross_exposure_by_rank(self) -> None:
        cfg = ExecutionConfig(regime_max_gross_exposure=0.30)
        targets = [
            ExecutionTarget(
                risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="AAPL",
                target_shares=100, entry_price=150.0, target_weight=0.20,
                sector="Tech", conviction_score=0.8, sizing_method="atr", kelly_fraction=0.1,
                candidate_rank=1,
            ),
            ExecutionTarget(
                risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="MSFT",
                target_shares=90, entry_price=140.0, target_weight=0.15,
                sector="Tech", conviction_score=0.7, sizing_method="atr", kelly_fraction=0.1,
                candidate_rank=2,
            ),
        ]

        kept, blocked = filter_targets_by_live_regime_guards(targets=targets, config=cfg)

        assert [target.symbol for target in kept] == ["AAPL"]
        assert len(blocked) == 1
        assert blocked[0]["symbol"] == "MSFT"
        assert blocked[0]["reason"] == "regime_max_gross_exposure"

    def test_filter_targets_by_live_regime_guards_blocks_fractional_target_when_asset_not_fractionable(self) -> None:
        cfg = ExecutionConfig(allow_fractional_shares=True)
        targets = [_target(shares=0.5)]

        kept, blocked = filter_targets_by_live_regime_guards(
            targets=targets,
            config=cfg,
            fractionable_by_symbol={"AAPL": False},
        )

        assert kept == []
        assert len(blocked) == 1
        assert blocked[0]["reason"] == "asset_not_fractionable"
        assert blocked[0]["symbol"] == "AAPL"

    def test_filter_targets_by_live_regime_guards_blocks_fractional_target_when_flag_disabled(self) -> None:
        cfg = ExecutionConfig(allow_fractional_shares=False)
        targets = [_target(shares=0.5)]

        kept, blocked = filter_targets_by_live_regime_guards(
            targets=targets,
            config=cfg,
            fractionable_by_symbol={"AAPL": True},
        )

        assert kept == []
        assert len(blocked) == 1
        assert blocked[0]["reason"] == "fractional_shares_disabled"
        assert blocked[0]["symbol"] == "AAPL"

    def test_filter_targets_by_live_regime_guards_keeps_fractional_target_when_asset_fractionable(self) -> None:
        cfg = ExecutionConfig(allow_fractional_shares=True)
        targets = [_target(shares=0.5)]

        kept, blocked = filter_targets_by_live_regime_guards(
            targets=targets,
            config=cfg,
            fractionable_by_symbol={"AAPL": True},
        )

        assert [target.symbol for target in kept] == ["AAPL"]
        assert blocked == []

    def test_filter_targets_by_live_regime_guards_blocks_fractional_short_target(self) -> None:
        cfg = ExecutionConfig(allow_fractional_shares=True)
        targets = [ExecutionTarget(
            risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="AAPL",
            target_shares=0.5, entry_price=150.0, target_weight=0.05,
            sector="Tech", conviction_score=0.8, sizing_method="atr", kelly_fraction=0.1,
            side="sell",
        )]

        kept, blocked = filter_targets_by_live_regime_guards(
            targets=targets,
            config=cfg,
            fractionable_by_symbol={"AAPL": True},
        )

        assert kept == []
        assert len(blocked) == 1
        assert blocked[0]["reason"] == "fractional_short_not_supported"
        assert blocked[0]["symbol"] == "AAPL"


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
        ts = build_trailing_stop_intent(parent, 100.0, 150.0, cfg)
        assert ts.side == "sell"
        assert ts.order_type == "trailing_stop"
        assert ts.trail_percent == pytest.approx(5.0)
        assert ts.intent_role == IntentRole.TRAILING_STOP

    def test_initial_stop_uses_explicit_stop_price_initial(self) -> None:
        cfg = ExecutionConfig(trailing_stop_pct=0.05)
        target = _target(price=150.0)
        parent = build_entry_intents([target], cfg, "run1")[0]
        stop_intent = build_initial_stop_intent(parent, 100.0, 150.0, cfg, target=target)
        assert stop_intent is not None
        assert stop_intent.order_type == "stop"
        assert stop_intent.intent_role == IntentRole.INITIAL_STOP
        assert stop_intent.stop_price == pytest.approx(140.0, abs=0.01)

    def test_initial_stop_can_be_derived_from_risk_per_share(self) -> None:
        cfg = ExecutionConfig(trailing_stop_pct=0.05)
        target = ExecutionTarget(
            risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="AAPL",
            target_shares=100, entry_price=150.0, target_weight=0.05,
            sector="Tech", conviction_score=0.8, sizing_method="atr", kelly_fraction=0.1,
            stop_price_initial=None, risk_per_share=7.5, risk_budget_dollars=750.0,
            initial_risk_dollars=750.0, target_notional=15_000.0,
        )
        parent = build_entry_intents([target], cfg, "run1")[0]
        stop_intent = build_initial_stop_intent(parent, 100.0, 152.0, cfg, target=target)
        assert stop_intent is not None
        assert stop_intent.stop_price == pytest.approx(144.5, abs=0.01)

    def test_take_profit_uses_risk_per_share_when_more_conservative(self) -> None:
        cfg = ExecutionConfig(profit_taker_pct=0.02)
        target = _target(price=150.0)
        parent = build_entry_intents([target], cfg, "run1")[0]
        tp = build_take_profit_intent(parent, 100.0, 150.0, cfg, target=target)
        assert tp.limit_price == pytest.approx(170.0, abs=0.01)

    def test_trailing_stop_uses_stop_price_initial_when_available(self) -> None:
        cfg = ExecutionConfig(trailing_stop_pct=0.05)
        target = _target(price=150.0)
        parent = build_entry_intents([target], cfg, "run1")[0]
        ts = build_trailing_stop_intent(parent, 100.0, 150.0, cfg, target=target)
        assert ts.trail_percent == pytest.approx(6.67, abs=0.01)

    def test_resolve_initial_stop_price_returns_none_when_reference_invalid(self) -> None:
        assert resolve_initial_stop_price(0.0, _target()) is None

    def test_resolve_trailing_activation_price_uses_multiple_r(self) -> None:
        cfg = ExecutionConfig(trailing_activation_trigger="multiple_r", trailing_activation_r_multiple=1.5)
        trigger_price, trigger_mode = resolve_trailing_activation_price(150.0, cfg, _target())
        assert trigger_price == pytest.approx(165.0, abs=0.01)
        assert trigger_mode == "multiple_r"

    def test_resolve_trailing_activation_price_falls_back_to_profit_pct(self) -> None:
        cfg = ExecutionConfig(trailing_activation_trigger="multiple_r", trailing_activation_profit_pct=0.04)
        target = ExecutionTarget(
            risk_run_id="abc123", trade_date=date(2026, 4, 18), symbol="AAPL",
            target_shares=100, entry_price=150.0, target_weight=0.05,
            sector="Tech", conviction_score=0.8, sizing_method="atr", kelly_fraction=0.1,
            stop_price_initial=140.0, risk_per_share=None, risk_budget_dollars=1_000.0,
            initial_risk_dollars=1_000.0, target_notional=15_000.0,
        )
        trigger_price, trigger_mode = resolve_trailing_activation_price(150.0, cfg, target)
        assert trigger_price == pytest.approx(156.0, abs=0.01)
        assert trigger_mode == "profit_pct_fallback"


class TestIntentToPayload:
    def test_market(self) -> None:
        cfg = ExecutionConfig()
        intent = build_entry_intents([_target()], cfg, "run1")[0]
        p = intent_to_alpaca_payload(intent)
        assert p["type"] == "market"
        assert p["time_in_force"] == "day"
        assert p["qty"] == "100"
        assert "limit_price" not in p
        assert p["client_order_id"] == intent.submission_key

    def test_limit(self) -> None:
        cfg = ExecutionConfig(entry_order_type="limit")
        intent = build_entry_intents([_target()], cfg, "run1")[0]
        p = intent_to_alpaca_payload(intent)
        assert p["type"] == "limit"
        assert "limit_price" in p

    def test_fractional_qty_is_formatted_without_trailing_noise(self) -> None:
        cfg = ExecutionConfig()
        intent = build_entry_intents([_target(shares=3.6540000001)], cfg, "run1")[0]
        p = intent_to_alpaca_payload(intent)
        assert p["qty"] == "3.654"

    def test_fractional_limit_qty_uses_compact_decimal_format(self) -> None:
        cfg = ExecutionConfig(entry_order_type="limit", allow_fractional_shares=True)
        intent = build_entry_intents([_target(shares=0.125, price=100.0)], cfg, "run1")[0]
        p = intent_to_alpaca_payload(intent)
        assert p["qty"] == "0.125"
        assert p["type"] == "limit"

    def test_fractional_stop_payload_uses_day_tif_in_intraday_only_mode(self) -> None:
        cfg = ExecutionConfig(
            allow_fractional_shares=True,
            fractional_live_mode="intraday_only",
            execution_profile="custom",
            swing_only=False,
            trailing_stop_pct=0.05,
        )
        target = _target(shares=0.5)
        parent = build_entry_intents([target], cfg, "run1")[0]
        stop_intent = build_initial_stop_intent(parent, 0.5, 150.0, cfg, target=target)
        assert stop_intent is not None

        p = intent_to_alpaca_payload(stop_intent, config=cfg)

        assert p["type"] == "stop"
        assert p["time_in_force"] == "day"

    def test_fractional_protection_payload_is_rejected_in_entry_only_mode(self) -> None:
        cfg = ExecutionConfig(
            allow_fractional_shares=True,
            fractional_live_mode="entry_only",
            trailing_stop_pct=0.05,
        )
        target = _target(shares=0.5)
        parent = build_entry_intents([target], cfg, "run1")[0]
        trailing_intent = build_trailing_stop_intent(parent, 0.5, 150.0, cfg, target=target)

        with pytest.raises(ValueError, match="Fractional protection payload"):
            intent_to_alpaca_payload(trailing_intent, config=cfg)

    def test_fractional_oco_payload_uses_day_tif_in_intraday_only_mode(self) -> None:
        cfg = ExecutionConfig(
            allow_fractional_shares=True,
            fractional_live_mode="intraday_only",
            execution_profile="custom",
            swing_only=False,
            profit_taker_pct=0.08,
            trailing_stop_pct=0.05,
        )
        target = _target(shares=0.5)
        parent = build_entry_intents([target], cfg, "run1")[0]
        tp_intent = build_take_profit_intent(parent, 0.5, 150.0, cfg, target=target)
        stop_intent = build_initial_stop_intent(parent, 0.5, 150.0, cfg, target=target)
        assert stop_intent is not None

        payload = build_oco_protection_payload(parent, tp_intent, stop_intent, config=cfg)

        assert payload["qty"] == "0.5"
        assert payload["time_in_force"] == "day"

    def test_trailing_stop_payload(self) -> None:
        cfg = ExecutionConfig(trailing_stop_pct=0.05)
        target = _target()
        parent = build_entry_intents([target], cfg, "run1")[0]
        ts = build_trailing_stop_intent(parent, 100.0, 150.0, cfg, target=target)
        p = intent_to_alpaca_payload(ts)
        assert p["type"] == "trailing_stop"
        assert p["trail_percent"] == "6.67"
        assert p["time_in_force"] == "gtc"

    def test_stop_payload(self) -> None:
        cfg = ExecutionConfig(trailing_stop_pct=0.05)
        target = _target()
        parent = build_entry_intents([target], cfg, "run1")[0]
        stop_intent = build_initial_stop_intent(parent, 100.0, 150.0, cfg, target=target)
        assert stop_intent is not None
        p = intent_to_alpaca_payload(stop_intent)
        assert p["type"] == "stop"
        assert p["stop_price"] == "140.0"
        assert p["time_in_force"] == "gtc"

    def test_time_in_force_day_for_entry_gtc_for_children(self) -> None:
        cfg = ExecutionConfig(profit_taker_pct=0.08)
        parent = build_entry_intents([_target()], cfg, "run1")[0]
        tp = build_take_profit_intent(parent, 100.0, 150.0, cfg)
        assert intent_to_alpaca_payload(parent)["time_in_force"] == "day"
        assert intent_to_alpaca_payload(tp)["time_in_force"] == "gtc"
