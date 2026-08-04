# Audit ML ModelFactory - Leakage, cohérence et correctifs

**Date d'audit initial :** 2026-08-03
**Dernière vérification des correctifs :** 2026-08-04
**Périmètre lu :** `doc/module_model_factory.md`, `modelFactory/{dataset,features,cross_sectional,global_ranking,tabular_baseline,trainer,trainer_sector,orchestrator,predictor}.py`, configuration et tests associés.  
**Modes examinés :** global ranking, per-symbol, per-sector, mono-horizon et multi-horizon, avec ou sans features cross-sectionnelles / stacking.  
**Méthode :** lecture statique des chemins de données et de leurs tests. Aucun batch historique n'a été relancé dans cet audit ; les métriques déjà documentées ne doivent donc pas être considérées comme revalidées.

## Résumé exécutif

Le module ne peut pas être déclaré globalement « sans data leakage » dans son état actuel.

* **Per-sector reste à valider en E2E avant production** : le format de route tabulaire sectorielle est reconnu par le prédicteur et le contrat catégoriel `symbol` est reconstruit à l'inférence. Il manque une exécution complète base de données -> artefact -> prédiction, notamment pour CatBoost qui n'est pas disponible dans l'environnement d'audit.
* **La winsorisation de régression est maintenant correctement post-split** dans les chemins préparés : `prepare_symbol_frame` désactive le clipping global et les baselines/LSTM appliquent les bornes fit sur train. Il reste à ajouter un test automatisé de non-régression sur cette invariance.
* **Le Global Ranking découpe maintenant ses folds par dates atomiques** : la correction est présente et le risque de partage d'une date entre train/validation est levé. Il manque toutefois un test de non-régression spécifique au ranking avec un nombre de symboles variable.
* La documentation est maintenant alignée sur le smoothing actif, et CatBoost global possède ses paramètres de profondeur, itérations et learning rate dédiés. La couverture OOF du stacking est journalisée, mais ne bloque toujours pas l'emploi de valeurs neutres dans les folds concernés.

**Décision recommandée :** ne pas servir `training_mode=per_sector`, ni publier de nouveaux résultats de régression, avant les correctifs P0/P1 restants et leur validation OOS. Réentraîner ensuite les artefacts et refaire les backtests ; les scores sectoriels historiques ne doivent pas guider le trading. Le stacking reste une amélioration de design à traiter séparément (P1-5), pas un blocage de fuite confirmé.

## Grille de sévérité

| Sévérité | Signification |
|---|---|
| P0 / Critique | Résultat invalide, modèle impossible à servir, ou contamination structurelle des données. Bloque la mise en production. |
| P1 / Haute | Fuite ou incohérence susceptible de fausser les métriques ou le contrat entraînement/inférence. Corriger avant de comparer des modèles. |
| P2 / Moyenne | Risque de robustesse, métrique ambiguë ou contrat incomplet. Corriger avant industrialisation. |
| P3 / Documentation | Documentation ou configuration trompeuse, sans être seule une fuite. |

## Correctifs vérifiés et retirés des constats actifs

