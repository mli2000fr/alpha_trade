"""Phase C / S15.1.a — Preuve formelle : idempotence des corporate actions.

Encode ``CorporateActionEvent.compute_idempotency_key`` sous forme
purement fonctionnelle (chaîne déterministe → SHA-256 → 32 chars
hexa) puis prouve via Z3 deux invariants :

1. **Déterminisme** : si tous les champs scope-pertinents (account_id,
   provider, symbol, ca_type, ex_date, montant ou ratio) sont égaux,
   les clés sont égales.
2. **Discrimination** : si l'``account_id`` diffère, les clés diffèrent
   (modulo collisions SHA-256 négligées).

La preuve repose sur la *fonction d'encodage* (pas sur la
cryptographie de SHA-256, modélisée comme fonction injective Z3).

Exécution :

    python -m formal.z3_invariants.idempotence_corporate_actions
"""
from __future__ import annotations

import sys

try:
    import z3  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - import opt
    z3 = None  # type: ignore[assignment]


def prove() -> dict[str, object]:
    """Retourne ``{theorem -> "proved" | "counterexample" | "skipped"}``."""
    if z3 is None:
        return {
            "determinism": "skipped",
            "discrimination": "skipped",
            "reason": "z3-solver non installé",
        }

    String = z3.StringSort()
    # Modélisation : payload = concat(scope, '|', provider, '|', symbol, '|',
    # ca_type, '|', ex_date, '|', amount).
    # SHA-256 modélisée comme fonction injective : sha(p1) == sha(p2) ⟺ p1 == p2.
    Sha = z3.Function("sha", String, String)

    # Injectivité (axiome) : ∀ x y. sha(x) == sha(y) ⟹ x == y.
    x, y = z3.Strings("x y")
    inj_axiom = z3.ForAll([x, y],
                          z3.Implies(Sha(x) == Sha(y), x == y))

    # Variables symboliques : deux events
    a1, p1, s1, t1, e1, m1 = z3.Strings("a1 p1 s1 t1 e1 m1")
    a2, p2, s2, t2, e2, m2 = z3.Strings("a2 p2 s2 t2 e2 m2")

    sep = z3.StringVal("|")
    payload1 = z3.Concat(a1, sep, p1, sep, s1, sep, t1, sep, e1, sep, m1)
    payload2 = z3.Concat(a2, sep, p2, sep, s2, sep, t2, sep, e2, sep, m2)
    key1 = Sha(payload1)
    key2 = Sha(payload2)

    results: dict[str, object] = {}

    # Théorème 1 : déterminisme
    s = z3.Solver()
    s.add(inj_axiom)
    s.add(a1 == a2, p1 == p2, s1 == s2, t1 == t2, e1 == e2, m1 == m2)
    # Négation de la conclusion : key1 != key2
    s.add(key1 != key2)
    results["determinism"] = "proved" if s.check() == z3.unsat else f"counterexample:{s.model()}"

    # Théorème 2 : discrimination par account_id (avec autres champs égaux)
    s = z3.Solver()
    s.add(inj_axiom)
    s.add(a1 != a2, p1 == p2, s1 == s2, t1 == t2, e1 == e2, m1 == m2)
    # Négation : key1 == key2
    s.add(key1 == key2)
    results["discrimination"] = "proved" if s.check() == z3.unsat else f"counterexample:{s.model()}"

    return results


def main() -> int:
    res = prove()
    for theorem, status in res.items():
        ok = status == "proved" or status == "skipped"
        print(f"  [{('OK' if ok else 'FAIL')}] {theorem}: {status}")
    if any(str(v).startswith("counterexample") for v in res.values()):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

