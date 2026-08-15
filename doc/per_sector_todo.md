# Per-Sector — Plan d'action (synthèse de l'avis GPT)

> **Date** : 2026-08-15
> **Source** : avis GPT sur `doc/per_sector.md`
> **Contexte** : le per-sector est actuellement `research-only` (F1 WF ≈ 0.33 = hasard). GPT considère que cela prouve que **la formulation actuelle n'extrait pas d'alpha**, pas que l'alpha sectoriel n'existe pas. Ce document synthétise son programme de recherche en tâches actionnables.

---

## 0. Changement de cadre (préalable à tout)

- [ ] **Abandonner la question « quel modèle donne le meilleur F1 ? »** au profit de :
  > **« Peut-on construire un ranking intra-sectoriel OOS qui produit un spread Long–Short net de coûts ? »**
- [ ] **F1/DirAcc/MSE deviennent des métriques secondaires** (diagnostic), la métrique primaire devient **IC Spearman relatif par date** + **spread long-short net de coûts**.
- [ ] **Décision utilisateur requise** : réouverture de la recherche per-sector sous protocole strict. Ce plan reste conforme à la règle de ré-entrée de `doc/per_sector.md` §1.2 : hypothèse matériellement nouvelle (= refonte de l'objectif : ranking intra-sectoriel au lieu de prédiction de magnitude), pré-registration, IC relatif, spread net, holdout gelé.
- [ ] **Coûts de référence** (pour tous les calculs de spread net) : commission 1 bps, slippage 2 bps, spread réel médian ~44 bps → aller-retour ≈ **51 bps** ; marge 7.5 %/an, levier 2×.

---

## Phase 0 — Construire le vrai benchmark (P0, avant toute modification de modèle)

Pour chaque **secteur × date × horizon H3/H5/H10/H15/H20**, calculer :
`future_return` (déjà en base) et **`relative_return = future_return − médiane_sectorielle(future_return, date)`** (colonne **à créer** — Action 2.1 de `ml_todo_1.md` jamais réalisée).

Puis tester des baselines simples, en IC relatif par date ET spread long-short net :

| ID | Baseline | Formule |
|---|---|---|
| B0 | Hasard | score aléatoire |
| B1 | Momentum | `mom20`, `mom60`, `mom120` (3 scores) |
| B2 | Reversal | `−ret_5`, `−ret_10` |
| B3 | Momentum × volatilité | `mom20 / vol20` |
| B4 | Momentum relatif | `ret20 − median_sector(ret20)` |
| B5 | Blend multi-horizon relatif | `0.5·rel_mom20 + 0.3·rel_mom60 + 0.2·rel_mom120` |

- [ ] Implémenter le calcul de `relative_return` par secteur/date (ajout au dataset per-sector).
- [ ] Implémenter l'évaluation baselines : IC relatif moyen/IR, spread top−bottom quintile avant/après coûts, % folds positifs.
- [ ] Exécuter B0-B5 sur les folds WF (2019-2024) + holdout gelé.
- **Question à trancher** : existe-t-il déjà un alpha intra-sectoriel trivial ?
  - Si `rel_mom20` produit un spread positif → le ML a simplement échoué à apprendre un signal simple → priorité à corriger les features/target avant tout nouveau modèle.
  - Si aucun baseline ne bat le hasard → le signal simple n'existe pas → aller directement aux phases 4-6 (informations nouvelles).

**Ancrage code** : `modelFactory/model_benchmark.py` (classe `SimpleBaselines` existante à étendre), `modelFactory/dataset.py` (création de `relative_return_h`), évaluation via un nouveau helper réutilisable par les phases suivantes.

---

## Phase 1 — Refaire la target (5 familles à tester séparément)

La target actuelle = `future_return → vol scaling → winsorize → − médiane sectorielle`. À remplacer/confronter par :

| Famille | Target | Note |
|---|---|---|
| A | `y = future_return_i − median_sector(future_return)` | Relative « brute », sans vol scaling |
| B | `y = percentile_rank(future_return)` intra-secteur/date ∈ [0,1] | L'objectif devient le classement |
| C | `y = (return_i − sector_mean) / sector_std` | Z-score cross-sectionnel |
| D | `y = 2·percentile_rank − 1` ∈ [−1,1] | Rang centré |
| E | **Pairwise ranking** : « A fera-t-il mieux que B ? » (paires intra-secteur/date) → modèle de ranking | Le plus proche de l'objectif économique |

- [ ] Ajouter les flags/targets B, C, D, E au pipeline per-sector (A ≈ T1 déjà testé ; T2/T3 existent mais mal métrisés — re-tester avec les nouvelles métriques, pas F1).
- [ ] Toutes les transformations (z-score, percentile) doivent être **fit train-only par fold** (sauf médiane sectorielle de date, contemporaine et licite).
- [ ] Évaluer chaque famille avec la métrique du §0 (IC relatif + spread net), jamais avec F1 seul.

**Ancrage code** : `modelFactory/dataset.py` (`build_multi_horizon_targets`), `modelFactory/labeling.py`, flags existants `--target-skip-vol-scaling`, `--target-intra-sector-rank`, `--target-ternary-intra-sector` à compléter.

---

## Phase 2 — Passer aux modèles de ranking (pas de classification)

- [ ] **LightGBM LambdaRank** (ou équivalent) avec **`group = secteur × date`** — le modèle apprend l'ordre des titres dans le secteur à chaque date. Métrique **NDCG**.
- [ ] **Pas de classification ternaire** LONG/FLAT/SHORT pour le per-sector (mauvaise abstraction : T3 a déjà montré 72 % flat et surapprentissage).
- [ ] Comparer LambdaRank vs régression continue sur target B/D, **uniquement via IC relatif + spread net**.
- [ ] Attention : les expériences PairLogit globales (B23/B24/B28/B29) ont échoué pour coût O(n²) — limiter le pairwise aux paires intra-secteur/date et borner le nombre de paires.

**Ancrage code** : `modelFactory/global_ranking.py` (LambdaRank déjà branché côté Global), `modelFactory/tabular_baseline.py` / `lightgbm_baseline.py` (étendre au ranking groupé pour le per-sector).

---

## Phase 3 — Features cross-sectionnelles relatives (prix, vol, volume, momentum)

Chaque feature doit répondre à « comment ce titre se comporte **par rapport aux autres titres du secteur aujourd'hui** ? » :

| Famille | Features |
|---|---|
| A. Prix relatifs | `ret5/10/20/60/120 − sector_median(...)`, `sector_percentile(ret20)`, `sector_zscore(ret20)` |
| B. Volatilité relative | `vol20 / sector_median(vol20)`, `ATR20 / sector_median(ATR20)`, `ATR20/price` relatif |
| C. Volume relatif | `volume / avg_volume20`, percentile sectoriel du volume relatif |
| D. Momentum relatif | `mom20/60/120` + leurs rangs sectoriels (`mom20_sector_rank`, ...) |

- [ ] Inventorier ce qui existe déjà dans `modelFactory/cross_sectional.py` (helpers `_sector_neutral_column_name`, `_sector_zscore_column_name`, rangs percentile) — **beaucoup de briques sont déjà là mais étaient neutres/0.5 dans les batchs per-sector historiques** (bug XS corrigé 2026-08-04, jamais re-testé proprement avec les bonnes métriques).
- [ ] Étendre aux relatifs vol/volume, puis **rejouer l'ablation XS ON/OFF avec les nouvelles métriques** (les batchs B13/B33 « XS toxiques » ont été jugés sur IC Global, pas sur spread intra-sectoriel net).

---

## Phase 4 — Fondamentaux **réellement relatifs**

Les fondamentaux absolus ont été testés (B9/B31 : toxiques pour le Global). GPT considère que l'hypothèse intra-sectorielle n'a **pas** été testée :

- [ ] Construire les percentiles sectoriels par date : `PE_sector_percentile`, `ROE_...`, `revenue_growth_...`, `EPS_growth_...`, `debt_...`, marges, FCF.
- [ ] Faire attention au forward-fill trimestriel des fondamentales (staleness) et à la PIT : un percentile sectoriel doit utiliser uniquement les valeurs publiées à la date.
- [ ] Test = 1 expérience : « fondamentaux relatifs ON » vs baseline de la Phase 0, même protocole.

**Ancrage code** : `modelFactory/fundamental_features.py`, `modelFactory/cross_sectional.py`.

---

## Phase 5 — Interactions conditionnelles

- [ ] `momentum relatif × volatilité relative`
- [ ] `earnings growth relatif × momentum relatif`
- [ ] `earnings surprise × momentum`
- [ ] `valuation relative × momentum relatif` (sous-évalué ET momentum positif)

- [ ] Une hypothèse = une expérience ; ne pas empiler les interactions dans un seul batch.

---

## Phase 6 — Événements PIT (le plus gros levier potentiel selon GPT)

- [ ] **Earnings** : `earnings_surprise`, `revenue_surprise`, `EPS_surprise`, `guidance_surprise`, et **`surprise_relative_sector`**.
- [ ] **Révisions analystes** (si les données existent en base) : `EPS_revision_7d/30d/90d`.
- [ ] **Réaction de prix post-earnings** : combiner surprise + retour post-annonce (« excellents résultats mais action −5 % » ≠ « excellents résultats + action +8 % »).
- [ ] **Vérifier d'abord la disponibilité PIT des données** (tables earnings/révisions, dates d'annonce) — c'est une condition bloquante de ré-entrée. Sans données PIT, cette phase est à reporter.

