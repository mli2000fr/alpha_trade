# 📋 Synthèse & Plan d'Action — Recommandations ML

> **Date** : 2026-07-26
> **Source** : Plan directeur ML externe (25/07/2026) + `prompt/refactor_model_global.md`
> **Objectif** : Roadmap consolidée avec priorités, fichiers cibles, et estimation d'effort.

---

## 📊 État des lieux — Ce qui est DÉJÀ FAIT ✅

### Architecture (Phase 1 & 2)
| Composant | Fichier | Statut |
|-----------|---------|:------:|
| Global Ranking Model (régression, target `future_return` J+10) | `modelFactory/global_ranking.py` | ✅ |
| Per-Symbol Stacking via `global_rank` ∈ [0,1] | `modelFactory/cross_sectional.py`, `predictor.py` | ✅ |
| Global Model **PAS** challenger champion | `pipeline_ml_defaults.py` (`DEFAULT_ML_ENABLE_GLOBAL_CHALLENGER = False`) | ✅ |
| Nettoyage `_has_global_rank` vs `_has_global_pred` | `trainer.py`, `tabular_baseline.py` | ✅ |
| Inférence : `predict_global_rank()` + cache par date + fallback 0.5 | `modelFactory/predictor.py` | ✅ |
| Tests stacking/global 115 OK | `tests/test_stacking.py`, `test_global_flags.py`, etc. | ✅ |

### Features
| Catégorie | Nb colonnes | Fichier | Statut |
|-----------|:---:|---------|:------:|
| Multi-horizons (momentum/vol/RSI/MA) | 10 | `modelFactory/features.py` | ✅ |
| Interactions non-linéaires | 16 | `modelFactory/features.py` | ✅ |
| Z-Score rolling 5 ans (1260j) | 21 | `modelFactory/features.py`, `cross_sectional.py` | ✅ |
| Sector-neutral (médiane sectorielle) | 10 | `modelFactory/features.py`, `cross_sectional.py` | ✅ |
| Fondamentaux EODHD (PE, ROE, marges, etc.) | 20 | `modelFactory/fundamental_features.py` | ✅ |
| Facteurs CAPM (beta_252, alpha_252, R², momentum_vs_market) | 4 | `modelFactory/factor_features.py` | ✅ |
| Interactions régime de marché (bull/bear/risk_off) | 18 | `modelFactory/features.py` | ✅ |

### Filtrage & Exécution
| Composant | Fichier | Statut |
|-----------|---------|:------:|
| Filtre de liquidité amont | `modelFactory/liquidity_filter.py` | ✅ (MySQL fix 26/07) |
| Batch diagnostics (F1 WF → exclusion) | `risk_management/batch_diagnostics.py` | ✅ |
| Boost scores avant sizing (Option C) | `risk_management/batch_diagnostics.py` | ✅ |
| Intégration Risk step 11 | `risk_management/cli.py` | ✅ |
| Intégration Backtest (side-aware boost) | `backtesting/cli/_impl.py` | ✅ |
| Tests batch diagnostics | 86 tests | ✅ |

### IHM
| Composant | Page | Statut |
|-----------|------|:------:|
| Suppression batch non complété | 🩺 Diagnostic ML | ✅ |
| Affichage batch diagnostics (filtered/boosted) | Backtesting → History | ✅ |
| Page fondamentaux | 📊 Fondamentaux | ✅ |

### Configuration
| Paramètre | Valeur | Fichier |
|-----------|--------|---------|
| `batch_diagnostics.live_batch_id` | `""` (défaut) | `config.yaml` |
| `batch_diagnostics.backtest_batch_id` | `""` (défaut) | `config.yaml` |
| `global_ranking.prediction_lookback_days` | `365` | `config.yaml` |

---

## 🔴 Recommandations Externes — Analyse & Position

### ✅ Déjà fait
| Recommandation | Implémentation |
|----------------|---------------|
| Architecture 2 phases (Global Ranking → Per-Symbol Stacking) | `global_ranking.py` + `predictor.py` |
| Filtre de liquidité amont | `liquidity_filter.py` |
| Filtrage par F1 WF (batch diagnostics) | `risk_management/batch_diagnostics.py` |
| Z-Scores glissants 5 ans | 21 colonnes dans `features.py` |
| Neutralisation sectorielle | 10 colonnes dans `cross_sectional.py` |
| Facteurs CAPM | 4 colonnes dans `factor_features.py` |
| Fondamentaux | 20 colonnes dans `fundamental_features.py` |

### 🟢 À faire — Court terme (prochain batch)
| # | Recommandation | Priorité | Effort |
|:--:|---------------|:--------:|:------:|
| 1 | **Indicateurs de régime macro** : `SPY_SMA_200_slope` + `VIX_zscore` injectés partout | 🔴 Haute | 1h |
| 2 | **Régularisation stricte des arbres** locaux (max_depth=3-4, num_leaves=8-15, min_child_samples=30-50) | 🔴 Haute | 30min |
| 3 | **`class_weight="balanced"`** LightGBM / CatBoost pour classes ternaires | 🔴 Haute | 15min |
| 4 | **Subsampling** : `subsample=0.7-0.8`, `colsample_bytree=0.6-0.8` | 🟡 Moyenne | 15min |

