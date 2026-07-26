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
| **Target market-neutral** : rendement excédentaire vs SPY | `modelFactory/global_ranking.py` | ✅ (26/07) |
| Per-Symbol Stacking via `global_rank` ∈ [0,1] | `modelFactory/cross_sectional.py`, `predictor.py` | ✅ |
| Global Model **PAS** challenger champion | `pipeline_ml_defaults.py` | ✅ |
| Nettoyage `_has_global_rank` vs `_has_global_pred` | `trainer.py`, `tabular_baseline.py` | ✅ |
| Inférence : `predict_global_rank()` + cache par date + fallback 0.5 | `modelFactory/predictor.py` | ✅ |
| **Inférence corrigée** : cross-sectional features réintégrées | `modelFactory/global_ranking.py` | ✅ (26/07) |
| Tests stacking/global 115 OK | `tests/test_stacking.py`, etc. | ✅ |

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
| **Régime macro** (`SPY_SMA_200_slope` + `VIX_zscore`) | 2 | `modelFactory/features.py` | ✅ (26/07) |
| **Interactions global_rank × locales** (`rank_x_rsi_14`, etc.) | 6 | `modelFactory/features.py` | ✅ (26/07) |

### Modélisation
| Composant | Fichier | Statut |
|-----------|---------|:------:|
| **Régularisation stricte** (`max_depth=4`, `num_leaves=15`, `min_child_samples=30`) | `config.py`, `trainer.py`, `global_ranking.py` | ✅ (26/07) |
| **`class_weight="balanced"`** + `auto_class_weights="Balanced"` | `trainer.py`, `global_ranking.py` | ✅ (26/07) |
| **Subsampling** (`subsample=0.8`, `colsample_bytree=0.7`) | `config.py`, `trainer.py`, `global_ranking.py` | ✅ (26/07) |

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
| IC Rank persisté en DB | `model_training_batch.ic_rank` | `alembic/versions/0056_*` |
| IC Rank affiché dans l'IHM | 🩺 Diagnostic ML → Détail batch | `ihm/pages/ml_diagnostics.py` |

---

## 🔧 Corrections & Optimisations (26/07/2026)

### Bug Fixes — Audit `global_ranking.py`
| # | Bug | Impact | Correction |
|:--:|------|--------|------------|
| 1 | `include_macro_regime` absent de `_get_ranking_feature_columns()` | `SPY_SMA_200_slope` + `VIX_zscore` calculés mais ignorés | Ajout du paramètre |
| 2 | `predict_global_rank()` sans cross-sectional features | Inférence live → `global_rank` = bruit | Ajout `build_cross_sectional_features` + `merge` |
| 3 | `fingerprint()` / `build_feature_contract()` sans `include_macro_regime` | Crash `TypeError` au `_build_run_summary` | Ajout du paramètre aux 3 fonctions |
| 4 | `effective_data_cfg` no-op + imports inutilisés | Code mort | Supprimé |

### Market-Neutral Target
| Changement | Avant | Après |
|-----------|-------|-------|
| Target du Global Ranking | `future_return = stock J+10` | `future_return = stock J+10 - SPY J+10` |
| Objectif | Prédire la direction absolue | Prédire la **surperformance relative** |
| Effet attendu | IC inversé par rotations sectorielles | IC stable à travers les régimes |
| Fallback | — | Si pas de `benchmark_df`, garde le rendement brut |

### Macro Feature Blacklist — Phase 1 (Global Ranking)
| Changement | Détail |
|-----------|--------|
| Features retirées | 15 features macro-globales (SPY/VIX/MOVE/régime) |
| Fichier | `modelFactory/global_ranking.py` → `_get_ranking_feature_columns()` |
| Raison | Ces features sont **identiques pour tous les symboles** à une date donnée → ne peuvent pas discriminer le classement cross-sectionnel |
| Features blacklistées | `SPY_SMA_200_slope`, `VIX_zscore`, `vix_close`, `vix_momentum_5j`, `vxn_close`, `vxn_spread_vix`, `vix3m_close`, `vix_term_structure_ratio`, `vix_backwardation`, `move_close`, `market_return_20`, `market_volatility_20`, `market_trend_strength_50`, `regime_bull_market`, `regime_risk_off` |
| Features conservées | Interactions régime (`_x_bull`, `_x_risk_off`), `relative_strength_*`, toutes les features cross-sectionnelles et locales |
| Effet attendu | Le modèle n'a plus de « bruit macro » → forcé d'utiliser des features discriminantes (`momentum_*_zscore`, `dollar_volume_20_rank`, `sector_neutral_*`) |
| **Important** | Ces features restent disponibles pour les **modèles per-symbol Phase 2** |

