# Audit ML ModelFactory - Leakage, cohérence et correctifs

**Date d'audit :** 2026-08-03  
**Périmètre lu :** `doc/module_model_factory.md`, `modelFactory/{dataset,features,cross_sectional,global_ranking,tabular_baseline,trainer,trainer_sector,orchestrator,predictor}.py`, configuration et tests associés.  
**Modes examinés :** global ranking, per-symbol, per-sector, mono-horizon et multi-horizon, avec ou sans features cross-sectionnelles / stacking.  
**Méthode :** lecture statique des chemins de données et de leurs tests. Aucun batch historique n'a été relancé dans cet audit ; les métriques déjà documentées ne doivent donc pas être considérées comme revalidées.

## Résumé exécutif

Le module ne peut pas être déclaré globalement « sans data leakage » dans son état actuel.

* **Per-sector est bloquant et non exploitable** : les barres de plusieurs symboles sont concaténées puis passées à une préparation prévue pour une série unique. Les indicateurs `rolling` et les `shift(-h)` traversent les symboles. Les labels, features et horizons sectoriels sont alors faux. De plus, aucun chemin d'inférence ne résout ni ne sert les artefacts sectoriels.
* **La régression per-symbol / per-sector fuit la distribution future de la target** : la winsorisation à 1 % / 99 % est calculée sur l'historique complet avant tout split. La standardisation ultérieure est bien fitée sur train dans les baselines, mais elle ne répare pas cette fuite initiale.
* **Le Global Ranking ne garantit pas des folds par date entière** : les splits sont calculés en lignes à partir d'un nombre médian de symboles. Si la couverture varie, une date peut être coupée entre train et validation. Cela contredit le contrat de ranking cross-sectionnel et rend les rangs/neutralisations pré-calculés dépendants du sous-ensemble de validation.
* Plusieurs résultats et affirmations de la documentation ne sont pas reproductibles depuis le code : lissage déclaré retiré mais actif, hyperparamètres CatBoost du ranking annoncés mais non utilisés, fondamentales annoncées dans des chemins où elles sont expressément exclues, et per-sector annoncé avec `symbol` catégoriel alors que cette colonne n'est jamais fournie aux modèles.

**Décision recommandée :** désactiver `training_mode=per_sector`, le stacking et toute publication de nouveaux résultats de régression jusqu'aux correctifs P0/P1 et à leur validation OOS. Réentraîner ensuite tous les artefacts et refaire les backtests ; les scores sectoriels existants ne doivent pas guider le trading.

## Grille de sévérité

| Sévérité | Signification |
|---|---|
| P0 / Critique | Résultat invalide, modèle impossible à servir, ou contamination structurelle des données. Bloque la mise en production. |
| P1 / Haute | Fuite ou incohérence susceptible de fausser les métriques ou le contrat entraînement/inférence. Corriger avant de comparer des modèles. |
| P2 / Moyenne | Risque de robustesse, métrique ambiguë ou contrat incomplet. Corriger avant industrialisation. |
| P3 / Documentation | Documentation ou configuration trompeuse, sans être seule une fuite. |

## Constats confirmés

### P0-1 - Per-sector mélange les séries des symboles

**Preuve.** Dans `modelFactory/trainer_sector.py`, `_prepare_sector_data` charge les barres de chaque titre, les concatène, puis les trie en `(date, symbol)` avant d'appeler `prepare_symbol_frame` ([trainer_sector.py](modelFactory/trainer_sector.py#L64)). Cette dernière appelle `compute_features`, puis `build_multi_horizon_targets` ou `build_target` sur le DataFrame reçu ([dataset.py](modelFactory/dataset.py#L732)). Ces fonctions utilisent des `rolling(...)` et `shift(-h)` sans `groupby("symbol")` ([features.py](modelFactory/features.py#L1245)).

Pour deux titres `AAA`, `BBB` et un ordre `(J0/AAA, J0/BBB, J1/AAA, J1/BBB)`, le `shift(-3)` de `J0/AAA` peut lire le prix de `J1/BBB`, et une fenêtre de volatilité peut contenir alternativement les deux titres. Ce n'est ni un rendement forward de `AAA`, ni une feature calculable en production. Le problème existe en mono-horizon et sur chaque `target_h*` du multi-horizon.

