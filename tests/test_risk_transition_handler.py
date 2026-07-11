"""Tests unitaires — risk_management/transition_handler.py (Sprint Maître 9).

Vérifie la gestion des positions et ordres lors des transitions de régime.
"""

from __future__ import annotations

import pytest

from risk_management.regime_state_machine import (
    RegimeState,
    RegimeTransition,
    TransitionAction,
)
from risk_management.transition_handler import (
    OpenOrder,
    OpenPosition,
    OrderAction,
    PositionTransitionPlan,
    TransitionHandler,
    TransitionStep,
    build_transition_plan,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def handler() -> TransitionHandler:
    return TransitionHandler()


@pytest.fixture
def long_positions() -> list[OpenPosition]:
    return [
        OpenPosition("AAPL", "long", 100, 150.0, current_price=155.0, unrealized_pnl_pct=0.033),
        OpenPosition("MSFT", "long", 50, 300.0, current_price=310.0, unrealized_pnl_pct=0.033),
    ]


@pytest.fixture
def short_positions() -> list[OpenPosition]:
    return [
        OpenPosition("TSLA", "short", 200, 250.0, current_price=240.0, unrealized_pnl_pct=0.04),
    ]


@pytest.fixture
def mixed_positions() -> list[OpenPosition]:
    return [
        OpenPosition("AAPL", "long", 100, 150.0),
        OpenPosition("TSLA", "short", 200, 250.0),
    ]


@pytest.fixture
def open_orders() -> list[OpenOrder]:
    return [
        OpenOrder("ord_001", "AAPL", "buy", "limit", 50, filled_quantity=20),
        OpenOrder("ord_002", "MSFT", "sell", "stop", 25),
    ]


@pytest.fixture
def escalation_transition() -> RegimeTransition:
    return RegimeTransition(
        from_state=RegimeState.NORMAL,
        to_state=RegimeState.CAPITAL_PRESERVATION,
        action=TransitionAction.LIQUIDATE_LONGS,
        reason="vix_spike_hard_trigger",
    )


@pytest.fixture
def liquidation_transition() -> RegimeTransition:
    return RegimeTransition(
        from_state=RegimeState.CAPITAL_PRESERVATION,
        to_state=RegimeState.CASH_ONLY,
        action=TransitionAction.LIQUIDATE_ALL,
        reason="yield_shock",
    )


@pytest.fixture
def no_op_transition() -> RegimeTransition:
    return RegimeTransition(
        from_state=RegimeState.NORMAL,
        to_state=RegimeState.NORMAL,
        action=TransitionAction.NO_OP,
        reason="maintien en normal",
    )


# ── OpenPosition / OpenOrder ────────────────────────────────────────────────


class TestOpenPosition:
    def test_valid_long(self) -> None:
        p = OpenPosition("AAPL", "long", 100, 150.0)
        assert p.symbol == "AAPL"
        assert p.side == "long"

    def test_valid_short(self) -> None:
        p = OpenPosition("TSLA", "short", 200, 250.0)
        assert p.side == "short"

    def test_rejects_invalid_side(self) -> None:
        with pytest.raises(ValueError, match="side"):
            OpenPosition("AAPL", "both", 100, 150.0)

    def test_rejects_zero_quantity(self) -> None:
        with pytest.raises(ValueError, match="quantity"):
            OpenPosition("AAPL", "long", 0, 150.0)

    def test_rejects_negative_quantity(self) -> None:
        with pytest.raises(ValueError, match="quantity"):
            OpenPosition("AAPL", "long", -10, 150.0)

    def test_partial_fill_tracking(self) -> None:
        p = OpenPosition("AAPL", "long", 100, 150.0, has_partial_fill=True, filled_quantity=60)
        assert p.has_partial_fill is True
        assert p.filled_quantity == 60


class TestOpenOrder:
    def test_valid_order(self) -> None:
        o = OpenOrder("ord_001", "AAPL", "buy", "limit", 50)
        assert o.order_id == "ord_001"
        assert o.side == "buy"

    def test_rejects_invalid_side(self) -> None:
        with pytest.raises(ValueError, match="side"):
            OpenOrder("ord_001", "AAPL", "hold", "limit", 50)

    def test_partial_fill_detection(self) -> None:
        o = OpenOrder("ord_001", "AAPL", "buy", "limit", 50, filled_quantity=20)
        assert o.has_partial_fill is True

    def test_no_partial_fill(self) -> None:
        o = OpenOrder("ord_001", "AAPL", "buy", "limit", 50, filled_quantity=0)
        assert o.has_partial_fill is False

    def test_fully_filled_not_partial(self) -> None:
        o = OpenOrder("ord_001", "AAPL", "buy", "limit", 50, filled_quantity=50)
        assert o.has_partial_fill is False


# ── TransitionStep ──────────────────────────────────────────────────────────


class TestTransitionStep:
    def test_cancel_step(self) -> None:
        step = TransitionStep("AAPL", OrderAction.CANCEL, order_id="ord_001")
        assert step.is_destructive is False

    def test_liquidate_step(self) -> None:
        step = TransitionStep("AAPL", OrderAction.LIQUIDATE, quantity=100)
        assert step.is_destructive is True

    def test_rejects_invalid_side(self) -> None:
        with pytest.raises(ValueError, match="side"):
            TransitionStep("AAPL", OrderAction.HOLD, side="both")


# ── TransitionHandler — NO_OP ───────────────────────────────────────────────


class TestTransitionHandlerNoOp:
    def test_no_positions_no_orders(self, handler, no_op_transition) -> None:
        plan = handler.build_plan(no_op_transition, [], [])
        assert plan.is_empty is True
        assert plan.total_positions_affected == 0
        assert plan.total_orders_cancelled == 0

    def test_orders_cancelled_even_on_no_op(self, handler, no_op_transition, open_orders) -> None:
        """Même sur NO_OP, les ordres ouverts sont annulés (sécurité)."""
        plan = handler.build_plan(no_op_transition, [], open_orders)
        # Tous les ordres sont annulés
        assert plan.total_orders_cancelled == len(open_orders)

    def test_positions_untouched_on_no_op(self, handler, no_op_transition, long_positions) -> None:
        plan = handler.build_plan(no_op_transition, long_positions, [])
        # Pas d'actions destructrices sur les positions
        assert plan.total_positions_affected == 0


# ── TransitionHandler — LIQUIDATE_LONGS ─────────────────────────────────────


class TestTransitionHandlerLiquidateLongs:
    def test_longs_liquidated_shorts_preserved(
        self, handler, escalation_transition, mixed_positions,
    ) -> None:
        plan = handler.build_plan(escalation_transition, mixed_positions, [])
        # Longs liquidés, shorts préservés
        liquidated_symbols = [
            s.symbol for s in plan.steps if s.action == OrderAction.LIQUIDATE
        ]
        assert "AAPL" in liquidated_symbols
        assert "TSLA" not in liquidated_symbols

    def test_short_positions_untouched(
        self, handler, escalation_transition, short_positions,
    ) -> None:
        plan = handler.build_plan(escalation_transition, short_positions, [])
        # Aucun short liquidé
        assert plan.total_positions_affected == 0


# ── TransitionHandler — LIQUIDATE_ALL ───────────────────────────────────────


class TestTransitionHandlerLiquidateAll:
    def test_all_positions_liquidated(
        self, handler, liquidation_transition, mixed_positions,
    ) -> None:
        plan = handler.build_plan(liquidation_transition, mixed_positions, [])
        assert plan.total_positions_affected == len(mixed_positions)

    def test_shorts_liquidated_before_longs(
        self, handler, liquidation_transition, mixed_positions,
    ) -> None:
        plan = handler.build_plan(liquidation_transition, mixed_positions, [])
        liquidate_steps = [s for s in plan.steps if s.action == OrderAction.LIQUIDATE]
        # Shorts (TSLA) avant longs (AAPL)
        assert liquidate_steps[0].symbol == "TSLA"
        assert liquidate_steps[1].symbol == "AAPL"


# ── TransitionHandler — REDUCE ──────────────────────────────────────────────


class TestTransitionHandlerReduce:
    def test_positions_reduced_by_half(self, handler, long_positions) -> None:
        transition = RegimeTransition(
            from_state=RegimeState.NORMAL,
            to_state=RegimeState.WARNING,
            action=TransitionAction.REDUCE,
            reason="soft_signals",
        )
        plan = handler.build_plan(transition, long_positions, [])
        reduce_steps = [s for s in plan.steps if s.action == OrderAction.REDUCE]
        assert len(reduce_steps) == len(long_positions)
        for step, pos in zip(reduce_steps, long_positions):
            assert step.quantity == pos.quantity * 0.5


# ── TransitionHandler — CLOSE_ONLY / CASH_ONLY ──────────────────────────────


class TestTransitionHandlerCloseOnly:
    def test_positions_preserved_in_close_only(self, handler, long_positions) -> None:
        transition = RegimeTransition(
            from_state=RegimeState.NORMAL,
            to_state=RegimeState.CLOSE_ONLY,
            action=TransitionAction.CLOSE_ONLY,
            reason="earnings_blackout",
        )
        plan = handler.build_plan(transition, long_positions, [])
        # Aucune liquidation, juste annulation d'ordres (s'il y en avait)
        assert plan.total_positions_affected == 0

    def test_positions_preserved_in_cash_only(self, handler, long_positions) -> None:
        transition = RegimeTransition(
            from_state=RegimeState.CLOSE_ONLY,
            to_state=RegimeState.CASH_ONLY,
            action=TransitionAction.CASH_ONLY,
            reason="market_crash",
        )
        plan = handler.build_plan(transition, long_positions, [])
        assert plan.total_positions_affected == 0


# ── TransitionHandler — partial fills ───────────────────────────────────────


class TestTransitionHandlerPartialFills:
    def test_partial_fill_orders_are_cancelled(
        self, handler, escalation_transition,
    ) -> None:
        orders = [
            OpenOrder("ord_001", "AAPL", "buy", "limit", 100, filled_quantity=40),
        ]
        plan = handler.build_plan(escalation_transition, [], orders)
        # L'ordre partiellement filled est annulé
        assert plan.total_orders_cancelled == 1
        # Le partial fill est audité
        assert any("PARTIAL_FILL" in log for log in plan.audit_log)

    def test_partial_fill_positions_included_in_liquidation(
        self, handler, escalation_transition,
    ) -> None:
        positions = [
            OpenPosition("AAPL", "long", 100, 150.0, has_partial_fill=True, filled_quantity=60),
        ]
        plan = handler.build_plan(escalation_transition, positions, [])
        # La position avec partial fill est liquidée comme les autres
        assert plan.total_positions_affected == 1


# ── TransitionHandler — audit ───────────────────────────────────────────────


class TestTransitionHandlerAudit:
    def test_audit_log_contains_transition_details(
        self, handler, escalation_transition, long_positions, open_orders,
    ) -> None:
        plan = handler.build_plan(escalation_transition, long_positions, open_orders)
        assert len(plan.audit_log) > 0
        # L'audit log contient les infos de transition
        full_log = " ".join(plan.audit_log)
        assert "TRANSITION" in full_log
        assert escalation_transition.reason in full_log

    def test_no_op_plan(self, handler, no_op_transition) -> None:
        plan = TransitionHandler.no_op_plan(no_op_transition)
        assert plan.is_empty is True
        assert len(plan.audit_log) > 0


# ── build_transition_plan (helper) ──────────────────────────────────────────


class TestBuildTransitionPlan:
    def test_helper_with_no_args(self, no_op_transition) -> None:
        plan = build_transition_plan(no_op_transition)
        assert plan.is_empty is True

    def test_helper_with_positions(self, escalation_transition, long_positions) -> None:
        plan = build_transition_plan(escalation_transition, long_positions)
        assert plan.total_positions_affected == len(long_positions)


# ── Parité backtest/live — plans déterministes ──────────────────────────────


class TestTransitionHandlerParity:
    """Le handler est pur : mêmes entrées → mêmes sorties."""

    def test_deterministic_plan(
        self, handler, escalation_transition, long_positions, open_orders,
    ) -> None:
        plan1 = handler.build_plan(escalation_transition, long_positions, open_orders)
        plan2 = handler.build_plan(escalation_transition, long_positions, open_orders)
        assert plan1 == plan2

    def test_plan_is_immutable(self, handler, no_op_transition) -> None:
        plan = handler.build_plan(no_op_transition, [], [])
        with pytest.raises(Exception):
            plan.total_positions_affected = 99  # type: ignore[misc]
