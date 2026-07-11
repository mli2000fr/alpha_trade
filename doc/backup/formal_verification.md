# Vérification formelle — Phase C / S15

> ⚠️ **POC / chantier de recherche non activé comme contrôle bloquant en production**.
> Les preuves décrites ici complètent les tests classiques mais ne constituent
> pas encore une barrière opératoire obligatoire dans le flux nominal.

## Objectif

Établir, par modélisation logique exécutable et par spécifications
TLA+, que **trois invariants critiques** d'Alpha Trade sont préservés
sous toutes les exécutions du système.

## Invariants

### 1. Idempotence des Corporate Actions

**Énoncé** — Pour tout couple d'événements `(e1, e2)` partageant le
tuple `(account_id, provider, symbol, ca_type, ex_date, amount)`,
`compute_idempotency_key(e1) == compute_idempotency_key(e2)`. De plus,
si `e1.account_id ≠ e2.account_id` (autres champs égaux), les clés
diffèrent.

**Preuve Z3** — `formal/z3_invariants/idempotence_corporate_actions.py`.
Modélise SHA-256 comme fonction injective Z3, puis vérifie les deux
théorèmes par négation (UNSAT).

**Spec TLA+** — `formal/tla/IdempotenceCA.tla`. Invariant
`NoDuplicate` : la cardinalité des clés appliquées est égale à la
cardinalité de l'image de `Key` sur `applied`.

### 2. Exclusivité OCO synthetic bracket

**Énoncé** — Pour tout parent rempli, exactement **un** des deux
enfants (TP, SL) atteint l'état terminal `filled` ; l'autre est dans
l'état terminal `canceled`.

**Preuve Z3** — `formal/z3_invariants/oco_synthetic_bracket.py`.
Modèle booléen 5 variables (parent, tp_filled, tp_canceled, sl_filled,
sl_canceled) + 5 contraintes du contrôleur. Théorème :
`¬(tp_filled ∧ sl_filled)` est UNSAT contre les contraintes ⇒ prouvé.

### 3. Pas de double exécution

**Énoncé** — Pour toute `idempotency_key k`, sous concurrence
pipeline ⊥ backtest, au plus un acteur réussit à enregistrer un
`fill` pour `k`.

**Preuve Z3** — `formal/z3_invariants/no_double_execution.py`. Modèle
verrou exclusif (mutex) au niveau de la clé. Théorème :
`¬(A_succeeded ∧ B_succeeded)` UNSAT.

## Reproduction

```bash
pip install z3-solver
python scripts/run_formal_verification.py
# → artifacts/formal_runs/<date>/proofs.json
pytest tests/formal -v --no-cov
```

## Limitations actuelles

* Les preuves Z3 utilisent des **abstractions** (SHA-256 = injective,
  verrou = exclusif). La fidélité à l'implémentation Python est
  vérifiée par les tests unitaires + property-based.
* Les specs TLA+ sont **descriptives** ; la vérification TLAPS
  requiert une JVM externe non câblée en CI (cf. `formal/tla/README.md`).
* Le **fuzzing différentiel** backtest vs live (S15.2) est un
  livrable optionnel hors périmètre Z3.

## Suite

* Étendre les preuves Z3 à la machine d'états complète de l'OCO
  (incl. timeouts, race condition replace).
* Introduire un consultant TLAPS pour vérification formelle de
  `formal/tla/*.tla` (S15-bis).