### 🟡 À faire — Moyen terme
| # | Recommandation | Priorité | Effort |
|:--:|---------------|:--------:|:------:|
| 5 | **Exploitation des rangs** : features d'interaction `rank_x_rsi`, `rank_x_momentum_20`, etc. | 🟡 Moyenne | 1-2h |
| 6 | **Multi-horizons Phase 1** : `global_rank` prédit sur J+3, J+5, J+10 → stack de 3 rangs | 🟡 Moyenne | 3-4h |
| 7 | **VectorScaler** (température + biais par classe) en remplacement du TemperatureScaler | 🟢 Basse | 2h |
| 8 | **TernaryDecisionPolicy** : ajustement des seuils selon probabilités calibrées | 🟢 Basse | 2h |

### 🔵 À faire — Long terme
| # | Recommandation | Priorité | Effort |
|:--:|---------------|:--------:|:------:|
| 9 | **Décomposition du global** : `rank_momentum`, `rank_mean_reversion`, `rank_volatility` | 🟢 Basse | 5-8h |
| 10 | **Ensembling per-symbol** : LightGBM + CatBoost (moyenne/stacking des prédictions) | 🟢 Basse | 3-4h |
| 11 | **Short Interest** : scraping FINRA (mensuel, fichier TXT gratuit) | 🟢 Basse | 3-4h |
| 12 | **Estimation d'incertitude** : variance intra-ensemble pour filtrer trades peu certains | 🟢 Basse | 5-8h |
| 13 | **Pondération dynamique du capital** selon confiance calibrée | 🟢 Basse | 5-8h |

---

## 🎯 Plan d'Action Détaillé — Sprint "Quick Wins"

### Action 1 — Indicateurs de Régime Macro
**Fichiers** : `modelFactory/features.py`, `modelFactory/config.py`

```python
# Deux nouvelles features calculées une fois par jour (pas par symbole) :

def _compute_macro_regime_features(df: pd.DataFrame, spy_df: pd.DataFrame, vix_df: pd.DataFrame) -> pd.DataFrame:
    """Injecte 2 features macro globales dans le DataFrame principal."""
    # 1. Pente de la SMA 200 du SPY (tendance long terme du marché)
    spy_df["SPY_SMA_200_slope"] = (
        spy_df["close"].rolling(200).mean().diff(20) /
        spy_df["close"].rolling(200).mean()
    )  # pente normalisée sur 20 jours

    # 2. Z-score du VIX sur 252 jours (régime de volatilité)
    vix_rolling = vix_df["vix"].rolling(252)
    vix_df["VIX_zscore"] = (vix_df["vix"] - vix_rolling.mean()) / vix_rolling.std()

    df = df.merge(spy_df[["date", "SPY_SMA_200_slope"]], on="date", how="left")
    df = df.merge(vix_df[["trade_date", "VIX_zscore"]], left_on="date", right_on="trade_date", how="left")
    return df
```

- [ ] Ajouter `include_macro_regime: bool = False` dans `DataConfig`
- [ ] Ajouter `SPY_SMA_200_slope`, `VIX_zscore` dans `get_feature_columns()` (mode `expert`)
- [ ] Les calculer dans `compute_features()` quand le flag est activé
- [ ] CLI : `--include-macro-regime`
- [ ] IHM : checkbox dans Pipeline → ML Train

### Action 2 — Régularisation Stricte des Arbres Locaux
**Fichier** : `modelFactory/tabular_baseline.py`

```python
# Dans _train_lightgbm() et _train_catboost() :

LIGHTGBM_REGULARIZED_PARAMS = {
    "max_depth": 4,             # ← actuellement -1 (illimité)
    "num_leaves": 15,           # ← actuellement 31
    "min_child_samples": 30,    # ← actuellement 20
    "subsample": 0.8,           # ← ajouter
    "colsample_bytree": 0.7,    # ← ajouter
    "reg_alpha": 0.1,           # ← L1
    "reg_lambda": 0.1,          # ← L2
}

CATBOOST_REGULARIZED_PARAMS = {
    "max_depth": 4,
    "subsample": 0.8,
    "colsample_bylevel": 0.7,
    "l2_leaf_reg": 3.0,
    "min_data_in_leaf": 30,
}
```

- [ ] Modifier `_train_lightgbm()` dans `tabular_baseline.py`
- [ ] Modifier `_train_catboost()` dans `tabular_baseline.py`
- [ ] Rendre paramétrable via `config.yaml` → `tabular_baseline.regularization: strict|loose`

### Action 3 — `class_weight="balanced"`
**Fichier** : `modelFactory/tabular_baseline.py`