### Target = Rang Percentile par Date (Rank Target)
| Changement | Avant | Après |
|-----------|-------|-------|
| Target | `future_return` continu (excess vs SPY) | `rank_percentile(future_return)` par date ∈ [0,1] |
| Fichier | `modelFactory/global_ranking.py` → `train_global_ranking_wf()` |
| Raison | Le L2 loss est sensible aux outliers (+80% sur une biotech), le Spearman non. Entraîner sur des rangs aligne la loss d'entraînement avec la métrique d'évaluation |
| Sortie modèle | `predicted_return` continu | `predicted_return` ∈ [0,1] → utilisé directement comme `global_rank` (clippé) |
| `_compute_per_date_rank()` | Utilisé en post-processing | **Plus nécessaire** — la prédiction est le rang |
| Effet attendu | — | Distribution uniforme de la target, plus d'outliers, IC plus stable |

### Historique des itérations IC Rank
| # | Correctifs cumulés | ic_mean | ic_std | Splits > 0 | Pire split |
|:---:|---------------------|:---:|:---:|:---:|:---:|
| 1 | Target absolue | +0.017 | 0.102 | 4/8 | −0.106 |
| 2 | + Excess return vs SPY | −0.003 | 0.043 | 3/8 | −0.061 |
| 3 | + Blacklist macro (15 features) | −0.023 | 0.033 | 2/8 | −0.075 |
| 4 | + **Target = rang percentile** | **+0.012** ✅ | **0.025** ✅ | **6/8** ✅ | **−0.033** |

**Conclusion** : IC passée de −0.023 à +0.012. Variance divisée par 4. 6 splits sur 8 positifs. Le `global_rank` a un signal cross-sectionnel faible mais réel. Top features = facteurs canoniques (`dollar_volume_20_rank`, `sma50_minus_sma200`, `rolling_volatility_120_zscore`, `momentum_250_zscore`).

### Multi-Horizons Global Rank (Action 6) — ✅ Implémenté (26/07)
| Changement | Détail |
|-----------|--------|
| Fichiers | `global_ranking.py`, `orchestrator.py`, `cross_sectional.py`, `predictor.py`, `features.py` |
| Horizons | `_GLOBAL_RANKING_HORIZONS = (3, 5, 10)` |
| Fonctionnement | Features communes, target recalculée par horizon, 3 modèles WF entraînés → 3 colonnes de rang |
| Sortie | `global_rank_3`, `global_rank_5`, `global_rank_10` dans le cache cross-sectional |
| IC | Loggué par horizon : `ic_by_h={3: x.xxx, 5: x.xxx, 10: x.xxx}` |
| `GLOBAL_PRED_FEATURE_COLUMNS` | `["global_rank_3", "global_rank_5", "global_rank_10", "global_rank"]` |
| Nouvelle feature dérivée | `rank_acceleration = global_rank_3 − global_rank_10` — vitesse du rang (> 0 = accélération, < 0 = décélération) |
| Modèles | `_global_ranking_model_3.txt`, `_5.txt`, `_10.txt` |
| Inférence | `predict_global_rank()` charge tous les modèles et retourne toutes les colonnes |

| # | Évolution | ic_mean | ic_std |
|:---:|----------|:---:|:---:|
| 5 | + **Multi-horizons (J+3/J+5/J+10) + LambdaRank** | **À mesurer** | **À mesurer** |

### 🔴 Bug Critique — Target Cross-Symbol Shift (26/07)
| Changement | Détail |
|-----------|--------|
| Fichier | `modelFactory/global_ranking.py` → `train_global_ranking_wf()` |
| Bug | `_close.shift(-horizon)` sur le DataFrame concaténé (trié par `[date, symbol]`) → shift entre symboles différents au lieu d'être intra-symbole |
| Correction | `base_df.groupby("symbol")["close"].shift(-horizon)` — shift strictement par symbole |
| Impact | IC factice de 0.44 → IC réel de 0.004. Tous les IC antérieurs étaient gonflés par cette fuite. |
| Purge WF | `forecast_horizon` passé de 10 lignes à `max_horizon × daily_symbols` (vraie purge en jours) |

