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

## Sélection des features depuis la page Pipeline

Hors bundle directionnel, la case « Entraîner aussi le modèle Oracle Extreme » affiche un sélecteur conditionnel :

- `Dynamique (selon les features cochées)` conserve le contrat O0 sans `global_rank_20`, utilise le `feature_set` demandé et ajoute les familles optionnelles activées dans l'écran (sentiment, screener, short score, macro, fondamentaux, facteurs, composants de score et volume) ;
- un fichier `*.json` de `config/features/oracle/` impose sa liste ordonnée de colonnes et ses `generator_options`. Les cases manuelles ne déterminent alors plus le contrat Oracle ;
- si la case Oracle est décochée, le sélecteur n'est pas affiché et aucun profil Oracle hors bundle n'est transmis ;
- dans un bundle Oracle + LONG/SHORT, le sélecteur à trois profils reste le seul contrat applicable.

La sélection JSON hors bundle est transmise par `--standalone-oracle-feature-profile <fichier.json>`. L'absence de ce paramètre signifie « dynamique ». Le contrat effectivement résolu est persisté dans `artifacts/models/<batch>/oracle/feature_profile.json` et auprès des champions Oracle, puis relu par la prédiction afin de reconstruire exactement les mêmes colonnes.

## Walk-forward

Chaque fold causal sélectionne uniquement les labels disponibles avant le test, valide T2, réentraîne, prédit le test et conserve `fold_start`. Les modes fixes/adaptatifs doivent publier dates effectives, minimum train, tailles validation/test, pas et nombre de folds.

Les sorties OOS vont sous `artifacts/models/oracle/<run_id>/` et dans la table spécialisée. Les champions sont sous `artifacts/models/oracle/champions/<batch_id>/` avec manifeste, `t_start`, fichier LightGBM et feature columns.

## Calibration/combinaison

`combine.py` recherche méthodes, poids et isotonic en séparant selection folds et final folds. Ajuster sur selection, geler une seule variante, évaluer une fois sur final et conserver une baseline non calibrée.

`apply_oracle_calibration(..., method="isotonic")` exige désormais un `calibration_df` explicite, distinct du DataFrame évalué. Il est interdit d'utiliser implicitement les labels `oracle_extreme10` de la fenêtre de backtest pour ajuster puis évaluer la même fenêtre. Un jeu de calibration absent, incomplet ou inférieur à 50 lignes provoque une erreur au lieu d'un fallback silencieux.

Le backtest strict ne dispose actuellement pas d'un artefact de calibration Oracle gelé et daté antérieurement à la période. Il utilise donc `proba_extreme` OOS brute (`oracle.calibration: none`). C'est le contrat adapté à `extreme_gate`, qui reclasse déjà quotidiennement les scores en percentiles. Une future réactivation d'isotonic exigera un artefact contenant au minimum la courbe, la période de fit, le batch source et une date de disponibilité antérieure au début du backtest.

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

