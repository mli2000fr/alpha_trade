# Qualité avancée : fuzzing, mutation et vérification formelle

## Positionnement

Ces outils complètent les tests classiques. Ils ne prouvent pas seuls le système en production : chacun vérifie un modèle, un espace d’entrées ou la capacité des tests à détecter des changements.

## Fuzzing différentiel

`backtesting/fuzz_runner.py` génère des scénarios ; `backtesting/fuzz_tolerance.py` porte les tolérances ; `scripts/run_fuzz_diff.py` est le point d’entrée. Les propriétés vivent dans `tests/property/test_fuzz_backtest_vs_live_diff.py`, `tests/property/test_fuzz_state_machine.py` et `tests/test_fuzz_diff_runner.py`. Le workflow `fuzz_weekly.yml` conserve ses artefacts 90 jours.

Pour une divergence : conserver seed/scénario, reproduire, trouver la première transition différente, comparer prix, intrabar, arrondis, gaps, frais, protections et temps, corriger puis élargir le corpus. Ne pas augmenter une tolérance sans expliquer la différence de contrat.

## Mutation testing

`scripts/run_mutation_testing.py` pilote la campagne et `scripts/list_mutation_survivors.py` classe les survivants. `mutation.yml` et `mutation_weekly.yml` l’exécutent en CI.

Un survivant peut signaler test absent, oracle faible, branche morte ou mutation équivalente. Il faut le classer avant d’ajouter un test. Le score de mutation n’est pas une métrique métier.

## Z3 et TLA+

`formal/z3_invariants/` encode absence de double exécution, bracket/OCO et idempotence des corporate actions. `scripts/run_formal_verification.py` les lance ; `tests/formal/` vérifie les artefacts.

`formal/tla/NoDoubleExec.tla`, `OCOBracket.tla` et `IdempotenceCA.tla`, avec `formal/tla/proofs/`, décrivent les transitions abstraites. `scripts/run_tlaps.py`, `tests/test_run_tlaps.py` et le workflow `formal_verification.yml` gèrent l’exécution.

Une preuve vaut sous les hypothèses du modèle. Prouver l’exclusion sous un lock ne prouve pas que tous les chemins acquièrent ce lock. Un statut `skipped` faute de solveur n’est pas un succès.

## Matrice de mise à jour

| Changement | Contrôles minimaux |
|---|---|
| ordre, verrou, idempotency key | unitaires, fuzz state machine, no-double-exec |
| OCO, stop, TP, protection | parité/replay, fuzz différentiel, modèle OCO |
| corporate action | tests et invariant d’idempotence |
| branche critique mal testée | mutation ciblée puis régression |

Conserver commande, commit, dépendances, seed/corpus, statut solveurs, rapport et artefacts. Un ancien résultat ne garantit que le commit vérifié.