### ✅ Cross-Sectional Rank Normalization — Features (26/07)
| Changement | Détail |
|-----------|--------|
| Fichier | `modelFactory/global_ranking.py` |
| Features concernées | 35 features brutes : momentum, volatilité, RSI, distance aux MA, rendements, volume, range, force relative |
| Transformation | `groupby("date")[feature].rank(pct=True)` → colonne `{feature}_xs_rank` ∈ [0, 1] |
| Nombre de nouvelles colonnes | +35 (`_xs_rank`) |
| Total feature_columns | 123 + 35 = 158 |
| Raison | Les features absolues (ex: RSI=70) changent de sens selon le régime de marché. Le rang intra-date les rend comparables dans le temps et entre secteurs/capitalisations. |
| Inférence | `predict_global_rank()` applique la même transformation sur l'univers du jour |

### Historique des IC après corrections

| # | Évolution | H3 | H5 | H10 | ic_mean |
|:---:|----------|:---:|:---:|:---:|:---:|
| 5 | Après fix cross-symbol shift + purge WF | +0.008 | −0.002 | +0.007 | **+0.004** |
| 6 | + Cross-sectional rank features (35 `_xs_rank`) | **À mesurer** | **À mesurer** | **À mesurer** | **À mesurer** |
| 7 | + Winsorization 1%/99% + rsi_3/dist_sma_5d/vol_zscore_5d + n_est 500 + early_stop 30 + top-K feat | **+0.009** | **+0.005** | **+0.004** | **+0.006** |
| 8 | + **Per-horizon feature selection** (chaque horizon choisit ses propres top-K) | **À mesurer** | **À mesurer** | **À mesurer** | **À mesurer** |
| 9 | + **Temporal dynamics features** (6 features Niveau 3 : accel, decay, rsi_slope, vol_expansion, meanrev, gap_fade) | **À mesurer** | **À mesurer** | **À mesurer** | **À mesurer** |

---

## 🚀 Sprint "5 Quick Wins" — Implémenté (26/07)

### Win 1 — Winsorization de la target (priorité #1)
| Changement | Détail |
|-----------|--------|
| Fichier | `modelFactory/global_ranking.py` → target pre-computation |
| Transformation | `groupby("date")[future_return].transform(lambda x: x.clip(lower=x.quantile(0.01), upper=x.quantile(0.99)))` |
| Raison | Élimine les outliers toxiques (±30% sur small caps) qui polluent le rank percentile et biaisent la feature importance |
| Coût | ~15 min, 3 lignes de code |

### Win 2 — Feature importance + pruning top-K
| Changement | Détail |
|-----------|--------|
| Fichier | `modelFactory/global_ranking.py` → `_compute_mean_importance()` + boucle d'entraînement |
| Config | `baseline.ranking_top_k_features: int = 0` (0 = désactivé, ex: 30 = top 30) |
| Fonctionnement | Après le 1er horizon (H3), moyenne des importances « gain » sur tous les splits → sélection top-K → appliqué à H5 et H10 |
| Log | Top 5 features + liste complète en info |
| Sauvegarde | `horizon_features` dans le metadata JSON → utilisées en inférence |
| Coût | ~30 min |

### Win 3 — Features de réversion court-terme
| Changement | Détail |
|-----------|--------|
| Fichier | `modelFactory/features.py` → `MULTI_HORIZON_FEATURES` + `compute_features()` |
| Nouvelles features | `rsi_3` (RSI 3 périodes), `dist_to_sma_5d` (écart à SMA 5j), `volume_zscore_5d` ((vol − moyenne_5j) / std_5j) |
| Ajout `_xs_rank` | Les 3 features sont aussi normalisées en rang cross-sectionnel |
| Total features | 158 + 3 + 3 (`_xs_rank`) = **164** |
| Coût | ~1h |

