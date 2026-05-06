"""Sprint S24.1 — Stateful fuzzing OCO via ``RuleBasedStateMachine``.

Complète ``tests/property/test_fuzz_backtest_vs_live_diff.py`` (qui se
focalise sur la **parité** scénario par scénario) en vérifiant les
**invariants OCO d'état** sous une exploration stateful d'hypothesis :

* TP et SL ne peuvent être ``FILLED`` simultanément (jamais).
* Si une jambe est ``FILLED``, l'autre finit ``FILLED`` (no-op à
  posteriori) ou ``CANCELED`` (jamais ``NEW``) au prochain événement.
* ``audit_hash`` live et replay coïncident à chaque état terminal
  (déterminisme bout-en-bout).
* ``qty_filled`` ne dépasse jamais ``qty`` du scénario.

Documenté dans ``doc/fuzz_diff.md`` §"Stateful invariants".
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    rule,
)

from backtesting.fuzz_runner import FuzzScenario, _run_engine

pytestmark = pytest.mark.property


_KIND = st.sampled_from(
    ("tick", "partial_fill", "cancel", "broker_error", "eod_close")
)


class OCOBracketStateMachine(RuleBasedStateMachine):
    """Pilote ``_run_engine`` en accumulant des événements puis vérifie
    que chaque snapshot conserve les invariants OCO.

    Stratégie : on ne réinvente pas un moteur d'état ; on s'appuie sur
    ``_run_engine`` qui est *déterministe* en fonction de la liste
    d'événements. À chaque nouvelle règle (= nouvel événement), on
    rejoue tout l'historique côté live et côté replay.
    """

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, float]] = []
        self.scenario: FuzzScenario | None = None

    @initialize(
        entry=st.floats(min_value=10.0, max_value=500.0,
                        allow_nan=False, allow_infinity=False),
        tp_mult=st.floats(min_value=1.005, max_value=1.05,
                          allow_nan=False, allow_infinity=False),
        sl_mult=st.floats(min_value=0.95, max_value=0.995,
                          allow_nan=False, allow_infinity=False),
        qty=st.integers(min_value=1, max_value=1000),
    )
    def _setup(self, entry: float, tp_mult: float, sl_mult: float,
               qty: int) -> None:
        self.scenario = FuzzScenario(
            seed=0,
            qty=float(qty),
            entry_price=round(entry, 4),
            tp_price=round(entry * tp_mult, 4),
            sl_price=round(entry * sl_mult, 4),
            events=tuple(self.events),
        )

    @rule(
        kind=_KIND,
        magnitude=st.floats(min_value=-0.05, max_value=0.05,
                            allow_nan=False, allow_infinity=False),
    )
    def push_event(self, kind: str, magnitude: float) -> None:
        if self.scenario is None:
            return
        self.events.append((kind, round(magnitude, 4)))
        self.scenario = FuzzScenario(
            seed=self.scenario.seed,
            qty=self.scenario.qty,
            entry_price=self.scenario.entry_price,
            tp_price=self.scenario.tp_price,
            sl_price=self.scenario.sl_price,
            events=tuple(self.events),
        )

    @invariant()
    def oco_mutual_exclusion(self) -> None:
        if self.scenario is None:
            return
        live = _run_engine(self.scenario, is_live=True)
        replay = _run_engine(self.scenario, is_live=False)

        # 1) TP et SL ne peuvent jamais être FILLED simultanément.
        assert not (live.tp_status == "FILLED" and live.sl_status == "FILLED"), (
            f"OCO violé (live) : TP+SL FILLED simultanément. "
            f"events={self.events!r}"
        )
        assert not (replay.tp_status == "FILLED"
                    and replay.sl_status == "FILLED"), (
            "OCO violé (replay) : TP+SL FILLED simultanément."
        )

        # 2) Finalisation OCO : après un eod_close (ou un événement
        #    post-fill), la jambe restante doit être terminale (CANCELED
        #    ou FILLED), jamais NEW. Cette propriété est vérifiée en
        #    rejouant le scénario avec un eod_close ajouté en queue.
        finalized_events = (*self.events, ("eod_close", 0.0))
        finalized = _run_engine(
            FuzzScenario(
                seed=self.scenario.seed,
                qty=self.scenario.qty,
                entry_price=self.scenario.entry_price,
                tp_price=self.scenario.tp_price,
                sl_price=self.scenario.sl_price,
                events=finalized_events,
            ),
            is_live=True,
        )
        assert finalized.tp_status in ("CANCELED", "FILLED"), (
            f"Finalisation incomplete : tp_status={finalized.tp_status}"
        )
        assert finalized.sl_status in ("CANCELED", "FILLED"), (
            f"Finalisation incomplete : sl_status={finalized.sl_status}"
        )

        # 3) Parité bout-en-bout : statuts et hash audit identiques.
        assert (live.tp_status, live.sl_status) == (
            replay.tp_status, replay.sl_status
        ), (
            f"Statut divergent live vs replay : "
            f"live=({live.tp_status},{live.sl_status}) "
            f"replay=({replay.tp_status},{replay.sl_status})"
        )
        assert live.audit_hash == replay.audit_hash, (
            "Audit hash divergent — déterminisme cassé."
        )

        # 4) qty_filled bornée par scenario.qty.
        assert 0.0 <= live.qty_filled <= self.scenario.qty + 1e-6
        assert 0.0 <= replay.qty_filled <= self.scenario.qty + 1e-6


TestOCOBracketStateMachine = OCOBracketStateMachine.TestCase
TestOCOBracketStateMachine.settings = settings(
    max_examples=50,
    stateful_step_count=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


