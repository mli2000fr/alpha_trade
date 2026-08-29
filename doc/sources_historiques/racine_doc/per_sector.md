# Synthèse Per-Sector — α-Trade (contexte pour recherche de leviers)

> **Date** : 2026-08-15
> **But de ce document** : donner à une IA externe (GPT) un contexte **précis et détaillé** sur la partie « per-sector » du projet α-Trade, pour qu'elle cherche des **leviers d'amélioration** sans refaire des erreurs déjà testées.
> **Sources** : `doc/ml/module_model_factory.md`, `doc/ml/features_ml.md`, `doc/ml/analyse_oos.txt`, `prompt/ml/ml_todo_1.md`, `doc/ml_todo.md`, code `modelFactory/`.

---

## 1. Positionnement : qu'est-ce que le per-sector dans ce projet ?

Le projet α-Trade est un système de trading long/short ML sur actions US mid-caps. Le ML comporte **2 modes d'entraînement** gérés par `modelFactory` :

| Mode | Granularité | Modèles | Statut (2026-08) |
|---|---|---|---|
| **Global Ranking** (Phase 1) | 1 modèle pour tout l'univers (400 symboles) | CatBoost RMSE/**YetiRank** (+ LightGBM/XGBoost en challengers) | ✅ **Seul signal avec un vrai alpha** (IC Rank ≈ 0.024-0.026) — champion production B25/B41 |
| **Per-Sector** (Phase 2bis) | 1 modèle par secteur GICS × horizon = **11 × 5 = 55 modèles** | LightGBM + CatBoost (pas de LSTM) | 🔴 **research-only depuis 2026-08-05** — F1 WF ≈ 0.33 = hasard |
| **Per-Symbol** (Phase 2, legacy) | 1 modèle par symbole (~400) | LSTM Attention + LightGBM + CatBoost | 🔄 **Pivot 2026-08-14** : le per-symbol est retravaillé (ablation F0-F4), le per-sector est abandonné comme signal |

### 1.1 Le principe du per-sector

Un modèle par secteur **GICS** apprend à prédire si un symbole va **surperformer ou sous-performer la médiane de son secteur** (surperformance relative intra-secteur), et non le rendement absolu.

```
target_h = future_return_h brut (close[t+h]/close[t] − 1)
1. Vol scaling (h ≥ 5)      : target_h /= rolling_volatility_20   (H3 : pas de scaling)
2. Winsorization            : clip 1%/99% par symbole
3. Neutralisation secteur   : target_neutralisée[t] = target_h[t] − médiane(target_h[t] de tous les symboles du secteur à la date t)
```

Le split chronologique garantit qu'aucune date n'est éclatée train/test → la médiane intra-date ne crée **pas de leakage**.

### 1.2 Statut décisionnel (à ne pas remettre en cause sans preuve nouvelle)

- **Décision du 2026-08-05** : le per-sector passe en **research-only**. Il ne doit ni être champion de production, ni entrer dans la cascade de trading, ni servir de veto ou de pondération du capital.
- **Règle de ré-entrée** : ne le reconsidérer que pour une **hypothèse matériellement nouvelle** avec information PIT inédite (révisions de résultats/estimations, flux ETF sectoriels, événements sectoriels), ou un objectif de portefeuille relatif entièrement redessiné. Une promotion exige : pré-registration, **IC relatif positif par date**, **spread long-short net de coûts stable sur la majorité des folds**, et confirmation sur **holdout gelé**.
- **Campagne contrôlée 2026-08-05 (S0/T0-T3)** : 8 batchs sur le même problème per-sector → résultat cohérent : **aucun alpha per-sector tradable n'est démontré** par les configurations et le dataset testés. Aucune nouvelle campagne de tuning de flags/hyperparamètres n'est justifiée.

---

## 2. Architecture technique

### 2.1 Fichiers clés

