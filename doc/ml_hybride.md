# ML Hybride — Features Cross-Sectionnelles & Sectorielles

## 📌 Pourquoi ce changement ?

L'application `modelFactory` est une architecture **per-symbol** : un modèle indépendant (LSTM / LightGBM / CatBoost) est entraîné par titre. Le secteur GICS (Technology, Financials, Healthcare…) est une information disponible dans `stock_metadata` mais n'était **jamais injectée** dans les features ML.

Or, le comportement agrégé d'un secteur (momentum sectoriel, volatilité intra-secteur, alpha titre vs secteur) est une information **émergente** — elle n'existe pas au niveau du titre individuel et n'est pas redondante avec les features OHLCV. C'est la brique manquante de l'approche **hybride** utilisée par les fonds professionnels : modèle per-symbol enrichi de features cross-sectionnelles ET sectorielles.

Les tests précédents ont montré que :
- Les scores screener n'apportent rien car redondants avec les features OHLCV
- Les features cross-sectionnelles (rangs percentiles) améliorent les métriques
- La **dimension sectorielle** est complémentaire et indissociable du cross-sectional

**→ Refactor Sprint 2026-07** : fusion des flags `--enable-cross-sectional` et `--include-sector-features` en un seul. Activer le cross-sectional active automatiquement les features sectorielles (même raw_panel, coût marginal nul).

## 🎯 Avantages attendus

| Avantage | Détail |
|---|---|
| **Information non redondante** | Le momentum d'un secteur n'est pas déductible des seuls prix du titre |
| **Signal macro indirect** | Un secteur qui décroche = signal bear ; un secteur qui accélère = signal bull |
| **Aide à la classe `flat`** | Les titres sont souvent flat quand leur secteur est flat → meilleure calibration |
| **Coût minimal** | Les features sont calculées en O(n) sur le raw_panel déjà existant |
| **Un seul flag** | `--enable-cross-sectional` active tout : percentiles + secteur |

## 📁 État du code

### `modelFactory/cross_sectional.py`

- `SECTOR_FEATURE_COLUMNS` : 8 colonnes
  - `sector_ret_20`, `sector_ret_60` — momentum moyen du secteur
  - `sector_vol_20` — volatilité moyenne du secteur
  - `sector_relative_strength_20` — surperformance du secteur vs benchmark
  - `sector_dollar_volume_20` — liquidité agrégée du secteur
  - `sector_symbol_count` — nombre de titres dans le secteur à cette date
  - `stock_vs_sector_ret_20`, `stock_vs_sector_ret_60` — alpha du titre vs son secteur
- `_load_sector_mapping(engine)` → `dict[str, str]` : charge le mapping `symbol → sector` depuis `stock_metadata`
- `_compute_sector_features(raw_panel, sector_map)` : agrège par `(date, secteur)` puis réinjecte
- `build_cross_sectional_features_from_db()` : paramètre `sector_map` toujours fourni quand cross-sectional activé
- `_compute_cross_symbol_features(raw_panel, sector_map)` 🆕 : calcule 6 features cross-symbol exclusives (breadth, dispersion, concentration, rang intra-secteur, ratio volatilité, momentum spread) — **réservées au Global Model**

### `modelFactory/config.py`

```python
enable_cross_sectional_features: bool = False  # percentiles + secteur (fusionné)
```
Le champ `include_sector_features` a été **supprimé** — le cross-sectional inclut désormais systématiquement les features sectorielles.

### `modelFactory/features.py`

- `get_feature_columns(include_cross_sectional=True)` → inclut automatiquement `CROSS_SECTIONAL_FEATURE_COLUMNS` + `SECTOR_FEATURE_COLUMNS`
- `fingerprint()`, `build_feature_contract()`, `validate_feature_contract()` : idem, un seul paramètre `include_cross_sectional`
- Le paramètre `include_sector_features` a été **supprimé** de toutes les signatures

### `modelFactory/cli.py`

```bash
--enable-cross-sectional    # Active rangs percentiles + features sectorielles
```
Le flag `--include-sector-features` a été **supprimé**. `--enable-cross-sectional` fait tout.

