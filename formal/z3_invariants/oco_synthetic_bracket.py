"""Phase C / S15.1.b — Preuve formelle : exclusivité OCO synthetic bracket.

Modélise une machine à états OCO : pour un parent rempli, **exactement
un seul** enfant (TP ou SL) est terminal en état "filled" ; l'autre
doit être annulé.

Variables booléennes Z3 :

* ``parent_filled``
* ``tp_filled``, ``tp_canceled``
* ``sl_filled``, ``sl_canceled``

Contraintes (axiomes du contrôleur OCO synthetic) :

* parent_filled ⟹ (tp_filled ∨ tp_canceled) ∧ (sl_filled ∨ sl_canceled)
* tp_filled ⟹ ¬tp_canceled ; sl_filled ⟹ ¬sl_canceled (un état terminal)
* tp_filled ⟹ sl_canceled (déclencheur OCO)
* sl_filled ⟹ tp_canceled

**Théorème** (à prouver) : sous ces contraintes, ¬(tp_filled ∧ sl_filled).
"""
from __future__ import annotations

import sys

try:
    import z3  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    z3 = None  # type: ignore[assignment]


def prove() -> dict[str, object]:
    if z3 is None:
        return {"oco_exclusivity": "skipped", "reason": "z3-solver non installé"}

    parent_filled = z3.Bool("parent_filled")
    tp_filled = z3.Bool("tp_filled")
    tp_canceled = z3.Bool("tp_canceled")
    sl_filled = z3.Bool("sl_filled")
    sl_canceled = z3.Bool("sl_canceled")

    s = z3.Solver()
    s.add(parent_filled)
    s.add(z3.Implies(parent_filled,
                     z3.And(z3.Or(tp_filled, tp_canceled),
                            z3.Or(sl_filled, sl_canceled))))
    s.add(z3.Implies(tp_filled, z3.Not(tp_canceled)))
    s.add(z3.Implies(sl_filled, z3.Not(sl_canceled)))
    s.add(z3.Implies(tp_filled, sl_canceled))
    s.add(z3.Implies(sl_filled, tp_canceled))

    # Négation de l'exclusivité : ∃ état où tp_filled ∧ sl_filled
    s.push()
    s.add(z3.And(tp_filled, sl_filled))
    result = s.check()
    s.pop()

    return {
        "oco_exclusivity": "proved" if result == z3.unsat else f"counterexample"
    }


def main() -> int:
    res = prove()
    for k, v in res.items():
        ok = v in ("proved", "skipped")
        print(f"  [{('OK' if ok else 'FAIL')}] {k}: {v}")
    return 0 if all(v in ("proved", "skipped") for v in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

