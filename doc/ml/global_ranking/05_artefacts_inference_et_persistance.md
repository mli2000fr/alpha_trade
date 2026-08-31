# 5 — Artefacts, inférence et persistance

## Répertoire d’artefacts

L’entraînement écrit un modèle par horizon :

| Extension | Backend |
|---|---|
| `_global_ranking_model_H.txt` | LightGBM Booster |
| `_global_ranking_model_H.pkl` | CatBoost |
| `_global_ranking_model_H.json` | XGBoost |

Le code d’inférence choisit le type par l’extension existante, ce qui permet à
chaque horizon de conserver son backend champion. En mode championnat, un seul
fichier gagnant doit représenter chaque horizon.

## Manifeste `_global_ranking_features.json`

Le manifeste contient notamment :

- liste générale et listes de features par horizon ;
- backend effectif et champions par horizon ;
- meilleur horizon et scores associés ;
- horizons présents et chemins sauvegardés ;
- feature set, benchmark et flags `include_*` ;
- activation cross-sectionnelle/directionnelle ;
- détails des horizons et splits ;
- IC, spreads de déciles, effectifs, lignes OOS et nombre de splits.

Le backend global `model_name` est le champion majoritaire lorsque les horizons
ont des gagnants différents ; pour charger un horizon, l’extension du fichier
reste l’autorité opérationnelle.

## Caches parquet

`global_rank_cache.parquet` contient les rangs OOS assemblés et sert au backtest
ou au backfill SQL. L’orchestrateur peut également écrire
`_global_rank_cache.parquet` pour l’injection stacking dans le cache
cross-sectionnel. Ces noms proches répondent à des chemins différents : vérifier
le producteur avant de les remplacer.

## Inférence courante

`predict_global_rank` :

1. lit le manifeste ;
2. recharge le benchmark si le contrat l’exige ;
3. reconstruit features par symbole et cross-sectionnelles ;
4. garde la dernière ligne de chaque symbole ayant assez d’historique ;
5. recrée rangs et features sector-neutral ;
6. aligne les colonnes dans l’ordre attendu ;
7. charge le modèle propre à chaque horizon ;
8. prédit un score continu ;
9. convertit les scores en percentiles par date.

Moins de 20 lignes de barres entraîne l’exclusion du symbole dans ce chemin.
Une erreur sur un symbole est attrapée et le symbole peut être omis. Un modèle
d’horizon absent ou une prédiction en erreur produit une colonne neutre à `0.5`.
L’absence du manifeste ou de toute frame valide renvoie `None`.

## Prédiction historique

`predict_global_rank_history` résout les dates de marché, l’univers de chaque
date, charge les barres nécessaires, appelle le prédicteur et upsert les rangs.
Ce chemin sert à construire une histoire admissible au backtest et à préremplir
la dépendance de certains traitements Oracle.

## Table `global_rank_history`

Le contrat logique possède :

```text
symbol, date, global_rank_3, global_rank_5,
global_rank_10, global_rank_15, global_rank_20,
batch_id, created_at
```

Clé primaire : `(symbol,date,batch_id)`. Les index par date et par
`(batch_id,date)` supportent les lectures. Les fonctions d’upsert inspectent les
colonnes disponibles pour tolérer certains schémas historiques ; les migrations
du dépôt restent la source d’état réel d’une base.

## Backfill

`backfill_global_rank_history.py` charge le parquet d’un batch, détecte les
colonnes d’horizon disponibles et upsert par chunks. Il ne réentraîne ni ne
recalcule les rangs. Avant usage, vérifier que le parquet appartient au batch et
au contrat attendus.