### `modelFactory/orchestrator.py`

- `_needs_cross_sectional = cfg.data.enable_cross_sectional_features` (plus de `or include_sector_features`)
- Le mapping sectoriel est **toujours** chargé quand cross-sectional est activé : `_load_sector_mapping(engine)`
- Passé systématiquement à `build_cross_sectional_features_from_db(sector_map=sector_map)`

### IHM

- **Un seul checkbox** : "🌐 Features cross-sectionnelles & sectorielles (rangs percentiles + momentum intra-secteur)"
- `pipeline_ml_enable_cross_sectional` → `True` active les deux
- `DEFAULT_ML_INCLUDE_SECTOR_FEATURES` supprimé de `pipeline_ml_defaults.py`
- `ml_include_sector_features` supprimé de `PipelineLaunchOptions`
- `--include-sector-features` n'est plus passé dans la commande

## 🚀 Comment activer ?

### Via CLI
```powershell
python -m modelFactory --mode train \
    --enable-cross-sectional \
    ...autres flags...
```

**Plus besoin** de `--include-sector-features` : un seul flag active tout.

### Via IHM
Cocher **"🌐 Features cross-sectionnelles & sectorielles"** dans les options ML du Pipeline.

### Vérification
Dans les logs, chercher :
```
run_training_batch sector features enabled: 487 symbols mapped to 11 sectors
```

## 🔬 Détails techniques

### Algorithme de calcul

1. **Chargement du mapping secteur** : `SELECT symbol, provider_sector FROM stock_metadata` — exécuté une seule fois par batch
2. **raw_panel** : déjà calculé par `build_cross_sectional_features_from_db` (rendements, volatilité, dollar volume par symbole et date)
3. **Agrégation sectorielle** : `raw_panel.groupby(["date", "sector"]).agg({"ret_20": "mean", ...})`
4. **Réinjection** : merge sur `(symbol, date)` → chaque titre reçoit les agrégats de son secteur
5. **Gestion des données manquantes** :
   - Secteurs avec < 3 titres → NaN → forward-fill → 0
   - Titres sans secteur → toutes les colonnes sectorielles à 0

### Performance

