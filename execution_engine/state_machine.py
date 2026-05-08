"""Order lifecycle state machine + execution phase state machine (Phase 5.2.a/b)."""
from __future__ import annotations

from dataclasses import dataclass, field

from execution_engine.models import OrderStatus

# Transitions autorisées : {old_status: {new_status, ...}}
_TRANSITIONS: dict[str, frozenset[str]] = {
    OrderStatus.NEW: frozenset({OrderStatus.SUBMITTED}),
    OrderStatus.SUBMITTED: frozenset({
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.FAILED,
        OrderStatus.EXPIRED,
    }),
    OrderStatus.PARTIALLY_FILLED: frozenset({
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.FAILED,
    }),
}

# Mapping statuts Alpaca → statuts internes
_ALPACA_MAP: dict[str, str] = {
    "new": OrderStatus.NEW,
    "held": OrderStatus.HELD,
    "accepted": OrderStatus.SUBMITTED,
    "pending_new": OrderStatus.SUBMITTED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED,
    "pending_cancel": OrderStatus.SUBMITTED,
    "pending_replace": OrderStatus.SUBMITTED,
}


def is_terminal(status: str) -> bool:
    return status in OrderStatus.TERMINAL


def can_transition(old: str, new: str) -> bool:
    if is_terminal(old):
        return False
    allowed = _TRANSITIONS.get(old)
    if allowed is None:
        return False
    return new in allowed


def require_transition(old: str, new: str) -> None:
    if not can_transition(old, new):
        raise ValueError(f"Transition illégale : {old} → {new}")


def map_alpaca_status(alpaca_status: str) -> str:
    return _ALPACA_MAP.get(alpaca_status.lower(), OrderStatus.FAILED)


# ---------------------------------------------------------------------------
# Phase 5.2.a / 5.2.b — Execution-level state machine.
# ---------------------------------------------------------------------------


class ExecutionPhase:
    """Phases nommées du run d'exécution (cf. ``executor.execute_run``).

    Versionné : ajouter une phase = bump ``schema_version`` du run_summary.
    """

    INIT = "INIT"
    PRECHECK = "PRECHECK"
    ACCOUNT_CONSTRAINTS = "ACCOUNT_CONSTRAINTS"
    CORPORATE_ACTIONS_CHECK = "CORPORATE_ACTIONS_CHECK"
    BUILD_INTENTS = "BUILD_INTENTS"
    SUBMIT = "SUBMIT"
    POLL = "POLL"
    CHILDREN = "CHILDREN"
    BROKER_SYNC = "BROKER_SYNC"
    RECONCILE = "RECONCILE"
    TCA = "TCA"
    FINALIZE = "FINALIZE"
    KILL_SWITCH = "KILL_SWITCH"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"

    ALL: frozenset[str] = frozenset({
        INIT, PRECHECK, ACCOUNT_CONSTRAINTS, CORPORATE_ACTIONS_CHECK,
        BUILD_INTENTS, SUBMIT, POLL, CHILDREN, BROKER_SYNC, RECONCILE,
        TCA, FINALIZE, KILL_SWITCH, COMPLETED, ABORTED, FAILED,
    })


def _terminal_phases() -> frozenset[str]:
    return frozenset({ExecutionPhase.COMPLETED, ExecutionPhase.ABORTED, ExecutionPhase.FAILED})


# Transitions : depuis chaque phase non-terminale, vers où peut-on aller ?
_PHASE_TRANSITIONS: dict[str, frozenset[str]] = {
    ExecutionPhase.INIT: frozenset({
        ExecutionPhase.PRECHECK,
        ExecutionPhase.ABORTED,
        ExecutionPhase.FAILED,
        ExecutionPhase.KILL_SWITCH,
    }),
    ExecutionPhase.PRECHECK: frozenset({
        ExecutionPhase.ACCOUNT_CONSTRAINTS,
        ExecutionPhase.ABORTED,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.ACCOUNT_CONSTRAINTS: frozenset({
        ExecutionPhase.CORPORATE_ACTIONS_CHECK,
        ExecutionPhase.BUILD_INTENTS,
        ExecutionPhase.ABORTED,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.CORPORATE_ACTIONS_CHECK: frozenset({
        ExecutionPhase.BUILD_INTENTS,
        ExecutionPhase.ABORTED,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.BUILD_INTENTS: frozenset({
        ExecutionPhase.SUBMIT,
        ExecutionPhase.FINALIZE,
        ExecutionPhase.ABORTED,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.SUBMIT: frozenset({
        ExecutionPhase.POLL,
        ExecutionPhase.BROKER_SYNC,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.POLL: frozenset({
        ExecutionPhase.CHILDREN,
        ExecutionPhase.BROKER_SYNC,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.CHILDREN: frozenset({
        ExecutionPhase.BROKER_SYNC,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.BROKER_SYNC: frozenset({
        ExecutionPhase.RECONCILE,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.RECONCILE: frozenset({
        ExecutionPhase.TCA,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.TCA: frozenset({
        ExecutionPhase.FINALIZE,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.FINALIZE: frozenset({
        ExecutionPhase.COMPLETED,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.KILL_SWITCH: frozenset({
        ExecutionPhase.COMPLETED,
        ExecutionPhase.FAILED,
    }),
}


def can_transition_phase(old: str, new: str) -> bool:
    if old in _terminal_phases():
        return False
    if new not in ExecutionPhase.ALL:
        return False
    allowed = _PHASE_TRANSITIONS.get(old)
    if allowed is None:
        return False
    return new in allowed


def require_transition_phase(old: str, new: str, *, strict: bool = False) -> None:
    """Phase 5.2.b — Valide une transition de phase.

    En mode non-strict (défaut), une transition invalide log un WARNING mais
    ne lève pas (feature flag ``strict_phase_transitions`` documenté plan §4).
    """
    if can_transition_phase(old, new):
        return
    msg = f"Transition de phase illégale : {old} → {new}"
    if strict:
        raise ValueError(msg)
    import logging

    logging.getLogger(__name__).warning(msg)


@dataclass(slots=True)
class PhaseTracker:
    """Phase 5.2.a/b — Trace l'historique des phases d'un run.

    Utilisé par ``ProductionExecutor.execute_run`` pour exposer
    ``last_phase`` dans le ``run_summary``.
    """

    current: str = ExecutionPhase.INIT
    history: list[str] = field(default_factory=lambda: [ExecutionPhase.INIT])
    strict: bool = False

    def transition(self, new_phase: str) -> None:
        require_transition_phase(self.current, new_phase, strict=self.strict)
        self.current = new_phase
        self.history.append(new_phase)

    def force(self, new_phase: str) -> None:
        """Bypass des transitions (cas exception → FAILED)."""
        self.current = new_phase
        self.history.append(new_phase)

    @property
    def last_phase(self) -> str:
        return self.current