---

## Phase 7 — Architectures hiérarchiques

| Architecture | Principe | Détail |
|---|---|---|
| **Modèle A** | GLOBAL + `sector` catégoriel + features sector-relatives | Partage l'information entre les 400 titres |
| **Modèle B** | Global → prédiction + modèle résiduel sectoriel léger | `final = global + α·sector_residual`, `α ∈ {0.10, 0.25, 0.50, 0.75, 1.0}` |
| **MoE** | `final = w_sector·sector_model + (1−w_sector)·global_model` | `w_sector` **appris/choisi sur validation uniquement, jamais optimisé sur test** |

- [ ] Modèle A vs Modèle B sur protocole identique.
- [ ] MoE en variante, avec la contrainte de non-optimisation de `w_sector` sur le test.

**Ancrage code** : `modelFactory/trainer_sector.py` (`_train_sector_models`), `modelFactory/global_model.py`, orchestrateur.

---

## Ablation de la feature `symbol` (à faire immédiatement)

- [ ] `A0` = sans `symbol`
- [ ] `A1` = `symbol` catégoriel (actuel)
- [ ] `A2` = features sector-relatives, sans `symbol`
- [ ] `A3` = `symbol` + features relatives

Le `symbol` permet potentiellement de mémoriser « XOM est généralement meilleur » — pas du signal généralisable. Décision sur folds WF, jamais sur le holdout.