### Win 4 — n_estimators 200→500 + early stopping
| Changement | Détail |
|-----------|--------|
| Fichier | `modelFactory/config.py` → `n_estimators: int = 500`, `lgbm_early_stopping_rounds: int = 30` |
| Eval set | 20% du train (le plus récent chronologiquement) utilisé comme validation pour early stopping |
| LightGBM | `eval_set`, `eval_group`, `eval_at=[10,20]` passés à `model.fit()` |
| Coût | ~30 min |

### Win 5 — Feature selection par horizon (top-K dédié)
| Changement | Détail |
|-----------|--------|
| Fichier | `modelFactory/global_ranking.py` → `_horizon_features` dict |
| Fonctionnement | Chaque horizon peut utiliser une liste de features différente (issue de sa propre importance ou de H3) |
| Inférence | `predict_global_rank()` utilise `horizon_features` du metadata → chaque modèle reçoit exactement ses features |
| Coût | ~2h (refactoring inclus dans Win 2) |

---

## 🧠 Peer Review — Ajustements & Garde-fous (26/07/2026)

Revue externe du plan d'action. Les ajustements suivants sont intégrés :

### ✅ Ajustement 1 — Garder le Global Model comme benchmark dans les métriques
> Le Global Model (régresseur → `global_rank`) ne doit **pas** être supprimé des métriques challengers. Il doit rester visible dans les rapports de batch comme **baromètre de marché** (IC Rank, F1 directionnel baseline). Il est tagué « Benchmark » et non « Ordre exécutable ». Le `challenger_enabled=false` empêche sa sélection comme champion, mais il reste dans `model_governance` et les dashboards pour le suivi.

- [x] `DEFAULT_ML_ENABLE_GLOBAL_CHALLENGER = False` (déjà fait) — il ne sera jamais champion
- [ ] Vérifier que le Global Model apparaît bien dans `model_governance` avec `is_selected_model=0`
- [ ] Ajouter le tag visuel "📊 Benchmark" dans l'IHM pour le modèle global dans le ranking challengers

