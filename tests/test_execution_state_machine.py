"""Tests Phase 5.2.a/5.2.b — execution state machine + phase tracker."""
from __future__ import annotations

import pytest

from execution_engine.state_machine import (
    ExecutionPhase,
    PhaseTracker,
    can_transition_phase,
    require_transition_phase,
)


def test_execution_phase_enum_values_stable() -> None:
    expected = {
        "INIT", "PRECHECK", "ACCOUNT_CONSTRAINTS", "CORPORATE_ACTIONS_CHECK",
        "BUILD_INTENTS", "SUBMIT", "POLL", "CHILDREN", "BROKER_SYNC",
        "RECONCILE", "TCA", "FINALIZE", "KILL_SWITCH",
        "COMPLETED", "ABORTED", "FAILED",
    }
    assert ExecutionPhase.ALL == frozenset(expected)


def test_init_to_precheck_allowed() -> None:
    assert can_transition_phase(ExecutionPhase.INIT, ExecutionPhase.PRECHECK)


def test_init_to_submit_forbidden() -> None:
    assert not can_transition_phase(ExecutionPhase.INIT, ExecutionPhase.SUBMIT)


def test_terminal_phase_blocks_further_transitions() -> None:
    assert not can_transition_phase(ExecutionPhase.COMPLETED, ExecutionPhase.PRECHECK)
    assert not can_transition_phase(ExecutionPhase.ABORTED, ExecutionPhase.PRECHECK)
    assert not can_transition_phase(ExecutionPhase.FAILED, ExecutionPhase.PRECHECK)


def test_require_transition_phase_non_strict_does_not_raise() -> None:
    require_transition_phase(ExecutionPhase.INIT, ExecutionPhase.SUBMIT)


def test_require_transition_phase_strict_raises() -> None:
    with pytest.raises(ValueError):
        require_transition_phase(ExecutionPhase.INIT, ExecutionPhase.SUBMIT, strict=True)


def test_phase_tracker_records_history() -> None:
    tr = PhaseTracker()
    tr.transition(ExecutionPhase.PRECHECK)
    tr.transition(ExecutionPhase.ACCOUNT_CONSTRAINTS)
    tr.transition(ExecutionPhase.BUILD_INTENTS)
    assert tr.last_phase == ExecutionPhase.BUILD_INTENTS
    assert tr.history == [
        ExecutionPhase.INIT,
        ExecutionPhase.PRECHECK,
        ExecutionPhase.ACCOUNT_CONSTRAINTS,
        ExecutionPhase.BUILD_INTENTS,
    ]


def test_phase_tracker_force_bypasses_validation() -> None:
    tr = PhaseTracker()
    tr.force(ExecutionPhase.FAILED)
    assert tr.last_phase == ExecutionPhase.FAILED
    assert tr.history[-1] == ExecutionPhase.FAILED


def test_phase_tracker_strict_raises_on_invalid_transition() -> None:
    tr = PhaseTracker(strict=True)
    with pytest.raises(ValueError):
        tr.transition(ExecutionPhase.SUBMIT)


def test_full_happy_path_transitions() -> None:
    tr = PhaseTracker(strict=True)
    happy_path = [
        ExecutionPhase.PRECHECK,
        ExecutionPhase.ACCOUNT_CONSTRAINTS,
        ExecutionPhase.CORPORATE_ACTIONS_CHECK,
        ExecutionPhase.BUILD_INTENTS,
        ExecutionPhase.SUBMIT,
        ExecutionPhase.POLL,
        ExecutionPhase.CHILDREN,
        ExecutionPhase.BROKER_SYNC,
        ExecutionPhase.RECONCILE,
        ExecutionPhase.TCA,
        ExecutionPhase.FINALIZE,
        ExecutionPhase.COMPLETED,
    ]
    for phase in happy_path:
        tr.transition(phase)
    assert tr.last_phase == ExecutionPhase.COMPLETED

