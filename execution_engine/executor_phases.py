"""Phase F / S23.5 + Sprint S26.3 — Découpage de ``ProductionExecutor.execute_run``.

État actuel : **interface fonctionnelle livrée** (S26.3 ; les 4 phases sont
des helpers purs réutilisables). Le branchement effectif dans
``ProductionExecutor.execute_run`` reste piloté par le flag d'opt-in
``EXECUTOR_PHASES_ENABLED`` afin de permettre un déploiement progressif
avec rollback immédiat en cas de régression OCO/bracket constatée.

Architecture cible (4 phases) :

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
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)

# Opt-in : tant que la suite ``test_executor_phases_round_trip`` n'a pas
# certifié l'équivalence comportementale ligne-à-ligne avec
# ``ProductionExecutor.execute_run`` historique, on garde l'orchestrateur
# désactivé par défaut (cf. §6 du `prompt/tod/32_plan.md` — risque élevé).
ENV_TOGGLE = "EXECUTOR_PHASES_ENABLED"


def is_phases_orchestrator_enabled() -> bool:
    """Retourne ``True`` si l'opérateur a explicitement activé l'orchestrateur."""
    return os.environ.get(ENV_TOGGLE, "").strip().lower() in {"1", "true", "yes", "on"}


class PhaseStatus(str, Enum):
    CONTINUE = "CONTINUE"
    ABORT = "ABORT"
    FAIL = "FAIL"


@dataclass
class PhaseOutcome:
    """Résultat d'une phase : indique si l'orchestrateur doit continuer."""
    status: PhaseStatus = PhaseStatus.CONTINUE
    reason: str | None = None

    @property
    def should_continue(self) -> bool:
        return self.status is PhaseStatus.CONTINUE


@dataclass
class PhaseContext:
    """État partagé entre les 4 phases.

    Les phases ne doivent JAMAIS muter le ``cfg`` ; elles peuvent muter
    ``metrics``, ``events``, ``fills``, ``submitted_orders``, ``account_state``.
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

    L'implémentation est **déléguée** à l'executor historique via
    ``executor._phase_init_and_preflight_impl`` (méthode privée à ajouter
    lors du branchement final S26.3.b). Cette indirection préserve
    100 % du comportement OCO/bracket tant que la PR de bascule n'est
    pas mergée et validée par la suite round-trip.
    """
    impl = getattr(executor, "_phase_init_and_preflight_impl", None)
    if impl is None:
        # Mode test/scaffold : la phase est observable mais inerte —
        # garantit que l'orchestrateur ne peut JAMAIS être activé en
        # prod sans branchement explicite (fail-loud).
        return PhaseOutcome(
            status=PhaseStatus.ABORT,
            reason="phase_init_and_preflight: orchestrateur S26.3 non câblé sur cet executor",
        )
    return impl(ctx)


# ---------------------------------------------------------------------------
# Phase 2 — Build intents + Submit entries
# ---------------------------------------------------------------------------


def phase_build_and_submit(executor: Any, ctx: PhaseContext) -> PhaseOutcome:
    impl = getattr(executor, "_phase_build_and_submit_impl", None)
    if impl is None:
        return PhaseOutcome(
            status=PhaseStatus.ABORT,
            reason="phase_build_and_submit: orchestrateur S26.3 non câblé sur cet executor",
        )
    return impl(ctx)


# ---------------------------------------------------------------------------
# Phase 3 — Poll fills + Children + Broker state sync
# ---------------------------------------------------------------------------


def phase_poll_and_children(executor: Any, ctx: PhaseContext) -> PhaseOutcome:
    impl = getattr(executor, "_phase_poll_and_children_impl", None)
    if impl is None:
        return PhaseOutcome(
            status=PhaseStatus.ABORT,
            reason="phase_poll_and_children: orchestrateur S26.3 non câblé sur cet executor",
        )
    return impl(ctx)


# ---------------------------------------------------------------------------
# Phase 4 — Reconciliation + TCA + Finalize
# ---------------------------------------------------------------------------


def phase_reconcile_and_finalize(executor: Any, ctx: PhaseContext) -> PhaseOutcome:
    impl = getattr(executor, "_phase_reconcile_and_finalize_impl", None)
    if impl is None:
        return PhaseOutcome(
            status=PhaseStatus.ABORT,
            reason="phase_reconcile_and_finalize: orchestrateur S26.3 non câblé sur cet executor",
        )
    return impl(ctx)


# ---------------------------------------------------------------------------
# Sprint S26.3 — Orchestrateur thin (à activer via ``EXECUTOR_PHASES_ENABLED=1``)
# ---------------------------------------------------------------------------

PHASE_SEQUENCE: tuple[Callable[[Any, PhaseContext], PhaseOutcome], ...] = (
    phase_init_and_preflight,
    phase_build_and_submit,
    phase_poll_and_children,
    phase_reconcile_and_finalize,
)


def run_phases(executor: Any, ctx: PhaseContext) -> dict[str, Any]:
    """Exécute séquentiellement les 4 phases ; arrête sur premier ABORT/FAIL.

    Garanties :
      * Aucune phase ne peut être skippée en silence : ``PhaseStatus.ABORT``
        ou ``FAIL`` propage immédiatement.
      * ``ctx.metrics`` est toujours retourné (état observable même en cas
        d'abort précoce).
      * Les exceptions inattendues sont **rethrown** : c'est à
        ``ProductionExecutor.execute_run`` de gérer le ``try/except/finally``
        global (release lock, persist events).
    """
    for phase in PHASE_SEQUENCE:
        outcome = phase(executor, ctx)
        if not isinstance(outcome, PhaseOutcome):
            raise TypeError(
                f"{phase.__name__} doit retourner PhaseOutcome, "
                f"got {type(outcome).__name__}"
            )
        if not outcome.should_continue:
            ctx.metrics.setdefault("status", "ABORTED")
            ctx.metrics["abort_phase"] = phase.__name__
            ctx.metrics["abort_reason"] = outcome.reason
            LOGGER.info(
                "Phase %s -> %s (%s) — orchestrateur stoppé",
                phase.__name__, outcome.status.value, outcome.reason,
            )
            return ctx.metrics
    return ctx.metrics


__all__ = [
    "ENV_TOGGLE",
    "PHASE_SEQUENCE",
    "PhaseContext",
    "PhaseOutcome",
    "PhaseStatus",
    "is_phases_orchestrator_enabled",
    "phase_build_and_submit",
    "phase_init_and_preflight",
    "phase_poll_and_children",
    "phase_reconcile_and_finalize",
    "run_phases",
]

