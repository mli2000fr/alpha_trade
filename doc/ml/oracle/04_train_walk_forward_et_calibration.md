# Oracle Extreme — entraînement, walk-forward, calibration et métriques

Retour : [dossier Oracle](README.md)

## Estimateurs

Le LightGBM binaire courant utilise objectif binary/AUC, learning rate 0,05, 31 leaves, minimum 50 rows/leaf, feature et bagging fractions 0,8, seed 42, pondération négatifs/positifs et early stopping 20 sur 400 rounds nominaux.

CatBoost utilise Logloss/AUC, profondeur 6, 300 itérations, même learning rate, poids de classe, early stopping 20, seed 42 et `allow_writing_files=False`. Des régresseurs LightGBM/CatBoost existent pour les diagnostics continus.

Ces defaults décrivent le code actuel ; les métadonnées d’un artefact historique font autorité.

## Métriques

`roc_auc()` calcule Mann–Whitney et retourne null si une classe manque. `precision_recall_at_top_pct()` sélectionne chaque jour `ceil(n×pct)` meilleurs scores, avec minimum 20 symboles, puis moyenne précision/rappel entre dates.

Comme la cible réunit deux queues de 10 %, son taux positif approche 20 %. La baseline aléatoire de l’ancien Oracle TOP seul (10 %) n’est pas la baseline correcte d’Oracle Extreme.

`decile_monotonicity()` groupe le score quotidien en dix bandes, agrège mean/median/count de future return et calcule Spearman. Pour une cible symétrique d’amplitude, compléter avec taux d’extrêmes et rendement absolu par décile.

## Ablations

`run_ablation()` construit dataset, train/validation, baseline rank puis O0/O1/O2. Il refuse implicitement une matrice vide ou une target constante. `evaluate_model()` correspond au Booster LightGBM utilisé dans ce chemin ; CatBoost nécessite ses méthodes propres.

## Walk-forward

Chaque fold causal sélectionne uniquement les labels disponibles avant le test, valide T2, réentraîne, prédit le test et conserve `fold_start`. Les modes fixes/adaptatifs doivent publier dates effectives, minimum train, tailles validation/test, pas et nombre de folds.

Les sorties OOS vont sous `artifacts/models/oracle/<run_id>/` et dans la table spécialisée. Les champions sont sous `artifacts/models/oracle/champions/<batch_id>/` avec manifeste, `t_start`, fichier LightGBM et feature columns.

## Calibration/combinaison

`combine.py` recherche méthodes, poids et isotonic en séparant selection folds et final folds. Ajuster sur selection, geler une seule variante, évaluer une fois sur final et conserver une baseline non calibrée.

Isotonic crée potentiellement des plateaux ; documenter les égalités dans le percentile. Aucune calibration ne transforme l’amplitude extrême en direction.

## Validation trading

Comparer mêmes dates, univers, direction, risque, capacité, lifecycle, coûts et intrabar. Les anciens résultats stop 3,5 ATR/time-stop actif appartenaient à un lifecycle de recherche et ne valident pas PROD.

Publier overlap baseline/Oracle, trades communs/ajoutés/retirés, exposition, turnover, PF, Sharpe, DD, PnL et exit reasons. Le niveau trading décide après les métriques ML.

## Commandes

```powershell
python -m modelFactory.oracle.train --batch-id <batch> --horizon 20
python -m modelFactory.oracle.walk_forward --batch-id <batch> --horizon 20 --ablation O0
python -m modelFactory.oracle.combine --oos-path <predictions.parquet>
```

Toujours vérifier `--help` : dates et options historiques peuvent avoir évolué.