```python
# LightGBM :
params["class_weight"] = "balanced"

# CatBoost :
params["auto_class_weights"] = "Balanced"
```

- [ ] Ajouter dans `_train_lightgbm()`
- [ ] Ajouter dans `_train_catboost()`

### Action 4 — Features d'Interaction `rank_x_*`
**Fichier** : `modelFactory/features.py`

```python
# Après merge du global_rank dans le per-symbol :
RANK_INTERACTION_FEATURES = [
    "rank_x_rsi_14",            # global_rank * rsi_14
    "rank_x_momentum_20",       # global_rank * momentum_20
    "rank_x_momentum_60",       # global_rank * momentum_60
    "rank_x_volatility_20",     # global_rank * rolling_volatility_20
    "rank_x_sma20_distance",    # global_rank * sma20_distance
]
```

- [ ] Ajouter dans `compute_features()` après le merge du global_rank
- [ ] Ajouter dans `get_feature_columns()` (mode `expert`)

---

## 📐 Plan d'Action Détaillé — Moyen Terme

### Action 5 — Multi-Horizons Global Rank
**Fichier** : `modelFactory/global_ranking.py`

Faire évoluer la Phase 1 pour prédire `future_return` sur 3 horizons :

```python
HORIZONS = [3, 5, 10]  # J+3, J+5, J+10

# Pour chaque horizon, entraîner un modèle et produire un rang :
# → global_rank_3, global_rank_5, global_rank_10
# → 3 colonnes stackées dans le per-symbol
```

- [ ] Modifier `train_global_ranking_wf()` pour boucler sur `HORIZONS`
- [ ] Persister 3 colonnes dans `_global_rank_cache.parquet`
- [ ] Mettre à jour `GLOBAL_RANK_FEATURE_COLUMNS` dans `cross_sectional.py`
- [ ] Mettre à jour `predictor.py` pour l'inférence multi-horizons

### Action 6 — VectorScaler (Température + Biais par Classe)
**Fichier** : `modelFactory/calibration.py` (nouveau ou modifier l'existant)

```python
class VectorScaler:
    """Calibration vecteur : température + biais par classe."""
    def fit(self, logits, labels):
        # Optimise temperature + bias_short + bias_long
        ...
    def transform(self, logits):
        return softmax((logits + bias_vector) / temperature)
```

- [ ] Créer `VectorScaler` dans `modelFactory/calibration.py`
- [ ] Remplacer `TemperatureScaler` dans `trainer.py` (flag `--calibration vector`)

---

## ✅ Vérification — Commandes de test

```powershell
# Lancer un batch avec les nouvelles features macro régime :
python -m modelFactory --mode train \
  --feature-set expert --enable-cross-sectional \
  --include-short-score --include-macro-move \
  --include-macro-regime \
  --include-factors --include-fundamentals \
  --enable-global-model --global-model-name lightgbm --enable-global-stacking \
  --compare-lightgbm --enable-catboost --select-champion --walkforward \
  --comment "global_ranking_v4_macro_regime_regularized"

# Vérifier les features dans le fingerprint :
python -c "from modelFactory.features import get_feature_columns; print(len(get_feature_columns('expert', include_macro_regime=True)))"
```

---

## 📊 Indicateurs de succès (mis à jour)

| Métrique | Actuel | Cible Court Terme | Cible Moyen Terme |
|----------|:---:|:---:|:---:|
| F1 WF LightGBM (per-symbol) | ~0.296 | > 0.310 | > 0.330 |
| IC Rank (Global Model) | ? | > 0.03 | > 0.05 |
| % symboles avec F1 Macro WF > seuil | ? | > 30% | > 40% |
| Temps batch (200 symboles, 6 workers) | ~? min | < +2 min vs actuel | < +5 min vs actuel |

---

## 📁 Fichiers impactés — Résumé

| Fichier | Actions 1-4 (Court Terme) | Actions 5-6 (Moyen Terme) |
|---------|:---:|:---:|
| `modelFactory/features.py` | 🔧 macro regime + rank_x interactions | — |
| `modelFactory/config.py` | 🔧 `include_macro_regime` | 🔧 `calibration: vector` |
| `modelFactory/tabular_baseline.py` | 🔧 régularisation + class_weight | — |
| `modelFactory/global_ranking.py` | — | 🔧 multi-horizons |
| `modelFactory/cross_sectional.py` | — | 🔧 multi-rank columns |
| `modelFactory/predictor.py` | — | 🔧 multi-horizon inference |
| `modelFactory/calibration.py` | — | 🔧 VectorScaler |
| `modelFactory/cli.py` | 🔧 `--include-macro-regime` | 🔧 `--calibration vector` |
| `ihm/pages/pipeline.py` | 🔧 checkbox macro regime | — |
| `config.yaml` | 🔧 `macro_regime`, `regularization` | 🔧 `multi_horizons` |
