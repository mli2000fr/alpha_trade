# Module ModelFactory — Documentation Complète

> **Version** : Sprint 2026-08-01 (à jour des tests A/B)  
> **Auteur** : Généré automatiquement depuis le code source

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture globale](#2-architecture-globale)
3. [Phase 1 — Global Ranking Model](#3-phase-1--global-ranking-model)
4. [Phase 2 — Per-Symbol Training](#4-phase-2--per-symbol-training)
5. [Sélection du Champion](#5-sélection-du-champion)
6. [Diagnostics Batch & Garde-fous](#6-diagnostics-batch--garde-fous)
7. [Prédiction & Inférence](#7-prédiction--inférence)
8. [IC Per-Symbol](#8-ic-per-symbol)
9. [Configuration](#9-configuration)
10. [Tables DB](#10-tables-db)
11. [Résultats & Benchmark](#11-résultats--benchmark)

---

## 1. Vue d'ensemble

Le module `modelFactory` est le cœur ML du système α-Trade. Il assure :

1. **Classement cross-sectionnel** : un modèle Global Ranking (CatBoost RMSE) qui ordonne tous les symboles de l'univers par rendement futur attendu sur 5 horizons → `global_rank ∈ [0, 1]`
2. **Prédiction directionnelle par symbole** : des modèles per-symbol (LSTM, LightGBM, CatBoost) qui prédisent `proba_long` / `proba_short` pour chaque symbole individuellement
3. **Garde-fous qualité** : filtrage automatique des symboles dont les modèles sont trop faibles (F1 bas, zéro short, etc.)
4. **Sélection automatique du meilleur modèle** par symbole (champion selection)

### Flux simplifié

```
Entraînement :
  Global Ranking (1 modèle, tous symboles) → global_rank_3/5/10/15/20
  Per-Symbol (~500 modèles, 1 par symbole)   → proba_long, proba_short
  Diagnostics batch                           → top/bottom N, weak, S7

Inférence (Live/Backtest) :
  global_rank × proba_long → cascade_select → trades filtrés
```

---

## 2. Architecture globale

```mermaid
flowchart TD
    A[run_training_batch] --> B[Phase 1 : Global Ranking Walk-Forward]
    B --> B1[train_global_ranking_wf<br/>CatBoost RMSE<br/>5 horizons J+3,5,10,15,20]
    B1 --> B2[global_rank_df<br/>symbol, date, rank ∈ 0..1]
    
    B2 --> C{Stacking ?}
    C -->|⚠️ Contre-indiqué| D[Déconseillé : rend le Per-Symbol<br/>dépendant du Global Ranking]
    C -->|✅ Recommandé| E[Phase 2 : Per-Symbol Training
    indépendant, patterns locaux]
    
    E --> E1[N workers parallèles<br/>LSTM + LightGBM + CatBoost<br/>+ Global Model en stacking]
    E1 --> E2[select_champion<br/>par symbole]
    
    E2 --> F[Post-Training]
    F --> F1[persist_batch_diagnostics<br/>top/bottom N, S7, weak]
    F --> F2[IC Per-Symbol<br/>depuis prédictions WF]
    F --> F3[Persist metadata_json<br/>pour IHM / rapport]
```

### Ordre des sections dans le rapport

| Ordre | Section | Contenu |
|-------|---------|---------|
| 1 | 📋 Détail du batch | Métadonnées, IC Rank Global, Stacking |
| 2 | 🏆 Sélection du champion | auto / fallback par modèle |
| 3 | 🔬 IC Per-Symbol | Tableau H3/H5/H10/H15/H20 |
| 4 | 🌐 Global Ranking — Détails | IC, Decile Spread, FI, splits par horizon |
| 5 | 📊 Métriques F1 par split | F1 macro/short/flat/long par modèle × split |
| 6 | 📊 Distribution true/pred | % short/flat/long prédit vs réel |
| 7 | 📈 Distribution F1 macro WF | Histogramme par bucket |
| 8 | 📅 Diagnostic par régime | F1 × régime de marché (bear/bull/range) |
| 9 | 🏆 Top 10 / Flop 10 | Meilleurs/pires symboles par F1 macro WF |
| 10 | ⚪ f1_short = 0 | Symboles sans signal short |

---

## 3. Phase 1 — Global Ranking Model

### 3.1 Objectif

Produire un **score de ranking cross-sectionnel** par symbole et par date, sur 5 horizons.

**Modèle** : CatBoost `RMSE` (principal, meilleur qu'LightGBM LambdaRank sur cet usage)  
**Objectif** : régression sur le rang continu [0, 1]  
**Métrique** : **IC Rank** (Spearman), pas de F1  
**Sortie** : `global_rank_h ∈ [0, 1]` — percentile dans l'univers  
**IC actuel** : 0.0208 (+84% vs baseline 0.0113), tous les IC IR > 1.0

### 3.2 Construction de la target

Pour chaque horizon $h \in \{3, 5, 10, 15, 20\}$ :

```
1. Rendement forward brut  : future_return_h = close[t+h] / close[t] - 1
2. Vol scaling (h ≥ 5)     : future_return_h /= rolling_volatility_20
   (H3 : pas de scaling, vol 20j décorrélée du rendement 3j)
3. Winsorization            : clip 1%/99% intra-date
4. Percentile rank          : rank(pct=True) → [0, 1]
5. Décile discret           : label_h = floor(rank × 10).clip(0, 9)
6. Target smoothing (h ≥ 10): blend 50% horizon + 50% avg(10,15,20) → re-rank
   (H3/H5 exclus du smoothing : trop bruités, pas de vol scaling pour H3)
7. Sector-neutral (tous)    : soustraire médiane sectorielle → re-rank → re-label
8. Factor-neutral (tous)    : OLS résiduel sur size+value+momentum → re-rank → re-label
```

| Horizon | Vol scaling | Fondamentales | Smoothing | Sector-neutral | Factor-neutral |
|---------|-------------|---------------|-----------|----------------|----------------|
| H3 | ❌ | ❌ | ❌ | ✅ | ✅ |
| H5 | ✅ | ✅ | ❌ | ✅ | ✅ |
| H10/15/20 | ✅ | ✅ | ❌ | ✅ | ✅ |

> **Smoothing supprimé** (Sprint 2026-08-02) : le mélange cross-horizon diluait
> le signal après correction du data leakage. H20 passe de 0.0140 à 0.0191 sans.
> **Vol scaling** : Testé OFF → IC -27%, conservé ON pour H5+.
> **Sector-neutral** : +84% IC — le levier le plus puissant.
> **H3/H5 réactivés** : IC 0.009/0.014, H5 pour trading 5j.

### 3.3 Walk-Forward

- **Fenêtre glissante** : 756 jours de train (max), 126j val, 126j test
- **Purge** : 1 jour (marge de sécurité résiduelle, P1 post-split)
- **Splits** : **8 × 252j** (optimal sans leakage ; 13 × 126j sous-performe)
- **Poids temporels** : `exp(-days_diff / 360)` — demi-vie ~12 mois

> **8 splits > 13 splits** (Sprint 2026-08-02) : avec target post-split étanche,
> 13 splits ont 83% de chevauchement → val corrélé. 8 splits × 252j →
> diversité des régimes, IC +40%, IR ×2. **504j** trop court, **1008j** diminishing.

### 3.4 Features

| Catégorie | Nb | Description |
|-----------|----|-------------|
| Base (OHLCV) | ~13 | daily_return, log_return, intraday_range, etc. |
| Expert | ~18 | SMA distances, momentum, relative strength, régime |
| Multi-horizons | ~17 | H3-H250 momentum, volatilité, RSI |
| Interactions | ~16 | momentum/vol, RSI/vol, SMA cross |
| Dynamique temporelle | ~6 | accel, decay, RSI slope, vol expansion |
| Z-scores | ~26 | Normalisation temporelle sur 5 ans |
| Régime × technique | ~18 | momentum × bull/bear, vol × bull/bear |
| Cross-sectional | 8 | Rangs percentiles intra-date |
| Sector features | 8 | Agrégats sectoriels |
| Sector-neutral | 13 | Techniques + fondamentales neutralisées |
| Fondamentales | ~23 | PE, ROE, marges, croissance (EODHD) |
| Facteurs CAPM | 4 | Beta, alpha, R² |

**Total** : ~177 features (160 pour H3, sans fondamentaux).

**Features blacklistées** (identiques ∀ symboles → pas de pouvoir discriminant) :
- Macro globales : VIX/VXN/VIX3M/MOVE
- Secteur agrégé : `sector_ret_*`, `sector_vol_*`, `sector_dollar_volume_*`
- Liquidité : `dollar_volume_20_rank`
- CAPM : `beta_252`, `alpha_252`, `r_squared_252`
- Volatilité 120j et `*_sector_neutral` de volatilité
- Fondamentales brutes (versions `_sector_neutral` conservées)
- Estimations analystes indisponibles
- Poids morts Mid Caps : `log_return`, `daily_return` bruts, `close_to_vwap`, `volume_zscore_5d`, `accel_3_5`

> **Note 2026-08-01** : `regime_risk_off` et `regime_bull_market` sont **dé-blacklistés** — les arbres (CatBoost) peuvent apprendre des splits conditionnels au régime.

### 3.5 Modèle

| Paramètre | Valeur | Note |
|-----------|--------|------|
| Algorithme | **CatBoost RMSE** | Meilleur que LightGBM LambdaRank (+60%) |
| `ranking_max_depth` | 7 | Indépendant du per-symbol (5) |
| `ranking_num_leaves` | 31 | Cohérent avec depth=7 |
| `n_estimators` | 500 | |
| `learning_rate` | 0.03 | |
| `loss_function` | RMSE | Régression sur rang continu |

> **LightGBM LambdaRank** testé : IC 0.0130 vs CatBoost 0.0208. LambdaRank ignore `regime_*` (importance 0.0), perd 20% des données (early stopping), et la MSE tolère mieux l'incertitude du classement.

### 3.6 Feature Importance

Calculée via `gain` (LightGBM) ou `feature_importance` (CatBoost). Moyennée sur tous les splits WF. Les fondamentales dominent le top 10 (PE, ROE, debt_to_equity, PS ratio), suivies des features de momentum long-terme (momentum_250, SMA distances).

### 3.7 Limitation du nombre de symboles

Paramètre `--global-ranking-max-symbols` (défaut: 300, IHM: 0 = tous).  
Si > 0 : garde les **top N par volume moyen** ou stratifié par déciles.

---

## 4. Phase 2 — Per-Symbol Training

### 4.1 Objectif

Pour **chaque symbole** de l'univers, entraîner un modèle qui prédit la direction (long/short/flat) ou un score continu (regression).

**Modèles** : LSTM Attention, LightGBM, CatBoost (3 challengers par symbole)  
**Target** : `future_return` (binaire, ternaire, ou regression selon config)  
**Métrique** : **F1 macro** (moyenne de F1 short, F1 flat, F1 long) — y compris en mode regression où le F1 est calculé par binarisation du signe

### 4.2 Mode ternaire (3 classes)

```
proba_short + proba_flat + proba_long = 1.0

Décision :
  if proba_long > threshold_long  → LONG
  if proba_short > threshold_short → SHORT
  else → FLAT
```

Seuils : `ternary_threshold_short` (0.35), `ternary_threshold_long` (0.35), `top2_margin` (0.02).

### 4.3 Mode regression (continu)

Ajouté le 2026-08-02. La target n'est plus discrète (long/short/flat) mais continue :

```
1. Rendement forward brut : future_return = close[t+h] / close[t] - 1
2. Vol scaling (h ≥ 5)   : target = future_return / rolling_vol_20
3. Winsorization          : clip 1%/99% par symbole
```

**Spécificités** :
- **Modèle** : `num_classes=1` → 1 neurone de sortie, loss **MSE** (pas CrossEntropy)
- **Métriques** : MSE, MAE, corrélation, directional accuracy, IC
- **F1 comparable** : binarisation du signe — `sign(pred)` vs `sign(future_return)` → classes {-1,0,1} → F1 macro identique au mode ternaire
- **Décision** : score > 0 → LONG, score < 0 → SHORT, score ≈ 0 → FLAT
- **Calibration** : désactivée (pas de Platt sur une régression)
- **Pas de threshold optimization** : ignorée automatiquement

**Avantages vs ternaire** :
- Pas de seuils arbitraires (up_threshold/down_threshold) — le modèle apprend la magnitude
- La force du signal est directement utilisable (pas juste une probabilité)
- Comparaison équitable avec le ternaire grâce au F1 binarisé

### 4.4 Walk-Forward

Mêmes splits que le Global Ranking. Chaque split produit des métriques sur train/val/test, agrégées en fin de boucle.

### 4.5 Stacking (injection des rangs globaux) ⚠️ Contre-indiqué

Quand `global_model.stacking_enabled = True` :

```
Avant entraînement per-symbol :
  cross_sectional_cache ← merge(global_rank_df[["symbol", "date", "global_rank_10", "_15", "_20"]])
  NaN → 0.5 (rang neutre)

Le modèle per-symbol voit donc les rangs cross-sectionnels comme features supplémentaires.
```

> **⚠️ Le stacking est une mauvaise idée pour le Per-Symbol.**
>
> Si tu donnes le `global_rank` de la Phase 1 comme feature à la Phase 2, tes modèles
> Per-Symbol (LSTM, LightGBM, CatBoost) vont devenir **dépendants du marché global**.
> Ils vont perdre leur capacité à détecter les figures de retournement propres au symbole
> et ne feront que « recopier » la tendance générale identifiée par la Phase 1.
>
> **Conséquence** : le Per-Symbol devient un simple amplificateur du Global Ranking,
> perdant toute sa valeur ajoutée (détection de patterns locaux, divergences,
> retournements idiosyncratiques). Les deux phases doivent rester complémentaires,
> pas redondantes.
>
> **Recommandation** : laisser `stacking_enabled = false`. Le Global Ranking
> et le Per-Symbol jouent des rôles distincts dans la cascade de trading (§7.2).

### 4.6 Limitation per-symbol (test rapide)

Paramètre `--per-symbol-max-symbols` (défaut: 0 = tous).  
Si > 0 : garde les **top N par volume moyen**, avant l'entraînement per-symbol.  
Le Global Ranking n'est PAS affecté.

---

## 5. Sélection du Champion

### 5.1 Principe

Pour chaque symbole, parmi les 3 challengers (LSTM, LightGBM, CatBoost), on sélectionne le **meilleur** selon des critères de qualité.

> **Note** : Le **Global Model ne participe pas** à la sélection du champion. Son rôle est différent :
> - Ses rangs (`global_rank_3/5/10`) sont injectés comme **features** dans les modèles per-symbol (stacking)
> - Il est utilisé dans la **cascade de trading** (`global_rank × proba_long` → score du trade)

### 5.2 Modes de sélection

| Mode | Condition | Modèle choisi |
|------|-----------|---------------|
| `auto_selected_champion` | ≥1 challenger éligible | Max `selection_score` (F1 macro WF) |
| `fallback_default_champion` | Aucun éligible | Modèle par défaut (ex: `lstm_attention`) |
| `default_champion` | Auto-sélection désactivée | Modèle par défaut |

### 5.3 Critères d'éligibilité

Un modèle est éligible si TOUS ces critères sont remplis :

1. **Statut** : `completed`
2. **Backend** : `lstm_attention`, `lightgbm_tabular`, `catboost_tabular`, ou `global_tabular`
3. **Artefacts** : fichiers checkpoint/scaler/config/model existent
4. **Métriques valides** :
   - Pas de `proba_valid = False`
   - AUC ∈ [0, 1] en val et WF
   - Pas de `collapsed = True`
   - `action_rate > 0` en ternaire
   - `n_observations ≥ 50` en val et WF
5. **Quarantaine** (optionnelle) : ≥ `min_runs` runs, premier succès ≥ `min_days` jours

### 5.4 Selection Score

Calculé à partir des partitions **val et walk_forward uniquement** (jamais test) :
- Priorité 1 : `f1_macro` dans `wf.mean`
- Priorité 2 : `f1_macro` dans `wf`
- Priorité 3 : `f1_macro` dans `val`
- Fallback : `auc` dans les mêmes partitions
- Si aucune métrique trouvée → `-∞` (jamais sélectionné)

---

## 6. Diagnostics Batch & Garde-fous

### 6.1 Top / Bottom N

Pour chaque symbole, classé par **F1 macro WF** décroissant :

| Groupe | Règle | Impact Live/Backtest |
|--------|-------|---------------------|
| **Top N** | N meilleurs F1 macro | Favorisés pour le sizing |
| **Bottom N** | N pires F1 macro | **Exclus** long ET short |

$N = \min(50, \text{total\_symbols})$, configurable.

### 6.2 Seuils directionnels

| Type | Condition | Impact |
|------|-----------|--------|
| `zero_short` | `f1_short == 0.0` | **Exclu short** |
| `weak_long` | `0 < f1_long < 0.15` | **Exclu long** |
| `weak_short` | `0 < f1_short < 0.15` | **Exclu short** |

### 6.3 Règles S7 (seuils absolus)

| Classe | Condition | Signification |
|--------|-----------|---------------|
| `s7_exclude_all` | `f1_long < 0.30` ET `f1_short < 0.30` | Aucune direction fiable → **exclu tout** |
| `s7_flat_pathological` | `f1_flat < 0.10` | Ne sait pas identifier les jours flat → **exclu tout** |
| `s7_long_only` | `f1_long > 0.40` ET `f1_short < 0.20` | Long OK, **short interdit** |
| `s7_short_only` | `f1_short > 0.40` ET `f1_long < 0.20` | Short OK, **long interdit** |
| `s7_monitor` | `f1_long > 0.35` ET `0.20 ≤ f1_short ≤ 0.30` | Alerte seulement, pas d'exclusion |

### 6.4 Filtrage final pour le Live/Backtest

```python
exclude_long  = bottom ∪ weak_long ∪ s7_exclude_all ∪ s7_flat_pathological ∪ s7_short_only
exclude_short = bottom ∪ zero_short ∪ weak_short ∪ s7_exclude_all ∪ s7_flat_pathological ∪ s7_long_only
prefer        = top
```

---

## 7. Prédiction & Inférence

### 7.1 Cascade de modèles par symbole

Au moment de prédire pour un symbole, le système utilise le champion sélectionné (LSTM, LightGBM, ou CatBoost). En cas d'échec, fallback vers le LSTM :

```
1. Champion (tel que sélectionné)
   └─ Échec → 2. LSTM Attention (fallback ultime)
```

Le Global Model n'est pas dans cette cascade — il est utilisé séparément via la cascade de trading (§7.2).

### 7.2 Cascade de trading (cascade_ml.md)

Combine **rang global** et **prédiction per-symbol** pour décider quels trades prendre :

```
Pour chaque symbole avec global_rank ET per-symbol prediction :
1. rank_avg = (global_rank_10 + global_rank_15) / 2
2. Si rank_avg > 0.80 (top 20%) ET proba_long > seuil → candidat LONG
3. Si rank_avg < 0.20 (bottom 20%) ET proba_short > seuil → candidat SHORT
4. Score = rank_avg × proba_long (ou (1-rank_avg) × proba_short)
5. Trié par score décroissant
```

### 7.3 Conversion proba/score → décision

**Mode binaire** :
```
pred_class = 1 si proba_long ≥ decision_threshold (0.55) sinon 0
```

**Mode ternaire** :
```
TernaryDecisionPolicy :
  si proba_long > threshold_long (0.35) ET proba_long - proba_flat > top2_margin → LONG
  si proba_short > threshold_short (0.35) ET proba_short - proba_flat > top2_margin → SHORT
  sinon → FLAT
```

**Mode regression** :
```
Décision au signe :
  si score > 0  → LONG  (pred_class=1, signal_label="long")
  si score < 0  → SHORT (pred_class=0, signal_label="short")
  si score ≈ 0  → FLAT  (pred_class=0, signal_label="no_trade")

Le score continu est stocké dans predicted_proba et raw_proba.
Pas de seuil de décision (decision_threshold ignoré).
```

---

## 8. IC Per-Symbol

### 8.1 Définition

L'IC Per-Symbol mesure la capacité de ranking cross-sectionnel **des modèles per-symbol agrégés** (≠ Global Ranking qui a son propre IC).

### 8.2 Calcul

```
1. Walk-Forward : pour chaque symbole, on sauvegarde (date, proba_long, close, future_return)
   → artifacts/<batch>/_per_symbol_wf_preds/<SYMBOLE>.parquet

2. Après le batch : _compute_per_symbol_ic_from_parquet()
   → lit tous les parquets
   → concatène par date tous symboles
   → pour chaque horizon h ∈ {3,5,10,15,20} :
       future_return_h = close[t+h]/close[t] - 1
       compute_cross_sectional_ic(score_col="proba_long", return_col="future_return_h")
   → stocke dans metadata_json.per_symbol_ic = {"3": {ic_mean, ic_std, n_dates}, ...}
```

### 8.3 Interprétation

| IC | Interprétation |
|----|---------------|
| > 0.02 | Bon — le signal per-symbol classe bien les actions |
| 0.01 - 0.02 | Utile — exploitable avec diversification |
| < 0.01 | Faible — signal peu discriminant |
| < 0 | Le classement est inversé |

L'IC IR (IC Mean / IC Std) mesure la **stabilité** :
- > 0.5 : bon
- > 1.0 : excellent

### 8.4 Comparaison stacking

L'IC Per-Symbol permet de comparer deux batchs :
- Batch A : `stacking_enabled = true` → IC avec stacking
- Batch B : `stacking_enabled = false` → IC sans stacking
- Si IC(A) > IC(B) → le stacking ajoute de la valeur

---

## 9. Configuration

### 9.1 Paramètres clés

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `forecast_horizon` | 10 | Horizon de prédiction (jours) |
| `feature_set` | `expert` | `v1` ou `expert` (plus de features) |
| `target_mode` | `ternary` | `binary`, `ternary`, ou `regression` (score continu) |
| `global_ranking_max_symbols` | 300 | Limite symboles Global Ranking (0 = tous) |
| `per_symbol_max_symbols` | 0 | Limite symboles Per-Symbol (0 = tous) |
| `wf_max_splits` | **8** | Nombre de splits walk-forward (optimal P1) |
| `wf_min_train_size` | 504 | Taille min fenêtre train (jours) |
| `wf_step_size` | **252** | Pas entre splits (jours) |
| `max_train_size` | **756** | Fenêtre train max (sweet spot) |
| `demi-vie` | **360j** | Poids temporels (12 mois) |
| `target_smoothing` | **OFF** | Supprimé — diluait le signal sans leakage |

### 9.2 Global Ranking (GlobalModelConfig)

| Paramètre | Défaut | Note |
|-----------|--------|------|
| `model_name` | `catboost` | CatBoost RMSE > LightGBM LambdaRank |
| `ranking_max_depth` | 7 | Indépendant du per-symbol |
| `ranking_num_leaves` | 31 | Cohérent avec depth=7 |
| `enabled` | false | Flag A : active le Global Ranking |
| `stacking_enabled` | false | Flag B : injecte global_rank dans per-symbol |
| `use_cross_sectional_features` | true | |

### 9.3 Per-Symbol (BaselineConfig)

| Paramètre | Défaut | Note |
|-----------|--------|------|
| `max_depth` | 5 | Conservateur (peu de données) |
| `lgbm_num_leaves` | 15 | Cohérent avec depth=5 |
| `n_estimators` | 500 | |
| `learning_rate` | 0.03 | |
| `lgbm_min_child_samples` | 150 | |
| `lgbm_colsample_bytree` | 0.7 | |

> **Séparation des configs** : `GlobalModelConfig` (ranking) et `BaselineConfig` (per-symbol) sont indépendants. Les paramètres `n_estimators`, `learning_rate` et tuning LGBM sont partagés.

### 9.4 Target pipeline

```
future_return brut → vol scaling (H5+) → winsorize 1%/99% → rank intra-date
→ sector-neutral (médiane secteur) → re-rank → label décile 0..9 [tous]
→ factor-neutral (OLS résiduel size+value+momentum) → re-rank → label [tous]
```

| Horizon | Vol scaling | Fondamentales | Sector-neutral | Factor-neutral |
|---------|-------------|---------------|----------------|----------------|
| H3 | ❌ | ❌ | ✅ | ✅ |
| H5 | ✅ | ✅ | ✅ | ✅ |
| H10/15/20 | ✅ | ✅ | ✅ | ✅ |

> **Smoothing retiré** (Sprint 2026-08-02) — contre-productif sans data leakage.

### 9.5 Garde-fous (config.yaml)

```yaml
batch_diagnostics:
  top_n: 50
  bottom_n: 50
  weak_long_threshold: 0.15
  weak_short_threshold: 0.15
  section7:
    long_good_threshold: 0.35
    short_good_threshold: 0.30
    flat_min_threshold: 0.10
    exclude_long_max_threshold: 0.30
    exclude_short_max_threshold: 0.30
```

---

## 10. Tables DB

### 10.1 Schéma simplifié

```
model_training_batch
  ├── batch_id (PK)
  ├── status, started_at, finished_at
  ├── ic_rank, ic_rank_std
  ├── decile_spread_h3, h5, h10
  ├── stacking_enabled
  └── metadata_json (JSON : global_ranking, per_symbol_ic, liquidity_filter, ...)

model_training_run
  ├── run_id (PK)
  ├── batch_id (FK → model_training_batch)
  ├── symbol, status, registry_id
  └── train_start_date, train_end_date

model_metrics
  ├── run_id (FK)
  ├── symbol, model_name, split_name
  └── f1_macro, f1_short, f1_flat, f1_long, ...

model_governance
  ├── run_id (FK)
  ├── symbol, model_name
  ├── is_selected_model (boolean)
  └── selection_mode (auto_selected_champion / fallback_default_champion / default_champion)

model_batch_diagnostics
  ├── batch_id (FK)
  ├── symbol, rank_idx
  └── rank_type (top / bottom / zero_short / weak_long / weak_short / s7_*)

global_rank_history
  ├── batch_id, date, symbol
  └── global_rank_3, global_rank_5, global_rank_10

model_predictions
  ├── run_id (FK)
  ├── symbol, prediction_date
  └── predicted_proba, predicted_side, proba_long, proba_flat, proba_short

stock_fundamentals_daily
  ├── id (PK)
  ├── symbol, trade_date (UNIQUE)
  └── pe_ratio, roe, roa, net_margin, eps_growth_yoy, beta, market_cap, ...
```

### 10.2 metadata_json structure

```json
{
  "cli_options": {...},
  "liquidity_filter": {...},
  "global_ranking": {
    "horizon_details": {
      "10": {
        "ic_mean": 0.0083,
        "decile_spread": 0.0034,
        "n_features": 176,
        "splits": [...],
        "feature_importance_top10": [...],
        "feature_importance_bottom10": [...]
      },
      "15": {...}, "20": {...}
    },
    "ic_by_horizon": {"10": 0.0083, "15": 0.0095, "20": 0.0161},
    "decile_spreads": {"10": 0.0034, ...},
    "symbols_count": 928,
    "splits_count": 13,
    "pred_rows": 1338623
  },
  "per_symbol_ic": {
    "3": {"ic_mean": 0.0013, "ic_std": 0.05, "n_dates": 348, "n_symbols": 12},
    "5": {"ic_mean": 0.0041, ...},
    "10": {...}, "15": {...}, "20": {...}
  }
}
```

---

## 11. Résultats & Benchmark

### 11.1 Tests A/B (13 tests, 2026-08-01)

| # | Test | IC Global | Δ vs Baseline | Verdict |
|---|------|-----------|---------------|---------|
| 1 | **Baseline** (504j, CatBoost RMSE) | 0.0113 | — | référence |
| 2 | Vol scaling OFF | 0.0082 | -27% | ❌ |
| 3 | Excès vs SPY | 0.0106 | -6% | ❌ |
| 4 | Déciles vs vingtiles | 0.0113 | 0% | ❌ |
| 5 | Whitelist 53 features | 0.0064 | -43% | ❌ |
| 6 | **756j + régime dé-blacklisté** | **0.0144** | **+27%** | ✅ |
| 7 | 1008j | 0.0135 | +19% | ❌ |
| 8 | colsample_bytree 0.4 | 0.0144 | 0% | ❌ |
| 9 | **+ Target smoothing** | **0.0163** | **+44%** | ✅ conservé |
| 10 | max_depth 7, num_leaves 31 | 0.0166 | +47% | ✅ |
| 11 | LightGBM LambdaRank | 0.0130 → 0.0086 P1 | −24% | ❌ confirmé |
| 12 | **+ Target sector-neutral** | **0.0208** | **+84%** | 🔥🔥 |
| 13 | **8 splits × 252j** (vs 13 × 126j) | 0.0161 → 0.0194 P1 | inversé | 🔥🔥 adopté |
| 14 | Composite features (×11) | 0.0198 | +75% | ❌ |
| 15 | **+ H3/H5 (5 horizons)** | **0.0208** | **+84%** | 🔥 |
| 16 | **+ Target factor-neutral (OLS)** | **0.0208** | **+84%** | ✅ |
| R1 | **Baseline P1 réel** (504j, H10 seul, étanche) | 0.0084 | référence réelle | — |
| R2 | **Smoothing OFF** (P1, 13 splits) | H20 +36% | — | retiré |
| R3 | **8 splits × 252j** (P1) | **0.0194 (+40%)** | — | 🔥🔥 adopté |
| R4 | **8 splits + no smoothing** | H10 −24% vs avec | — | ❌ interaction |

### 11.2 Configuration gagnante

| Paramètre | Valeur |
|-----------|--------|
| Modèle | CatBoost RMSE |
| Horizons | **3, 5, 10, 15, 20** |
| Fenêtre train | 756j (rolling) |
| Demi-vie | 360j |
| Target smoothing | **50% h + 50% avg(10,15,20)** (H3/H5 bruts) — inactif sans 8 splits |
| Target sector-neutral | Oui (tous horizons) |
| Target factor-neutral | Oui (OLS size+value+momentum) |
| Target computation | **Post-split (P1 étanche)** |
| ranking_max_depth | 7 |
| Splits | **8 × 252j** (optimal, +40% IC vs 13 × 126j) |
| Features | ~177 (160 pour H3) |

> **Interaction smoothing × splits** : avec 13 splits (83% chevauchement), le smoothing dilue.
> Avec 8 splits (régimes distincts), il apporte +31% sur H10. Les deux sont complémentaires.

### 11.3 Métriques finales (P1 étanche, 8 splits, smoothing ON, Z-score fondamentales)

| Métrique | H3 | H5 | H10 | H15 | H20 | Global |
|----------|----|----|-----|-----|-----|--------|
| IC Mean | 0.0129 | **0.0120** | 0.0211 | 0.0239 | 0.0251 | **0.0190** |
| IC IR | 1.46 | **1.19** | 1.69 | 2.28 | 2.76 | — |
| Decile Spread | 0.0116 | 0.0147 | 0.0238 | 0.0247 | 0.0260 | — |

> Baseline P1 réel (504j, H10 brut) = 0.0084 / IR 0.30.
> Pipeline target ×2.3, 8 splits +40%, Z-score stabilise H15/H20.

### 11.4 Leçons apprises

1. **Target sector-neutral** est le levier #1 (+84% IC). Sans cela, on fait du sector-riding, pas du stock-picking.
2. **CatBoost RMSE > LightGBM LambdaRank** pour le ranking financier faible signal.
3. **756j** est le sweet spot de fenêtre train (504 trop court, 1008 diminishing).
4. **13 splits > 8 splits** — granularité fine → adaptation au régime.
5. **Smoothing + 8 splits sont complémentaires** — +31% H10 vs sans. Le smoothing seul (13 splits) diluait.
6. **Moins de features ≠ meilleur** — les arbres excellent à combiner des signaux faibles.
7. **Le vol scaling est indispensable** (testé OFF : -27%).
8. **Configs séparées** : `GlobalModelConfig` vs `BaselineConfig`.
9. **Composites inutiles** : les arbres apprennent déjà ces interactions.
10. **H3/H5 viables** : IC IR > 1.0, H5 exploitable pour trading 5j.
11. **Target post-split** : l'unique source de leakage était le shift pré-split — corrigé, le pipeline est étanche.
12. **8 splits > 13 splits** (post-leakage) : moins de chevauchement → meilleure généralisation, IC +40%.

---

## 12. Questions / Réponses

### Q1 : Per-Symbol, Comment comparer réellement la performance entre le mode ternaire et le mode regression ?

Les métriques des deux modes sont **directement comparables** car le F1 est calculé de la même façon dans les deux cas : par binarisation du signe. Cependant, il y a des pièges à éviter.

#### ⚠️ Ne pas utiliser `f1_macro` pour comparer

En mode regression, le F1 est calculé ainsi :

```
pred_side = sign(pred)         → +1 (long), -1 (short), 0 (flat)
true_side = sign(future_return) → +1, -1, 0
```

Or un modèle de régression ne prédit **jamais exactement 0.0** (sortie continue). Donc :

| Classe | Regression | Ternaire |
|--------|-----------|----------|
| `f1_long` | ✅ Comparable | ✅ Comparable |
| `f1_short` | ✅ Comparable | ✅ Comparable |
| `f1_flat` | ❌ Toujours ~0 | ✅ Peut être >0 |
| `f1_macro` | ❌ Mécaniquement tiré vers le bas | ✅ Correct |

→ **`f1_macro` est systématiquement plus bas en regression**, ce qui ne reflète pas une moins bonne performance mais un artefact de la binarisation.

#### ✅ Métriques recommandées pour la comparaison

| Métrique | Signification | Disponible |
|----------|--------------|------------|
| **`f1_long`** | Capacité à identifier les jours haussiers | LSTM + baselines |
| **`f1_short`** | Capacité à identifier les jours baissiers | LSTM + baselines |
| **`directional_accuracy`** | % de jours où sign(pred) = sign(future_return) | LSTM + baselines |
| **`ic`** (Information Coefficient) | Corrélation prédiction vs rendement futur | LSTM + baselines |
| **`mse`** / **`mae`** | Erreur de prédiction absolue | Regression seulement |
| **`correlation`** | Corrélation pred vs target continue | Regression seulement |

#### Exemple de comparaison

```
Modèle A (ternaire) :  f1_long=0.35, f1_short=0.28, f1_flat=0.25, f1_macro=0.293
Modèle B (regression): f1_long=0.37, f1_short=0.30, f1_flat=0.00, f1_macro=0.223

→ f1_macro : A gagne (0.293 vs 0.223) ← ⚠️ trompeur!
→ f1_long  : B gagne (0.37 vs 0.35)   ← ✅ vrai signal
→ f1_short : B gagne (0.30 vs 0.28)   ← ✅ vrai signal
→ IC       : B (0.045) vs A (0.038)    ← ✅ B mieux corrélé aux rendements

Conclusion : B (regression) est meilleur en signal directionnel pur.
```

#### 🏆 Critère de décision final

| Si tu veux... | Utilise |
|---------------|---------|
| Un signal directionnel fort (long/short) | `f1_long` + `f1_short` → le meilleur gagne |
| Un score de confiance continu (forces de conviction) | Regression (le score est directement la force du signal) |
| Rester neutre souvent (frais de transaction réduits) | Ternaire (la classe flat est activement apprise) |
| Éviter les seuils arbitraires (up/down_threshold) | Regression (pas de seuils, le modèle apprend la magnitude) |

> **Règle pratique** : si `f1_long` et `f1_short` sont plus élevés en regression qu'en ternaire,
> la regression est objectivement meilleure — ignore `f1_macro` et `f1_flat`.

### Q2 : Per-Symbol, Comment savoir si les scores de regression sont bons ou mauvais ?

Les métriques de regression (MSE, MAE, IC, directional accuracy) n'ont pas la même échelle
que le F1 (0 à 1). Voici comment les interpréter.

#### 📊 Les métriques et leurs seuils

| Métrique | Excellent | Correct | Faible | Inutilisable | Signification |
|----------|-----------|---------|--------|--------------|---------------|
| **MSE** | < 0.5 | 0.5 – 1.5 | 1.5 – 3.0 | > 3.0 | Erreur quadratique moyenne sur la target vol-scalée |
| **MAE** | < 0.5 | 0.5 – 1.0 | 1.0 – 1.5 | > 1.5 | Erreur absolue moyenne |
| **Directional Accuracy** | > 0.54 | 0.51 – 0.54 | 0.50 – 0.51 | < 0.50 | % de signes corrects (pire que le hasard si < 0.50) |
| **IC** | > 0.03 | 0.01 – 0.03 | 0.00 – 0.01 | < 0.00 | Corrélation pred vs future_return |
| **Correlation** | > 0.10 | 0.03 – 0.10 | 0.00 – 0.03 | < 0.00 | Corrélation pred vs target continue |

#### 🔍 Diagnostic rapide

**1. Vérifie d'abord le « modèle nul »**

Un modèle naïf qui prédit toujours 0 (ou la moyenne) donne :

$$MSE_{nul} = Var(target) \approx 0.5 \text{ à } 1.5$$

Si ton MSE > 2.0 → le modèle fait **pire que de ne rien prédire**. Il est cassé.

**2. Vérifie la directional accuracy**

```
directional_accuracy > 0.50 → le modèle bat le pile-ou-face
directional_accuracy > 0.53 → signal exploitable
directional_accuracy > 0.55 → très bon
```

C'est la métrique la plus intuitive : quel % du temps le signe prédit est-il correct ?

**3. Vérifie la cohérence entre les métriques**

| Situation | Diagnostic |
|-----------|-----------|
| MSE bas + IC élevé + dir_acc > 0.53 | ✅ Modèle sain, signal réel |
| MSE élevé (>3) + dir_acc > 0.52 | 🟡 Le modèle capte la direction mais pas la magnitude — acceptable |
| MSE bas (<1) + dir_acc < 0.50 | 🟡 Le modèle fit bien la target mais prédit le mauvais signe — inutilisable en trading |
| MSE bas + IC élevé + dir_acc ≈ 0.50 | 🟡 Le modèle prédit bien le rang cross-sectionnel mais pas la direction absolue |
| MSE > 5 | ❌ Modèle non convergé, erreur d'échelle, ou target mal normalisée |

#### 📐 Comprendre l'échelle de la target

La target regression est un rendement forward **divisé par la volatilité 20j** puis winsorizé :

```
future_return ≈ ±2% à ±8% sur 10j
vol_20j       ≈ 1.5% à 3% par jour
target        ≈ future_return / vol_20j ≈ ±0.5 à ±5
Après winsorize 1%/99%                ≈ ±2 à ±3 (valeurs extrêmes coupées)
```

Donc une **MAE de 1.0** signifie que le modèle se trompe en moyenne de 1 unité de vol — soit environ 2% de rendement pour un titre à vol 2%. C'est beaucoup mais pas aberrant pour un modèle financier.

#### 🎯 Combinaison gagnante

Un bon modèle regression doit avoir **simultanément** :

```
MSE < 1.5          (erreur contenue)
directional_accuracy > 0.52  (direction fiable)
IC > 0.01           (bon classement cross-sectionnel)
f1_long > 0.25      (détection haussière)
f1_short > 0.20     (détection baissière)
```

Si UNE SEULE de ces conditions manque, le modèle n'est pas exploitable en l'état.
13. **Smoothing conservé avec 8 splits** : contre-productif avec 13 splits (dilution), bénéfique avec 8 splits (signal frais +31% H10).
14. **LightGBM LambdaRank confirmé inférieur** : régimes ignorés (imp 0.0), IC −38% vs CatBoost.
15. **Pas besoin de retester les 18 pistes** : le leakage était proportionnel (33% constant). Les classements relatifs tiennent. Seuls smoothing, splits et LambdaRank interagissaient avec le mécanisme de leakage.
16. **Z-score fondamentales** : stabilise H15/H20 (IR +54%), léger trade-off sur H5.
17. **Blending inutile** : horizons trop corrélés, ne dépasse pas le meilleur horizon individuel.

### 11.5 Audit Data Leakage (2026-08-01) — ✅ RÉSOLU

**Conclusion** : Plus de data leakage. Le pipeline est étanche par construction.

#### Historique du problème

La target était pré-calculée sur `base_df` (toutes dates) **avant** les splits walk-forward.
Le `shift(-horizon)` trouvait le close futur au-delà des frontières train/val → biais de ~33%
sur l'IC global (0.0208 → 0.0139).

| Étape | Approche | IC Global | Statut |
|-------|----------|-----------|--------|
| Original | purge=1j, target pré-split | 0.0208 | ❌ 33% leakage |
| P0 | purge=20j, target pré-split | 0.0163 | 🟡 résiduel |
| **P1** | **target post-split** (`_compute_ranking_targets` par fold) | **0.0139** | ✅ **étanche** |

**P1** : la fonction `_compute_ranking_targets()` est appelée sur chaque fold isolément
(train puis val) dans la boucle split/horizon. Le `shift(-h)` ne peut pas physiquement
traverser les frontières car le DataFrame du fold ne contient pas les dates voisines.
Purge = 1j (marge de sécurité résiduelle uniquement).

#### 🟢 Composants vérifiés sans leakage (tous OK)

| Composant | Méthode | Statut |
|-----------|---------|--------|
| Features OHLCV | `rolling`, `shift(N)` backward | ✅ |
| Features cross-section | `groupby("date").rank(pct=True)` intra-date | ✅ |
| Features macro | `ffill()` PIT-safe | ✅ |
| Features fondamentales | `ffill()` par symbole, `trade_date ≤ date` | ✅ |
| Features facteurs (CAPM) | Rolling 252j backward-only | ✅ |
| Regime (bull/risk_off) | SMA/Std backward | ✅ |
| Sector-neutral target | `groupby(["date","_sector"]).median()` intra-date | ✅ |
| Factor-neutral target | OLS par date, résidus intra-date | ✅ |
| XS rank features | `groupby("date").rank(pct=True)` intra-date | ✅ |
| Sample weights | `exp(-days_diff/360)` dates train uniquement | ✅ |

---

## 12. Stratégie d'exploitation (validée par backtest 2026-08-02)

### 12.1 Principe : H20 seul pour la sélection

| Horizon | Rôle | IC / IR |
|---------|------|---------|
| **H20** | Filtre d'univers — quoi acheter | 0.0251 / 2.76 |
| **H5** | Monitoring uniquement (alerte si < 0.10) | 0.0120 / 1.19 |

**Logique** : H20 identifie les actions qui vont surperformer sur 1 mois (signal fiable, IR 2.76).
Le backtest a montré que tout filtre H5 (rising ou dip) dégrade la performance (−3.6% à −12.8%).
H5 est conservé uniquement comme signal de monitoring — une chute brutale (< 0.10) peut déclencher
une alerte de sortie, mais pas un signal d'entrée.

### 12.2 Algorithme

```python
# Pour chaque date, pour chaque symbole :
eligible = global_rank_20 > 0.70  # Top 30% H20
# C'est tout. Pas de filtre H5.
```

### 12.3 Paramètres de backtest

| Paramètre | Valeur |
|-----------|--------|
| Univers éligible | Top 30% H20 |
| Rebalancement | Toutes les 3-4 semaines |
| Frais A/R estimés | 0.25-0.30% par trade |
| Turnover cible | < 50% par mois |
| **H5** | Monitoring uniquement (alerte si < 0.10) |

---

## Annexe A — Glossaire

| Terme | Définition |
|-------|-----------|
| **IC Rank** | Information Coefficient — corrélation de Spearman entre rang prédit et rendement réalisé |
| **IC IR** | IC Information Ratio = IC Mean / IC Std — mesure la stabilité du signal |
| **Decile Spread** | Rendement moyen du top décile moins bottom décile |
| **F1 macro** | Moyenne non pondérée des F1 de chaque classe (short, flat, long) |
| **WF** | Walk-Forward — validation glissante PIT-safe |
| **PIT** | Point-In-Time — pas de fuite de données futures |
| **Stacking** | Injection du rang global comme feature dans les modèles per-symbol |
| **Champion** | Meilleur modèle sélectionné par symbole (LSTM, LightGBM ou CatBoost) |
| **S7** | Règles absolues d'exclusion basées sur les F1 |
| **Target smoothing** | Moyenne pondérée cross-horizon du forward return (50% h + 50% avg) |
| **Target sector-neutral** | Soustraction de la médiane sectorielle du forward return avant le rank |
| **CatBoost RMSE** | Régression sur rang continu — plus robuste que LambdaRank pour le signal faible |

## Annexe B — Flux de bout en bout

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ENTRAÎNEMENT (batch)                         │
├─────────────────────────────────────────────────────────────────────┤
│  1. Chargement univers (939 Mid Caps)                               │
│  2. Filtrage liquidité (volume, market cap, spread)                 │
│  3. Features (~188) : OHLCV + expert + cross-sectional + composites │
│                                                                     │
│  ┌─ Global Ranking (CatBoost RMSE) ────────────────────────┐      │
│  │  5 horizons (3,5,10,15,20), 756j train, 13 splits      │      │
│  │  Target : vol-scaled → smoothed(10+) → sector-neutral   │      │
│  │  Sortie : global_rank_df[symbol, date, rank_3..20]      │      │
│  │  Métrique : IC Rank ~0.021, tous IC IR > 1.0            │      │
│  └──────────────────────────────────────────────────────────┘      │
│                            ↓                                        │
│  ┌─ Per-Symbol Training ───────────────────────────────────┐      │
│  │  Pour chaque symbole (parallèle) :                      │      │
│  │    - LSTM Attention + LightGBM + CatBoost               │      │
│  │    - Walk-forward avec splits identiques                │      │
│  │    - select_champion() → 1 modèle élu par symbole       │      │
│  └──────────────────────────────────────────────────────────┘      │
│                            ↓                                        │
│  ┌─ Post-Training ─────────────────────────────────────────┐      │
│  │  - persist_batch_diagnostics (top/bottom N, S7, weak)   │      │
│  │  - _compute_per_symbol_ic_from_parquet                  │      │
│  │  - Persist metadata_json → IHM + rapport                │      │
│  └──────────────────────────────────────────────────────────┘      │
├─────────────────────────────────────────────────────────────────────┤
│                      INFÉRENCE (live/backtest)                       │
│  Pour chaque date :                                                 │
│  1. Charger global_rank_history[date]                               │
│  2. Pour chaque symbole : predict_symbol() → proba_long/short/flat  │
│  3. cascade_select(global_rank × proba) → candidats triés           │
│  4. filter_predictions(batch_diagnostics) → exclusion weak/bottom   │
│  5. Sortie : liste de trades (symbol, side, score)                  │
└─────────────────────────────────────────────────────────────────────┘
```
