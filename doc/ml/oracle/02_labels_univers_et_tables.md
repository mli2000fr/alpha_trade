# Oracle Extreme — labels, univers, calendrier et tables

Retour : [dossier Oracle](README.md)

## Construction de l’univers

`build_labels()` commence par charger les couples `(date, symbol)` de `global_rank_history` pour le batch et l’horizon. Il compare ensuite cet ensemble au run synthétique `model_predictions` dont l’id est `<batch_id>_globalrank_synth`.

`check_universe_equality()` publie tailles, écarts et échantillons. Avec `strict_universe=True`, la moindre divergence arrête le run. Avec false, le code utilise l’univers des ranks et journalise l’écart ; ce mode est un outil d’arbitrage, pas une garantie de parité.

Deux fallbacks standalone existent si aucun rank n’est disponible :

- si des symboles sont fournis, l’univers est dérivé de leurs barres sur la fenêtre ;
- sinon, les symboles déjà présents dans les labels du batch sont relus, puis les couples date/symbole viennent des barres.

Ces fallbacks permettent `--oracle-model-only`, mais ils ne sont pas identiques à l’univers historique du Global Ranking. Le summary doit préciser le chemin utilisé.

## Prix et rendement futur

La matrice de prix lit `COALESCE(adj_close, close)` dans `stock_bars_daily`, ordonne par date/symbole/source, garde le dernier doublon puis pivote et applique `ffill`.

Pour une date D et une position `pos` dans l’index :

`future_return = close[pos + horizon] / close[pos] - 1`.

L’exit date est la date de séance à `pos+horizon`. L’available date est la séance suivante si elle existe. Les dernières dates sans horizon futur complet ne sont pas stockées.

Le `ffill` mérite une attention particulière : il permet une matrice dense mais peut faire porter un prix ancien à un symbole suspendu/délisté. Les audits de qualité doivent mesurer l’âge effectif des observations et ne pas confondre disponibilité matricielle et tradabilité.

## Rang cross-sectionnel

`compute_cross_sectional_ranks()` supprime les rendements non finis puis calcule :

- `oracle_pct_rank = rank(method="max") / n` ;
- `oracle_decile = ceil(percentile × 10)`, borné 1–10 ;
- `oracle_extreme10 = percentile >= 1-top_pct OR percentile <= top_pct`.

Un minimum de 20 observations finies est exigé par date. Sous ce seuil, les rows restent présentes mais les champs de rang/label sont nulls.

La méthode `rank(method="max")` affecte les égalités. La proportion positive peut dépasser exactement 20 % si beaucoup d’égalités touchent les seuils. Les rapports doivent publier population et taux positif réels.

## Table `global_oracle_labels`

Clé primaire : `prediction_date, symbol, batch_id, horizon`.

| Colonne | Sémantique |
|---|---|
| `prediction_date` | date D |
| `symbol` | symbole dans l’univers |
| `batch_id` | batch source |
| `horizon` | nombre de séances futures |
| `future_return` | rendement réalisé |
| `oracle_pct_rank` | percentile futur intra-date |
| `oracle_decile` | décile futur |
| `oracle_extreme10` | appartenance à une queue |
| `oracle_exit_date` | séance D+H |
| `oracle_available_date` | première date d’usage du label |
| `created_at` | écriture DB |

Les index couvrent batch/date et available date. L’upsert remplace les valeurs calculées pour une même clé et met à jour `created_at`.

## Persistance incrémentale

Les écritures SQL sont chunkées par 2 000 rows. La boucle flush les rows accumulées à partir de 5 000 afin qu’une interruption ne perde pas tout le calcul. Chaque flush appelle d’abord l’assertion de disponibilité.

Le run peut donc laisser un préfixe cohérent mais partiel. Le summary contient rows, labeled, unavailable, skipped dates et symboles. Une reprise est idempotente grâce à la clé primaire et à `ON DUPLICATE KEY UPDATE`.

En dry-run, aucune écriture n’est réalisée et le summary porte `status=dry_run`. La validation T1 est néanmoins exécutée sur les rows restant en mémoire. Pour un très gros dry-run, noter que le chemin n’effectue pas les flushs intermédiaires persistants.

## Table `oracle_extreme_predictions`

Clé primaire : `prediction_date, symbol, batch_id`. Elle contient :

- `proba_extreme` obligatoire ;
- `future_return` et `oracle_extreme10` optionnels ;
- `fold_start` pour rattacher le champion ;
- batch et timestamp.

Cette table cumule les campagnes. Une lecture sans batch mélangerait des modèles incompatibles ; le loader refuse donc par défaut un batch vide.

## États d’erreur

| Raison/statut | Interprétation |
|---|---|
| exception strict universe | ranks et predictions divergent |
| `empty_universe` | aucun couple date/symbole |
| `empty_window` | bornes hors univers |
| `no_bars` | matrice de prix vide |
| rows unavailable | prix futur ou rang absent |
| skipped dates | date de l’univers absente de la matrice |

## Contrôles après build

1. Comparer tailles ranks/predictions.
2. Vérifier nombre de symboles par date.
3. Mesurer valeurs nulles et taux positif.
4. Vérifier `exit_date > prediction_date`.
5. Vérifier `available_date > prediction_date`.
6. Inspecter fin de série et symboles avec ffill long.
7. Relancer une plage et confirmer idempotence.
8. Rapprocher le batch et l’horizon des consumers.

