# Panel screener PIT dense sur la population Oracle

## Objectif

Le screener de production persiste principalement les symboles qui ont déjà
survécu à ses filtres. C'est correct pour le serving, mais cela biaise une étude
cherchant les règles capables de distinguer les futurs mouvements haussiers et
baissiers après l'Oracle Extreme.

`modelFactory.dense_screener_panel` produit donc un artefact de recherche
séparé. Il n'écrit ni dans `stock_scores`, ni dans `stock_scores_history`.

## Population et chronologie PIT

1. Le cache `_oracle_oof_gate.parquet` fournit la population quotidienne Oracle
   en Walk-Forward OOF.
2. Seules les lignes réellement disponibles OOF sont recevables.
3. Les facteurs sont calculés sur toute la population, avant rejet.
4. `oracle_top_pool` marque ensuite le TOP20 (`percentile >= 0,80`).
5. Une ligne datée `t` n'utilise que des barres `date <= t`.

Calculer les percentiles seulement au sein du TOP20 changerait leur définition;
le module évite explicitement cette erreur.

## Formules fidèles au screener actuel

- `liquidity_val`: moyenne 30 barres de `adj_close × volume`;
- `relative_strength_index`: ratio du rendement symbole au rendement SPY sur
  183 jours calendaires, multiplié par 100;
- `historical_range_score`: position du close ajusté dans le range des 504
  derniers jours calendaires; les barres `is_filled=1` sont exclues des bornes;
- score composite: liquidité 15 %, force relative 55 %, range 30 %.

`total_score_dense` utilise toute la population disponible. Le champ
`total_score_survivors` reproduit le classement parmi les seuls symboles ayant
passé les quatre filtres, comme la population scorée en production.

## Rejets et données absentes

Aucune ligne n'est supprimée en cas d'échec. Les colonnes `filter_*_pass` et
`rejection_reasons` expliquent la décision. Les colonnes
`feature_available_*` distinguent une valeur observée d'une valeur absente;
aucun zéro artificiel n'est injecté.

## Artefacts

Sous `artifacts/research/screener_dense/`, chaque run produit:

- `dense_screener_panel.parquet`: population Oracle OOF complète;
- `oracle_top20_screener_panel.parquet`: extraction TOP20;
- `coverage.json`: dimensions et configuration;
- `feature_dictionary.json`: dictionnaire et formules;
- `quality_report.csv`: couverture et taux de passage des gates.

## Commande

```powershell
python -m modelFactory.dense_screener_panel --oracle-batch-id model-factory-20260904192500-0802c8 --pool-pct 0.20
```

`--start-date` et `--end-date` bornent un smoke test. Aucun téléchargement
supplémentaire n'est requis pour cette première version technique fondée sur
`stock_bars_daily`. Les quotes anciennes, révisions d'earnings et sources non
garanties PIT ne sont volontairement pas imputées.
