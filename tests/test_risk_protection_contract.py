"""Tests unitaires — risk_management/protection_contract.py (Sprint Maître 12)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from risk_management.protection_contract import (
    OCOGroup,
    ProtectionContract,
    ProtectionSLA,
    ProtectionState,
    ProtectionStatus,
    build_oco_group,
    check_protection_state,
)


# ── ProtectionStatus ────────────────────────────────────────────────────────


class TestProtectionStatus:
    def test_protected_is_safe(self) -> None:
        assert ProtectionStatus.PROTECTED.is_safe is True
        assert ProtectionStatus.PARTIALLY_PROTECTED.is_safe is True

    def test_unprotected_not_safe(self) -> None:
        assert ProtectionStatus.UNPROTECTED.is_safe is False

    def test_requires_action(self) -> None:
        assert ProtectionStatus.UNPROTECTED.requires_action is True
        assert ProtectionStatus.PENDING_ARM.requires_action is True
        assert ProtectionStatus.PROTECTED.requires_action is False


# ── ProtectionSLA ───────────────────────────────────────────────────────────


class TestProtectionSLA:
    def test_arm_breach(self) -> None:
        sla = ProtectionSLA(arm_timeout_seconds=30)
        assert sla.is_breached(ProtectionStatus.PENDING_ARM, 35) is True
        assert sla.is_breached(ProtectionStatus.PENDING_ARM, 20) is False

    def test_unprotected_not_breached_when_none(self) -> None:
        sla = ProtectionSLA()
        assert sla.is_breached(ProtectionStatus.PROTECTED, 100) is False  # Pas de seuil pour PROTECTED


# ── OCOGroup ────────────────────────────────────────────────────────────────


class TestOCOGroup:
    def test_complete(self) -> None:
        oco = OCOGroup(
            oco_id="oco_001", symbol="AAPL", side="long",
            parent_intent_id="int_001",
            stop_order_id="stop_001", tp_order_id="tp_001",
            protected_quantity=100, filled_quantity=100,
        )
        assert oco.is_complete is True
        assert oco.quantity_match is True

    def test_incomplete(self) -> None:
        oco = OCOGroup(
            oco_id="oco_001", symbol="AAPL", side="long",
            parent_intent_id="int_001",
            protected_quantity=100, filled_quantity=50,
        )
        assert oco.is_complete is False
        assert oco.quantity_match is False

    def test_orphan(self) -> None:
        oco = OCOGroup(
            oco_id="oco_001", symbol="AAPL", side="long",
            parent_intent_id="int_001",
            stop_order_id="stop_001",  # stop existe
            entry_order_id=None,  # mais pas d'ordre parent
            protected_quantity=100, filled_quantity=100,
        )
        assert oco.is_orphan is True

    def test_to_dict(self) -> None:
        oco = OCOGroup(
            oco_id="oco_001", symbol="AAPL", side="long",
            parent_intent_id="int_001",
        )
        d = oco.to_dict()
        assert d["oco_id"] == "oco_001"


# ── ProtectionState ─────────────────────────────────────────────────────────


class TestProtectionState:
    def test_default_pending_arm(self) -> None:
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
        )
        assert state.status == ProtectionStatus.PENDING_ARM
        assert state.is_protected is False
        assert state.needs_repair is True

    def test_protected_state(self) -> None:
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            stop_price=145.0, tp_price=160.0,
            status=ProtectionStatus.PROTECTED,
        )
        assert state.is_protected is True
        assert state.needs_repair is False

    def test_to_dict(self) -> None:
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            stop_price=145.0, mae_pct=0.02, mfe_pct=0.05, r_multiple=1.5,
        )
        d = state.to_dict()
        assert d["mae_pct"] == 0.02
        assert d["r_multiple"] == 1.5
        assert d["is_protected"] is False


# ── ProtectionContract.check_state ──────────────────────────────────────────


class TestProtectionContractCheckState:
    def test_valid_state(self) -> None:
        contract = ProtectionContract()
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            stop_price=145.0, status=ProtectionStatus.PROTECTED,
        )
        ok, violations = contract.check_state(state)
        assert ok is True
        assert len(violations) == 0

    def test_stop_wrong_side_long(self) -> None:
        contract = ProtectionContract()
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            stop_price=155.0, status=ProtectionStatus.PROTECTED,
        )
        ok, violations = contract.check_state(state)
        assert ok is False
        assert any("stop_long_mal_place" in v for v in violations)

    def test_stop_wrong_side_short(self) -> None:
        contract = ProtectionContract()
        state = ProtectionState(
            symbol="TSLA", side="short", entry_price=200.0, fill_quantity=50,
            stop_price=190.0, status=ProtectionStatus.PROTECTED,
        )
        ok, violations = contract.check_state(state)
        assert ok is False
        assert any("stop_short_mal_place" in v for v in violations)

    def test_unprotected_violation(self) -> None:
        contract = ProtectionContract()
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            status=ProtectionStatus.UNPROTECTED,
        )
        ok, violations = contract.check_state(state)
        assert ok is False
        assert any("non_protegee" in v for v in violations)

    def test_oco_quantity_mismatch(self) -> None:
        contract = ProtectionContract()
        oco = OCOGroup(
            oco_id="oco_001", symbol="AAPL", side="long",
            parent_intent_id="int_001", stop_order_id="stop_001",
            protected_quantity=80, filled_quantity=100,  # Mismatch
        )
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            stop_price=145.0, status=ProtectionStatus.PROTECTED,
            oco_group=oco,
        )
        ok, violations = contract.check_state(state)
        assert ok is False
        assert any("quantity_mismatch" in v for v in violations)

    def test_sla_breach(self) -> None:
        contract = ProtectionContract()
        old_time = datetime.now() - timedelta(seconds=120)  # 2 min ago
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            status=ProtectionStatus.UNPROTECTED,
            last_action_at=old_time,
        )
        ok, violations = contract.check_state(state)
        assert ok is False
        assert any("sla_breached" in v for v in violations)


# ── ProtectionContract.should_force_close ───────────────────────────────────


class TestProtectionContractForceClose:
    def test_no_force_close_when_protected(self) -> None:
        contract = ProtectionContract()
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            stop_price=145.0, status=ProtectionStatus.PROTECTED,
        )
        should, reason = contract.should_force_close(state, 10.0)
        assert should is False

    def test_force_close_after_timeout(self) -> None:
        contract = ProtectionContract()
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            status=ProtectionStatus.UNPROTECTED,
        )
        should, reason = contract.should_force_close(state, 200.0)  # > 120s timeout
        assert should is True

    def test_force_close_wrong_side_stop(self) -> None:
        contract = ProtectionContract()
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            stop_price=155.0,  # Stop au-dessus (invalide)
            status=ProtectionStatus.PROTECTED,
        )
        should, reason = contract.should_force_close(state, 10.0)
        assert should is True


# ── ProtectionContract.resolve_conflicts ────────────────────────────────────


class TestProtectionContractResolveConflicts:
    def test_find_conflicting_orders(self) -> None:
        contract = ProtectionContract()
        orders = [
            {"order_id": "ord_001", "symbol": "AAPL"},
            {"order_id": "ord_002", "symbol": "MSFT"},
        ]
        to_cancel = contract.resolve_conflicts(orders, "AAPL")
        assert "ord_001" in to_cancel
        assert "ord_002" not in to_cancel

    def test_no_conflicts(self) -> None:
        contract = ProtectionContract()
        orders = [{"order_id": "ord_001", "symbol": "MSFT"}]
        to_cancel = contract.resolve_conflicts(orders, "AAPL")
        assert len(to_cancel) == 0


# ── Helpers ─────────────────────────────────────────────────────────────────


class TestCheckProtectionState:
    def test_helper(self) -> None:
        state = ProtectionState(
            symbol="AAPL", side="long", entry_price=150.0, fill_quantity=100,
            stop_price=145.0, status=ProtectionStatus.PROTECTED,
        )
        ok, violations = check_protection_state(state)
        assert ok is True


class TestBuildOCOGroup:
    def test_helper(self) -> None:
        oco = build_oco_group(
            "oco_001", "AAPL", "long", "int_001", 100,
            stop_order_id="stop_001", tp_order_id="tp_001",
        )
        assert oco.is_complete is True
        assert oco.quantity_match is True
