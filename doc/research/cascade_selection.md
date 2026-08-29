# Cascade de sélection et modes de ranking

Retour : [recherche](README.md)

`modelFactory.predictor.cascade_select` centralise plusieurs modes ; leurs noms ne sont pas synonymes.

| Mode | Source/effet |
|---|---|
| `ml` | Global Rank du batch/horizon |
| `extreme_gate` | percentile Oracle quotidien, gate du pool |
| `oracle` | ranking Oracle direct selon code |
| `oracle_filter` | Oracle comme filtre du ranking principal |
| `oracle_rerank` | pool/candidats rerankés par Oracle |
| `oracle_pool` | sélection dans un pool Oracle |
| `random` | contrôle random déterministe par date/seed |

La fonction résout ranks du jour, horizon disponible, Oracle map et éventuel dip filter. Elle traite long/short, top pct, min probability, slots et saturation. Les modes Oracle-first modifient aussi l'ordre de déduplication dans la synthèse.

Le backtest peut basculer automatiquement vers `extreme_gate` selon batch/config ; le mode effectif est journalisé dans `_rank_mode_eff`. `skip_ml_coverage` peut être vrai pour extreme gate parce que la source de couverture diffère. Ce n'est pas une autorisation générale d'ignorer les données manquantes.

Pour comparer deux modes : même date/univers/batch, même nombre de slots, même dip filter et lifecycle. Archiver candidats avant/après chaque gate et raisons de saturation.

