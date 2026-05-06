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

| Fichier | Invariant prouvé | Pendant Z3 |
|---|---|---|
| `IdempotenceCA.tla` | `NoDuplicate` : pas de double application CA | `formal/z3_invariants/idempotence_corporate_actions.py` |
| `OCOBracket.tla` *(stub)* | `MutualExclusion` : TP ⊕ SL terminal | `oco_synthetic_bracket.py` |
| `NoDoubleExec.tla` *(stub)* | `Singleton` : une fill par idempotency_key | `no_double_execution.py` |

Les preuves Z3 sont l'engagement formel exécutable de Phase C. Les
specs TLA+ servent de documentation de modèle et de base à un audit
externe (cf. `doc/external_audit_checklist.md`, S18).