| Fichier | Rôle |
|---|---|
| `modelFactory/trainer_sector.py` | Entraînement per-sector : `run_per_sector_batch()` (entrée), `_train_sector_models()` (1 secteur), `_prepare_sector_data()` (préparation du panel sectoriel), `_persist_sector_metrics()`, loaders `_load_sentiment_for_symbols`, `_load_selector_for_symbols`, `_load_fundamentals_for_symbols`, `_load_universe`, `_load_benchmark` |
| `modelFactory/cross_sectional.py` | Mapping DB sub-industry → 11 secteurs GICS (`_GICS_SECTOR_MAP`), `load_sector_groups()`, `build_cross_sectional_features_from_db()` (cache XS global) |
| `modelFactory/predict_per_sector.py` | Job live quotidien + backfill : prédiction des batchs per-sector (cascade rank-driven) |
| `scripts/live_ml_predict_per_sector.py` | Variante script du job live |
| `modelFactory/predictor.py` | Inférence : routage symbole → secteur GICS → modèle sectoriel ; `cascade_select()` (couplage rang global × proba) ; `apply_cascade_to_predictions()` |
| `modelFactory/synthesize_global_rank_predictions.py` | Agrégation des prédictions en scores consommables (la cascade gère l'absence de modèles per-symbol pour les batchs per_sector) |
| `modelFactory/report.py` | Rapport markdown : section « 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement » (champions, F1 par horizon/split, distribution true/pred, top/flop, métriques régression) |
| `ihm/pages/ml_diagnostics.py` | Page IHM de diagnostic batch (mêmes sections) |
| `modelFactory/orchestrator.py` | Orchestration des phases (branche `--training-mode per_sector`) |
| `modelFactory/db_registry.py` | Détection du mode d'entraînement d'un batch (`per_sector` vs `per_symbol`) |
| `alembic/versions/0061_widen_symbol_columns_for_sector_names.py` | Migration : élargissement des colonnes `symbol` pour les noms de secteurs (jusqu'à 24 chars) |

### 2.2 Les 11 secteurs GICS

Mapping DB (`stock_metadata.provider_sector`, noms de sub-industries) → 11 secteurs : **Energy, Materials, Industrials, Consumer Discretionary, Consumer Staples, Health Care, Financials, Information Technology, Communication Services, Utilities, Real Estate**. ~85 titres en moyenne par secteur sur l'univers de 400 (les tailles réelles varient).

### 2.3 Pipeline d'entraînement (`run_per_sector_batch`)

```
run_per_sector_batch(symbols, engine, cfg)
  1. load_sector_groups(engine) → 11 groupes, filtrés par l'univers demandé
  2. Chargement partagé (1 seule fois) : sentiment, benchmark SPY, universe,
     selector (si include_screener/short_score), fondamentales (si include_fundamentals)
  3. Cache cross-sectionnel construit UNE FOIS sur l'univers global PIT
     (si enable_cross_sectional ou stacking) — build_cross_sectional_features_from_db
  4. Pour chaque secteur (séquentiel) :
       _train_sector_models → _prepare_sector_data →
         pour chaque symbole du secteur (INDÉPENDAMMENT, fix P0-1) :
           load_symbol_bars + prepare_symbol_frame (features + targets, pas de neutralisation)
         → concat panel + colonne symbol (catégorielle)
         → merge du cache XS réel sur (symbol, date) APRÈS concaténation
         → neutralisation de la target par médiane sectorielle/date
         → split chronologique train/val/test (dates, pas de leakage)
         → pour chaque horizon h ∈ {3,5,10,15,20} :
             swap target_h / future_return_h
             run_tabular_baseline (LightGBM + CatBoost, purge = h jours)
             run_tabular_walk_forward (purge = h jours)
         → sélection champion LightGBM vs CatBoost par secteur
         → _persist_sector_metrics
  5. Résumé final (completed/failed/skipped par secteur)
```

### 2.4 Modèles & hyperparamètres

| Paramètre | LightGBM | CatBoost |
|---|---|---|
| Type | `LGBMRegressor` | `CatBoostRegressor` |
| Loss | MSE | RMSE |
| `max_depth` | 5 | `catboost_depth` = 6 |
| `n_estimators` | 200 | `catboost_iterations` = 300 |
| `learning_rate` | 0.03 | 0.03 |
| Régularisation | `reg_alpha=0.1, reg_lambda=0.1` | `l2_leaf_reg=3.0` |
| `min_child_samples` | 150 | — |
| `subsample` / `colsample_bytree` | 0.8 / 0.7 | — |

- **Target-mode** : `regression` (num_classes=1, 1 sortie continue, MSE). Pas de classes long/flat/short au fit.
- **Décision** : `side = signe(score)` ; score ≈ 0 → FLAT. Pas de calibration Platt, pas de seuils ternaires en mode regression.
- **Walk-forward** : mêmes paramètres que le Global (train max 756j, val 126j, test 126j, pas 252j, `--wf-max-splits 8`), purge dynamique = h jours par horizon (H3 purge 3j → +17j de train vs H20).

### 2.5 Features

- Base = mêmes features `expert` que le per-symbol, **plus** la colonne `symbol` **catégorielle** (permet de différencier les titres au sein du secteur).
- Familles optionnelles par flags (toutes testées dans la campagne, aucune n'a apporté d'alpha) : `--include-short-score`, `--include-screener-scores` (22 colonnes), `--include-sentiment` (5), `--include-macro-vix/vxn/vix3m/move` (auto-chargées par `_merge_macro_features`, DB directe), `--include-fundamentals` (22 EODHD), `--include-factors` (CAPM : beta, alpha, r²), `--include-macro-regime`, `--enable-cross-sectional`, `--enable-global-stacking`.
- **Politique symboles inconnus à l'inférence (P2-6)** : LightGBM → catégories `pd.Categorical` étendues ; CatBoost → accepte nativement les catégories non vues ; fallback → modèle per-symbol du titre si le modèle sectoriel est indisponible.

### 2.6 Inférence & cascade

- `predictor.py` route `symbole → secteur GICS → modèle sectoriel` (artefacts JSON dans `artifacts/models/<batch_id>/...`), avec vérification de **feature contract** (colonnes + fingerprint).
- **Cascade de trading** (`cascade_select` dans `predictor.py`, config `config.yaml` → `ml.cascade.min_prob_regression: 0.10`) :
  - Candidat LONG : `global_rank_h > 0.90` (top 10 %) ET `proba_long > seuil`.
  - Candidat SHORT : `global_rank_h < 0.10` (bottom 10 %) ET `proba_short > seuil`.
  - En mode regression, `proba_long/proba_short` sont NULL dans la DB → la cascade fabrique **`long_prob = |score|`** (P0-5). Le seuil effectif est `min_prob_regression = 0.10` (le `0.55` ne vaut que pour le ternaire).
  - Filtre momentum short-side (mom20 < +2 %).
- **Problème observé en 2026** : le modèle sectoriel dit « long » là où le rang global classe au milieu (médiane `|score|` long = 0.094) → seulement 11 candidats longs satisfaisaient les deux conditions sur 96 jours, contre 213 candidats shorts → backtest 100 % shorts → −53 % OOS 2026.

---

## 3. Métriques & évaluation

| Métrique | Définition | Lecture |
|---|---|---|
| **F1 macro (WF)** | Moyenne F1 short/flat/long calculée par binarisation du signe : `sign(pred)` vs `sign(target_neutralisée)` | En regression, **≈ 0.33 = hasard** (2 classes aléatoires + F1 flat nulle) |
| **Directional accuracy** | % de signes concordants vs target neutralisée | ≈ 50 % = pile ou face |
| **MSE** | Sur target standardisée | ≈ 1.0 = modèle naïf (prédire la moyenne), aucune variance expliquée |
| **IC** | Volontairement calculé sur `future_return` **brut** (lecture économique distincte) | Distinct de l'IC relatif intra-secteur (qui n'est pas encore rapporté) |
| Champion | `selection_score` largement lié au F1 WF | Compté en nb de secteurs gagnés par LightGBM vs CatBoost |

**Alignement (2026-08-03)** : F1/DirAcc sont calculés sur la target **neutralisée**, pas le rendement brut — pour mesurer la vraie capacité de ranking intra-secteur.

---

## 4. Historique des résultats per-sector

### 4.1 Batchs de référence

| Batch | Date | Contexte | F1 macro WF | Dir Acc | MSE | Verdict |
|---|---|---|---|---|---|---|
| `7e4cf8` | 2026-08-03 | Premier batch per-sector | 0.499–0.514 | 0.67–0.71 | — | ⚠️ **Non comparable** : antérieur aux correctifs/alignement, chiffres non reproductibles ensuite |
| `f82ab5` | 2026-08-04 | Référence « alerte » | 0.330–0.332 | 0.502–0.504 | 1.01–1.05 | 🔴 Niveau nul sur tous les horizons/secteurs |
| `d21cb1` | 2026-08-05 | 1er rerun après corrections XS/fondamentales | 0.325–0.329 | 0.498–0.504 | 1.089–1.118 | 🔴 Aucun gain économique ; le correctif de contrat est valide mais sans alpha |

Sur `f82ab5` : 11/11 secteurs entraînés, F1 macro par secteur 0.308–0.344, meilleurs secteurs Industrials/Consumer Staples (0.342-0.344), pire Energy (0.308), F1 **stable ~0.33 quel que soit le régime** (bull/range/high-vol). Sur `d21cb1`, la dispersion sectorielle existe (meilleur point Utilities/CatBoost dir_acc 0.5346 mais MSE 1.34) mais n'est pas robuste ; plusieurs secteurs/backends < 0.48.

### 4.2 Campagne contrôlée S0/T0-T3 (2026-08-05) — verdict définitif

| Expérience | ID | Hypothèse | F1 WF H20 | Dir Acc | MSE | Lecture |
|---|---|---:|---:|---:|---|
| `S0` | `799d9e` | Baseline sans flag optionnel | 0.330 | 50.0 % | 1.01 | Niveau nul |
| `S0+short` | `57461f` | Score short incrémental | 0.330 | 50.0 % | 1.01 | Aucun effet mesuré |
| `d21cb1` | — | XS/fondamentales réellement présentes | 0.325 | 49.8 % | 1.09 | Correctif valide, sans gain |
| `T0` | `a3aaa3` | H20 seul, cible continue actuelle | 0.330 | 50.0 % | 1.01 | Le multi-horizon n'est pas responsable |
| `T1` | `1b2059` | Cible sans vol scaling | 0.330 | 50.0 % | 1.24 | Dégradation nette de l'erreur |
| `T2` | `054378` | Rang percentile intra-secteur | 0.330 | 49.9 % | 1.07 | Pas de signal de ranking exploitable |
| `T3` | `5b6760` | Classes ternaires intra-secteur | 0.331 | **39.3 %** | 0.23 | **Surapprentissage temporel sévère** (69.3 % DA en val / 71.3 % en test interne → 39-40 % en WF) |

### 4.3 Campagne flags B0–B44 (2026-08-09 → 08-14) — colonne per-sector

Tous les batchs B0-B44 incluaient un entraînement per-sector (sauf B44 `--global-model-only`). La colonne « Per-Sector Champions » (nb de secteurs gagnés par LightGBM) n'a jamais montré de gain directionnel :

- B0 : lgbm 6/11 · B4 : lgbm 8/11 (meilleur count) · B12 : lgbm 10/11 · B17 (ternary T3) : 9/11 mais **72 % flat** · B25/B26/B27/B31-B34/B39-B42 : 5-7/11.
- **Aucun flag n'a bougé le F1 WF sectoriel** (~0.33 partout). Les flags macro (VIX/VXN/VIX3M/MOVE/régime) = 0 gain ; fondamentales et cross-sectional = toxiques aussi pour le Global ; YetiRank/CAPM/volume n'améliorent que le **Global Ranking**.
- Constat final de la campagne : « **Per-Sector ≈ hasard** : F1 macro ~0.33, F1 short < 0.50. Seul le Global Ranking a un vrai pouvoir prédictif. »

---

## 5. Bugs corrigés & fixes de contrat (à connaître pour ne pas refaire les mêmes erreurs)

1. **P0-1 (2026-08-04) — corruption des features par concaténation** : avant, les barres étaient concaténées puis `prepare_symbol_frame` tournait sur le panel → `rolling()` et `shift(-h)` traversaient les frontières entre symboles. Fix : **préparer chaque symbole isolément, puis concaténer**.
2. **XS non fusionnées (Action 1.1, 2026-08-04)** : le per-sector préparait avec `universe_df=None` → ~30 colonnes cross-sectionnelles remplies de valeurs neutres (0.5/0.0). Fix : cache XS construit **une fois** dans `run_per_sector_batch` puis mergé après concaténation ; le helper **supprime les colonnes XS par défaut avant merge** pour éviter les suffixes Pandas `_x/_y` (les valeurs réelles écrasent les defaults).
3. **Fondamentales exclues du feature contract (Action 1.2, 2026-08-04)** : `get_feature_columns` était appelé sans `include_fundamentals` → fondamentales calculées mais non transmises aux estimateurs. Fix : propagation du flag.
4. **Bugs d'ordre d'arguments (2026-08-08)** : `_load_selector_for_symbols` et `_load_sentiment_for_symbols` appelaient les loaders avec les arguments inversés, masqués par `except Exception: return None` → `selector_short_score` et les 22 scores screener étaient `0.0` partout, le sentiment absent. Fix : appels aux loaders multi-symboles.
5. **Feature contract à la prédiction (2026-08-06, cf. mémoire `per_sector_predict_fix_2026-08-06.md`)** : `feature_contract_columns_mismatch` car les flags `include_macro_*/include_fundamentals/include_factors/include_macro_regime` n'étaient pas transmis à `validate_feature_contract` (entraînement et prédiction) ; `_load_data_cfg_from_payload` priorisait `ps_features` sur la config du batch ; la colonne post-hoc `symbol` manquait dans le contrat → auto-append ; fingerprint calculé avec des flags faux dans `_build_feature_contract_for_columns`. Fingerprint mismatch rétrogradé ERROR → WARNING quand c'est le seul problème (anciens modèles incompatibles).
6. **Migration Alembic 0061** : colonnes `symbol` élargies pour stocker les noms de secteurs (24 chars).

**Tests en place** (vert, 36 passed) : `test_per_sector_xs_merge_uses_global_universe`, `test_per_sector_feature_contract_includes_fundamentals_when_enabled`, test d'intégration `_prepare_sector_data` (2 symboles + cache XS + fondamentales : contrat, variance, absence de colonne fantôme), `test_batch_training_mode_dispatch` (détection per_sector/per_symbol), `test_cross_symbol_features` (min_symbols_per_sector).

---

## 6. Le « sectoriel » ailleurs dans le projet (contexte à ne pas confondre)

Le per-sector (mode ML) est distinct d'autres mécanismes sectoriels qui, eux, sont actifs :

| Mécanisme | Où | Rôle actuel |
|---|---|---|
| **Neutralisation sectorielle de la target du Global Ranking** | `global_ranking.py` / target pipeline | Soustrait la médiane sectorielle avant re-rank → le rang est **sector-neutre** par construction (levier majeur historique : +84 % d'IC) |
| **Neutralisation factorielle** (size+value+momentum OLS) | idem | 2e neutralisation de la target Global |
| **`max_tickers_per_sector`** | `risk_management/constraints.py`, `service/market/config.py`, `config.yaml` (2) | Limite de concentration par secteur au sizing |
| **Multiplicateurs sectoriels** | `config/p21_sector_multipliers.json`, `modelFactory/analyze_p21_attribution.py` | Facteurs ×0.5..×1.25 par secteur appliqués au sizing |
| **Garde-fou breadth live 75 %** | `modelFactory/universe_guard.py`, `config.yaml` | L'univers live doit couvrir ≥ 75 % du référentiel |

---

## 7. Leviers potentiels déjà identifiés (non testés ou à valider)

Issus de `prompt/ml/ml_todo_1.md` (phases 4-7) — **tout ceci est conditionné à la règle de ré-entrée du §1.2** :

1. **Métriques économiques relatives** (P0, jamais fait) : IC Spearman **par date** vs `relative_return_h` (future_return − médiane sectorielle) + IR ; spread long-short top/bottom quintile intra-secteur **avant et après coûts** ; baselines de contrôle (prédiction zéro, momentum intra-secteur 20/60, ridge/elastic net, rang momentum simple). Le F1/MSE actuels disent « ça ne marche pas » mais pas pourquoi.
2. **Séparer 3 objets par horizon** : `future_return_h` (absolu), `relative_return_h` (économique intra-secteur), `target_h` (transformation statistique de fit) — aujourd'hui la neutralisation est appliquée directement sur la target.
3. **Règle de champion alignée** : remplacer `selection_score` (F1 WF) par `IC_relatif + λ·spread_net − γ·turnover`, sélectionnée sur validation/WF uniquement.
4. **Ablation de la feature `symbol`** : le catégoriel peut mémoriser des comportements historiques non généralisables (A0 sans / A1 avec / A2 avec + XS+fonda).
5. **Architecture hiérarchique** au lieu de 11 modèles isolés : 1 modèle global de rendement relatif avec `sector` catégoriel + interactions ; ou global + résiduel sectoriel léger ; ou groupes cyclique/défensif/tech-finance. (~85 titres/secteur = peu de cross-sections utiles par date.)
6. **Interactions macro × régime × secteur** plutôt que niveaux macro bruts (VIX etc. identiques pour tous les titres d'une date).
7. **Usage prudent alternatif** si un alpha relatif apparaissait : veto faible / pondération bornée / diagnostic de dispersion — jamais moteur principal.

### 7.1 Ce qui a déjà été testé et a échoué (ne pas re-proposer sans hypothèse nouvelle)

- Toutes les familles de features optionnelles (short-score, screener, sentiment, macro ×4, fondamentales, CAPM, macro-régime, XS, stacking) : 0 gain per-sector.
- 3 formulations de cible (T0/T1/T2/T3), H20 seul, sans vol scaling : échec.
- Tuning d'hyperparamètres ou de flags : aucune campagne supplémentaire justifiée.

---

## 8. Contexte élargi : pourquoi le Global Ranking domine et le per-sector échoue

- Le **Global Ranking** (cross-sectionnel, 400 titres, ~155-177 features, YetiRank) a un IC Rank WF de **0.0241 (B25)** → **0.0260 (B41, record, IR 1.55)**. Sa target est **sector-neutre + factor-neutre**. Il généralise OOS 2025 (spreads 4/4 positifs) mais s'est **inversé en Q1 2026** (correction de marché : top décile −3.5 %, bottom +0.4 % en H15) → le problème actuel du projet est la **protection en régime de correction**, pas le per-sector.
- Le per-sector, lui, a toujours été au niveau du hasard dès que les métriques ont été correctement alignées sur la target neutralisée.
- **Pivot décidé le 2026-08-14** : retour au **per-symbol** (protocole `prompt/ml/ml_analyse_per_symbol.md`, ablations F0-F4). Le per-sector ne fait plus partie de la chaîne de valeur.

---

## 9. Lancement, artefacts, DB

### 9.1 Commandes

Entraînement per-sector (research-only) :

```bash
python -m modelFactory --mode train \
  --training-mode per_sector \
  --target-mode regression --num-classes 1 \
  --forecast-horizons 3,5,10,15,20 \
  --target-up-threshold 0.03 --target-down-threshold -0.03 \
  --feature-set expert --benchmark-symbol SPY \
  --compare-lightgbm --enable-catboost --select-champion --walkforward \
  --symbol-source ticket-recherche \
  [--include-short-score] [--include-factors] [--target-excess-vs-spy] \
  [--include-fundamentals] [--enable-cross-sectional] [--enable-global-stacking] ...
```

Prédiction / backfill per-sector : `modelFactory/predict_per_sector.py` (job) ou `scripts/live_ml_predict_per_sector.py`, avec `--batch-id <id> <start> <end>`.

### 9.2 Environnement

- Python 3.14, venv `F:\projets\.venv\Scripts\python.exe` ; MySQL `alpha_trade` (root/root) ; Windows/PowerShell.
- Tables : `model_training_batch` (metadata_json), `model_metrics` (métriques par split/horizon), `model_predictions`, `global_rank_history`, `stock_bars_daily`, `stock_metadata` (provider_sector), `stock_fundamentals_daily`, `stock_scores_history`, `ticker_daily_sentiment_features`, `stock_macro_indicators_daily`.
- Artefacts : `artifacts/models/<batch_id>/...` (modèles + feature contract par secteur) ; rapports markdown générés par `modelFactory/report.py` ; univers `config/ticket_mid_cap_400.txt` / `config/ticket_recherche.txt`.

---

## 10. Questions ouvertes pour GPT (leviers à explorer)

1. **Pourquoi le per-sector est-il structurellement à 0.33 F1 / 50 % DirAcc** alors que le même feature set produit un IC positif en cross-sectionnel global ? Est-ce la neutralisation médiane (trop brutale ? bruit court-terme H3/H5 ?), la petite taille effective par secteur, ou l'absence de vraie dispersion intra-secteur prédictible ?
2. Un **ranking intra-secteur** (IC relatif par date + spread long-short net de coûts) pourrait-il être exploitable même avec un F1 directionnel nul ? (métriques jamais mesurées — levier #1 du §7)
3. Quelles **informations PIT nouvelles** (révisions analystes, flux ETF sectoriels, événements sectoriels) pourraient matérialiser une hypothèse de ré-entrée conforme à la règle du §1.2 ?
4. Le secteur reste utile **passivement** : le projet l'utilise déjà pour neutraliser la target du Global Ranking, limiter la concentration (`max_tickers_per_sector`), appliquer des multiplicateurs de sizing et calculer des diagnostics (Brinson-Fachler : `backtesting/brinson_fachler.py`, `tests/test_brinson_fachler.py`). Y a-t-il d'autres usages passifs du secteur (ex. covariance par bloc sectoriel, couverture de risque de facteur) qui apporteraient de la valeur sans exiger un alpha sectoriel ?

---

## 11. Références

| Document | Chemin |
|---|---|
| Doc module (architecture complète) | `doc/ml/module_model_factory.md` (§5 = per-sector) |
| Flags & features par mode | `doc/ml/features_ml.md` |
| Journal de recherche ML (toutes décisions) | `doc/ml_todo.md` |
| Journal des batchs B0-B44 | `doc/ml/global_per_sector/test/test_global_per_sector.md` |
| Plan d'action ML 1 (diagnostic per-sector) | `prompt/ml/ml_todo_1.md` |
| Analyse OOS 2026 (contexte Global) | `doc/ml/analyse_oos.txt` |
| Ordre d'exécution / workflow | `doc/ml/ordre_execution_ml.md` |
| Synthèse regression/ternaire/équilibre | `prompt/ml/per-symbol_sector.md` |
| Mémoire fix contrat prédiction | (repo memory) `per_sector_predict_fix_2026-08-06` |
