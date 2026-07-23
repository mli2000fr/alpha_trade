# Synthèse — Vérification filtre ML live & backtest

## Résultat de vérification

Les filtres et boosts sont **implémentés**, persistés après le batch, puis appelés dans le live et le backtest. Les tests ciblés passent sans couverture : `pytest --no-cov ...` ✅

Mais il y a deux écarts critiques entre le document et le comportement réel.

1. **[Critique] Le batch de diagnostics n’est pas lié au batch ML utilisé, ni à la date du backtest.**  
   Dans `backtesting/cli/_impl.py`, les prédictions sont bien chargées avec `args.ml_batch_id`, mais les filtres sont récupérés via `get_batch_filters(engine)` sans `batch_id` ni date de simulation. La fonction choisit donc le **dernier batch diagnostiqué en base** dans `modelFactory/batch_diagnostics.py`.

   Conséquences :
   - un backtest historique peut appliquer les diagnostics d’un batch entraîné après la période backtestée : **look-ahead bias** ;
   - avec `--ml-batch-id`, le filtre peut provenir d’un autre batch que les prédictions ;
   - en live, la même fonction utilise le dernier batch, alors que le serving dispose déjà d’un mécanisme de promotion explicite `model_serving_batch`.

   Cela contredit directement les précautions 1 et 2 de `doc/filtre_ml.md`. C’est le point à corriger avant de considérer ce filtre comme exploitable pour mesurer une performance backtestée.

2. **[Critique] Le boost n’est pas réellement identique entre live et backtest.**  
   En live, `risk_management/batch_diagnostics.py` multiplie directement `approved_shares` et `target_notional`, après la construction du portefeuille et ses contraintes de risque. Le `target_weight` n’est pas ajusté. Cela peut rendre incohérents poids, notionnel et quantité, et potentiellement dépasser une limite déjà validée.

   En backtest, `backtesting/cli/_impl.py` multiplie à la fois `proba_long` **et** `proba_short` pour tout symbole préféré, quel que soit son `predicted_side`. Ce n’est pas un boost de sizing strict : cela peut modifier le ranking et la sélection des candidats. Le document indique une « parité live ↔ backtest » qui n’est donc pas exacte.

3. **[Moyen] Les tests du backtest ne testent pas le chemin réel `_run_backtest()`.**  
   `tests/test_batch_diagnostics_backtest.py` définit une fonction locale qui reproduit la logique du backtest, au lieu d’appeler le bloc de `backtesting/cli/_impl.py`. Les tests couvrent bien les règles d’exclusion et le clipping à `1.0`, mais ils ne détecteraient pas un changement ou une suppression de l’intégration réelle dans le CLI.

## Ce qui est correctement implémenté

- La persistence est appelée après un batch comportant au moins un entraînement complété dans `modelFactory/orchestrator.py`.
- Les catégories sont conformes au document dans `modelFactory/batch_diagnostics.py` :
  - `bottom` et `weak_long` excluent le long ;
  - `bottom`, `zero_short`, `weak_short` excluent le short ;
  - le top est limité par `prefer_top_n`.
- Le live applique exclusion puis boost avant `persist_decisions()` et `persist_portfolio_targets()` dans `risk_management/cli.py`.
- Le backtest applique l’exclusion avant la reconstruction des signaux et des candidats, donc le filtre a un effet réel.
- La configuration déclarée dans `config.yaml` correspond bien aux paramètres consommés par le code : `top_n`, `bottom_n`, seuils weak, `prefer_top_n`, multiplicateur.
- Les erreurs DB restent non bloquantes, conformément au document.

## Verdict

| Surface | Filtrage | Boost | Parité/PIT |
|---|---|---|---|
| Persistence batch | ✅ | — | ✅ |
| Live Risk | ✅ | ⚠️ après les contraintes, poids non mis à jour | ❌ dernier batch au lieu du batch promu |
| Backtest | ✅ | ⚠️ modifie les probabilités, pas directement le sizing | ❌ look-ahead et batch potentiellement différent |
| Tests | ✅ règles unitaires | ✅ clipping | ⚠️ pas d’intégration réelle du CLI |

Le mécanisme est donc présent et fonctionnel au niveau des règles, mais **il ne faut pas l’utiliser pour valider une performance de backtest tant que la sélection PIT du batch de diagnostics n’est pas reliée au `ml_batch_id` et à la date simulée**.