### ✅ Ajustement 2 — Pas de diète de features : régularisation d'abord
> Les 42+ features actuelles restent. LightGBM/CatBoost font leur propre sélection implicite (gain d'information). On applique la régularisation stricte (`max_depth=3-4`, `min_child_samples=30`) et on analyse les *feature importance* après le batch. On n'élague que les features à importance quasi-nulle (< 1%).

- [x] Action 2 (régularisation) reste prioritaire
- [ ] Après 2-3 batchs, exporter les feature importance et identifier les colonnes à ~0%
- [ ] Supprimer UNIQUEMENT celles qui n'apportent rien — ne pas fixer de seuil arbitraire à l'avance

### ✅ Ajustement 3 — TemperatureScaler conservé, VectorScaler dépriorisé
> Le `TemperatureScaler` actuel fonctionne. Le gain du `VectorScaler` est marginal et ne justifie pas le risque de régression. On garde le TemperatureScaler, et on revisitera la calibration uniquement si les probabilités calibrées montrent un biais directionnel systématique.

- [x] Action 7 (VectorScaler) rétrogradée de Moyen Terme → Long Terme
- [x] Action 8 (TernaryDecisionPolicy) reste en Moyen Terme car indépendante du scaler

### ✅ Ajustement 4 — Valider `global_rank` avant de le décomposer
> On ne crée pas 3 sous-rangs tant que le `global_rank` unique n'a pas fait ses preuves (IC > 0.03 confirmé sur plusieurs batchs). La décomposition est conditionnelle.

- [x] Action 9 (Décomposition) reste en Long Terme, avec pré-condition explicite : IC Rank > 0.03 stable

### ✅ Ajustement 5 — LambdaRank + approche « Learning-to-Rank » (26/07)
> L'IC actuel (+0.012, ic_std=0.025) est positif mais faible. Pour passer au seuil institutionnel (> 0.03), deux leviers professionnels identifiés :

#### Levier 5a — `objective="lambdarank"` (implémenté ✅)
| Changement | Détail |
|-----------|--------|
| Fichier | `modelFactory/global_ranking.py` → `_build_ranking_estimator()` |
| Avant | `LGBMRegressor(objective="regression")` → L2 loss sur valeurs brutes |
| Après | `LGBMRanker(objective="lambdarank", metric="ndcg", eval_at=[10,20,50])` → loss directement sur la qualité du classement |
| `group` | Nombre de symboles par date, injecté via `model.fit(X, y, group=group_sizes)` |
| CatBoost | Inchangé (`objective="RMSE"`) — pas d'équivalent LambdaRank natif |

#### Levier 5b — Horizon J+5 (→ intégré à l'Action 6, implémenté ✅)
- L'horizon J+10 est bruité ; J+5 capture mieux le momentum court terme
- Utiliser `--forecast-horizon 5` en CLI

#### Leviers 5c/d — Normalisation cross-sectionnelle + Winsorization (futur)
- Transformer toutes les features en rang percentile par date avant la Phase 1
- Winsoriser la target et les features à 1%/99% pour éliminer les outliers
- À implémenter si LambdaRank + J+5 ne suffisent pas à atteindre IC > 0.03

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
| ~~1~~ | ~~**Indicateurs de régime macro**~~ → ✅ Fait (26/07) | — | — |
| ~~2~~ | ~~**Régularisation stricte des arbres**~~ → ✅ Fait (26/07) | — | — |
| ~~3~~ | ~~**`class_weight="balanced"`**~~ → ✅ Fait (26/07) | — | — |
| ~~4~~ | ~~**Subsampling**~~ → ✅ Fait (26/07) | — | — |

### 🟡 À faire — Moyen terme
| # | Recommandation | Priorité | Effort |
|:--:|---------------|:--------:|:------:|
| ~~5~~ | ~~**Exploitation des rangs** : features d'interaction `rank_x_*`~~ → ✅ Fait (26/07) | — | — |
| 6 | **Multi-horizons Phase 1** : `global_rank` prédit sur J+3, J+5, J+10 → stack de 3 rangs + `rank_acceleration` | ~~🟡 Moyenne~~ ✅ Fait (26/07) |
| 7 | **TernaryDecisionPolicy** : ajustement des seuils selon probabilités calibrées | 🟡 Moyenne | 2h |

### 🔵 À faire — Long terme
| # | Recommandation | Priorité | Effort |
|:--:|---------------|:--------:|:------:|
| 8 | **VectorScaler** (température + biais par classe) — si biais directionnel avéré | 🟢 Basse | 2h |
| 9 | **Décomposition du global** : `rank_momentum`, `rank_mean_reversion`, `rank_volatility` — si IC > 0.03 stable | 🟢 Basse | 5-8h |
| 10 | **Ensembling per-symbol** : LightGBM + CatBoost (moyenne/stacking des prédictions) | 🟢 Basse | 3-4h |
| 11 | **Short Interest** : scraping FINRA (mensuel, fichier TXT gratuit) | 🟢 Basse | 3-4h |
| 12 | **Estimation d'incertitude** : variance intra-ensemble pour filtrer trades peu certains | 🟢 Basse | 5-8h |
| 13 | **Pondération dynamique du capital** selon confiance calibrée | 🟢 Basse | 5-8h |

---

## 🎯 Plan d'Action Détaillé — Sprint "Quick Wins"

### Action 1 — Indicateurs de Régime Macro
**Fichiers** : `modelFactory/features.py`, `modelFactory/config.py`

**🎯 Pourquoi ?**
> Aujourd'hui, chaque modèle per-symbol travaille « en aveugle » sur le contexte macro. Un RSI à 70 en marché haussier (SPY au-dessus de sa SMA 200, VIX bas) n'a PAS la même signification qu'un RSI à 70 en bear market (SPY sous SMA 200, VIX élevé). Sans ces features, le modèle local traite ces deux situations de façon identique, ce qui dégrade la qualité des prédictions — surtout en changement de régime.
>
> `SPY_SMA_200_slope` donne la tendance long terme du marché (bull/bear structurel). `VIX_zscore` donne le régime de volatilité (stress vs calme). Injectées à TOUS les symboles, ces 2 features permettent au modèle local d'adapter ses décisions au contexte macro sans coût additionnel.

- [ ] Ajouter `include_macro_regime: bool = False` dans `DataConfig`
- [ ] Ajouter `SPY_SMA_200_slope`, `VIX_zscore` dans `get_feature_columns()` (mode `expert`)
- [ ] Les calculer dans `compute_features()` quand le flag est activé
- [ ] CLI : `--include-macro-regime`
- [ ] IHM : checkbox dans Pipeline → ML Train

### Action 2 — Régularisation Stricte des Arbres Locaux
**Fichier** : `modelFactory/tabular_baseline.py`

**🎯 Pourquoi ?**
> Sur ~2 000 lignes daily par symbole, un arbre non contraint (`max_depth=-1`, `num_leaves=31`) a assez de capacité pour **mémoriser le bruit** plutôt que d'apprendre le signal. C'est le problème classique du surapprentissage sur petits échantillons financiers : le modèle trouve des patterns qui marchent parfaitement en backtest mais échouent en live.
>
> `max_depth=3-4` et `num_leaves=8-15` limitent la complexité à ce que 2 000 lignes peuvent raisonnablement supporter. `min_child_samples=30-50` empêche les splits sur des micro-groupes non représentatifs. C'est le standard en finance quantitative pour les modèles tree-based sur données daily.

- [ ] Modifier `_train_lightgbm()` → `max_depth=4, num_leaves=15, min_child_samples=30`
- [ ] Modifier `_train_catboost()` → `max_depth=4, min_data_in_leaf=30`
- [ ] Rendre paramétrable via `config.yaml` → `tabular_baseline.regularization: strict|loose`

### Action 3 — `class_weight="balanced"` + Subsampling
**Fichier** : `modelFactory/tabular_baseline.py`

**🎯 Pourquoi ?**
> En classification ternaire (long/flat/short), la classe `flat` domine souvent 50-60% des échantillons. Sans pondération, le modèle apprend à prédire `flat` par défaut — c'est le chemin de moindre résistance pour minimiser la loss, mais c'est inutile pour le trading. `class_weight="balanced"` force le modèle à accorder autant d'importance à un `long` ou un `short` qu'à un `flat`, quelle que soit leur fréquence.
>
> Le **subsampling** (`subsample=0.8`, `colsample_bytree=0.7`) empêche la corrélation excessive entre arbres (chacun voit un sous-échantillon différent) et réduit le surapprentissage. C'est le deuxième pilier de la régularisation après la contrainte de profondeur.

- [ ] LightGBM : `class_weight="balanced"`, `subsample=0.8`, `colsample_bytree=0.7`
- [ ] CatBoost : `auto_class_weights="Balanced"`, `subsample=0.8`, `colsample_bylevel=0.7`

### Action 4 — Features d'Interaction `rank_x_*`
**Fichier** : `modelFactory/features.py`

**🎯 Pourquoi ?**
> Aujourd'hui `global_rank` est injecté comme une feature brute. Mais la relation entre le rang global et le signal local n'est pas linéaire : un titre top 10% (`global_rank ≈ 0.9`) avec un RSI de 30 (survente) est une opportunité d'achat bien plus forte qu'un titre top 10% avec un RSI de 80 (surachat). Les features d'interaction `rank_x_rsi`, `rank_x_momentum_20`, etc. permettent au modèle local de capturer ces **effets croisés** que ni le rang seul ni les features locales seules ne peuvent exprimer.
>
> Coût quasi nul : 5 features calculées en une ligne chacune. Gain potentiel : amélioration du F1 WF de 0.01-0.02 si le `global_rank` a un IC > 0.02.

- [ ] Ajouter `rank_x_rsi_14`, `rank_x_momentum_20`, `rank_x_momentum_60`, `rank_x_volatility_20`, `rank_x_sma20_distance`
- [ ] Calcul dans `compute_features()` après le merge du `global_rank`
- [ ] Ajouter dans `get_feature_columns()` (mode `expert`)

---

## 📐 Plan d'Action Détaillé — Moyen Terme

### Action 5 — Multi-Horizons Global Rank
**Fichier** : `modelFactory/global_ranking.py`

**🎯 Pourquoi ?**
> Un seul `global_rank` sur J+10 donne une vision uniforme du rendement futur. Mais le marché réagit à différentes vitesses : certains titres sur-réagissent à court terme (J+3) puis mean-revert, d'autres ont un momentum qui se construit sur J+10. En empilant 3 horizons (J+3, J+5, J+10), le modèle per-symbol reçoit une « courbe de rendement attendu » : il peut apprendre qu'un titre avec `rank_3` élevé mais `rank_10` faible est un trade court terme, pas un swing.
>
> Coût : 3 modèles au lieu d'un en Phase 1, mais la Phase 1 est déjà rapide (~2 min pour 200 symboles). Gain attendu : +0.01-0.02 de F1 WF si le IC multi-horizons est bon.

- [ ] Modifier `train_global_ranking_wf()` pour boucler sur `HORIZONS = [3, 5, 10]`
- [ ] Persister 3 colonnes `global_rank_3`, `global_rank_5`, `global_rank_10` dans le cache
- [ ] Mettre à jour `GLOBAL_RANK_FEATURE_COLUMNS` dans `cross_sectional.py`
- [ ] Mettre à jour `predictor.py` pour l'inférence multi-horizons

### Action 6 — VectorScaler (Température + Biais par Classe)
**Fichier** : `modelFactory/calibration.py`

**🎯 Pourquoi ?**
> Le `TemperatureScaler` actuel applique une seule température T à toutes les classes. Mais en classification ternaire, le biais « flat » est structurel : les logits de la classe `flat` sont systématiquement plus élevés que `long` et `short`. Une température unique ne corrige pas ce déséquilibre directionnel.
>
> Le `VectorScaler` apprend un vecteur `[bias_short, bias_flat, bias_long] + température T` — le biais `flat` sera abaissé et les biais `long`/`short` remontés, rendant les probabilités calibrées réellement exploitables pour le dimensionnement des positions.

- [ ] Créer `VectorScaler` dans `modelFactory/calibration.py`
- [ ] Remplacer `TemperatureScaler` → `VectorScaler` dans `trainer.py`
- [ ] Ajouter `--calibration vector` dans la CLI

### Action 7 — TernaryDecisionPolicy
**Fichier** : `modelFactory/decision.py` (nouveau)

**🎯 Pourquoi ?**
> Actuellement, la décision long/flat/short est prise avec un seuil fixe (`decision_threshold=0.55`). Mais après calibration, les distributions de probabilités changent : un seuil unique n'est plus optimal. La `TernaryDecisionPolicy` ajuste dynamiquement les seuils en fonction des distributions calibrées pour maximiser le F1 ou le business score.

- [ ] Créer `TernaryDecisionPolicy` avec seuils adaptatifs par split
- [ ] Intégrer dans `trainer.py` → `_prepare_target_optimization_summary()`

---

## 🔵 Plan d'Action Détaillé — Long Terme

### Action 8 — VectorScaler (Température + Biais par Classe)
**Fichier** : `modelFactory/calibration.py`

**🎯 Pourquoi ?**
> Dépriorisé : le `TemperatureScaler` actuel est stable et fonctionnel. Le VectorScaler n'apporte un gain que si on observe un **biais directionnel systématique** dans les probabilités calibrées (ex: `proba_flat` systématiquement surgonflée). À ne faire que si l'analyse post-batch le justifie.

- [ ] Condition : observer un biais > 5% entre `pred_flat_pct` et `true_flat_pct` sur plusieurs batchs
- [ ] Créer `VectorScaler` dans `modelFactory/calibration.py`
- [ ] Remplacer `TemperatureScaler` → `VectorScaler` dans `trainer.py`

### Action 9 — Décomposition du Global en 3 sous-rangs
**Fichier** : `modelFactory/global_ranking.py`

**🎯 Pourquoi ?**
> Conditionnel : nécessite IC Rank > 0.03 confirmé sur au moins 3 batchs. Un `global_rank` unique qui ne prédit rien ne donnera pas 3 sous-rangs magiques. Si le IC est bon, la décomposition permet au per-symbol de pondérer différemment momentum, mean-reversion et volatilité selon le régime.

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

| Métrique | Actuel (absolu) | Après excess return | Après blacklist macro | Après rank target | Cible |
|----------|:---:|:---:|:---:|:---:|:---:|
| IC Rank (Global Model) | +0.017 (ic_std=0.102) | −0.003 (ic_std=0.043) | −0.023 (ic_std=0.033) | **+0.012 (ic_std=0.025)** | > 0.03 |
| Splits positifs | 4/8 | 3/8 | 2/8 | **6/8** | 8/8 |
| F1 WF LightGBM (per-symbol) | ~0.296 | — | — | — | > 0.310 |

---

## 📁 Fichiers impactés — Résumé

| Fichier | Actions 1-4 (Court Terme) | Actions 5-7 (Moyen Terme) |
|---------|:---:|:---:|
| `modelFactory/features.py` | 🔧 macro regime + rank_x interactions | — |
| `modelFactory/config.py` | 🔧 `include_macro_regime` | — |
| `modelFactory/tabular_baseline.py` | 🔧 régularisation + class_weight | — |
| `modelFactory/global_ranking.py` | — | 🔧 multi-horizons |
| `modelFactory/cross_sectional.py` | — | 🔧 multi-rank columns |
| `modelFactory/predictor.py` | — | 🔧 multi-horizon inference |
| `modelFactory/decision.py` | — | 🔧 TernaryDecisionPolicy |
| `modelFactory/cli.py` | 🔧 `--include-macro-regime` | — |
| `ihm/pages/pipeline.py` | 🔧 checkbox macro regime | — |
| `config.yaml` | 🔧 `macro_regime`, `regularization` | 🔧 `multi_horizons` |

---

## 🔵 Plan d'Action Détaillé — Long Terme

### Action 9 — Décomposition du Global en 3 sous-rangs
**Fichier** : `modelFactory/global_ranking.py`

**🎯 Pourquoi ?**
> Un `global_rank` unique est un « fourre-tout » : il mélange momentum, mean-reversion et volatilité en un seul score. Un titre peut être bien classé parce qu'il a un bon momentum... ou parce qu'il est anormalement peu volatile. Le modèle per-symbol ne peut pas distinguer la raison du classement.
>
> En décomposant en 3 sous-modèles spécialisés (`rank_momentum` : performance relative, `rank_mean_reversion` : sur-achat/vente relatif, `rank_volatility` : profil de risque), le per-symbol reçoit 3 signaux orthogonaux qu'il peut pondérer différemment selon le régime. Un modèle local pourrait apprendre à privilégier le momentum en bull market et la mean-reversion en range.

### Action 10 — Ensembling LightGBM + CatBoost
**Fichier** : `modelFactory/tabular_baseline.py`

**🎯 Pourquoi ?**
> LightGBM et CatBoost ont des biais différents (gestion des catégorielles, splitting strategy). Leur moyenne simple réduit la variance sans augmenter le biais — c'est le principe de l'ensembling. En pratique, un ensemble LightGBM+CatBoost surpasse systématiquement le meilleur des deux seul de 0.01-0.02 de F1 sur des tâches de classification financière. Coût : x2 en temps d'entraînement par symbole, mais les deux modèles sont déjà entraînés aujourd'hui (juste pas moyennés).

### Action 11 — Short Interest (FINRA)
**Fichier** : `modelFactory/short_interest.py` (nouveau)

**🎯 Pourquoi ?**
> Le short interest est un signal contraire fort : un titre avec >20% de float shorté est vulnérable à un short squeeze (hausse violente), ce qu'aucune feature technique ne peut anticiper. La donnée FINRA est gratuite (fichier TXT mensuel), légère à scraper, et apporte une information orthogonal à tout le feature set actuel. 3 features (`short_interest_pct_float`, `change_14d`, `days_to_cover`) suffisent.

### Action 12 — Estimation d'Incertitude (Variance intra-ensemble)
**Fichier** : `modelFactory/uncertainty.py` (nouveau)

**🎯 Pourquoi ?**
> Aujourd'hui, une prédiction `proba_long=0.65` est traitée de la même façon qu'elle vienne d'un consensus fort (LightGBM et CatBoost d'accord) ou d'un désaccord (l'un dit long, l'autre dit flat). La variance des probabilités entre modèles est un proxy de l'incertitude : les trades à haute variance sont moins fiables et devraient être filtrés ou sous-pondérés. C'est un filtre de qualité gratuit qui réduit le bruit sans réduire le nombre de trades.

### Action 13 — Pondération Dynamique du Capital
**Fichier** : `risk_management/position_sizing.py`

**🎯 Pourquoi ?**
> Actuellement, tous les trades ont le même poids (equal-weight ou risk-parity). Mais la confiance du modèle varie : un `proba_long=0.85` calibré devrait recevoir plus de capital qu'un `proba_long=0.55`. La pondération dynamique alloue le capital proportionnellement à la confiance calibrée (probabilité - 0.5) × (1 - variance), ce qui améliore le ratio de Sharpe sans changer le nombre de trades. C'est le dernier kilomètre de la chaîne ML → exécution.
