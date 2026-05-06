# Spécifications TLA+ — Phase C / S15

Ces spécifications sont **descriptives** et accompagnent les preuves
exécutables Z3 dans `formal/z3_invariants/`. Elles ne sont **pas**
vérifiées en CI (TLAPS requiert une JVM + outils tierce-partie).

## Vérification locale (optionnelle)

1. Installer [TLA+ tools](https://github.com/tlaplus/tlaplus/releases) :
   `tla2tools.jar`.
2. Parser :
   ```bash
   java -cp tla2tools.jar tla2sany.SANY formal/tla/IdempotenceCA.tla
   ```
3. Model-check (TLC) :
   ```bash
   java -cp tla2tools.jar tlc2.TLC formal/tla/IdempotenceCA.tla
   ```

## Spécifications

| Fichier | Invariant prouvé | Pendant Z3 | TLAPS |
|---|---|---|---|
| `IdempotenceCA.tla` | `NoDuplicate` : pas de double application CA | `formal/z3_invariants/idempotence_corporate_actions.py` | ⚠️ S24.3 |
| `OCOBracket.tla` | `MutualExclusion` / `SiblingCancelInitiated` / `NoActiveAfterFinalize` | `oco_synthetic_bracket.py` | ⚠️ S24.3 |
| `NoDoubleExec.tla` | `Singleton` : ≤ 1 fill par `idempotency_key` | `no_double_execution.py` | ⚠️ S24.3 |

Les preuves Z3 sont l'engagement formel exécutable de Phase C. Les
specs TLA+ servent de documentation de modèle et de base à un audit
externe (cf. `doc/external_audit_checklist.md`, S18).

## TLAPS — Sprint S24.3

Wrapper Python : `python scripts/run_tlaps.py --strict` (auto-détecte
`tlapm`, fallback `tlc2.TLC`). Workflow CI : job `tlaps` dans
`formal_verification.yml`. Spec consultants : `doc/tlaps_proofs.md`.

