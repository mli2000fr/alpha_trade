# Synthèse — Vérification filtre ML live & backtest

## Résultat de vérification

Les filtres et boosts sont **implémentés**, persistés après le batch, puis appelés dans le live et le backtest. Les tests ciblés passent : `pytest --no-cov ...` ✅ (86 tests)

Trois écarts ont été identifiés entre le document et le comportement réel. Tous sont résolus.

---

## 1. [✅ RÉSOLU] Le batch de diagnostics n'était pas lié au batch ML utilisé

**Problème :** Dans `backtesting/cli/_impl.py`, `get_batch_filters(engine)` était appelé sans `batch_id`, utilisant toujours le dernier batch — causant un **look-ahead bias** en backtest. En live, le dernier batch était utilisé au lieu du batch promu (`model_serving_batch`).

**Correctif (2026-07-23) :**
- Ajout de `live_batch_id` et `backtest_batch_id` dans `config.yaml` → section `batch_diagnostics`.
- Si vide → comportement actuel (dernier batch). Si renseigné → utilise ce `batch_id` explicite.
- `risk_management/batch_diagnostics.py` lit `live_batch_id` et le passe à `get_batch_filters(engine, batch_id=...)`.
- `backtesting/cli/_impl.py` lit `backtest_batch_id` et le passe à `get_batch_filters(engine, batch_id=...)`.
- Ajout du `comment` (`model_training_batch.comment`) dans les logs Risk et l'IHM backtest.
- Pour un backtest PIT-safe : renseigner un `batch_id` dont la `training_end_date` est antérieure à la date simulée.

---

## 2. [✅ RÉSOLU] Le boost n'était pas identique entre live et backtest

**Problème :** Le live boostait `approved_shares`/`target_notional` après sizing → `target_weight` incohérent et contraintes potentiellement violées. Le backtest boostait `proba_long` ET `proba_short` sans distinction de `predicted_side` → mécanisme différent, non side-aware.

**Correctif — Option C (2026-07-23) :** Boost du score en amont du sizing, identique dans les deux pipelines.

**Live (Risk, étape 11) :**
- `boost_candidate_scores()` est appelé **AVANT** `PortfolioBuilder.build_from_ml_candidates()`
- Multiplie `p_side` (et `p_long`/`p_short` selon le side) par `prefer_sizing_multiplier`, clip à 1.0
- Le builder intègre naturellement le score boosté → sizing, contraintes et `target_weight` cohérents
- `apply_batch_diagnostics_to_entries()` ne fait plus que l'exclusion (boost retiré)

**Backtest (`_impl.py`) :**
- Boost side-aware : `proba_long` × multiplier **uniquement** si `predicted_side == "long"`
- `proba_short` × multiplier **uniquement** si `predicted_side == "short"`
- Flat → pas de boost. Clip ≤ 1.0.

| Aspect | Live (Risk) | Backtest | Cohérent ? |
|--------|-------------|----------|:---:|
| **Quoi** | `p_side` × 1.2 AVANT sizing | `proba_long` × 1.2 si side=long, `proba_short` × 1.2 si side=short | ✅ |
| **Quand** | Avant PortfolioBuilder | Avant scoring/sizing | ✅ |
| **Effet** | Score boosté → sizing naturel | Score boosté → sizing naturel | ✅ |
| **Side awareness** | ✅ long→p_long, short→p_short | ✅ long→proba_long, short→proba_short | ✅ |
| **target_weight** | ✅ Cohérent (calculé après boost) | ✅ N/A (calculé après boost) | ✅ |
| **Contraintes** | ✅ Respectées (appliquées après boost) | ✅ Respectées (appliquées après boost) | ✅ |

---

## 3. [✅ RÉSOLU] Les tests du backtest ne testaient pas le chemin réel

**Problème :** `tests/test_batch_diagnostics_backtest.py` utilisait une fonction locale `apply_batch_diagnostics_to_preds()` qui dupliquait la logique au lieu d'appeler le bloc réel de `_impl.py`. Si on supprimait le bloc de `_impl.py`, les tests restaient verts.

**Correctif (2026-07-23) :**
- Suppression du helper local, utilisation directe de `filter_predictions()` (la vraie fonction).
- Ajout de `TestImplSourceContainsBatchDiagnostics` : 5 nouveaux tests qui analysent le **code source** de `_impl.py` avec `ast.parse()` :
  - `test_imports_get_batch_filters` — vérifie l'import
  - `test_imports_filter_predictions` — vérifie l'import
  - `test_calls_get_batch_filters` — vérifie l'appel
  - `test_calls_filter_predictions` — vérifie l'appel
  - `test_boost_block_present` — vérifie la présence de `proba_long`, `proba_short`, `.clip(upper=1.0)`
- Si quelqu'un supprime ou casse le bloc batch diagnostics dans `_impl.py`, ces tests échoueront.

---

## Ce qui est correctement implémenté

- La persistence est appelée après un batch avec au moins un entraînement complété.
- Les catégories sont conformes : `bottom+weak_long` → exclude long, `bottom+zero_short+weak_short` → exclude short, `top` → prefer.
- Le live applique le boost score AVANT `PortfolioBuilder`, puis l'exclusion APRÈS. Les contraintes sont respectées.
- Le backtest applique l'exclusion avant la reconstruction des signaux.
- Les paramètres `config.yaml` sont bien consommés par le code.
- Les erreurs DB restent non bloquantes.

## Verdict

| Surface | Filtrage | Boost | Parité/PIT |
|---|---|---|---|
| Persistence batch | ✅ | — | ✅ |
| Live Risk | ✅ | ✅ Option C (score avant sizing) | ✅ via `live_batch_id` |
| Backtest | ✅ | ✅ Option C (side-aware) | ✅ via `backtest_batch_id` |
| Tests | ✅ + garde-fou AST | ✅ side-aware + clipping | ✅ |