---

## Nouvelle métrique de champion (remplace `selection_score` ≈ F1)

- [ ] Critère primaire : **IC Spearman relatif par date** (vs `relative_return`).
- [ ] Critère secondaire : **spread long-short net de coûts** (top vs bottom quintile intra-secteur).
- [ ] Robustesse : **% folds positifs** (+ IR de l'IC relatif).
- [ ] Version pondérée si besoin : `score = 50% IC_relatif + 30% spread_net + 20% stabilité`, pénalités turnover/drawdown.
- [ ] Le champion LightGBM vs CatBoost (et LambdaRank) est choisi **sur validation/WF uniquement**.

**Ancrage code** : `modelFactory/trainer_sector.py` (`_persist_sector_metrics`, logique de champion).

---

## Protocole expérimental strict

- [ ] **Train → Validation → Walk-Forward → Frozen Holdout** (jamais de choix sur le holdout).
- [ ] **Frozen holdout à définir une fois** (ex. train jusqu'à 2024-12-31 comme B44, holdout 2025 gelé ; ou 2026 réservé). Une seule consultation par hypothèse confirmée.
- [ ] **Une hypothèse = une expérience** : `S1` relative momentum, `S2` fondamentaux relatifs, `S3` LambdaRank, `S4` target pairwise, `S5` modèle hiérarchique, `S6` earnings surprise. Interdit : `S7 = 38 features + ranking + fondamentaux + macro`.
- [ ] **Pré-registration** de chaque expérience (hypothèse, métrique, seuil de décision) avant de lancer.
- [ ] **Stop/go** : une idée sans IC relatif positivement stable OU sans spread net significatif après coûts est abandonnée — même si un secteur isolé s'améliore.
- [ ] **Levier en dernier** : ne toucher au sizing/levier qu'après un spread relatif OOS démontré. Le levier est la conséquence de l'alpha, pas un moyen de fabriquer de la performance.

---

## Ordre de priorité d'exécution

| Priorité | Expérience | Potentiel |
|---|---|---|
| 🥇 | Baseline momentum relatif (Phase 0) | ⭐⭐⭐⭐⭐ |
| 🥈 | IC + spread relatif correctement mesurés (§0/Champion) | ⭐⭐⭐⭐⭐ |
| 🥉 | LambdaRank / ranking par secteur×date (Phase 2) | ⭐⭐⭐⭐⭐ |
| 4 | Features prix/volume relatives (Phase 3) | ⭐⭐⭐⭐ |
| 5 | Fondamentaux relatifs (Phase 4) | ⭐⭐⭐⭐ |
| 6 | Earnings / révisions PIT (Phase 6) | ⭐⭐⭐⭐⭐ (si données dispo) |
| 7 | Global + résiduel sectoriel (Phase 7 B) | ⭐⭐⭐⭐⭐ |
| 8 | Mixture Global/Sector (Phase 7 MoE) | ⭐⭐⭐⭐ |
| 9 | Pairwise learning (Phase 1 E) | ⭐⭐⭐⭐ |
| 10 | Macro × secteur × régime | ⭐⭐⭐ |
| 11 | Tuning hyperparamètres | ⭐ |
| 12 | Ajouter encore des features absolues | ⭐ |

---

## Hypothèse directrice

Le problème n'est probablement pas « le secteur n'est pas prédictible » mais **« on demande au modèle de prédire une magnitude (régression continue) alors que l'objectif économique est uniquement le classement intra-sectoriel »**.

Indice : le **Global Ranking** atteint IC ≈ 0.026 sur 400 titres → l'information existe. La question devient : **comment la conserver quand on impose une neutralisation intra-sectorielle ?**

→ Priorité absolue : **LambdaRank (secteur×date) + features relatives + hiérarchie Global→Sector**, évalués par IC relatif + spread net, sur protocole train/val/WF/holdout gelé.

---

## Dépendances à vérifier avant de lancer

- [ ] `relative_return_h` : colonne absente aujourd'hui (seuls `future_return_h` brut et `target_h` neutralisée existent) — à créer dans `dataset.py`.
- [ ] Disponibilité PIT des données earnings/révisions (Phase 6) — inventaire des tables (`stock_fundamentals_daily` n'a pas de dates d'annonce ? vérifier `stock_earnings_*` s'il existe).
- [ ] Le cache XS actuel (`cross_sectional.py`) couvre déjà rangs/z-scores sectoriels — inventorier l'existant pour éviter de réécrire.
- [ ] Les métriques IC relatif/spread net par secteur×date ne sont rapportées nulle part (`report.py`, `trainer_sector.py`) — à ajouter avant toute expérience, sinon les résultats ne seront pas mesurables.
- [ ] Rappel historique : `7e4cf8` (F1 0.51, DirAcc 0.70) est antérieur aux correctifs — ne pas l'utiliser comme preuve qu'un signal a déjà existé.

---

## Références

| Document | Chemin |
|---|---|
| Contexte per-sector complet | `doc/per_sector.md` |
| Plan d'action ML 1 (phases/actions d'origine) | `prompt/ml/ml_todo_1.md` |
| Journal de recherche | `doc/ml_todo.md` |
| Architecture du module | `doc/ml/module_model_factory.md` (§5) |
| Flags & features | `doc/ml/features_ml.md` |
| Analyse OOS Global (contexte 2026) | `doc/ml/analyse_oos.txt` |