**Impact.** Toutes les métriques per-sector annoncées, y compris les F1 0.486-0.544 du document, sont invalidées. C'est avant tout une corruption de dataset ; elle introduit aussi une dépendance indue aux observations d'autres titres et peut créer un apparent signal prédictif.

**Correctif.** Préparer chaque symbole indépendamment, puis concaténer des frames déjà feature-engineered et labellisés :

1. charger et trier les barres d'un symbole ;
2. appeler `prepare_symbol_frame` pour ce seul symbole, sans neutraliser la target ;
3. concaténer les frames par `(date, symbol)` ;
4. calculer la target sector-neutre sur cette matrice déjà correcte, par `(date, secteur)` ;
5. découper exclusivement par dates, puis entraîner.

Ne jamais appeler une fonction qui suppose une série temporelle unique sur un panel multi-symboles sans groupby explicite. Une alternative plus robuste est de faire évoluer `compute_features`, `compute_future_return`, `build_target` et `build_multi_horizon_targets` pour grouper par symbole lorsque la colonne est présente, puis de les tester sur un panel.

**Tests P0 requis.** Construire deux séries volontairement très différentes et vérifier, pour chaque symbole et horizon $h$, que :

$$r_{s,t,h}=\frac{close_{s,t+h}}{close_{s,t}}-1$$

La valeur obtenue ne doit pas changer si l'ordre des symboles du panel est permuté ni si un symbole supplémentaire est ajouté.

### P0-2 - Les modèles per-sector ne sont pas servis par l'inférence