- **Coût** : ~0.5s supplémentaire pour 500 titres (l'agrégation par secteur est triviale)
- **Mémoire** : +8 colonnes float64 par ligne → négligeable
- **Pas de re-chargement** des barres : le raw_panel est réutilisé

## 📋 Fichiers modifiés

| Fichier | Changement |
|---|---|
| `modelFactory/cross_sectional.py` | +SECTOR_FEATURE_COLUMNS, +_load_sector_mapping, +_compute_sector_features |
| `modelFactory/config.py` | +enable_cross_sectional_features (inclut secteur), -include_sector_features |
| `modelFactory/features.py` | include_cross_sectional inclut automatiquement SECTOR_FEATURE_COLUMNS |
| `modelFactory/cli.py` | --enable-cross-sectional fait tout, --include-sector-features supprimé |
| `modelFactory/dataset.py` | propagation simplifiée |
| `modelFactory/trainer.py` | propagation simplifiée |
| `modelFactory/predictor.py` | propagation simplifiée |
| `modelFactory/orchestrator.py` | sector_map toujours chargé avec cross-sectional |
| `modelFactory/tabular_baseline.py` | propagation simplifiée |
| `modelFactory/global_model.py` | propagation simplifiée |
| `modelFactory/lstm_benchmark_adapter.py` | propagation simplifiée |
| `modelFactory/model_benchmark.py` | propagation simplifiée |
| `ihm/services/pipeline_ml_defaults.py` | -DEFAULT_ML_INCLUDE_SECTOR_FEATURES |
| `ihm/services/pipeline_runner.py` | -ml_include_sector_features, ---include-sector-features |
| `ihm/pages/_execution_center/__init__.py` | 1 checkbox fusionné "cross-sectional & sectoriel" |

---

## 🧠 Approche 2 — Stacking : Global Model comme Feature enrichissante

### 📌 Pourquoi ce changement ?

Le Global Model (`--enable-global-model`) est aujourd'hui un challenger **fantôme** : il participe à la sélection champion mais ne peut jamais gagner car :

- `selection_score_from_result()` cherche `walk_forward.f1_macro` — le Global Model n'a pas de WF per-symbol
- Même si on lui ajoutait `val`, comparer `val` à `wf` n'est pas robuste (1 split vs 11 splits)

L'**Approche 2 (Stacking)** résout ça élégamment : le Global Model ne remplace **pas** les modèles per-symbol, il les **enrichit** avec une feature apprise non-linéaire (`global_pred`), PIT-safe.

C'est le prolongement naturel des features sectorielles : au lieu d'injecter `sector_ret_20` (agrégat statique), on injecte la **prédiction entraînée du Global Model** (signal transverse appris). Même principe, version ML.

### 🎯 Les 3 flags (A/B testing indépendant)

Le Global Model est découpé en **3 flags orthogonaux** pour permettre l'A/B testing :

```
┌─────────────────────────────────────────────────────────────────────┐
│ FLAG A : --enable-global-model                                      │
│ ☐ Entraîner un modèle global multi-symboles                        │
│                                                                     │
│ → Phase 1 : WF 11 splits, produit global_pred(symbol, date)         │
│ → Si décoché : rien ne se passe (comportement actuel)               │
│ → Si coché mais B et C décochés : global entraîné mais inutilisé    │
│   (utile pour debug / inspection des prédictions globales)          │
├─────────────────────────────────────────────────────────────────────┤
│ FLAG B : --enable-global-stacking                                   │
│ ☐ Utiliser la prédiction globale comme feature (Stacking)           │
│                                                                     │
│ → Phase 2 : global_pred_long ajouté aux features per-symbol         │
│ → Nécessite FLAG A (sinon pas de global_pred à injecter)            │
│ → Indépendant de C : stacking sans challenger, c'est OK             │
├─────────────────────────────────────────────────────────────────────┤
│ FLAG C : --enable-global-challenger                                 │
│ ☐ Inclure le modèle global dans la sélection champion               │
│                                                                     │
│ → Phase 3 : 4 challengers (lstm, lgbm, catboost, global)            │
│ → Nécessite FLAG A (sinon pas de métriques WF pour le global)       │
│ → Indépendant de B : challenger sans stacking, c'est OK             │
└─────────────────────────────────────────────────────────────────────┘
```

### 🧪 Matrice d'A/B testing

| A | B | C | Comportement | Ce qu'on teste |
|---|---|---|------|-------------|
| ☐ | ☐ | ☐ | **Baseline** : LSTM/LGBM/CatBoost, 3 challengers, pas de global | Référence actuelle |
| ☑ | ☐ | ☐ | Global entraîné (WF), pas utilisé | Debug : inspecter `global_pred` |
| ☑ | ☑ | ☐ | **Test 1** : Stacking pur — `global_pred` enrichit les 3 modèles, champion parmi 3 | Le stacking améliore-t-il le LSTM ? |
| ☑ | ☐ | ☑ | **Test 2** : Global challenger standalone — le global affronte les 3 modèles NON enrichis | Le global bat-il les per-symbol ? |
| ☑ | ☑ | ☑ | **Test 3** : Full — stacking + 4 challengers (les 3 enrichis + global standalone) | Les deux combinés > chaque isolé ? |

### 🏗️ Architecture des 3 phases

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1 : Global Model avec Walk-Forward (FLAG A)               │
│                                                                 │
│ WF Split 1  : train global sur TOUS [2018-2021]                 │
│              → predict per-symbol sur [2022] → global_pred      │
│ WF Split 2  : train global sur TOUS [2018-2022]                 │
│              → predict per-symbol sur [2023] → global_pred      │
│ ... (11 splits)                                                 │
│                                                                 │
│ → Sauvegarde global_pred(symbol, date) PIT-safe                 │
│ → Coût : ~1 minute (11 × LGBM.fit() sur poolé)                  │
│ → Stocké dans cross_sectional_cache (comme les rangs today)     │
│ → by_symbol avec wf.f1_macro (pour Phase 3 si FLAG C)           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2 : Per-Symbol Enrichi — Stacking (FLAG B, si A+B)       │
│                                                                 │
│ Chaque LSTM / LightGBM / CatBoost reçoit :                      │
│   • Features existantes (OHLCV + cross-sectional + sector)      │
│   • + global_pred_long  ← feature apprise non-linéaire          │
│                                                                 │
│ Le LSTM peut apprendre :                                        │
│   "Quand global_pred > 0.7 ET momentum aligné → confiance haute"│
│   "Quand global_pred = 0.5 → j'ignore, je suis mes patterns"    │
│                                                                 │
│ → WF per-symbol normal, tous les modèles restent comparables    │
│ → Si FLAG B = False : pas de global_pred, per-symbol standard   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3 : Champion Selection avec 4 challengers (FLAG C, si A+C)│
│                                                                 │
│ Puisque le Global Model a maintenant wf.f1_macro par symbole    │
│ (produit en Phase 1), il devient un VRAI challenger :           │
│                                                                 │
│   select_champion({lstm, lgbm, catboost, global})               │
│                                                                 │
│ → Tous comparables via wf.f1_macro (même métrique, même échelle)│
│ → Si global gagne → pas de stacking pour ce symbole             │
│ → Si per-symbol gagne → stacking appliqué si FLAG B actif       │
│ → Si FLAG C = False : champion selection standard (3 way)       │
└─────────────────────────────────────────────────────────────────┘
```

### 🔬 Détails techniques — Phase 1 (Global Model WF)

**Algorithme** :
1. Définir les 11 fenêtres WF (mêmes paramètres que le WF per-symbol : `wf_min_train_size`, `wf_val_size`, `wf_step_size`)
2. Pour chaque split `i` :
   - `train_dates` = [start, split_end - 2 × val_size]
   - `val_dates` = [split_end - 2 × val_size, split_end - val_size]
   - Charger les barres de tous les symboles sur `train_dates` → `train_df` poolé
   - `.fit()` LightGBM/CatBoost sur `train_df`
   - `.predict_proba()` sur chaque symbole pour `val_dates` → `global_pred(symbol, date)`
3. Concaténer tous les `global_pred` → DataFrame `[symbol, date, global_pred]`
4. Stocker dans le cache cross-sectional (merge automatique dans `merge_cross_sectional_features`) + fichier parquet pour les workers multiprocessing
5. `by_symbol` produit `wf.f1_macro` par symbole (agrégé sur les 11 splits)

**Features du Global Model** (principe d'orthogonalité) :
- `_get_global_feature_columns(cfg)` : rangs cross-sectional (8) + secteur (8) + cross-symbol exclusives (6) = **22 features**
- **Exclues** : OHLCV (13), expert (18), sentiment (4), screener (22), short_score (1)
- Les features macro (VIX, VXN, VIX3M, MOVE) sont incluses si activées
- `global_pred_long` n'est JAMAIS inclus (pas de récursion)
- Le Global apprend des patterns cross-symboles que le per-symbol ne peut pas déduire

**Feature dans le contrat** :
- `GLOBAL_PRED_FEATURE = "global_pred_long"` — ajoutée à `get_feature_columns()` quand FLAG A + FLAG B sont actifs
- Le fingerprint inclut cette colonne → pas de breaking change pour les modèles existants sans global

**Performance** :
- 11 × LGBM/CatBoost.fit() sur poolé avec ~16 features → ~2s chacun → ~25 secondes
- 200 symboles × 11 splits × predict_proba() → ~5 secondes
- **Total : < 1 minute** (contre ~heures pour les LSTM per-symbol)

### 🔬 Détails techniques — Phase 2 (Stacking)

- `global_pred_long` est mergé dans le DataFrame du symbole au même titre que les rangs percentiles (via `merge_cross_sectional_features`)
- Le `feature_contract` et le `fingerprint` incluent automatiquement `global_pred_long` quand FLAG A + FLAG B
- Les modèles per-symbol ne changent pas — ils reçoivent juste une colonne de plus
- Si `global_pred_long` est NaN (début de série, pas encore de WF global pour cette date) → fillna(0.5)
- **Multiprocessing** : le cache cross-sectional complet n'est pas picklé vers les workers. `global_pred_df` est sauvegardé en parquet (`_global_pred_cache.parquet`) dans le dossier du batch. Chaque worker le charge et le merge localement.

### 🔬 Détails techniques — Phase 3 (Champion Selection)

- `_compute_by_symbol_metrics()` produit maintenant `walk_forward` en plus de `test` pour le Global Model
- `selection_score_from_result()` fonctionne normalement (même code, même métrique wf.f1_macro)
- Aucune modification de `select_champion()` — le Global Model est juste un 4ème challenger avec des métriques WF comparables

### ⚙️ Configuration

```python
@dataclass(frozen=True, slots=True)
class GlobalModelConfig:
    enabled: bool = False             # FLAG A : entraîne le global (Phase 1)
    stacking_enabled: bool = False    # FLAG B : global_pred comme feature (Phase 2)
    challenger_enabled: bool = False  # FLAG C : global dans champion selection (Phase 3)
    model_name: str = "catboost"
    artifact_symbol: str = "__GLOBAL__"
    use_cross_sectional_features: bool = True
```

**Gating logique** :
```python
# Phase 1 (orchestrator) — FLAG A
if cfg.global_model.enabled:
    global_result = train_global_model_wf(...)

# Phase 2 (features.py) — FLAG A + B
if cfg.global_model.enabled and cfg.global_model.stacking_enabled:
    cols.append("global_pred_long")

# Phase 3 (orchestrator) — FLAG A + C
if cfg.global_model.enabled and cfg.global_model.challenger_enabled:
    _inject_global_model_into_symbol_artifacts(...)
```

### 🖥️ IHM : 3 checkboxes hiérarchiques

```
┌─ Options Global Model ─────────────────────────────────────────────┐
│                                                                     │
│ ☐ Entraîner un modèle global multi-symboles                        │
│   └─ Requis pour les deux options ci-dessous                       │
│                                                                     │
│   ☐ Utiliser la prédiction globale comme feature (Stacking)         │
│      └─ Ajoute global_pred_long aux features per-symbol             │
│                                                                     │
│   ☐ Inclure le modèle global dans la sélection champion            │
│      └─ 4ème challenger avec wf.f1_macro comparable                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

Les deux sous-checkboxes sont **grisées** tant que la première n'est pas cochée.

### 📁 Fichiers modifiés (Sprint 2026-07 — Approche 2)

| Fichier | Changement |
|---|---|
| `modelFactory/config.py` | `GlobalModelConfig` : +`stacking_enabled`, +`challenger_enabled` |
| `modelFactory/global_model.py` | +`train_global_model_wf()` : WF 11 splits, +`_get_global_feature_columns()` : features cross-symbol uniquement (22 cols), +`GLOBAL_EXCLUSIVE_FEATURE_COLUMNS`, `_aggregate_wf_per_symbol_metrics()`, `_compute_by_symbol_metrics()` |
| `modelFactory/cross_sectional.py` | +`GLOBAL_PRED_FEATURE_COLUMNS`, +`GLOBAL_EXCLUSIVE_FEATURE_COLUMNS`, +`_compute_cross_symbol_features()`, `merge_cross_sectional_features()` gère 4 familles + fillna |
| `modelFactory/features.py` | `get_feature_columns()`, `fingerprint()`, `build_feature_contract()`, `validate_feature_contract()` : +`include_global_stacking` |
| `modelFactory/orchestrator.py` | Phase 1 AVANT per-symbol, merge `global_pred` dans cache + persistance parquet pour workers multiprocessing, Phase 3 gated par FLAG C, logging worker configuré |
| `modelFactory/dataset.py` | `SymbolDataModule` + `prepare_symbol_frame()` : +`include_global_stacking` |
| `modelFactory/trainer.py` | `_run_walk_forward_validation()` : +`include_global_stacking` + `datamodule_kwargs` |
| `modelFactory/tabular_baseline.py` | `run_tabular_baseline()` + `run_tabular_walk_forward()` : +`include_global_stacking` |
| `modelFactory/predictor.py` | 2 call sites : `include_global_stacking=False` (pas de global à l'inférence) |
| `modelFactory/model_benchmark.py` | `_get_feature_columns()` : +`include_global_stacking` |
| `modelFactory/global_benchmark_runner.py` | +`include_global_stacking` |
| `modelFactory/lstm_benchmark_adapter.py` | +`include_global_stacking` |
| `modelFactory/cli.py` | +`--enable-global-stacking` (FLAG B), +`--enable-global-challenger` (FLAG C) |
| `ihm/services/pipeline_ml_defaults.py` | +`DEFAULT_ML_ENABLE_GLOBAL_STACKING`, +`DEFAULT_ML_ENABLE_GLOBAL_CHALLENGER` |
| `ihm/services/pipeline_runner.py` | `PipelineLaunchOptions` : +`ml_enable_global_stacking`, +`ml_enable_global_challenger`. Command builder : flags CLI. |
| `ihm/pages/_execution_center/__init__.py` | 3 checkboxes hiérarchiques (A maître, B/C subordonnées grisées) |

### 📋 Plan d'action — Statut final

| Étape | Fichier | Action | Statut |
|:-----:|---------|--------|:------:|
| **1** | `modelFactory/config.py` | `GlobalModelConfig` +2 flags | ✅ |
| **2** | `modelFactory/global_model.py` | `train_global_model_wf()` WF 11 splits | ✅ |
| **3** | `modelFactory/cross_sectional.py` | `GLOBAL_PRED_FEATURE_COLUMNS` + merge + fillna | ✅ |
| **4** | `modelFactory/features.py` | `include_global_stacking` param | ✅ |
| **5** | `modelFactory/orchestrator.py` | 3 phases restructurées | ✅ |
| **6** | `modelFactory/dataset.py` + propagation | `DataModule` + 6 fichiers (trainer, tabular, predictor, etc.) | ✅ |
| **7** | `modelFactory/cli.py` | `--enable-global-stacking`, `--enable-global-challenger` | ✅ |
| **8** | `ihm/services/pipeline_ml_defaults.py` | 2 constantes | ✅ |
| **9** | `ihm/services/pipeline_runner.py` | `PipelineLaunchOptions` + command builder | ✅ |
| **10** | `ihm/pages/_execution_center/__init__.py` | 3 checkboxes hiérarchiques | ✅ |
| **11** | `tests/` | 87 tests : `test_global_model_wf.py` (16), `test_stacking.py` (16), `test_global_flags.py` (23) + existants (32) | ✅ |

---

## 📊 Tableau complet des features — par modèle et par flag IHM

> **Principe d'orthogonalité (Sprint 2026-07-21)** : le Global Model n'utilise que des features
> **cross-symboles** (rangs, secteur, macro). Les features locales au titre (OHLCV, expert,
> sentiment, screener) sont **exclues** — elles sont redondantes avec le per-symbol.
> Le Global doit apprendre des patterns émergents que le per-symbol ne peut pas voir seul.
> `global_pred_long` encode ainsi un signal **non redondant**, pas une simple recombinaison.

| # | Famille | Colonnes | Flag CLI | Checkbox IHM | Global | LSTM | LGBM/CB |
|:--|:--|:--|:--|:--|:--:|:--:|:--:|
| 1 | OHLCV | 13 | *(toujours actif)* | — | ❌² | ✅ | ✅ |
| 2 | Expert | 18 | `--feature-set expert` | *(toujours `expert`)* | ❌² | ✅ | ✅ |
| 3 | Rangs cross-sectional | 8 | `--enable-cross-sectional` | 🌐 Features cross-sectionnelles & sectorielles | ✅ | ✅ | ✅ |
| 4 | Secteur | 8 | *(avec `--enable-cross-sectional`)* | *(même checkbox)* | ✅ | ✅ | ✅ |
| 5 | **Cross-symbol exclusives** 🆕 | 6 | *(avec `--enable-cross-sectional`)* | *(même checkbox)* | ✅ | ❌³ | ❌³ |
| 6 | **global_pred_long** | 1 | `--enable-global-stacking` | 📥 Utiliser la prédiction globale comme feature | ❌¹ | ✅ | ✅ |
| 7 | Sentiment | 4 | `--include-sentiment` | Inclure les features sentiment | ❌² | ✅ | ✅ |
| 8 | Screener | 22 | `--include-screener-scores` | Inclure les scores du screener | ❌² | ✅ | ✅ |
| 9 | Short score | 1 | `--include-short-score` | Inclure le short_score dédié | ❌² | ✅ | ✅ |
| 10 | VIX/VIX9D | 2 | `--include-macro-vix` | 📊 VIX/VIX9D (volatilité S&P 500) | ✅ | ✅ | ✅ |
| 11 | VXN | 2 | `--include-macro-vxn` | 📊 VXN (volatilité NASDAQ-100) | ✅ | ✅ | ✅ |
| 12 | VIX3M + term structure | 3 | `--include-macro-vix3m` | 📊 VIX3M + ratio (term structure) | ✅ | ✅ | ✅ |
| 13 | MOVE | 1 | `--include-macro-move` | 📊 MOVE (volatilité obligataire) | ✅ | ✅ | ✅ |
| | **Total max** | **89** | | | 30 | 83 | 83 |
| | **Avec config standard¹** | | | | 22 | 48 | 48 |

> ¹ Pas de récursion : le Global Model n'utilise pas sa propre prédiction.  
> ² Exclues du Global Model par principe d'orthogonalité.  
> ³ Exclusives au Global Model — le per-symbol ne peut pas les calculer seul (breadth, dispersion, concentration, rang intra-secteur).
>
> **Config standard** = `--feature-set expert --enable-cross-sectional --enable-global-stacking` (pas de flags macro/sentiment/screener).
>
> 🐛 **Corrigé Sprint 2026-07-21** : `run_tabular_baseline()`, `run_tabular_walk_forward()`, `_run_walk_forward_validation()` ne passaient pas les flags macro/sentiment/screener à `get_feature_columns()`. Corrigé.  
> 🏗️ **Refactor Sprint 2026-07-21** : `_get_global_feature_columns()` — le Global Model utilise uniquement rangs + secteur + macro, excluant OHLCV/expert/sentiment/screener.

### 🚀 Comment activer ?

```powershell
# Test 1 : Stacking pur (A+B)
python -m modelFactory --mode train \
    --enable-cross-sectional \
    --enable-global-model \
    --enable-global-stacking \
    ...autres flags...

# Test 2 : Global challenger standalone (A+C)
python -m modelFactory --mode train \
    --enable-cross-sectional \
    --enable-global-model \
    --enable-global-challenger \
    ...autres flags...

# Test 3 : Full (A+B+C)
python -m modelFactory --mode train \
    --enable-cross-sectional \
    --enable-global-model \
    --enable-global-stacking \
    --enable-global-challenger \
    ...autres flags...
```

### Vérification

Dans les logs :
```
# Phase 1 — Global Model (22 features cross-symbol)
run_training_batch global_model_wf start symbols=200
train_global_model_wf start symbols=200 splits=11 feature_cols=22
train_global_model_wf split=1/11 train_rows=494 val_rows=116
...
train_global_model_wf done pred_rows=1276 symbols=176 dates=9

# Phase 2 — Stacking
run_training_batch stacking enabled: global_pred_long merged into cache rows=395826
run_training_batch global_pred persisted to .../_global_pred_cache.parquet

# Phase 3 — Per-symbol (48 features = 47 + global_pred_long)
walk_forward start symbol=AAPL splits=11 ... feature_cols=48 stacking=True global_pred=True
tabular_wf start symbol=AAPL model=lightgbm ... feature_cols=48 stacking=True global_pred=True
```
