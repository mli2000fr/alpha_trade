# 📋 Plan d'action — Refonte du Global Model (Stacking)

> **Date** : 2026-07-25  
> **Statut** : Étapes 1, 2, 3, 4, 5, 6 (fondamentaux), 7 (factors) réalisées ✅ | Short Interest à planifier  
> **Objectif** : Transformer le Global Model d'un classifieur ternaire faible en un régresseur de rang cross-sectionnel, puis réinjecter ce rang comme feature de stacking dans les per-symbol.  
> **Périmètre** : Global Model = stacking uniquement. Pas de challenger champion selection.

---

## ✅ Réalisé (2026-07-25)

### Étape 1 — Features d'interaction + multi-horizons ✅

**Fichier** : `modelFactory/features.py`

- **10 features multi-horizons** : `momentum_5`, `momentum_120`, `momentum_250`, `rolling_volatility_5`, `_10`, `_120`, `sma10_distance`, `sma250_distance`, `rsi_5`, `rsi_21`
- **16 features d'interaction** : `momentum_20_div_vol_20`, `momentum_60_div_vol_60`, `momentum_5_minus_momentum_20`, `momentum_20_minus_momentum_60`, `volume_ratio_5_div_volume_ratio_20`, `rsi_14_times_volume_ratio_20`, `rsi_14_div_volatility_20`, `sma20_minus_sma50`, `sma50_minus_sma200`, `ema20_minus_sma20`, `intraday_range_div_atr_14`, `range_position_20_times_vol_ratio_20_60`, `daily_return_times_volume_ratio_20`, `log_return_div_intraday_range`, `relative_strength_20_times_market_trend`, `relative_strength_60_div_market_volatility`
- Intégrées dans `get_feature_columns()` (mode `expert`) et `compute_features()`
- **Impact** : ~26 nouvelles features sans aucune donnée externe. Avec les 18 interactions régime déjà présentes, le feature set `expert` passe de 31 à ~75 colonnes.

### Étape 3 — Global Ranking Model ✅

**Fichier** : `modelFactory/global_ranking.py` (nouveau)