**Preuve.** Les artefacts sectoriels sont écrits dans `artifacts/.../_sector_<secteur>/h*/...` ([trainer_sector.py](modelFactory/trainer_sector.py#L339)). Leur configuration conserve le secteur et les symboles, mais aucun routage de modèle exploitable ([trainer_sector.py](modelFactory/trainer_sector.py#L471)). `_persist_sector_metrics` enregistre des chemins vides dans `artifact_routes` ([trainer_sector.py](modelFactory/trainer_sector.py#L211)). `predictor.py` ne contient aucune résolution de secteur ni de dossier `_sector_`; il résout les artefacts depuis le symbole demandé et ne connaît que les backends global, LightGBM, CatBoost et LSTM ([predictor.py](modelFactory/predictor.py#L1336)).

**Impact.** Un champion per-sector ne peut pas être sélectionné pour `AAPL` en live/backtest. Même après correction des données, le mode n'a pas de parité entraînement/inférence.

**Correctif.** Définir un vrai contrat sectoriel : `symbol -> secteur -> horizon -> champion -> artefact`, enregistrer des chemins réels et ajouter un routeur dans `predict_symbol`. Ce routeur doit aussi reconstruire exactement les features sectorielles à la date de cutoff, avec le même univers et la même taxonomie GICS. Ajouter des tests E2E entraînement minimal -> registre -> prédiction sur un symbole du secteur.

### P0-3 - Le prétendu `symbol` catégoriel per-sector n'est jamais utilisé

Le document affirme que `symbol` est une feature catégorielle per-sector. `_prepare_sector_data` l'ajoute bien à une variable locale `feature_cols` ([trainer_sector.py](modelFactory/trainer_sector.py#L154)). Mais `run_tabular_baseline` et `run_tabular_walk_forward` recalculent ensuite leurs propres `feature_columns` via `get_feature_columns` et ne reçoivent pas cette liste ([tabular_baseline.py](modelFactory/tabular_baseline.py#L397), [tabular_baseline.py](modelFactory/tabular_baseline.py#L847)). La colonne `symbol` est donc absente de `X_train` et `X_test`.

**Impact.** Le comportement réel contredit la conception documentée. Les modèles n'apprennent aucune composante spécifique au titre via cette feature. Cela masque aussi le fait qu'aucun encodage catégoriel n'est configuré pour CatBoost (`cat_features`) ou LightGBM (dtype `category` / encodage).

**Correctif.** Ajouter un paramètre obligatoire `feature_columns` aux deux helpers tabulaires, persister cette liste dans le contrat, puis :

* CatBoost : fournir l'index/nom de `symbol` dans `cat_features` ;
* LightGBM : convertir en `category` de manière stable, ou utiliser un encodage fit sur train seulement avec une valeur inconnue ;
* inférence : aligner les catégories à l'artefact.

Ne pas utiliser un encodage target sur toutes les dates ; il faudrait être calculé OOF dans le train puis figé pour validation/test.

### P1-1 - Winsorisation de la target de régression sur l'historique complet

**Preuve.** En `regression`, `build_target` calcule les bornes avec `target.quantile(0.01)` et `target.quantile(0.99)` avant tout split ([features.py](modelFactory/features.py#L1279)). `build_multi_horizon_targets` répète ce comportement pour chaque horizon ([features.py](modelFactory/features.py#L1314)). `prepare_symbol_frame` est exécuté avant le split ([dataset.py](modelFactory/dataset.py#L713)).

Les données de train sont donc transformées avec des quantiles observés dans validation/test et dans les régimes futurs. La standardisation train-only est correcte dans `run_tabular_baseline` ([tabular_baseline.py](modelFactory/tabular_baseline.py#L427)) et dans chaque fold WF ([tabular_baseline.py](modelFactory/tabular_baseline.py#L888)), mais intervient après la fuite.

**Impact.** Per-symbol regression et per-sector regression, avec et sans multi-horizon. Le biais est moins visible que le fuite par label, mais rend les métriques OOS optimistes, surtout lors de changements de volatilité.

**Correctif.** Séparer la génération du rendement/vol-scaling de la calibration robuste : générer une target brute, faire le split, fit les quantiles sur `train.target` du split/fold, appliquer les bornes gelées à train/val/test. Pour un walk-forward, chaque fold doit avoir ses propres bornes. Conserver `winsor_lower`, `winsor_upper`, moyenne et écart-type dans l'artefact et dans les métriques de fold.

### P1-2 - Global Ranking : splits par lignes, pas par dates atomiques

**Preuve.** `base_df` est trié par `(date, symbol)` ([global_ranking.py](modelFactory/global_ranking.py#L866)). Le ranking estime un nombre de titres quotidien médian, multiplie les tailles en jours par ce nombre, puis appelle `generate_walk_forward_splits`, la version indexée par lignes ([global_ranking.py](modelFactory/global_ranking.py#L925)). Cette fonction tranche avec `iloc` ([dataset.py](modelFactory/dataset.py#L105)). Elle ne vérifie jamais qu'une date n'appartient qu'à un seul morceau.

Un univers réel contient des IPO, suspensions, jours manquants et exclusions, donc le nombre de lignes n'est pas constant. Une frontière peut couper une date. Or les ranks XS et features sector-neutral sont calculés auparavant sur le panel complet ([global_ranking.py](modelFactory/global_ranking.py#L881)), tandis que les targets sont ensuite calculées séparément par morceau ([global_ranking.py](modelFactory/global_ranking.py#L1005)). Le train et la validation peuvent alors partager le contexte cross-sectionnel d'une même date, et le classement / la neutralisation ne portent pas sur un univers cohérent.

**Impact.** Global ranking, toutes les options XS/sector-neutral/factor-neutral, et stacking dérivé de ses rangs. Le code P1 post-split protège le `shift` de traverser une frontière, mais ne protège pas l'atomicité cross-sectionnelle par date.

**Correctif.** Remplacer le split global par `generate_walk_forward_splits_by_dates`, avec `min_train_dates`, `val_dates`, `test_dates`, `step_dates` en jours de bourse. Purger/embargo doivent aussi être exprimés en dates. Ajouter une assertion bloquante pour chaque fold :

```python
assert set(train.date).isdisjoint(val.date)
assert set(val.date).isdisjoint(test.date)
assert set(train.date).isdisjoint(test.date)
```

Puis calculer toutes les opérations cross-sectionnelles de la date entière dans le fold auquel elle appartient. Une neutralisation intra-date est PIT-compatible seulement si la même date est servie avec le même univers en backtest/live.

### P1-3 - Les contrats de features ne propagent pas toutes les options

`prepare_symbol_frame` peut calculer fondamentales, facteurs et régime macro ([dataset.py](modelFactory/dataset.py#L732)). Mais ses `active_features` omettent `include_fundamentals` ([dataset.py](modelFactory/dataset.py#L773)). Les deux helpers tabulaires omettent également `include_fundamentals`, `include_factors` et `include_macro_regime` dans leurs appels à `get_feature_columns` ([tabular_baseline.py](modelFactory/tabular_baseline.py#L397), [tabular_baseline.py](modelFactory/tabular_baseline.py#L847)). Enfin l'orchestrateur documente explicitement les fondamentales comme réservées au global et les fixe à `False` dans `_per_symbol_features.json` ([orchestrator.py](modelFactory/orchestrator.py#L790)).

**Impact.** Des colonnes peuvent être calculées et chargées sans être utilisées, ou être annoncées par la documentation sans faire partie de l'entraînement/inférence. Les feature fingerprints peuvent alors ne pas représenter le dataset réel. Le per-sector est affecté directement ; le per-symbol ne doit pas être présenté comme utilisant les fondamentales.

**Correctif.** Construire une unique `FeatureSpec` depuis `TrainingConfig.data`, l'injecter dans préparation, LSTM, baseline, global, artefact et prédicteur. Interdire toute recomposition locale ad hoc des colonnes. Écrire un test qui active simultanément fondamentales/facteurs/régime, puis compare à l'identique : colonnes de train, contrat persisté et matrice d'inférence.

### P1-4 - Hyperparamètres du CatBoost global incohérents avec la documentation

Le document annonce un CatBoost RMSE global avec `ranking_max_depth=7` et `n_estimators=500`. Or `_build_ranking_estimator` n'utilise `ranking_max_depth` et `ranking_num_leaves` que pour LightGBM. Pour CatBoost, il utilise `cfg.baseline.catboost_depth`, `catboost_iterations` et `catboost_learning_rate` ([global_ranking.py](modelFactory/global_ranking.py#L520)). Avec les défauts actuels, cela veut dire depth 4 et 300 itérations, pas 7 et 500.

**Impact.** Les expériences de tuning et les résultats présentés comme CatBoost depth 7 ne sont pas traçables depuis la configuration effectivement appliquée.

**Correctif.** Introduire dans `GlobalModelConfig` des paramètres CatBoost dédiés (par exemple `ranking_catboost_depth`, `ranking_catboost_iterations`, `ranking_catboost_learning_rate`) et les persister dans `horizon_details`. Sinon, corriger la documentation pour afficher les valeurs `BaselineConfig` réelles.

### P1-5 - Le stacking n'a pas de couverture OOF complète

`global_rank_df` ne contient que les prédictions des partitions de validation du ranking, car les résultats sont alimentés avec `pred_part` issu de `val_df` ([global_ranking.py](modelFactory/global_ranking.py#L1130)). L'orchestrateur les merge ensuite dans les features per-symbol et remplit toute date absente par 0.5 ([orchestrator.py](modelFactory/orchestrator.py#L759)).

**Impact.** Les modèles per-symbol entraînent/évaluent potentiellement sur un mélange de ranks OOF et de rangs neutres. La performance du stacking dépend alors de la position temporelle des folds, sans métrique de couverture. Ce n'est pas une fuite si chaque rank présent est réellement OOF, mais c'est un contrat incomplet et un biais de comparabilité.

**Correctif.** Produire des prédictions OOF pour chaque date utilisable, versionnées par fold, et refuser le stacking si la couverture sur chaque split per-symbol est inférieure à un seuil explicite. Rapporter `coverage_global_rank` par train/val/test/WF. Pour l'inférence live, ne jamais confondre une valeur 0.5 de fallback avec une vraie prédiction : stocker une colonne `global_rank_available`.

### P2-1 - Les métriques globales ne sont pas calculées comme un IC quotidien

Dans la boucle globale, `compute_ic_rank` reçoit l'ensemble de `pred_part` du fold, pas une moyenne d'IC calculés date par date ([global_ranking.py](modelFactory/global_ranking.py#L1125)). Les labels sont des ranks par date, alors qu'un Spearman poolé mélange les distributions de dates différentes. La fonction dédiée `compute_cross_sectional_ic` montre pourtant le pattern attendu par date ([global_ranking.py](modelFactory/global_ranking.py#L379)).

**Impact.** L'IC affiché ne correspond pas exactement à la définition cross-sectionnelle décrite dans la documentation. Il peut être sensible à la composition des dates et au nombre de symboles.

**Correctif.** Calculer l'IC Spearman par date avec un minimum de symboles, puis rapporter moyenne pondérée/non pondérée, écart-type, IR et nombre de dates. Conserver aussi l'IC poolé si nécessaire, mais avec un nom différent.

### P2-2 - La sélection du champion sectoriel est figée sur H15

Le code prend `h15` comme horizon primaire dès qu'il existe ([trainer_sector.py](modelFactory/trainer_sector.py#L424)), alors que le contrat général dit que l'horizon primaire est `forecast_horizon` / maximum configuré. Cela peut choisir le mauvais champion quand les horizons fournis ne sont pas centrés sur 15 ou quand l'exécution attend H20.

**Correctif.** Employer `f"h{cfg.data.forecast_horizon}"` et échouer explicitement si ce résultat n'existe pas. Persister un champion par horizon, ou exposer clairement un champion primaire unique et la règle de sélection.

### P2-3 - Les assertions de purge testent des jours calendaires, pas des sessions

`validate_fold_isolation` compare des différences de dates calendaires (`.days`) à un horizon exprimé en sessions ([dataset.py](modelFactory/dataset.py#L249)). Un week-end peut faire croire qu'une purge de 5 sessions est respectée alors qu'il n'y a que 3 séances. Les tests utilisent majoritairement `freq="D"` ([tests/test_model_factory_dataset.py](tests/test_model_factory_dataset.py#L22)).

**Correctif.** Vérifier les positions dans l'index ordonné de séances uniques, pas le nombre de jours calendaires. Construire des tests avec jours de bourse et week-ends.

### P2-4 - Pré-calcul cross-sectionnel : compatible PIT sous conditions non garanties

Les ranks et médianes cross-sectionnels de `cross_sectional.py` sont calculés par date sur tous les symboles chargés ([cross_sectional.py](modelFactory/cross_sectional.py#L644), [cross_sectional.py](modelFactory/cross_sectional.py#L567)). Ce n'est **pas automatiquement du leakage temporel** : à la clôture de $t$, les données disponibles de tous les titres de l'univers à $t$ peuvent légitimement servir à classer les titres pour $t+1$.

La condition manquante est l'identité de l'univers : même date de cutoff, mêmes titres éligibles et mêmes données disponibles en entraînement, backtest et live. Le chargement d'un univers courant sur toute une période doit être audité spécifiquement contre une source d'appartenance PIT pour exclure le survivorship bias. Le code actuel ne persiste ni l'univers journalier, ni une empreinte du panel exact utilisé pour chaque date.

**Correctif.** Versionner un `universe_snapshot(date, symbols, eligibility_reason)` et faire dépendre chaque feature XS/sectorielle de ce snapshot. Ajouter un test qui retire un symbole à une date et vérifie un changement attendu, traçable, uniquement pour cette date.

## Constats positifs et faux positifs écartés

* **Purge multi-horizon tabulaire : correcte dans son principe.** Pour chaque horizon, `trainer.py` et `trainer_sector.py` appellent bien séparément les helpers avec `forecast_horizon_override=h` ([trainer.py](modelFactory/trainer.py#L1673), [trainer_sector.py](modelFactory/trainer_sector.py#L377)). Les helpers régénèrent leurs splits pour cet horizon ([tabular_baseline.py](modelFactory/tabular_baseline.py#L824)). H3 ne réutilise donc pas silencieusement les splits H20. Ce point reste dépendant de la correction P0-1 pour le per-sector.
* **Standardisation de régression tabulaire : correcte après split.** En train/val/test, les statistiques viennent de train ([tabular_baseline.py](modelFactory/tabular_baseline.py#L427)); en WF, elles sont recalculées par fold ([tabular_baseline.py](modelFactory/tabular_baseline.py#L888)). La fuite est la winsorisation précédente, pas cette standardisation.
* **Target global post-split : amélioration réelle.** `_compute_ranking_targets` groupe les shifts par symbole ([global_ranking.py](modelFactory/global_ranking.py#L582)) et est invoquée séparément sur train/validation ([global_ranking.py](modelFactory/global_ranking.py#L1005)). Elle évite bien que le `shift(-h)` traverse une frontière. Elle ne résout pas P1-2 si une date est coupée.
* **Médiane sectorielle de target par date : pas intrinsèquement une fuite.** La neutralisation per-sector avant split ([trainer_sector.py](modelFactory/trainer_sector.py#L95)) ne consomme pas d'information future si les splits sont strictement par dates et si les rendements individuels sont déjà corrects. Le diagnostic critique du per-sector est P0-1, non la médiane elle-même. Pour lisibilité, il reste préférable de la faire après préparation par symbole et de tracer les dates/symboles utilisés.

## Incohérences de documentation à corriger

1. Le document affirme à plusieurs endroits que le lissage est supprimé, mais `_SMOOTHING_HORIZONS = (10, 15, 20)` est actif et `_compute_ranking_targets` l'applique ([global_ranking.py](modelFactory/global_ranking.py#L58), [global_ranking.py](modelFactory/global_ranking.py#L614)). Les sections 3.2, 10.4 et 12 se contredisent elles-mêmes. Choisir un comportement, puis documenter le code réellement exécuté.
2. La table per-sector annonce `symbol` catégoriel et CatBoost depth 6 ; aucun des deux n'est garanti par le chemin effectif. Voir P0-3 et P1-4.
3. La documentation dit que le Global Ranking dispose d'une purge « 1 jour ». Le code purge un nombre de **lignes** égal au nombre médian de symboles, ce qui n'est ni une date garantie ni une session garantie ([global_ranking.py](modelFactory/global_ranking.py#L925)).
4. Elle annonce que toutes les fondamentales sont intégrées dans les modèles selon plusieurs tableaux, mais l'orchestrateur les exclut explicitement du per-symbol ([orchestrator.py](modelFactory/orchestrator.py#L790)). Distinguer clairement : global ranking, per-symbol, per-sector et inférence.
5. La partie Q/R affirme que la `directional_accuracy` de régression est évaluée contre `future_return`; le code récent l'évalue contre la target neutralisée dans `_compute_regression_metrics` ([tabular_baseline.py](modelFactory/tabular_baseline.py#L258)). C'est cohérent pour du per-sector relatif, mais pas comparable directement à une direction absolue.
6. L'affirmation « Plus de data leakage » et « l'unique source de leakage était le shift pré-split » est fausse au regard de P0-1, P1-1 et P1-2. Remplacer par une liste d'invariants vérifiés et des tests automatiques, jamais par une conclusion absolue non réexécutable.

## Plan de correction priorisé

### Phase A - Bloquer les résultats invalides

1. Désactiver `per_sector` côté CLI/IHM ou le marquer expérimental et non servi.
2. Désactiver publication/usage des artefacts sectoriels existants et des métriques associées.
3. Ajouter une alerte si un entraînement per-sector est demandé jusqu'à ce que les tests P0 soient verts.
4. Geler les comparaisons de régression existantes jusqu'au réentraînement avec clipping fit sur train.

### Phase B - Refaire le dataset sectoriel et son contrat de service

1. Introduire `prepare_panel_by_symbol(...)` : préparation symbol-by-symbol, concaténation ensuite seulement.
2. Introduire `neutralize_target_by_sector_date(...)` avec mapping GICS versionné, minimum de titres et diagnostic des secteurs incomplets.
3. Passer explicitement la liste de features jusqu'aux baselines ; ne jamais la reconstruire dans un helper.
4. Mettre en place l'encodage stable de `symbol` ou retirer cette feature de la conception/documentation.
5. Implémenter le routage live/backtest sectoriel et un manifest d'artefacts complet, par horizon.

### Phase C - Rendre tous les splits auditables

1. Remplacer les splits globaux par date entière.
2. Ajouter à chaque résultat de fold : bornes de dates, nombre de dates, nombre de symboles par date min/médiane/max, hash de l'univers et tailles après purge.
3. Échouer un fold si une date apparaît dans deux partitions, si l'horizon dépasse le gap de séances, ou si l'univers XS est sous le minimum.
4. Ajouter `FoldIsolationReport` aux résultats réels de run, pas uniquement aux tests unitaires.

### Phase D - Cadrer les transformations de target

1. Faire retourner à la construction de target une valeur brute, sans quantiles globaux.
2. Introduire un transformateur de target `fit(train) / transform(partition)` pour winsorisation et standardisation.
3. En multi-horizon, conserver un transformateur distinct par horizon et par fold.
4. Pour les artefacts finaux, refitter ce transformateur sur la fenêtre de train complète retenue et le persister.

### Phase E - Réconcilier configuration, métriques et documentation

1. Séparer réellement les paramètres Global CatBoost de `BaselineConfig` ou supprimer les options de ranking non actives.
2. Choisir et implémenter exactement une politique de smoothing ; tester H3/H5/H10/H15/H20.
3. Calculer l'IC global par date et afficher clairement le nombre de dates/symboles.
4. Générer la documentation depuis des tests de contrat ou une configuration sérialisée, pas depuis des commentaires de sprint.

## Matrice de tests à ajouter

| Test | Cible | Invariant bloquant |
|---|---|---|
| Panel permutation | per-sector | Permuter les symboles ne modifie ni features ni targets d'un titre. |
| Forward return par symbole | per-sector, chaque horizon | `future_return_h` correspond exactement au close du même symbole à $t+h$. |
| Fenêtre rolling par symbole | per-sector | Ajouter/modifier un autre titre ne change aucun rolling d'un titre donné. |
| Train-only target transform | régression | Changer uniquement val/test ne modifie pas les quantiles/targets normalisées de train. |
| Fold dates disjointes | global et sector | Aucune date partagée entre train/val/test, même avec trous et nombre de titres variable. |
| Purge en sessions | tous | Dernière séance train + horizon est strictement avant la première séance de la partition suivante. |
| Contrat features complet | tous | Matrice d'entraînement = feature contract = matrice d'inférence, ordre inclus. |
| Feature `symbol` | per-sector | La colonne est réellement reçue par chaque backend et gère une catégorie inconnue. |
| E2E sectoriel | per-sector | Un entraînement minimal produit un artefact, un routage et une prédiction pour chaque symbole du secteur. |
| Couverture OOF stacking | global + per-symbol | Toute valeur de rank utilisée pour train/validation/test est OOF ; la couverture est mesurée. |
| IC par date | global | L'agrégat est égal à la moyenne documentée des IC quotidiens. |

## Critères de sortie avant remise en service

Le mode global/per-symbol peut être considéré robuste seulement lorsque les tests de split par dates, de clipping train-only et de contrat de features sont verts dans CI. Le per-sector ne peut être remis en service qu'après les dix tests de la matrice ci-dessus, avec une prédiction E2E live/backtest par symbole et un réentraînement complet.

Après correction, effectuer un nouveau protocole : période de développement, période de sélection des hyperparamètres, puis période finale totalement gelée. Rapporter l'IC quotidien, le turnover, les coûts et les résultats par régime, avec l'univers PIT exact. Ne pas comparer aux anciens IC/F1 comme s'ils provenaient du même protocole : le dataset sectoriel et les targets de régression auront changé matériellement.