| Référence initiale | Statut | Vérification effectuée | Dette résiduelle |
|---|---|---|---|
| P0-1 - Panel per-sector mélangeant les séries | **Corrigé dans le code et test validé** | `trainer_sector._prepare_sector_data` appelle désormais `prepare_symbol_frame` une fois par symbole, puis concatène les frames préparées ([trainer_sector.py](modelFactory/trainer_sector.py#L73)). Les `rolling` et `shift(-h)` ne traversent donc plus les titres. Le test `test_per_sector_prepare_isolates_symbols` passe avec `feature_set="v1"` et vérifie target forward, invariance à l'ordre de concaténation et rolling volatility isolée. | Si `enable_cross_sectional_features=True`, les features XS sont actuellement laissées à leurs valeurs neutres : le commentaire annonce une fusion post-concaténation, mais le code ne la fait pas. Ce n'est pas une fuite de séries, mais une fonctionnalité manquante. |
| P1-2 - Global Ranking découpé en lignes | **Corrigé dans le code** | `train_global_ranking_wf` utilise `generate_walk_forward_splits_by_dates`, avec tailles et purge en dates ([global_ranking.py](modelFactory/global_ranking.py#L929)). Une même date ne peut plus être répartie entre train, validation et test. | Ajouter un test spécifique au Global Ranking avec un panel dont le nombre de symboles varie par date. Les tests de `dataset.py` couvrent le helper générique, pas son appel dans le ranking. |
| P2-2 - Champion sectoriel H15 hardcodé | **Corrigé dans le code** | L'horizon primaire est maintenant `f"h{cfg.data.forecast_horizon}"`, avec fallback seulement si aucun résultat n'existe à cet horizon ([trainer_sector.py](modelFactory/trainer_sector.py#L443)). Une configuration `forecast_horizons=(3,5,20)` désigne donc H20, pas H15. | Aucun test automatisé ne couvre le cas sans H15 ou le fallback. La sélection reste un champion unique sur l'horizon primaire, pas un champion distinct servi par horizon. |
| P2-1 - IC global poolé | **Corrigé dans le code** | Chaque validation de fold appelle maintenant `compute_cross_sectional_ic`, qui calcule Spearman séparément par date puis retourne `ic_mean`, `ic_std` et `n_dates` ([global_ranking.py](modelFactory/global_ranking.py#L378), [global_ranking.py](modelFactory/global_ranking.py#L1105)). Un contrôle minimal avec deux dates d'IC $+1$ et $-1$ retourne `ic_mean=0` et `n_dates=2`. | Aucun test automatisé ne verrouille l'agrégat ni l'exposition de `n_dates` dans les métriques de run. L'agrégat final reste une moyenne non pondérée des moyennes de folds. |
| P1-1 - Winsorisation de régression pré-split | **Corrigé dans le code** | `build_target` et `build_multi_horizon_targets` acceptent `skip_winsorize`; `prepare_symbol_frame` l'active pour les chemins mono et multi-horizon ([features.py](modelFactory/features.py#L1245), [dataset.py](modelFactory/dataset.py#L793)). Les winsorisations fit sur train des baselines et du LSTM prennent alors le relais. Un contrôle de mutation future confirme que les 90 premières targets restent identiques. | Aucun test pytest dédié ne couvre encore l'invariance de la target préparée ni les quantiles post-split LSTM. |
| P1-4 - Paramètres CatBoost global | **Corrigé dans le code** | `GlobalModelConfig` définit `ranking_catboost_iterations=500` et `ranking_catboost_learning_rate=0.03`, consommés par `_build_ranking_estimator` avec `ranking_max_depth` ([config.py](modelFactory/config.py#L252), [global_ranking.py](modelFactory/global_ranking.py#L546)). Un double d'estimateur confirme `depth=7`, `iterations=500`, `learning_rate=0.03` malgré des valeurs différentes dans `BaselineConfig`. | Les paramètres dédiés n'ont pas encore de test pytest ni de persistance explicite dans les détails d'horizon. |
| P0-3 - `symbol` catégoriel per-sector | **Corrigé dans le code ; validation backend/E2E à compléter** | LightGBM reçoit `symbol` en pandas `category`; CatBoost reçoit `cat_features=["symbol"]`; les catégories d'entraînement sont persistées sous `symbol_categories` et reconstruites dans `_predict_with_tabular_model` ([trainer_sector.py](modelFactory/trainer_sector.py#L245), [predictor.py](modelFactory/predictor.py#L1161)). Un contrôle LightGBM avec séparation effective confirme que `AAA`/`BBB` conservent leurs prédictions quand la catégorie `CCC` est ajoutée. | CatBoost n'est pas installé dans l'environnement d'audit. Le symbole inconnu `CCC` est accepté par LightGBM mais suit une branche apprise existante : documenter cette politique ou réserver explicitement une catégorie inconnue. Ajouter un E2E par backend. |

## Constats confirmés

### P0-2 - Routage d'inférence per-sector : format de route corrigé, E2E non validé

**Statut 2026-08-04 : partiellement corrigé, non validé E2E.** `trainer_sector` persiste maintenant `artifact_routes = {selected_model, models: {lightgbm, catboost}}` dans le `config.json`, avec `inference_backend`, `config_path` et `model_path` ([trainer_sector.py](modelFactory/trainer_sector.py#L246)). `predictor._resolve_artifact_paths` appelle bien `_resolve_sector_run` lorsque le modèle per-symbol est absent ([predictor.py](modelFactory/predictor.py#L531)). `_resolve_sector_run` utilise une requête directe `model_training_run JOIN model_governance` qui récupère le `model_path` sélectionné et n'exige plus de checkpoint/scaler LSTM ([predictor.py](modelFactory/predictor.py#L548)).

Le format est consommé correctement par `_resolve_selected_model_route` : un contrôle ciblé avec une route sectorielle LightGBM retourne `inference_backend='lightgbm_tabular'` et le `model_path` `.txt` attendu ([predictor.py](modelFactory/predictor.py#L814)). Il reste toutefois une validation E2E sur une vraie ligne de registre, un vrai config/artefact et `predict_symbol`.

**Impact.** Le mapping `symbol -> GICS -> secteur`, la route tabulaire et le contrat catégoriel sont cohérents statiquement. Aucune prédiction sectorielle tabulaire E2E n'est encore démontrée.

**Correctif restant.** Ajouter un test E2E registre -> `_resolve_artifact_paths` -> `predict_symbol` pour un symbole du secteur, par backend et horizon. Faire retourner au fallback une route tabulaire explicite plutôt qu'un `model_path` déguisé en checkpoint si cette compatibilité empêche la traçabilité.

### P1-3 - Contrat de features : correction partielle

**Statut 2026-08-04 : corrigé dans le code, test de contrat manquant.** `prepare_symbol_frame` transmet `include_fundamentals`, `include_factors` et `include_macro_regime` à `get_feature_columns` ([features.py](modelFactory/features.py#L1174)). Les deux helpers tabulaires transmettent aussi les trois flags ([tabular_baseline.py](modelFactory/tabular_baseline.py#L397), [tabular_baseline.py](modelFactory/tabular_baseline.py#L847)). `_prepare_prediction_frame` les transmet maintenant à `compute_features` ([predictor.py](modelFactory/predictor.py#L1016)).

Il reste à ajouter un test qui active simultanément les trois flags et compare la matrice entraînement, le contrat persisté et la matrice d'inférence.

**Impact.** Des colonnes peuvent être calculées et chargées sans être utilisées, ou être annoncées par la documentation sans faire partie de l'entraînement/inférence. Les feature fingerprints peuvent alors ne pas représenter le dataset réel. Le per-sector est affecté directement ; le per-symbol ne doit pas être présenté comme utilisant les fondamentales.

**Correctif.** Construire une unique `FeatureSpec` depuis `TrainingConfig.data`, l'injecter dans préparation, LSTM, baseline, global, artefact et prédicteur. Interdire toute recomposition locale ad hoc des colonnes. Écrire un test qui active simultanément fondamentales/facteurs/régime, puis compare à l'identique : colonnes de train, contrat persisté et matrice d'inférence.

### P1-5 - Le stacking n'a pas de couverture OOF complète

`global_rank_df` ne contient que les prédictions des partitions de validation du ranking, car les résultats sont alimentés avec `pred_part` issu de `val_df` ([global_ranking.py](modelFactory/global_ranking.py#L1130)). L'orchestrateur les merge ensuite dans les features per-symbol et remplit toute date absente par 0.5 ([orchestrator.py](modelFactory/orchestrator.py#L759)).

**Statut 2026-08-04 : partiellement corrigé.** L'orchestrateur calcule et journalise maintenant la couverture en dates (`X/Y`, pourcentage) avant le merge, avec un warning sous 50% ([orchestrator.py](modelFactory/orchestrator.py#L766)). Le diagnostic rend la dette observable, mais la logique conserve le `fillna(0.5)` et continue l'entraînement, quelle que soit la couverture.

**Impact.** Les modèles per-symbol entraînent/évaluent potentiellement sur un mélange de ranks OOF et de rangs neutres. La performance du stacking dépend alors de la position temporelle des folds. Ce n'est pas une fuite si chaque rank présent est réellement OOF, mais c'est un contrat incomplet et un biais de comparabilité.

**Correctif restant.** Produire des prédictions OOF pour chaque date utilisable, versionnées par fold, et refuser le stacking si la couverture sur chaque split per-symbol est inférieure à un seuil explicite. Rapporter `coverage_global_rank` par train/val/test/WF. Pour l'inférence live, ne jamais confondre une valeur 0.5 de fallback avec une vraie prédiction : stocker une colonne `global_rank_available`.

### P2-3 - Les assertions de purge testent des jours calendaires, pas des sessions

**Statut 2026-08-04 : non corrigé, limitation documentée.** `validate_fold_isolation` compare toujours des différences de dates calendaires (`.days`) à un horizon exprimé en sessions ([dataset.py](modelFactory/dataset.py#L383)). Le commentaire ajouté reconnaît explicitement cette limite ; il ne change pas le calcul. Un contrôle minimal sur les séances consécutives lundi/mardi, avec `label_horizon=1`, retourne encore `purge_adequate=False` et une violation `1j < 1j` selon la convention du code.

`_purge_by_dates` retire bien les dernières **dates distinctes** du dataset ([dataset.py](modelFactory/dataset.py#L79)), ce qui est le comportement productif pertinent pour les splits par dates. Il ne valide cependant pas l'assertion annoncée : l'outil de validation peut émettre des faux positifs autour des week-ends et ne prouve pas la purge en sessions.

**Correctif restant.** Vérifier les positions dans l'index ordonné de séances uniques, pas le nombre de jours calendaires. Construire des tests avec jours de bourse et week-ends.

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

1. **Smoothing : corrigé.** La table de la section 3.2 affiche maintenant `✅` pour H10/H15/H20, conforme à `_SMOOTHING_HORIZONS = (10, 15, 20)` ([module_model_factory.md](doc/module_model_factory.md#L136)).
2. La table per-sector annonce `symbol` catégoriel et CatBoost depth 6. Le contrat catégoriel est désormais présent dans l'entraînement et l'inférence LightGBM ; un test réel CatBoost et une politique explicite pour symbole inconnu restent à ajouter.
3. La documentation doit indiquer une purge d'une **date** dans le Global Ranking, et non une purge « 1 jour » ambiguë. Le code utilise maintenant `generate_walk_forward_splits_by_dates(..., forecast_horizon=1)` ([global_ranking.py](modelFactory/global_ranking.py#L929)); l'invariant de partition par date est corrigé, mais une date n'est pas nécessairement une séance quand les données contiennent des jours non ouvrés.
4. **Fondamentales per-symbol : clarifié.** La comparaison per-symbol/per-sector indique désormais « pas de fondamentales » ([module_model_factory.md](doc/module_model_factory.md#L365)), cohérent avec l'orchestrateur. Le contrat préparation/baselines est maintenant aligné lorsque les flags sont activés manuellement, mais l'inférence doit encore transmettre les trois flags P1-3.
5. **Q/R `directional_accuracy` : corrigé.** La documentation compare maintenant `sign(pred)` à `sign(target)` ([module_model_factory.md](doc/module_model_factory.md#L883)), conformément à `_compute_regression_metrics`. Elle précise aussi que l'IC conserve `future_return` brut pour l'interprétation économique ([module_model_factory.md](doc/module_model_factory.md#L381)).
6. L'affirmation « Plus de data leakage » ne doit pas être employée : P0-2, P1-5, P2-3 et P2-4 restent à traiter ou à valider. Remplacer toute conclusion absolue par une liste d'invariants vérifiés et des tests automatiques.

## Plan de correction priorisé

### Phase A - Bloquer les résultats invalides

1. Désactiver `per_sector` côté CLI/IHM ou le marquer expérimental et non servi tant que P0-2 et le test E2E de routage ne sont pas résolus.
2. Désactiver publication/usage des artefacts sectoriels existants et des métriques associées.
3. Ajouter une alerte si un entraînement per-sector est demandé jusqu'à ce que les tests P0 soient verts.
4. Geler les comparaisons de régression existantes jusqu'au réentraînement avec clipping fit sur train.

### Phase B - Refaire le dataset sectoriel et son contrat de service

1. Ajouter la fusion post-concaténation des features cross-sectionnelles per-sector, ou désactiver explicitement cette option pour ce mode afin de ne pas entraîner silencieusement avec des valeurs neutres.
2. Introduire `neutralize_target_by_sector_date(...)` avec mapping GICS versionné, minimum de titres et diagnostic des secteurs incomplets.
3. Conserver `feature_columns_override` comme contrat unique, puis étendre le contrat persisté aux catégories et aux options fondamentales/facteurs/régime.
4. Mettre en place l'encodage stable de `symbol` ou retirer cette feature de la conception/documentation.
5. Implémenter le routage live/backtest sectoriel et un manifest d'artefacts complet, par horizon.

### Phase C - Rendre tous les splits auditables

1. Ajouter à chaque résultat de fold : bornes de dates, nombre de dates, nombre de symboles par date min/médiane/max, hash de l'univers et tailles après purge.
2. Échouer un fold si une date apparaît dans deux partitions, si l'horizon dépasse le gap de séances, ou si l'univers XS est sous le minimum.
3. Ajouter `FoldIsolationReport` aux résultats réels de run, pas uniquement aux tests unitaires.

### Phase D - Cadrer les transformations de target

1. **Réalisé :** conserver une target brute/vol-scalée avant le split avec `skip_winsorize=True` dans les chemins préparés.
2. Ajouter des tests pytest qui modifient seulement val/test et vérifient les quantiles et targets de train pour baseline, WF et LSTM.
3. En multi-horizon, tracer les bornes distinctes appliquées par horizon et par fold.
4. Pour les artefacts finaux, persister les bornes de winsorisation, moyenne et écart-type de la fenêtre train retenue.

### Phase E - Réconcilier configuration, métriques et documentation

1. **Réalisé :** isoler depth, itérations et learning rate CatBoost du ranking dans `GlobalModelConfig`. Ajouter un test pytest et persister explicitement la configuration effective dans les détails d'horizon.
2. **Réalisé :** corriger la table documentaire du smoothing. Ajouter un test versionné pour H3/H5/H10/H15/H20.
3. Ajouter un test de contrat d'IC quotidien et exposer clairement le nombre de dates/symboles dans les métriques de run.
4. **Réalisé dans le code :** transmettre fondamentales, facteurs et régime macro dans `_prepare_prediction_frame`. Ajouter le test de contrat entraînement/inférence avant de générer la documentation depuis des tests de contrat ou une configuration sérialisée.

## Matrice de tests à ajouter

| Test | Cible | Invariant bloquant |
|---|---|---|
| Panel permutation | per-sector | **Test validé.** `test_per_sector_prepare_isolates_symbols` vérifie que permuter les symboles ne modifie ni features ni targets d'un titre. |
| Forward return par symbole | per-sector, chaque horizon | **Test validé pour H3.** `test_per_sector_prepare_isolates_symbols` confirme l'alignement de `target_h3` avec le forward return du symbole. Étendre aux autres horizons actifs. |
| Fenêtre rolling par symbole | per-sector | **Test validé.** `test_per_sector_prepare_isolates_symbols` confirme l'isolation de `rolling_volatility_20`. |
| Train-only target transform | régression | **Contrôle manuel vert ; test pytest à ajouter.** Changer uniquement val/test ne modifie pas les targets préparées ni les quantiles/targets normalisées de train, pour baseline, WF et LSTM. |
| Fold dates disjointes | global et sector | Global corrigé par dates ; **test ranking à ajouter** avec trous et nombre de titres variable. |
| Purge en sessions | tous | Dernière séance train + horizon est strictement avant la première séance de la partition suivante. |
| Contrat features complet | tous | Matrice d'entraînement = feature contract = matrice d'inférence, ordre inclus. |
| Feature `symbol` | per-sector | **Contrat LightGBM validé ; E2E CatBoost à ajouter.** Les catégories sont persistées et reconstruites. Les symboles inconnus sont acceptés par LightGBM mais leur politique de branchement doit être explicitée. |
| E2E sectoriel | per-sector | Un entraînement minimal produit un artefact, un routage et une prédiction pour chaque symbole du secteur. |
| Couverture OOF stacking | global + per-symbol | **Métrique globale journalisée ; test et gate à ajouter.** Toute valeur de rank utilisée pour train/validation/test doit être OOF, la couverture doit être mesurée par partition et le run refusé sous le seuil explicite. |
| IC par date | global | **Calcul implémenté ; test à ajouter.** L'agrégat est égal à la moyenne documentée des IC quotidiens et expose le nombre de dates. |

## Critères de sortie avant remise en service

Le mode global/per-symbol peut être considéré robuste seulement lorsque les tests de split par dates, de clipping train-only et de contrat de features sont verts dans CI. Le per-sector ne peut être remis en service qu'après les dix tests de la matrice ci-dessus, avec une prédiction E2E live/backtest par symbole et un réentraînement complet.

Après correction, effectuer un nouveau protocole : période de développement, période de sélection des hyperparamètres, puis période finale totalement gelée. Rapporter l'IC quotidien, le turnover, les coûts et les résultats par régime, avec l'univers PIT exact. Ne pas comparer aux anciens IC/F1 comme s'ils provenaient du même protocole : le dataset sectoriel et les targets de régression auront changé matériellement.
