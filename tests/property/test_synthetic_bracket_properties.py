"""Phase F / S22.4 — Property-based tests pour le synthetic bracket OCO.

Vérifie sous fuzz d'événements (entry filled → enfants TP/SL armés →
événements aléatoires `tp_filled`, `sl_filled`, `cancel_*`, `broker_error`)
les invariants suivants :

1. À tout instant, ``count(filled in {TP, SL}) <= 1`` (mutuelle exclusivité).
2. Si TP est ``FILLED``, SL est ``CANCELED`` ou en cours d'annulation
   dans la fenêtre suivante (et inversement).
3. Aucune fuite d'ordre actif après ``RUN_COMPLETED``.
4. La quantité totale fillée ≤ quantité enfant initiale.

Note d'implémentation : on simule la machine d'état OCO directement
(modèle pur Python) plutôt que de tester l'intégration ``OcoManager`` +
``MockBroker`` (couvert par les tests d'intégration existants). Ceci permet
au property test de tourner en < 60 s avec ``max_examples=200``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pytest
from hypothesis import HealthCheck, settings
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    rule,
)

pytestmark = pytest.mark.property


class _Status(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


_TERMINAL = {_Status.FILLED, _Status.CANCELED, _Status.REJECTED}


@dataclass
class _Child:
    role: str  # "TP" | "SL"
    qty: float
    filled_qty: float = 0.0
    status: _Status = _Status.NEW

    def is_terminal(self) -> bool:
        return self.status in _TERMINAL


@dataclass
class _Bracket:
    parent_qty: float
    tp: _Child
    sl: _Child
    run_completed: bool = False
    events: list[str] = field(default_factory=list)

    def sibling(self, role: str) -> _Child:
        return self.sl if role == "TP" else self.tp

    def on_fill(self, role: str, qty: float) -> None:
        leg = self.tp if role == "TP" else self.sl
        if leg.is_terminal():
            return
        new_filled = min(leg.filled_qty + qty, leg.qty)
        leg.filled_qty = new_filled
        if new_filled >= leg.qty:
            leg.status = _Status.FILLED
            sib = self.sibling(role)
            # Invariant 2 : on enclenche immédiatement l'annulation du sibling.
            if sib.status not in _TERMINAL and sib.status != _Status.CANCEL_PENDING:
                sib.status = _Status.CANCEL_PENDING
        else:
            leg.status = _Status.PARTIALLY_FILLED
        self.events.append(f"FILL {role} {qty}")

    def on_cancel_ack(self, role: str) -> None:
        leg = self.tp if role == "TP" else self.sl
        if leg.status == _Status.CANCEL_PENDING:
            leg.status = _Status.CANCELED
            self.events.append(f"CANCEL_ACK {role}")

    def on_cancel_request(self, role: str) -> None:
        leg = self.tp if role == "TP" else self.sl
        if leg.status not in _TERMINAL and leg.status != _Status.CANCEL_PENDING:
            leg.status = _Status.CANCEL_PENDING
            self.events.append(f"CANCEL_REQ {role}")

    def on_broker_error(self, role: str) -> None:
        # Erreur transitoire : ne change PAS le status (à confirmer par poll).
        self.events.append(f"ERROR {role}")

    def finalize(self) -> None:
        # Phase 10 RUN_COMPLETED : tout ordre encore non terminal doit être
        # cancel_pending ou canceled.
        for leg in (self.tp, self.sl):
            if leg.status not in _TERMINAL and leg.status != _Status.CANCEL_PENDING:
                leg.status = _Status.CANCEL_PENDING
        self.run_completed = True


class SyntheticBracketStateMachine(RuleBasedStateMachine):
    """Machine d'état RuleBased fuzzant le cycle de vie d'un synthetic bracket."""

    def __init__(self) -> None:
        super().__init__()
        qty = 100.0
        self.bracket = _Bracket(
            parent_qty=qty,
            tp=_Child(role="TP", qty=qty),
            sl=_Child(role="SL", qty=qty),
        )

    # --- règles -------------------------------------------------------

    @rule(qty=...)
    def fill_tp(self, qty: float = 10.0) -> None:  # type: ignore[override]
        if self.bracket.run_completed:
            return
        self.bracket.on_fill("TP", max(0.1, min(qty, self.bracket.parent_qty)))

    @rule(qty=...)
    def fill_sl(self, qty: float = 10.0) -> None:  # type: ignore[override]
        if self.bracket.run_completed:
            return
        self.bracket.on_fill("SL", max(0.1, min(qty, self.bracket.parent_qty)))

    @rule()
    def cancel_tp(self) -> None:
        if not self.bracket.run_completed:
            self.bracket.on_cancel_request("TP")

    @rule()
    def cancel_sl(self) -> None:
        if not self.bracket.run_completed:
            self.bracket.on_cancel_request("SL")

    @rule()
    def ack_cancel_tp(self) -> None:
        self.bracket.on_cancel_ack("TP")

    @rule()
    def ack_cancel_sl(self) -> None:
        self.bracket.on_cancel_ack("SL")

    @rule()
    def broker_error(self) -> None:
        self.bracket.on_broker_error("TP")

    @rule()
    def finalize_run(self) -> None:
        self.bracket.finalize()

    # --- invariants ---------------------------------------------------

    @invariant()
    def mutual_exclusion(self) -> None:
        """Invariant #1 : au plus une jambe peut être ``FILLED``."""
        filled = sum(1 for leg in (self.bracket.tp, self.bracket.sl)
                     if leg.status == _Status.FILLED)
        assert filled <= 1, (
            f"Mutual exclusion violée : tp={self.bracket.tp.status} "
            f"sl={self.bracket.sl.status} events={self.bracket.events[-5:]}"
        )

    @invariant()
    def sibling_cancel_initiated(self) -> None:
        """Invariant #2 : si une jambe est FILLED, l'autre est CANCEL_PENDING/CANCELED/REJECTED."""
        if self.bracket.tp.status == _Status.FILLED:
            assert self.bracket.sl.status in (_Status.CANCEL_PENDING, _Status.CANCELED, _Status.REJECTED), (
                f"TP filled mais SL={self.bracket.sl.status}"
            )
        if self.bracket.sl.status == _Status.FILLED:
            assert self.bracket.tp.status in (_Status.CANCEL_PENDING, _Status.CANCELED, _Status.REJECTED), (
                f"SL filled mais TP={self.bracket.tp.status}"
            )

    @invariant()
    def no_active_after_run_completed(self) -> None:
        """Invariant #3 : après finalize, aucun ordre n'est NEW/PARTIALLY_FILLED."""
        if self.bracket.run_completed:
            for leg in (self.bracket.tp, self.bracket.sl):
                assert leg.status not in (_Status.NEW, _Status.PARTIALLY_FILLED), (
                    f"Ordre actif après RUN_COMPLETED : {leg.role}={leg.status}"
                )

    @invariant()
    def fills_within_qty(self) -> None:
        """Invariant #4 : la quantité fillée ≤ quantité initiale par jambe."""
        for leg in (self.bracket.tp, self.bracket.sl):
            assert leg.filled_qty <= leg.qty + 1e-9, (
                f"Overfill {leg.role}: {leg.filled_qty} > {leg.qty}"
            )


TestSyntheticBracketProperties = SyntheticBracketStateMachine.TestCase
TestSyntheticBracketProperties.settings = settings(  # type: ignore[attr-defined]
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
    print_blob=True,
)

