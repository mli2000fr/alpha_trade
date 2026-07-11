"""Tests unitaires — risk_management/regime_state_machine.py (Sprint Maître 9).

Vérifie la state machine pure : états, transitions, hystérésis, actions.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from risk_management.regime_state_machine import (
    RegimeState,
    RegimeStateMachine,
    RegimeTransition,
    TransitionAction,
    compute_regime_transition,
)
from service.market.models import MarketRegimeSnapshot


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sm() -> RegimeStateMachine:
    return RegimeStateMachine()


@pytest.fixture
def normal_snapshot() -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        trade_date=date(2026, 7, 1),
        mode="normal",
        risk_multiplier=1.0,
        allow_new_entries=True,
        allowed_long_entries=True,
        allowed_short_entries=False,
        reasons=("all_clear",),
    )


@pytest.fixture
def defensive_snapshot() -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        trade_date=date(2026, 7, 1),
        mode="capital_preservation",
        risk_multiplier=0.3,
        allow_new_entries=False,
        allowed_long_entries=False,
        allowed_short_entries=True,
        reasons=("vix_spike",),
        hard_triggered=True,
    )


# ── RegimeState ─────────────────────────────────────────────────────────────


class TestRegimeState:
    def test_normal_is_not_defensive(self) -> None:
        assert RegimeState.NORMAL.is_defensive is False

    def test_capital_preservation_is_defensive(self) -> None:
        assert RegimeState.CAPITAL_PRESERVATION.is_defensive is True

    def test_normal_allows_long(self) -> None:
        assert RegimeState.NORMAL.allows_long is True
        assert RegimeState.NORMAL.allows_short is True

    def test_capital_preservation_allows_short_only(self) -> None:
        assert RegimeState.CAPITAL_PRESERVATION.allows_long is False
        assert RegimeState.CAPITAL_PRESERVATION.allows_short is True

    def test_close_only_blocks_entries(self) -> None:
        assert RegimeState.CLOSE_ONLY.is_blocking_entries is True
        assert RegimeState.CASH_ONLY.is_blocking_entries is True

    def test_normal_does_not_block_entries(self) -> None:
        assert RegimeState.NORMAL.is_blocking_entries is False

    def test_from_regime_mode_normal(self) -> None:
        assert RegimeState.from_regime_mode("normal") == RegimeState.NORMAL

    def test_from_regime_mode_defensive(self) -> None:
        assert RegimeState.from_regime_mode("capital_preservation") == RegimeState.CAPITAL_PRESERVATION

    def test_from_regime_mode_unknown_defaults_to_normal(self) -> None:
        assert RegimeState.from_regime_mode("unknown_mode") == RegimeState.NORMAL

    def test_to_regime_mode(self) -> None:
        assert RegimeState.CAPITAL_PRESERVATION.to_regime_mode() == "capital_preservation"
        assert RegimeState.NORMAL.to_regime_mode() == "normal"

    def test_warning_converts_to_normal_for_service_market(self) -> None:
        # WARNING est interne à risk_management
        assert RegimeState.WARNING.to_regime_mode() == "normal"


# ── TransitionAction ────────────────────────────────────────────────────────


class TestTransitionAction:
    def test_liquidate_is_destructive(self) -> None:
        assert TransitionAction.LIQUIDATE_ALL.is_destructive is True
        assert TransitionAction.LIQUIDATE_LONGS.is_destructive is True

    def test_no_op_not_destructive(self) -> None:
        assert TransitionAction.NO_OP.is_destructive is False

    def test_block_entry_blocks(self) -> None:
        assert TransitionAction.BLOCK_ENTRY.blocks_new_entries is True
        assert TransitionAction.CLOSE_ONLY.blocks_new_entries is True

    def test_no_op_does_not_block(self) -> None:
        assert TransitionAction.NO_OP.blocks_new_entries is False


# ── RegimeTransition ────────────────────────────────────────────────────────


class TestRegimeTransition:
    def test_same_state_no_transition(self) -> None:
        t = RegimeTransition(
            from_state=RegimeState.NORMAL,
            to_state=RegimeState.NORMAL,
            action=TransitionAction.NO_OP,
        )
        assert t.is_transition is False

    def test_different_state_is_transition(self) -> None:
        t = RegimeTransition(
            from_state=RegimeState.NORMAL,
            to_state=RegimeState.CAPITAL_PRESERVATION,
            action=TransitionAction.LIQUIDATE_LONGS,
        )
        assert t.is_transition is True

    def test_escalation_normal_to_defensive(self) -> None:
        t = RegimeTransition(
            from_state=RegimeState.NORMAL,
            to_state=RegimeState.CAPITAL_PRESERVATION,
            action=TransitionAction.LIQUIDATE_LONGS,
        )
        assert t.is_escalation is True
        assert t.is_deescalation is False

    def test_deescalation_defensive_to_normal(self) -> None:
        t = RegimeTransition(
            from_state=RegimeState.CAPITAL_PRESERVATION,
            to_state=RegimeState.RECOVERY,
            action=TransitionAction.NO_OP,
        )
        assert t.is_deescalation is True

    def test_to_dict(self) -> None:
        t = RegimeTransition(
            from_state=RegimeState.NORMAL,
            to_state=RegimeState.CAPITAL_PRESERVATION,
            action=TransitionAction.LIQUIDATE_LONGS,
            reason="vix_spike",
            hysteresis_applied=False,
        )
        d = t.to_dict()
        assert d["from_state"] == "normal"
        assert d["to_state"] == "capital_preservation"
        assert d["is_escalation"] is True


# ── RegimeStateMachine — transitions de base ────────────────────────────────


class TestRegimeStateMachineBasic:
    def test_no_transition_same_state(self, sm: RegimeStateMachine) -> None:
        t = sm.evaluate_transition(
            RegimeState.NORMAL, RegimeState.NORMAL,
            days_in_current_mode=10,
        )
        assert t.action == TransitionAction.NO_OP
        assert t.is_transition is False

    def test_hard_trigger_immediate_escalation(self, sm: RegimeStateMachine) -> None:
        """Hard trigger → escalade immédiate sans hystérésis."""
        t = sm.evaluate_transition(
            RegimeState.NORMAL, RegimeState.CAPITAL_PRESERVATION,
            hard_triggered=True, hard_trigger_immediate=True,
        )
        assert t.to_state == RegimeState.CAPITAL_PRESERVATION
        assert t.action == TransitionAction.LIQUIDATE_LONGS
        assert t.hysteresis_applied is False  # Immédiat

    def test_hard_trigger_no_immediate_stays(self, sm: RegimeStateMachine) -> None:
        """Hard trigger sans immediate → attend confirmation."""
        t = sm.evaluate_transition(
            RegimeState.NORMAL, RegimeState.CAPITAL_PRESERVATION,
            hard_triggered=True, hard_trigger_immediate=False,
            soft_entry_streak=0,
        )
        # Sans soft_entry_streak suffisant, on reste en normal
        assert t.to_state == RegimeState.NORMAL


# ── RegimeStateMachine — hystérésis ─────────────────────────────────────────


class TestRegimeStateMachineHysteresis:
    def test_min_hold_prevents_early_exit(self, sm: RegimeStateMachine) -> None:
        """Min hold non atteint → pas de sortie du défensif."""
        sm.min_hold_days_defensive = 5
        t = sm.evaluate_transition(
            RegimeState.CAPITAL_PRESERVATION, RegimeState.NORMAL,
            days_in_current_mode=2,  # Seulement 2 jours
            soft_exit_streak=10, hard_calm_streak=10,
        )
        assert t.to_state == RegimeState.CAPITAL_PRESERVATION  # Reste bloqué
        assert t.hysteresis_applied is True
        assert t.min_hold_remaining == 3

    def test_min_hold_reached_allows_exit(self, sm: RegimeStateMachine) -> None:
        """Min hold atteint + streaks OK → sortie autorisée."""
        sm.min_hold_days_defensive = 5
        sm.exit_confirm_days = 3
        t = sm.evaluate_transition(
            RegimeState.CAPITAL_PRESERVATION, RegimeState.NORMAL,
            days_in_current_mode=6,
            soft_exit_streak=5, hard_calm_streak=5,
        )
        assert t.to_state == RegimeState.RECOVERY
        assert t.hysteresis_applied is True

    def test_soft_entry_needs_confirm_days(self, sm: RegimeStateMachine) -> None:
        """Soft entry → besoin de jours de confirmation."""
        sm.enter_confirm_days = 3
        t = sm.evaluate_transition(
            RegimeState.NORMAL, RegimeState.CAPITAL_PRESERVATION,
            soft_entry_streak=1,  # Insuffisant
            hard_triggered=False,
        )
        assert t.to_state == RegimeState.NORMAL  # Pas encore entré
        assert t.hysteresis_applied is True

    def test_soft_entry_confirmed(self, sm: RegimeStateMachine) -> None:
        """Soft entry → streak suffisant → entrée confirmée."""
        sm.enter_confirm_days = 3
        t = sm.evaluate_transition(
            RegimeState.NORMAL, RegimeState.CAPITAL_PRESERVATION,
            soft_entry_streak=5,
            hard_triggered=False,
        )
        assert t.to_state == RegimeState.CAPITAL_PRESERVATION
        assert t.hysteresis_applied is True

    def test_flip_flop_prevented(self, sm: RegimeStateMachine) -> None:
        """Un flip-flop NORMAL → DEFENSIF → NORMAL en 2 jours est bloqué."""
        sm.min_hold_days_defensive = 5
        # Jour 1 : entrée en défensif
        t1 = sm.evaluate_transition(
            RegimeState.NORMAL, RegimeState.CAPITAL_PRESERVATION,
            hard_triggered=True, hard_trigger_immediate=True,
        )
        assert t1.to_state == RegimeState.CAPITAL_PRESERVATION

        # Jour 2 : tentative de sortie → bloquée par min_hold
        t2 = sm.evaluate_transition(
            RegimeState.CAPITAL_PRESERVATION, RegimeState.NORMAL,
            days_in_current_mode=1,
            soft_exit_streak=10, hard_calm_streak=10,
        )
        assert t2.to_state == RegimeState.CAPITAL_PRESERVATION  # Reste bloqué


# ── RegimeStateMachine — evaluate_from_snapshot ─────────────────────────────


class TestRegimeStateMachineFromSnapshot:
    def test_normal_snapshot_no_transition(self, sm: RegimeStateMachine) -> None:
        snap = MarketRegimeSnapshot(
            trade_date=date(2026, 7, 1),
            mode="normal",
            reasons=("all_clear",),
        )
        t = sm.evaluate_from_snapshot(RegimeState.NORMAL, snap)
        assert t.action == TransitionAction.NO_OP
        assert t.is_transition is False

    def test_defensive_snapshot_with_hard_trigger(self, sm: RegimeStateMachine) -> None:
        snap = MarketRegimeSnapshot(
            trade_date=date(2026, 7, 1),
            mode="capital_preservation",
            hard_triggered=True,
            reasons=("vix_spike",),
        )
        t = sm.evaluate_from_snapshot(RegimeState.NORMAL, snap)
        assert t.to_state == RegimeState.CAPITAL_PRESERVATION
        assert t.action == TransitionAction.LIQUIDATE_LONGS

    def test_soft_constraints_active_keeps_warning(self, sm: RegimeStateMachine) -> None:
        snap = MarketRegimeSnapshot(
            trade_date=date(2026, 7, 1),
            mode="normal",
            soft_constraints_active=True,
            soft_signal_count=3,
        )
        t = sm.evaluate_from_snapshot(RegimeState.NORMAL, snap)
        assert t.to_state == RegimeState.WARNING

    def test_deescalation_to_recovery(self, sm: RegimeStateMachine) -> None:
        sm.min_hold_days_defensive = 0  # Désactive min_hold pour ce test
        sm.exit_confirm_days = 0  # Désactive la confirmation de sortie
        snap = MarketRegimeSnapshot(
            trade_date=date(2026, 7, 1),
            mode="normal",
            state_age_days=10,
            reasons=("all_clear",),
        )
        t = sm.evaluate_from_snapshot(RegimeState.CAPITAL_PRESERVATION, snap)
        assert t.to_state == RegimeState.RECOVERY
        assert t.risk_multiplier == 0.5  # Ramp-up progressif


# ── compute_regime_transition (helper) ──────────────────────────────────────


class TestComputeRegimeTransition:
    def test_helper_normal_to_normal(self) -> None:
        snap = MarketRegimeSnapshot(
            trade_date=date(2026, 7, 1),
            mode="normal",
        )
        t = compute_regime_transition("normal", snap)
        assert t.action == TransitionAction.NO_OP

    def test_helper_normal_to_defensive(self) -> None:
        snap = MarketRegimeSnapshot(
            trade_date=date(2026, 7, 1),
            mode="capital_preservation",
            hard_triggered=True,
        )
        t = compute_regime_transition("normal", snap)
        assert t.to_state == RegimeState.CAPITAL_PRESERVATION


# ── Parité backtest/live — même entrées → mêmes transitions ─────────────────


class TestRegimeStateMachineParity:
    """La state machine est pure : mêmes entrées → mêmes sorties."""

    def test_deterministic_transition(self, sm: RegimeStateMachine) -> None:
        snap = MarketRegimeSnapshot(
            trade_date=date(2026, 7, 1),
            mode="capital_preservation",
            hard_triggered=True,
            reasons=("vix_spike",),
        )
        t1 = sm.evaluate_from_snapshot(RegimeState.NORMAL, snap)
        t2 = sm.evaluate_from_snapshot(RegimeState.NORMAL, snap)
        assert t1 == t2

    def test_immutable_output(self, sm: RegimeStateMachine) -> None:
        snap = MarketRegimeSnapshot(
            trade_date=date(2026, 7, 1),
            mode="normal",
        )
        t = sm.evaluate_from_snapshot(RegimeState.NORMAL, snap)
        # Le dataclass est frozen, donc immutabilité garantie
        with pytest.raises(Exception):
            t.action = TransitionAction.LIQUIDATE_ALL  # type: ignore[misc]

    def test_maintained_close_only_keeps_entries_blocked(self, sm: RegimeStateMachine) -> None:
        snap = MarketRegimeSnapshot(
            trade_date=date(2026, 7, 1),
            mode="close_only",
        )

        transition = sm.evaluate_from_snapshot(RegimeState.CLOSE_ONLY, snap)

        assert transition.action == TransitionAction.NO_OP
        assert transition.allow_new_entries is False
        assert transition.allow_long is False
        assert transition.allow_short is False


# ── Stress scenarios ────────────────────────────────────────────────────────


class TestRegimeStateMachineStress:
    """Scénarios de stress exigés par la gate de sortie."""

    def test_v_shaped_recovery(self, sm: RegimeStateMachine) -> None:
        """V-shaped recovery : entrée rapide en défensif, sortie après min_hold."""
        sm.min_hold_days_defensive = 5
        sm.exit_confirm_days = 3
        # Jour 1 : crash → hard trigger immédiat
        t1 = sm.evaluate_transition(
            RegimeState.NORMAL, RegimeState.CAPITAL_PRESERVATION,
            hard_triggered=True, hard_trigger_immediate=True,
        )
        assert t1.to_state == RegimeState.CAPITAL_PRESERVATION

        # Jour 6 : recovery → sortie (min_hold atteint, streaks OK)
        t2 = sm.evaluate_transition(
            RegimeState.CAPITAL_PRESERVATION, RegimeState.NORMAL,
            days_in_current_mode=6,
            soft_exit_streak=5, hard_calm_streak=5,
        )
        assert t2.to_state == RegimeState.RECOVERY

    def test_vol_spike_temporary(self, sm: RegimeStateMachine) -> None:
        """Vol spike temporaire → warning, mais pas d'escalade sans confirmation."""
        sm.enter_confirm_days = 3
        t = sm.evaluate_transition(
            RegimeState.NORMAL, RegimeState.CAPITAL_PRESERVATION,
            soft_entry_streak=1,  # 1 seul jour, insuffisant
            hard_triggered=False,
        )
        assert t.to_state == RegimeState.NORMAL  # Pas d'escalade précipitée
        assert t.hysteresis_applied is True

    def test_yield_shock_escalation(self, sm: RegimeStateMachine) -> None:
        """Yield shock → hard trigger → escalade immédiate."""
        t = sm.evaluate_transition(
            RegimeState.NORMAL, RegimeState.CLOSE_ONLY,
            hard_triggered=True, hard_trigger_immediate=True,
        )
        assert t.to_state == RegimeState.CLOSE_ONLY
        assert t.action == TransitionAction.CLOSE_ONLY
        assert t.allow_new_entries is False
