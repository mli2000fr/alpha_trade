"""Phase C / S15.1.c — Preuve formelle : pas de double exécution.

Modèle simplifié de verrou d'exécution : pour une ``idempotency_key``
donnée, au plus un seul ``fill`` peut être enregistré, même sous
concurrence pipeline ⊥ backtest.

On encode :

* Deux acteurs A (pipeline) et B (backtest) tentent de submit la même
  ``idempotency_key`` k.
* Le système possède un verrou idempotent : ``submit(k)`` ne réussit
  que si ``k`` n'a pas déjà été marqué dans ``executed_keys``.

Théorème : ¬(A_succeeded ∧ B_succeeded).
"""
from __future__ import annotations

import sys

try:
    import z3  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    z3 = None  # type: ignore[assignment]


def prove() -> dict[str, object]:
    if z3 is None:
        return {"no_double_execution": "skipped", "reason": "z3-solver non installé"}

    # Booléens : Acteur X a tenté ; Acteur X a réussi.
    A_attempted = z3.Bool("A_attempted")
    A_succeeded = z3.Bool("A_succeeded")
    B_attempted = z3.Bool("B_attempted")
    B_succeeded = z3.Bool("B_succeeded")
    # Lock acquis par exactement un des deux (ordre indéterministe)
    A_acquired_lock = z3.Bool("A_acquired_lock")
    B_acquired_lock = z3.Bool("B_acquired_lock")

    s = z3.Solver()
    # Modèle de verrou exclusif idempotent
    s.add(z3.Not(z3.And(A_acquired_lock, B_acquired_lock)))
    s.add(z3.Implies(A_succeeded, z3.And(A_attempted, A_acquired_lock)))
    s.add(z3.Implies(B_succeeded, z3.And(B_attempted, B_acquired_lock)))

    # Négation : les deux réussissent
    s.add(A_succeeded, B_succeeded)
    return {
        "no_double_execution": "proved" if s.check() == z3.unsat else "counterexample"
    }


def main() -> int:
    res = prove()
    for k, v in res.items():
        ok = v in ("proved", "skipped")
        print(f"  [{('OK' if ok else 'FAIL')}] {k}: {v}")
    return 0 if all(v in ("proved", "skipped") for v in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