- Régresseur LightGBM/CatBoost, target = `future_return` J+10 (continu, swing trade)
- Walk-forward identique au per-symbol (PIT-safe)
- Sortie : `global_rank` ∈ [0,1] (percentile dans l'univers par date)
- Métrique : IC Rank (Spearman correlation)
- Utilise toutes les features (pas seulement cross-sectionnelles)
- Persisté en `_global_rank_cache.parquet` pour le stacking

### Étape 4 — Nettoyage ✅

| Fichier | Changement |
|---------|-----------|
| `cross_sectional.py` | `GLOBAL_PRED_FEATURE_COLUMNS = ["global_rank"]` (1 colonne au lieu de 3) |
| `orchestrator.py` | `train_global_ranking_wf()` remplace `train_global_model_wf()`. Suppression du bloc challenger injection. Suppression de la persistence `model_metrics` pour global_model. |
| `trainer.py` | `_has_global_rank` au lieu de `_has_global_pred` |
| `tabular_baseline.py` | `_has_global_rank` au lieu de `_has_global_pred` |
| `pipeline_ml_defaults.py` | `DEFAULT_ML_ENABLE_GLOBAL_CHALLENGER = False` |
| `features.py` | Docstring mise à jour |
| `config.yaml` | (inchangé, `challenger_enabled: false` par défaut dans le code) |

### Étape 5 — Tests ✅

| Fichier | Changement |
|---------|-----------|
| `test_stacking.py` | `global_rank` au lieu de `global_pred_*`, 1 colonne au lieu de 3 |
| `test_global_flags.py` | Tests simplifiés, fingrprint conservé |
| `test_global_model_wf.py` | 1 colonne `global_rank` |
| `test_model_factory_cross_sectional.py` | `global_rank` au lieu de `global_pred_long` |
| `test_model_factory_features.py` | `global_rank` au lieu de `global_pred_long` |

**Résultat** : 115 tests OK (94 stacking/flags/features + 21 factor features).

---

## ✅ Réalisé (2026-07-25) — Sprint 3

### Étape 5 (originale) — Fondamentaux ✅

**Fichiers** : `modelFactory/features.py`, `modelFactory/cross_sectional.py`

- **21 colonnes z-score** (`ZSCORE_SOURCE_FEATURES` → `ZSCORE_FEATURE_COLUMNS`) : normalisation temporelle sur 5 ans glissants (1260j, min_periods=252j)
- **10 colonnes sector-neutral** (`SECTOR_NEUTRAL_SOURCE_FEATURES` → `SECTOR_NEUTRAL_FEATURE_COLUMNS`) : soustraction de la médiane sectorielle par date
- `_compute_sector_neutral_features()` dans `cross_sectional.py`
- `_compute_symbol_raw_values()` enrichi avec `momentum_20/60`, `rolling_volatility_60`, `rsi_14`, `sma20/50_distance`, `relative_strength_20/60`
- **Impact** : ~31 nouvelles features sans donnée externe (21 z-score + 10 sector-neutral)

### Étape 5 (originale) — Fondamentaux ✅

**Fichiers créés/modifiés** :

| Fichier | Changement |
|---------|-----------|
| `alembic/versions/0055_add_stock_fundamentals_daily.py` | Nouvelle table `stock_fundamentals_daily` (20+ colonnes : PE, ROE, marges, croissance, etc.) |
| `modelFactory/fundamental_features.py` | Chargement, forward-fill, dérivation de features fondamentales (20 colonnes `fund_*`) |
| `modelFactory/features.py` | Flag `include_fundamentals` dans `get_feature_columns()`, `compute_features()`, `fingerprint()`, `build_feature_contract()`, `validate_feature_contract()` |
| `modelFactory/dataset.py` | `fundamental_df` paramètre dans `prepare_symbol_frame()` et `SymbolDataModule` |
| `modelFactory/trainer.py` | `fundamental_df` propagé dans `train_symbol()` et `_prepare_target_optimization_summary()` |
| `modelFactory/orchestrator.py` | `fundamental_cache` chargé dans `run_training_batch()`, passé aux workers |
| `modelFactory/config.py` | `DataConfig.include_fundamentals_features: bool = False` |
| `modelFactory/cli.py` | `--include-fundamentals` flag CLI |
| `ihm/pages/fundamentals.py` | Page Streamlit : couverture, détail par symbole, distribution sectorielle, recherche |

**20 features fondamentales** :
- Valuation : `fund_pe_ratio`, `fund_forward_pe`, `fund_peg_ratio`, `fund_pb_ratio`, `fund_ps_ratio`, `fund_ev_to_ebitda`
- Profitabilité : `fund_roe`, `fund_roa`, `fund_net_margin`, `fund_operating_margin`, `fund_gross_margin`
- Croissance : `fund_eps_growth_yoy`, `fund_revenue_growth_yoy`
- Yield : `fund_dividend_yield`
- Marché : `fund_market_cap_log`, `fund_beta`
- Estimations : `fund_eps_estimate_current`, `fund_eps_estimate_next`
- Dérivées : `fund_eps_to_price`, `fund_estimate_revision`

**Source** : EODHD `/fundamentals/{symbol}`. Stockage PIT-safe avec `trade_date` + forward-fill.

**Populateur** : `python -c "from modelFactory.fundamental_features import fetch_and_store_fundamentals; fetch_and_store_fundamentals(['AAPL', 'MSFT'], provider='eodhd')"`

### Étape 6 — Factor Exposures (CAPM) ✅

**Fichier créé** : `modelFactory/factor_features.py`

- **4 features** calculées par rolling regression 252j stock vs SPY (zéro API externe) :
  - `beta_252` : CAPM beta — `Cov(r_stock, r_market) / Var(r_market)`
  - `alpha_252` : CAPM alpha annualisé — `(mean(r_stock) - beta × mean(r_market)) × 252`
  - `r_squared_252` : qualité du fit — `Cov² / (Var_stock × Var_market)`
  - `momentum_252_vs_market` : `Σ r_stock − Σ r_market` sur 252j
- Flag `include_factors` ajouté dans `features.py` (`get_feature_columns`, `compute_features`, `fingerprint`, `build_feature_contract`, `validate_feature_contract`)
- `DataConfig.include_factors_features: bool = False`
- CLI : `--include-factors`
- IHM : checkbox "📊 Facteurs CAPM" dans Pipeline → ML Train
- **21 tests unitaires** dans `tests/test_factor_features.py`

### Intégration pipeline — résumé des flags

## ⏳ Restant à faire

### Short Interest

- Source FINRA gratuite (mensuel, scraping fichier TXT)
- Priorité basse

---

## 🚀 Prochain batch à lancer

```powershell
python -m modelFactory --mode train \
  --feature-set expert --enable-cross-sectional \
  --include-short-score --include-macro-move \
  --include-factors --include-fundamentals \
  --enable-global-model --global-model-name lightgbm --enable-global-stacking \
  --compare-lightgbm --enable-catboost --select-champion --walkforward \
  --comment "global_ranking_v3_all_features"
```

**Attendu** : IC Rank > 0.03 → `global_rank` est une feature utile pour le stacking.

---

## 🎯 Vision cible (rappel)

```
┌──────────────────────────────────────────────────────────────────┐
│                  PHASE 1 — Global Model (Ranking)                │
│  - Toutes les features (OHLCV, cross-sectionnelles, macro,      │
│    sentiment, screener, régime, interactions)                   │
│  - Target : rendement futur (continu, J+10)                     │
│  - Sortie : RANG percentile dans l'univers à chaque date         │
│  - Métrique : IC Rank (Information Coefficient)                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│              PHASE 2 — Per-Symbol Model (Classification)         │
│  - Features existantes + global_rank (nouvelle feature)         │
│  - Target : long/flat/short (inchangé)                          │
│  - Sortie : proba_long, proba_short                             │
│  - Métrique : F1 macro WF                                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📐 Architecture détaillée

### Phase 1 — Global Model régressif

```
Entrée :
├── Toutes les features du per-symbol (FEATURE_COLUMNS + EXPERT + ...)
├── Toutes les features cross-sectionnelles (CROSS_SECTIONAL + SECTOR + GLOBAL_EXCLUSIVE)
├── Features macro (si activées)
├── Features sentiment (si activées)
├── Features screener (si activées)
├── Nouvelles features d'interaction (cf. §3)
└── Nouvelles features fondamentales (cf. §4, si dispo)

Modèle : LightGBM / CatBoost en mode régression
  objective="regression"  (ou "quantile" / "l2")
  target = future_return (rendement futur à J+10, continu)

Sortie par date :
├── predicted_return[symbol, date]  → float
└── global_rank[symbol, date]       → percentile(0..1) dans l'univers
```

### Phase 2 — Stacking dans le per-symbol

```
Entrée per-symbol :
├── Features existantes (47 colonnes)
└── global_rank (1 colonne, PIT-safe via walk-forward)

Le per-symbol reçoit le rang global du titre comme feature.
→ Si global_rank = 0.9 (top 10%), le per-symbol peut renforcer sa conviction long
→ Si global_rank = 0.1 (bottom 10%), le per-symbol peut renforcer sa conviction short
→ Le per-symbol reste maître de la décision finale (classification ternaire)
```

---

## 3. Nouvelles features — Phase 1 (zéro donnée externe)

Ces features sont calculables immédiatement, sans nouvelle source de données.

### 3.1 Features multi-horizons supplémentaires

```python
# Actuellement : momentum_10, momentum_20, momentum_60
# Ajouter :
MOMENTUM_MULTI_HORIZON: list[str] = [
    "momentum_5",        # momentum très court
    "momentum_120",      # momentum 6 mois
    "momentum_250",      # momentum 1 an
]

# Actuellement : rolling_volatility_20, rolling_volatility_60
# Ajouter :
VOLATILITY_MULTI_HORIZON: list[str] = [
    "rolling_volatility_5",
    "rolling_volatility_10",
    "rolling_volatility_120",
]

# Actuellement : sma20/50/100/200_distance
# Ajouter :
MA_MULTI_HORIZON: list[str] = [
    "sma10_distance",
    "sma250_distance",
]

# Actuellement : rsi_14
# Ajouter :
RSI_MULTI: list[str] = [
    "rsi_5",
    "rsi_21",
]
```

### 3.2 Features d'interaction (combinaisons non linéaires)

```python
INTERACTION_FEATURES: list[str] = [
    # Efficacité du momentum
    "momentum_20_div_vol_20",        # rendement / risque
    "momentum_60_div_vol_60",        # rendement long / risque long

    # Accélération
    "momentum_5_minus_momentum_20",  # accélération court terme
    "momentum_20_minus_momentum_60", # décélération
    "volume_ratio_5_div_volume_ratio_20",  # accélération volume

    # RSI contextuel
    "rsi_14_times_volume_ratio_20",  # RSI ajusté au volume
    "rsi_14_div_volatility_20",      # RSI normalisé par la volatilité

    # Distance aux MA — croisements implicites
    "sma20_minus_sma50",             # golden cross simplifié
    "sma50_minus_sma200",            # death cross simplifié
    "ema20_minus_sma20",             # EMA vs SMA (réactivité)

    # Range / volatilité
    "intraday_range_div_atr_14",     # range intraday vs ATR
    "range_position_20_times_vol_ratio",  # position dans range × régime de vol

    # Volume / rendement
    "daily_return_times_volume_ratio_20",  # rendement pondéré par le volume
    "log_return_div_intraday_range",       # efficacité du rendement

    # Force relative contextuelle
    "relative_strength_20_times_market_trend",  # RS × tendance marché
    "relative_strength_60_div_market_volatility",  # RS ajustée à la vol marché
]
```

### 3.3 Z-score rolling (normalisation temporelle)

Chaque feature transformée en z-score sur fenêtre glissante de 5 ans (1260 jours) :

```python
def compute_rolling_zscore(series: pd.Series, window: int = 1260) -> pd.Series:
    """Z-score sur fenêtre glissante : (x - mean_rolling) / std_rolling."""
    rolling_mean = series.rolling(window, min_periods=252).mean()
    rolling_std = series.rolling(window, min_periods=252).std()
    return (series - rolling_mean) / rolling_std

# Générer pour chaque feature de momentum, volatilité, RSI, distance MA
# Exemple : momentum_20_zscore, rsi_14_zscore, sma50_distance_zscore
# ~20 colonnes supplémentaires
```

Avantage : rend les features comparables dans le temps, indépendamment du régime de marché.

### 3.4 Sector-neutralisation

Chaque feature ajustée par soustraction de la médiane sectorielle :

```python
def compute_sector_neutral(
    df: pd.DataFrame, feature_col: str, sector_map: dict[str, str]
) -> pd.Series:
    """Neutralise une feature par la médiane de son secteur."""
    df["sector"] = df["symbol"].map(sector_map)
    sector_median = df.groupby(["date", "sector"])[feature_col].transform("median")
    return df[feature_col] - sector_median

# Exemple : momentum_20_sector_neutral, rsi_14_sector_neutral
# ~10 colonnes supplémentaires
```

Avantage : isole l'alpha spécifique au titre, indépendamment de la tendance sectorielle.

---

## 4. Nouvelles features — Phase 2 (données externes)

### 4.1 Fondamentaux (via EODHD API ou Financial Modeling Prep)

```python
FUNDAMENTAL_FEATURES: list[str] = [
    # Valuation
    "pe_ratio",
    "pb_ratio",
    "ps_ratio",
    "ev_to_ebitda",
    "price_to_fcf",

    # Rentabilité
    "roe",
    "roa",
    "roic",
    "gross_margin",
    "net_margin",

    # Croissance
    "eps_growth_yoy",
    "revenue_growth_yoy",
    "fcf_growth_yoy",

    # Santé financière
    "debt_to_equity",
    "current_ratio",
    "interest_coverage",

    # Rendement
    "dividend_yield",
    "buyback_yield",
    "fcf_yield",

    # Momentum fondamental
    "earnings_surprise_pct",     # surprise vs consensus
    "estimate_revision_30d",     # révision des estimations
]
# → ~20 colonnes, actualisées trimestriellement, forward-filled jusqu'à la prochaine publication
```

### 4.2 Short interest (si dispo via Alpaca ou autre broker)

```python
SHORT_INTEREST_FEATURES: list[str] = [
    "short_interest_pct_float",
    "short_interest_change_14d",
    "days_to_cover",
]
```

### 4.3 Factor exposures (CAPM, Fama-French)

```python
# Calcul par rolling regression 252 jours sur les rendements quotidiens
FACTOR_FEATURES: list[str] = [
    "beta_252",          # CAPM beta
    "alpha_252",         # CAPM alpha (annualisé)
    "size_loading",      # SMB loading
    "value_loading",     # HML loading
    "momentum_loading",  # MOM loading
    "r_squared_252",     # qualité du fit
]
```

---

## 5. Implémentation du Global Model régressif

### 5.1 Nouveau fichier : `modelFactory/global_ranking.py`

```python
"""
Global Ranking Model — Régression cross-sectionnelle du rendement futur.

Contrat PIT :
- Entraîné en walk-forward (mêmes splits que le per-symbol)
- Les prédictions pour une date D utilisent UNIQUEMENT des features connues à D
- La target (future_return D→D+10) est forward-looking mais le split WF gère le PIT
- Sortie : global_rank[symbol, date] ∈ [0, 1]
"""

def train_global_ranking_wf(
    symbols: list[str],
    cfg: TrainingConfig,
    *,
    artifacts_dir: Path,
    engine: Any,
) -> dict[str, Any]:
    """
    Entraîne un Global Ranking Model en walk-forward.

    Retourne un dict avec :
    - global_rank_df : pd.DataFrame [symbol, date, global_rank]
    - feature_columns : list[str] — les features utilisées
    - ic_rank_mean : float — Information Coefficient moyen (WF)
    """
    ...
```

### 5.2 Target : rendement futur continu

```python
# Dans _prepare_global_ranking_frame() :
df["future_return"] = df.groupby("symbol")["close"].transform(
    lambda x: x.shift(-horizon) / x - 1.0
)
# → Pas de binarisation en long/flat/short
# → Le modèle apprend à prédire le rendement directement
```

### 5.3 Métrique : IC Rank (Information Coefficient)

```python
def compute_ic_rank(predicted: np.ndarray, actual: np.ndarray) -> float:
    """
    Spearman rank correlation entre prédictions et réalisations.
    Valeur ∈ [-1, 1]. Les pros visent IC > 0.05.
    """
    from scipy.stats import spearmanr
    return float(spearmanr(predicted, actual)[0])

# Stocké dans model_metrics comme "ic_rank" (nouvelle colonne à ajouter)
```

### 5.4 Sortie : rang percentile

```python
# Par date, calculer le rang percentil de chaque titre dans l'univers
global_rank_df["global_rank"] = global_rank_df.groupby("date")[
    "predicted_return"
].rank(pct=True)
```

---

## 6. Injection dans le per-symbol (Stacking)

### 6.1 Modification de `cross_sectional.py`

```python
# Remplacer GLOBAL_PRED_FEATURE_COLUMNS par :
GLOBAL_RANK_FEATURE_COLUMNS: list[str] = ["global_rank"]
# + optionnellement les 3 probas ternaires si on veut les garder :
GLOBAL_PRED_FEATURE_COLUMNS: list[str] = [
    "global_pred_short", "global_pred_flat", "global_pred_long",
    "global_rank",  # ← NOUVEAU
]
```

### 6.2 Flow dans l'orchestrateur

```python
# Dans run_training_batch() :
if cfg.global_model.enabled:
    # Phase 1 : Global Ranking Model
    global_ranking_result = train_global_ranking_wf(symbols, cfg, ...)

    # Phase 2 : Sauvegarder global_rank_df pour les workers
    global_rank_df = global_ranking_result["global_rank_df"]
    # → persisté en parquet comme _global_pred_cache actuellement
    _global_rank_path = Path(cfg.artifacts_dir) / "_global_rank_cache.parquet"
    global_rank_df.to_parquet(_global_rank_path, index=False)

# Dans _train_worker :
# Charger et merger global_rank dans le cross_sectional_df
if cfg.global_model.stacking_enabled:
    global_rank_df = pd.read_parquet(_global_rank_path)
    cross_sectional_df = cross_sectional_df.merge(
        global_rank_df, on=["symbol", "date"], how="left",
    )
    cross_sectional_df["global_rank"] = (
        cross_sectional_df["global_rank"].fillna(0.5).astype(np.float64)
    )
```

---

## 7. Suppression du Global Model comme challenger

### 7.1 Code à supprimer/désactiver

- `orchestrator.py` : `_inject_global_model_into_symbol_artifacts()` — supprimer ou garder dormant
- `orchestrator.py` : persistence `global_model` dans `model_metrics` — remplacer par persistence `global_ranking`
- `global_model.py` : `train_global_model()` et `train_global_model_wf()` — marquer comme legacy
- `champion_selection.py` : éligibilité `global_model` — supprimer
- `config.py` : `global_model.challenger_enabled` — mettre `False` par défaut
- `ihm/pipeline_ml_defaults.py` : `DEFAULT_ML_ENABLE_GLOBAL_CHALLENGER = False`

### 7.2 Configuration simplifiée

```yaml
# config.yaml
global_model:
  enabled: true
  model_name: "lightgbm"     # ou catboost
  stacking_enabled: true     # Active le stacking (global_rank comme feature)
  challenger_enabled: false  # DÉSACTIVÉ — le global model ne participe pas au championnat
  use_cross_sectional_features: true
  use_all_features: true     # NOUVEAU — utilise toutes les features, pas seulement cross-sectionnelles
```

---

## 8. Plan de déploiement

### Étape 1 — Features d'interaction (1-2h)

| Action | Fichier | Détail |
|--------|---------|--------|
| Ajouter `INTERACTION_FEATURES` | `features.py` | 15 colonnes, calculées dans `compute_features()` |
| Ajouter `MOMENTUM_MULTI_HORIZON` | `features.py` | momentum_5, momentum_120, momentum_250 |
| Ajouter `VOLATILITY_MULTI_HORIZON` | `features.py` | rolling_volatility_5, _10, _120 |
| Ajouter `RSI_MULTI` | `features.py` | rsi_5, rsi_21 |
| Ajouter `MA_MULTI_HORIZON` | `features.py` | sma10_distance, sma250_distance |
| Ajouter les features au `feature_set="expert"` | `features.py:get_feature_columns()` | |

**Test** : lancer un batch `baseline + interactions` et comparer F1 WF.

### Étape 2 — Z-score rolling + sector-neutralisation (1-2h)

| Action | Fichier | Détail |
|--------|---------|--------|
| `compute_rolling_zscore()` | `features.py` | Appliquer aux features momentum, vol, RSI, distance MA |
| `compute_sector_neutral()` | `features.py` | Utiliser `sector_map` de `cross_sectional.py` |
| Colonnes suffixées `_zscore`, `_sector_neutral` | `features.py` | ~30 colonnes |

**Test** : lancer un batch `baseline + interactions + zscore` et comparer.

### Étape 3 — Global Ranking Model (3-4h)

| Action | Fichier | Détail |
|--------|---------|--------|
| Créer `global_ranking.py` | `modelFactory/global_ranking.py` | Régresseur WF avec toutes les features |
| Modifier `_get_global_feature_columns()` | `global_ranking.py` | Utiliser TOUTES les features (pas seulement cross-sec) |
| Ajouter `compute_ic_rank()` | `global_ranking.py` | Spearman rank correlation |
| Persister `global_rank_df` en parquet | `orchestrator.py` | Comme `_global_pred_cache.parquet` actuellement |
| Ajouter `global_rank` dans `GLOBAL_PRED_FEATURE_COLUMNS` | `cross_sectional.py` | |
| Ajouter `ic_rank` dans `model_metrics` | `db_registry.py` | Nouvelle colonne DB |

**Test** : lancer un batch avec `--enable-global-model --enable-global-stacking` et vérifier IC > 0.02.

### Étape 4 — Nettoyage (1h)

| Action | Détail |
|--------|--------|
| Supprimer `--enable-global-challenge` du pipeline | Garder le flag mais le rendre no-op |
| Migrer `model_metrics` pour ajouter `ic_rank` | `alembic/versions/0055_add_ic_rank.py` |
| Mettre à jour le rapport pour afficher `ic_rank` du global | `report.py` |
| Tests de non-régression | |

### Étape 5 — Fondamentaux (si API dispo) (2-3h)

| Action | Détail |
|--------|--------|
| Créer `modelFactory/fundamental_features.py` | Chargement depuis EODHD / FMP |
| Cache fondamentaux dans `artifacts/fundamentals_cache/` | PIT-safe avec `publication_date` |
| Forward-fill jusqu'au prochain trimestre | |
| Ajouter dans `get_feature_columns()` | |

---

## 9. Schéma PIT (Point-In-Time)

```
Timeline pour une date de trading D :

D-252 ... D-20 ... D ... D+10
  │                │      │
  │                │      └── future_return (target du ranking model)
  │                │
  ├── Features OHLCV calculées à D (connues)
  ├── Features cross-sectionnelles calculées à D (connues, basées sur univers à D)
  ├── Fondamentaux du dernier trimestre publié avant D (connus)
  └── global_rank[D] = prédit par le Global Ranking Model entraîné sur données ≤ D
                         (walk-forward : le split WF garantit pas de look-ahead)

Le per-symbol à D reçoit :
  - Ses 47+ features locales (calculées à D)
  - global_rank (calculé à D par le Global Model)
  → Prédit long/flat/short pour D+10
```

---

## 10. Indicateurs de succès

| Métrique | Actuel | Cible | Mesure |
|----------|:---:|:---:|--------|
| F1 WF LightGBM (per-symbol) | 0.296 | > 0.300 | Après stacking global_rank |
| IC Rank (Global Model) | N/A | > 0.03 | Spearman correlation |
| Global Model F1 directionnel | 0.07 | N/A (abandonné) | Le ranking n'a pas de F1 |
| Temps batch additionnel | +0min | < +10min | Le ranking est rapide (1 modèle) |

---

## 11. Questions ouvertes

1. **LightGBM ou CatBoost pour le ranking ?** LightGBM est plus rapide et souvent meilleur en régression. À tester les deux.

2. **Faut-il garder `global_pred_short/flat/long` en plus de `global_rank` ?** Probablement pas — le rang capture déjà l'information directionnelle. Mais on peut tester A/B.

3. **Faut-il normaliser `global_rank` par secteur ?** Intéressant — un top 10% dans un secteur défensif n'a pas la même signification qu'un top 10% dans la tech. À explorer.

4. **Fondamentaux : EODHD ou FMP ?** EODHD a déjà un client dans le projet (`service/eodhd/`). Vérifier si les fondamentaux sont inclus dans le plan tarifaire.
