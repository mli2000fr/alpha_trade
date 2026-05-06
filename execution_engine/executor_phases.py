"""Phase F / S23.5 — Scaffold pour le découpage de ``ProductionExecutor.execute_run``.

État : **scaffold livré, branchement à faire dans une PR dédiée**
(refacto à risque qui doit s'accompagner d'une suite AppTest exhaustive
+ relecture diff ligne-à-ligne — voir §8 du `28_plan_10_10_2.md`).

Architecture cible (4 phases pures, ~150 l. chacune) :

1. :func:`phase_init_and_preflight` — Phases 1 + 2 + 2b (init/lock,
   load targets, account constraints, corporate actions check).
2. :func:`phase_build_and_submit` — Phases 3 + 4 (build intents, dedupe,
   submit entries avec retry/throttle).
3. :func:`phase_poll_and_children` — Phases 5 + 6 (poll fills, submit
   children synthetic bracket, broker state sync).
4. :func:`phase_reconcile_and_finalize` — Phases 8 + 9 + 10 (reconciliation,
   TCA, finalize).

Chaque phase prend un :class:`PhaseContext` partagé et retourne un
:class:`PhaseOutcome` indiquant si le run doit continuer ou aborter.

Branchement futur (S23.5 PR dédiée) :
    ``ProductionExecutor.execute_run`` devient un thin orchestrator
    (~80 l.) qui instancie le contexte, appelle les 4 phases en séquence,
    et factorise le try/except/finally global (release lock, persist
    events).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class PhaseStatus(str, Enum):
    CONTINUE = "CONTINUE"
    ABORT = "ABORT"
    FAIL = "FAIL"


@dataclass
class PhaseOutcome:
    """Résultat d'une phase : indique si l'orchestrateur doit continuer."""
    status: PhaseStatus = PhaseStatus.CONTINUE
    reason: str | None = None


@dataclass
class PhaseContext:
    """État partagé entre les 4 phases.

    Attributs minimums attendus par le découpage S23.5. Les phases ne
    doivent JAMAIS muter le ``cfg`` ; elles peuvent muter ``metrics``,
    ``events``, ``fills``, ``submitted_orders``, ``account_state``.
    """
    # Identifiants
    exec_run_id: str = ""
    risk_run_id: str | None = None
    trade_date: date | None = None
    account_id: str | None = None

    # Dépendances injectées
    cfg: Any = None
    repo: Any = None
    broker: Any = None
    oco: Any = None
    circuit_breaker: Any = None
    progress_callback: Any = None

    # État mutable inter-phases
    metrics: dict[str, Any] = field(default_factory=dict)
    events: list[Any] = field(default_factory=list)
    fills: list[Any] = field(default_factory=list)
    targets: list[Any] = field(default_factory=list)
    target_by_symbol: dict[str, Any] = field(default_factory=dict)
    submitted_orders: dict[str, tuple] = field(default_factory=dict)
    account_state: Any = None
    consecutive_failures: int = 0
    lock_acquired: bool = False


# ---------------------------------------------------------------------------
# Phase 1 — Init + Pre-flight + Corporate Actions check
# ---------------------------------------------------------------------------

def phase_init_and_preflight(executor: Any, ctx: PhaseContext) -> PhaseOutcome:
    """Phases 1 + 2 + 2b extraites de ``ProductionExecutor.execute_run``.

    À implémenter dans la PR S23.5 dédiée. Pour l'instant, lève
    ``NotImplementedError`` afin d'éviter toute substitution silencieuse
    en prod.
    """
    raise NotImplementedError(
        "phase_init_and_preflight — branchement S23.5 à faire dans PR dédiée"
    )


# ---------------------------------------------------------------------------
# Phase 2 — Build intents + Submit entries
# ---------------------------------------------------------------------------

def phase_build_and_submit(executor: Any, ctx: PhaseContext) -> PhaseOutcome:
    raise NotImplementedError(
        "phase_build_and_submit — branchement S23.5 à faire dans PR dédiée"
    )


# ---------------------------------------------------------------------------
# Phase 3 — Poll fills + Children + Broker state sync
# ---------------------------------------------------------------------------

def phase_poll_and_children(executor: Any, ctx: PhaseContext) -> PhaseOutcome:
    raise NotImplementedError(
        "phase_poll_and_children — branchement S23.5 à faire dans PR dédiée"
    )


# ---------------------------------------------------------------------------
# Phase 4 — Reconciliation + TCA + Finalize
# ---------------------------------------------------------------------------

def phase_reconcile_and_finalize(executor: Any, ctx: PhaseContext) -> PhaseOutcome:
    raise NotImplementedError(
        "phase_reconcile_and_finalize — branchement S23.5 à faire dans PR dédiée"
    )


__all__ = [
    "PhaseContext",
    "PhaseOutcome",
    "PhaseStatus",
    "phase_init_and_preflight",
    "phase_build_and_submit",
    "phase_poll_and_children",
    "phase_reconcile_and_finalize",
]

