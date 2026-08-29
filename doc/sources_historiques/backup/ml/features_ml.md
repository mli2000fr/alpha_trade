# 📊 Features ML — Documentation des paramètres

> Fichier de référence listant chaque flag `--include-*` / `--target-*`, son rôle, les features concernées, et le statut de propagation dans les 4 modes d'entraînement.
>
> Dernière mise à jour : 2026-08-14 (vérifié contre le code source)

---

## 1. `--include-short-score`

### Rôle
Ajoute le score baissier composite du screener (`short_score`) comme feature ML indépendante.

### Features concernées
| # | Feature | Source DB | Valeur par défaut |
|:--|:--------|:----------|:-------------------|
| 1 | `selector_short_score` | `stock_scores_history.short_score` | `0.0` |

### Data loading par mode

| Mode | Point de chargement | Statut |
|:-----|:--------------------|:-------|
| **Per-symbol** | `orchestrator.py:397` — `load_symbol_selector_context(engine, symbol, ...)` | ✅ Correct |
| **Global model** | `global_model.py:404` — `load_symbols_selector_context(engine, symbols, ...)` | ✅ Correct |
| **Global Ranking** | `global_ranking.py:873` — `load_symbols_selector_context(engine, symbols, ...)` | ✅ Correct |
| **Per-sector** | `trainer_sector.py:789` — `_load_selector_for_symbols(symbols, engine, cfg)` | 🔴 **Bug corrigé 2026-08-08** |

### Détail du bug (corrigé)
`_load_selector_for_symbols` appelait `load_symbol_selector_context(sym, engine, cfg)` avec les arguments dans le mauvais ordre. L'`except Exception: return None` masquait le crash → `selector_df` toujours `None` → `selector_short_score` = `0.0` partout.  
**Fix** : utilise `load_symbols_selector_context(engine, symbols, end_date=..., start_date=...)`.

---

## 2. `--include-screener-scores`

### Rôle
Ajoute l'ensemble des scores du screener PIT-safe (trend, VCP, final_score, etc.) comme features ML.

### Features concernées (22)
| # | Feature | Source DB |
|:--|:--------|:----------|
| 1 | `selector_trend_score` | `stock_scores_history.trend_score` |
| 2 | `selector_vcp_score` | `stock_scores_history.vcp_score` |
| 3 | `selector_final_score` | `stock_scores_history.final_score` |
| 4 | `selector_raw_final_score` | `stock_scores_history.raw_final_score` |
| 5 | `selector_selection_rank` | `stock_scores_history.selection_rank` |
| 6 | `selector_atr_pct_20` | `stock_scores_history.atr_pct_20` |
| 7 | `selector_weekly_trend_score` | `stock_scores_history.weekly_trend_score` |
| 8 | `selector_high_52w_proximity` | `stock_scores_history.high_52w_proximity` |
| 9 | `selector_volatility_ratio` | `stock_scores_history.volatility_ratio` |
| 10 | `selector_earnings_blackout` | `stock_scores_history.earnings_blackout` |
| 11 | `selector_mode_sector_neutralized` | `stock_scores_history.selector_signal_mode` |
| 12 | `selector_market_cap` | `stock_scores_history.market_cap` |
| 13 | `selector_beta_126` | `stock_scores_history.beta_126` |
| 14 | `selector_spread_bps` | `stock_scores_history.spread_bps` |
| 15 | `selector_days_to_earnings` | `stock_scores_history.days_to_earnings` |
| 16 | `selector_normalized_total_score` | `stock_scores_history.normalized_total_score` |
| 17 | `selector_normalized_rsi` | `stock_scores_history.normalized_rsi` |
| 18 | `selector_total_score_neutralized` | `stock_scores_history.total_score_neutralized` |
| 19 | `selector_relative_strength_index_neutralized` | `stock_scores_history.relative_strength_index_neutralized` |
| 20 | `selector_trend_vcp_component` | `stock_scores_history.trend_vcp_component` |
| 21 | `selector_total_score_component` | `stock_scores_history.total_score_component` |
| 22 | `selector_rsi_component` | `stock_scores_history.rsi_component` |

### Data loading par mode

| Mode | Point de chargement | Statut |
|:-----|:--------------------|:-------|
| **Per-symbol** | `orchestrator.py:397` — `load_symbol_selector_context(engine, symbol, ...)` | ✅ Correct |
| **Global model** | `global_model.py:404` — `load_symbols_selector_context(engine, symbols, ...)` | ✅ Correct |
| **Global Ranking** | `global_ranking.py:873` — `load_symbols_selector_context(engine, symbols, ...)` | ✅ Correct |
| **Per-sector** | `trainer_sector.py:789` — `_load_selector_for_symbols(symbols, engine, cfg)` | 🔴 **Bug corrigé 2026-08-08** (même bug que `--include-short-score`) |

---

## 3. `--include-sentiment`

### Rôle
Ajoute les features de sentiment quotidiennes (news, confiance, événements majeurs).

### Features concernées (5)
| # | Feature | Source |
|:--|:--------|:-------|
| 1 | `sentiment_net_mean_1d` | `ticker_daily_sentiment_features.sentiment_net_mean_1d` |
| 2 | `sentiment_confidence_mean_1d` | `ticker_daily_sentiment_features.sentiment_confidence_mean_1d` |
| 3 | `news_count_log` | `log1p(ticker_daily_sentiment_features.news_count_1d)` — calculé |
| 4 | `major_event_flag` | `ticker_daily_sentiment_features.major_event_flag` |
| 5 | `sentiment_intensity` | `net × confiance × news_count_log` — calculé |

### Data loading par mode

| Mode | Point de chargement | Statut |
|:-----|:--------------------|:-------|
| **Per-symbol** | `orchestrator.py:389` — `load_symbol_sentiment(engine, symbol, ...)` | ✅ Correct |
| **Global model** | `global_model.py:395` — `load_symbols_sentiment(engine, symbols, ...)` | ✅ Correct |
| **Per-sector** | `trainer_sector.py:784` — `_load_sentiment_for_symbols(symbols, engine, cfg)` | 🔴 **Bug corrigé 2026-08-08** |
| **Global Ranking** | `global_ranking.py:868` — `sentiment_df = None` | ⚪ Intentionnellement désactivé |

### Détail du bug (corrigé)
Même pattern que `_load_selector_for_symbols` : `load_symbol_sentiment(sym, engine, cfg.data)` → arguments inversés → `except Exception: return None`.  
**Fix** : utilise `load_symbols_sentiment(engine, symbols, end_date=..., start_date=...)`.

### Note Global Ranking
Le commentaire dans `global_ranking.py:869` indique : « sentiment → per-symbol uniquement ; le global ranking ignore ces features (sparse, noyées dans 177 features). On saute le chargement pour gagner du temps. »

---

## 4. `--target-excess-vs-spy`

### Rôle
Centre la distribution de la target en soustrayant le rendement du SPY :  
$target = \frac{return_{symbol} - return_{SPY}}{\sigma_{20j}}$

Réduit le biais directionnel long/short dans la target de régression.

### Features concernées
Aucune feature ajoutée — modifie uniquement la **target** (`future_return_h{horizon}` et `target_h{horizon}`).

### Data loading par mode

| Mode | Point d'application | benchmark_close présent ? | Statut |
|:-----|:--------------------|:--------------------------|:-------|
| **Per-symbol** | `dataset.py:820` — `build_target(excess_vs_spy=...)` | ✅ via `compute_features(benchmark_df=...)` | ✅ Correct |
| **Per-sector** | `dataset.py:803` — `build_multi_horizon_targets(excess_vs_spy=...)` | ✅ via `compute_features(benchmark_df=...)` | ✅ Correct |
| **Global model** | `global_model.py:155` — `build_target(excess_vs_spy=...)` | ✅ via `compute_features(benchmark_df=...)` | ✅ Correct |
| **Global Ranking** | N/A | ⚪ Non applicable (ranking cross-sectionnel) | Par design |

### Mécanisme (`features.py:1342`)
```python
if excess_vs_spy and "benchmark_close" in df.columns:
    spy_return = spy_close.shift(-horizon) / spy_close - 1.0
    target = target - spy_return
```

---

## 5. `--include-macro-vix`

### Rôle
Ajoute les features de volatilité implicite S&P 500 (VIX).

### Features concernées (2)
| # | Feature | Source |
|:--|:--------|:-------|
| 1 | `vix_close` | `stock_macro_indicators_daily.vix` (forward-fillé) |
| 2 | `vix_momentum_5j` | `pct_change(5)` sur `vix_close` — calculé |

### Data loading par mode

| Mode | Point de chargement | Statut |
|:-----|:--------------------|:-------|
| **Per-symbol** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Per-sector** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Global model** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Global Ranking** | ⚪ Blacklisté — exclus du ranking cross-sectionnel | Par design |

### Architecture
Contrairement aux flags `--include-sentiment` / `--include-screener-scores`, les features macro sont **auto-chargées** par `_merge_macro_features()` qui crée sa propre connexion DB. Aucune dépendance aux fonctions `_load_*` de l'orchestrateur → immunisé contre les bugs d'inversion d'arguments.

---

## 6. `--include-macro-vxn`

### Rôle
Ajoute les features de volatilité implicite NASDAQ-100 (VXN) et son spread vs VIX.

### Features concernées (2)
| # | Feature | Source |
|:--|:--------|:-------|
| 1 | `vxn_close` | `stock_macro_indicators_daily.vxn` (forward-fillé) |
| 2 | `vxn_spread_vix` | `vxn_close - vix_close` — calculé (différentiel NASDAQ vs S&P) |

### Data loading par mode

| Mode | Point de chargement | Statut |
|:-----|:--------------------|:-------|
| **Per-symbol** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Per-sector** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Global model** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Global Ranking** | ⚪ Blacklisté — exclus du ranking cross-sectionnel | Par design |

### Architecture
Identique à `--include-macro-vix` : auto-chargé par `_merge_macro_features()`, immunisé contre les bugs des `_load_*`.

---

## 7. `--include-macro-vix3m`

### Rôle
Ajoute les features de term structure VIX (VIX3M) : ratio VIX/VIX3M et indicateur de backwardation.

### Features concernées (3)
| # | Feature | Source |
|:--|:--------|:-------|
| 1 | `vix3m_close` | `stock_macro_indicators_daily.vix3m` (forward-fillé) |
| 2 | `vix_term_structure_ratio` | `vix / vix3m` — ratio < 1 = contango, > 1 = backwardation |
| 3 | `vix_backwardation` | `vix > vix3m` — flag binaire (1.0 = backwardation, 0.0 = contango) |

> ⚠️ Ce flag nécessite aussi la colonne `vix` dans `stock_macro_indicators_daily`. Elle est chargée automatiquement par `_merge_macro_features()`, même si `--include-macro-vix` n'est pas activé.

### Data loading par mode

| Mode | Point de chargement | Statut |
|:-----|:--------------------|:-------|
| **Per-symbol** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Per-sector** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Global model** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Global Ranking** | ⚪ Blacklisté — exclus du ranking cross-sectionnel | Par design |

### Architecture
Identique à `--include-macro-vix` : auto-chargé par `_merge_macro_features()`, immunisé contre les bugs des `_load_*`.

---

## 8. `--include-macro-move`

### Rôle
Ajoute la feature de volatilité obligataire ICE BofA MOVE (équivalent VIX pour le marché des taux).

### Features concernées (1)
| # | Feature | Source |
|:--|:--------|:-------|
| 1 | `move_close` | `stock_macro_indicators_daily.move` (forward-fillé) |

### Data loading par mode

| Mode | Point de chargement | Statut |
|:-----|:--------------------|:-------|
| **Per-symbol** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Per-sector** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Global model** | `compute_features()` → `_merge_macro_features()` (auto, DB directe) | ✅ Correct |
| **Global Ranking** | ⚪ Blacklisté — exclus du ranking cross-sectionnel | Par design |

### Architecture
Identique aux autres flags macro (`--include-macro-vix`, `--include-macro-vxn`, `--include-macro-vix3m`) : auto-chargé par `_merge_macro_features()`, immunisé contre les bugs des `_load_*`.

---

## 9. `--include-fundamentals`

### Rôle
Ajoute les features fondamentales EODHD (valuation, profitabilité, croissance, santé financière) depuis `stock_fundamentals_daily`. Les données sont forward-fillées entre chaque fetch (trimestriel).

### Features concernées (22)
| # | Feature | Catégorie | Source DB |
|:--|:--------|:----------|:----------|
| 1 | `fund_pe_ratio` | Valuation | `stock_fundamentals_daily.pe_ratio` |
| 2 | `fund_forward_pe` | Valuation | `stock_fundamentals_daily.forward_pe` |
| 3 | `fund_peg_ratio` | Valuation | `stock_fundamentals_daily.peg_ratio` |
| 4 | `fund_pb_ratio` | Valuation | `stock_fundamentals_daily.pb_ratio` |
| 5 | `fund_ps_ratio` | Valuation | `stock_fundamentals_daily.ps_ratio` |
| 6 | `fund_ev_to_ebitda` | Valuation | `stock_fundamentals_daily.ev_to_ebitda` |
| 7 | `fund_roe` | Profitabilité | `stock_fundamentals_daily.roe` |
| 8 | `fund_roa` | Profitabilité | `stock_fundamentals_daily.roa` |
| 9 | `fund_net_margin` | Profitabilité | `stock_fundamentals_daily.net_margin` |
| 10 | `fund_operating_margin` | Profitabilité | `stock_fundamentals_daily.operating_margin` |
| 11 | `fund_gross_margin` | Profitabilité | `stock_fundamentals_daily.gross_margin` |
| 12 | `fund_eps_growth_yoy` | Croissance | `stock_fundamentals_daily.eps_growth_yoy` |
| 13 | `fund_revenue_growth_yoy` | Croissance | `stock_fundamentals_daily.revenue_growth_yoy` |
| 14 | `fund_debt_to_equity` | Santé financière | `stock_fundamentals_daily.debt_to_equity` |
| 15 | `fund_current_ratio` | Santé financière | `stock_fundamentals_daily.current_ratio` |
| 16 | `fund_dividend_yield` | Rendement | `stock_fundamentals_daily.dividend_yield` |
| 17 | `fund_market_cap_log` | Market | `log(market_cap)` — dérivé |
| 18 | `fund_beta` | Market | `stock_fundamentals_daily.beta` |
| 19 | `fund_eps_estimate_current` | Estimations | `stock_fundamentals_daily.eps_estimate_current` |
| 20 | `fund_eps_estimate_next` | Estimations | `stock_fundamentals_daily.eps_estimate_next` |
| 21 | `fund_eps_to_price` | Dérivé | `eps / price` — calculé |
| 22 | `fund_estimate_revision` | Dérivé | `(eps_next - eps_current) / |eps_current|` — calculé |

### Data loading par mode

| Mode | Point de chargement | Statut |
|:-----|:--------------------|:-------|
| **Per-symbol** | `orchestrator.py:744` — `load_fundamentals_from_db()` → cache → `fundamental_df` | ✅ Correct |
| **Per-sector** | `trainer_sector.py:848` — `_load_fundamentals_for_symbols()` → `fundamental_df` | ✅ Correct |
| **Global Ranking** | `compute_features()` → `merge_fundamentals()` → fallback auto DB | ✅ Correct |
| **Global model** | `_get_global_feature_columns()` n'inclut **pas** les fondamentales | ⚪ Par design |

### Architecture
Double mécanisme :
1. **Cache orchestrateur** (per-symbol/per-sector) : `fundamental_df` pré-chargé, passé à `compute_features()` → `merge_fundamentals()`
2. **Fallback auto** (Global Ranking) : si `fundamental_df` est `None`, `merge_fundamentals()` charge directement depuis `stock_fundamentals_daily` via `get_sqlalchemy_engine()`

> Note : le label IHM « Global Model uniquement » était trompeur — corrigé le 2026-08-08. Les fondamentales fonctionnent en per-symbol, per-sector et Global Ranking. Seul le **Global Model** (cross-symbol) les exclut car ce sont des features par titre.

---

## 10. `--include-factors`

### Rôle
Ajoute les expositions factorielles CAPM calculées par rolling regression 252j des rendements du titre contre le benchmark (SPY).

### Features concernées (4)
| # | Feature | Méthode | Valeur par défaut |
|:--|:--------|:--------|:-------------------|
| 1 | `beta_252` | Rolling CAPM β (252j) vs SPY | `1.0` |
| 2 | `alpha_252` | Rolling CAPM α annualisé (252j) | `0.0` |
| 3 | `r_squared_252` | R² de la régression (252j) | `0.0` |
| 4 | `momentum_252_vs_market` | Retour 252j stock − retour 252j SPY | `0.0` |

### Data loading par mode

| Mode | Point de calcul | benchmark_df requis ? | Statut |
|:-----|:----------------|:----------------------|:-------|
| **Per-symbol** | `compute_features()` → `compute_factor_features(df, benchmark_df=...)` | ✅ si `feature_set=expert` | ✅ Correct |
| **Per-sector** | `compute_features()` → `compute_factor_features(df, benchmark_df=...)` | ✅ chargé par `_load_benchmark()` | ✅ Correct |
| **Global Ranking** | `compute_features()` → `compute_factor_features(df, benchmark_df=...)` | ✅ | ⚠️ Partiel (voir note) |
| **Global model** | `_get_global_feature_columns()` n'inclut **pas** les facteurs | N/A | ⚪ Par design |

### Architecture
Calcul entièrement **in-memory** : rolling regression 252j des `daily_return` stock vs benchmark (SPY). Aucune DB externe, aucune dépendance aux fonctions `_load_*`. Si `benchmark_df` est absent → valeurs par défaut.

### Note Global Ranking
Seul `momentum_252_vs_market` est conservé. `beta_252`, `alpha_252`, `r_squared_252` sont blacklistés (`global_ranking.py:326`) — importance 0.0 sur tous les horizons (batch 2026-07-28).

---

## 11. `--include-macro-regime`

### Rôle
Ajoute les indicateurs de régime macro : tendance long terme du SPY (SMA 200) et z-score du VIX.

### Features concernées (2)
| # | Feature | Source | Défaut si absent |
|:--|:--------|:-------|:------------------|
| 1 | `SPY_SMA_200_slope` | `benchmark_df.close` → SMA 200 → pente 20j normalisée | `0.0` |
| 2 | `VIX_zscore` | `vix_close` → z-score rolling 252j (min 60j) | `0.0` |

> ⚠️ `VIX_zscore` = `0.0` si `--include-macro-vix` n'est **pas** activé. Les deux flags sont complémentaires.

### Data loading par mode

| Mode | Point de calcul | Statut |
|:-----|:----------------|:-------|
| **Per-symbol** | `compute_features()` → calcul in-memory depuis `benchmark_df` + `vix_close` | ✅ Correct |
| **Per-sector** | `compute_features()` → calcul in-memory depuis `benchmark_df` + `vix_close` | ✅ Correct |
| **Global model** | `_prepare_global_symbol_frame()` **ne passe pas** `include_macro_regime` | ⚪ Par design |
| **Global Ranking** | Blacklistés (`SPY_SMA_200_slope`, `VIX_zscore` — communs ∀ symboles) | ⚪ Par design |

### Architecture
Calcul entièrement **in-memory** :
- `SPY_SMA_200_slope` : dérivé de `benchmark_df` (déjà chargé pour `feature_set=expert`)
- `VIX_zscore` : dérivé de `vix_close` (déjà présent si `--include-macro-vix` activé)

Aucune DB externe, aucune dépendance aux fonctions `_load_*`.

---

## 12. `--include-score-components`

### Rôle
Ajoute les composants de score issus de `stock_scores_history` (sentiment, idiosyncratique, macro, quant). Signal orthogonal aux features techniques.

### Features concernées (9)
| # | Feature | Source DB |
|:--|:--------|:----------|
| 1 | `sentiment_net_agg` | `stock_scores_history.sentiment_net_agg` |
| 2 | `company_idio_score` | `stock_scores_history.company_idio_score` |
| 3 | `macro_regime_score` | `stock_scores_history.macro_regime_score` |
| 4 | `quant_component` | `stock_scores_history.quant_component` |
| 5 | `company_idio_signal_norm` | `stock_scores_history.company_idio_signal_norm` |
| 6 | `macro_regime_signal_norm` | `stock_scores_history.macro_regime_signal_norm` |
| 7 | `company_idio_component` | `stock_scores_history.company_idio_component` |
| 8 | `macro_regime_component` | `stock_scores_history.macro_regime_component` |
| 9 | `sector_impact_agg` | `stock_scores_history.sector_impact_agg` |

### Data loading par mode

| Mode | Statut |
|:-----|:-------|
| **Per-symbol** | ⚪ Désactivé par défaut (`include_score_components=False` dans orchestrateur) |
| **Per-sector** | ✅ **Corrigé 2026-08-08** |
| **Global model** | ✅ **Corrigé 2026-08-08** |
| **Global Ranking** | ✅ **Corrigé 2026-08-08** |

### Détail du bug (corrigé)
Les 9 colonnes existaient dans `stock_scores_history` mais n'étaient **pas** listées dans `SELECTOR_HISTORY_CONTEXT_COLUMNS` (`data_loader.py`). `load_symbols_selector_context` ne les chargeait donc pas. `compute_features` ne les peuplait ni ne les défautait → **KeyError** au `model.fit()`.

**Fix (2026-08-08)** :
1. ✅ Ajout des 9 colonnes dans `SELECTOR_HISTORY_CONTEXT_COLUMNS` (`data_loader.py`)
2. ✅ Ajout des mappings identité dans `_SELECTOR_CONTEXT_SOURCE_TO_FEATURE` (`features.py`)
3. ✅ Ajout des valeurs par défaut (`0.0`) dans `_SELECTOR_CONTEXT_DEFAULTS` (`features.py`)
4. ✅ Ajout du paramètre `include_score_components` à `compute_features()` + mise à jour des 4 callers (`dataset.py`, `global_model.py`, `global_ranking.py`, `predictor.py`)

---

## 13. `--target-skip-vol-scaling`

### Rôle
Désactive la division de la target par la volatilité 20j en mode `regression`. Expérience T1 : tester si le vol-scaling amplifie le bruit.

Target normale : $target = \frac{return_{symbol} - return_{SPY}}{\sigma_{20j}}$  
Avec le flag : $target = return_{symbol} - return_{SPY}$ (forward return brut)

### Features concernées
Aucune feature ajoutée — modifie uniquement la **target** de régression.

### Data loading par mode

| Mode | Point d'application | Statut |
|:-----|:--------------------|:-------|
| **Per-symbol** | `dataset.py:820` — `build_target(skip_vol_scaling=...)` | ✅ Correct |
| **Per-sector** | `dataset.py:803` — `build_multi_horizon_targets(skip_vol_scaling=...)` | ✅ Correct |
| **Global model** | `global_model.py:155` — `build_target(skip_vol_scaling=...)` | ✅ Correct |
| **Global Ranking** | N/A (target pipeline différente) | ⚪ N/A |

### Mécanisme (`features.py:1367`)
```python
if not skip_vol_scaling and horizon >= 5:
    rolling_vol = close.pct_change().rolling(20).std()
    target = target / rolling_vol
```

> Note : le vol-scaling n'est appliqué que pour les horizons ≥ 5j. Les horizons courts (H3) ne sont jamais vol-scalés.

---

## 14. `--target-intra-sector-rank`

### Rôle
Convertit la target en rang percentile $[0,1]$ intra-secteur par date. Le modèle apprend à **classer** les titres dans leur secteur plutôt qu'à prédire une magnitude. Expérience T2 (2026-08-05).

### Features concernées
Aucune — modifie uniquement la **target** après `compute_features()`, avant le split chronologique.

### Data loading par mode

| Mode | Statut |
|:-----|:-------|
| **Per-sector** | ✅ Appliqué dans `_prepare_sector_data` (`trainer_sector.py:167`) |
| **Per-symbol** | ⚪ Non applicable (pas de notion de secteur) |
| **Global model** | ⚪ Non applicable |
| **Global Ranking** | ⚪ Non applicable (déjà un ranking cross-sectionnel) |

### Mécanisme (`trainer_sector.py:167-181`)
```python
if cfg.data.target_intra_sector_rank:
    for h in cfg.data.forecast_horizons:
        prepared[f"target_h{h}"] = prepared.groupby("date")[f"target_h{h}"].rank(pct=True)
```

> Note : PIT-safe car le `groupby("date")` garantit qu'aucune information future n'est utilisée pour le ranking d'une date donnée.

---

## 15. `--target-ternary-intra-sector`

### Rôle
Convertit la target continue (regression) en labels ternaires LONG(+1)/FLAT(0)/SHORT(-1) par quantiles intra-secteur. Les seuils sont calculés sur le **train uniquement** (PIT-safe). Le modèle passe en mode classification ternaire. Expérience T3 (2026-08-05).

### Features concernées
Aucune — modifie la target et le `target_mode` après split chronologique.

### Data loading par mode

| Mode | Statut |
|:-----|:-------|
| **Per-sector** | ✅ Appliqué dans `_train_sector_models` (`trainer_sector.py:386`) |
| **Per-symbol** | ⚪ Non applicable |
| **Global model** | ⚪ Non applicable |
| **Global Ranking** | ⚪ Non applicable |

### Mécanisme (`trainer_sector.py:386-424`)
```python
_q_lo = cfg.data.target_ternary_quantile      # défaut 0.30 → bottom 30% = SHORT
_q_hi = 1.0 - _q_lo                            # défaut 0.70 → top 30% = LONG
_train_lo = train_df["target"].quantile(_q_lo)
_train_hi = train_df["target"].quantile(_q_hi)
# target > _train_hi → +1 (LONG), target < _train_lo → -1 (SHORT), sinon 0 (FLAT)
```

> ⚙️ Config : `--target-ternary-quantile` (défaut `0.30`) contrôle le seuil. Après conversion, `cfg.data.target_mode` devient `"ternary"`.

## 16. `--include-volume-features`

### Rôle
Ajoute le profil volume/liquidité (10 features opt-in, P3-5). Source : barres OHLCV uniquement, calcul in-memory — aucune DB externe.

### Features concernées (10)

| # | Feature | Calcul |
|:--|:--------|:-------|
| 1 | `dollar_volume_log_20` | log(moyenne 20j du dollar volume) |
| 2 | `dollar_volume_trend_20_60` | moyenne 20j / moyenne 60j − 1 |
| 3 | `amihud_illiq_20` | moyenne 20j de \|retour\| / dollar volume |
| 4 | `volume_std_ratio_20` | std 20j / moyenne 20j du volume |
| 5 | `up_volume_ratio_20` | part du volume des jours haussiers (20j) |
| 6 | `volume_price_corr_20` | corrélation 20j volume × retour |
| 7 | `obv_slope_20` | pente 20j de l'OBV normalisée |
| 8 | `dollar_volume_zscore_20` | z-score 20j du dollar volume |
| 9 | `high_low_range_20` | moyenne 20j de (high−low)/close |
| 10 | `volume_skew_20` | skew 20j du volume |

### Data loading par mode

| Mode | Point de calcul | Statut |
|:-----|:----------------|:-------|
| **Per-symbol** | `compute_features()` (`features.py`) via `include_volume_features` | ✅ Correct |
| **Per-sector** | `trainer_sector.py:212` → `compute_features()` | ✅ Correct |
| **Global model** | `global_model.py:140` → `compute_features()` | ✅ Correct |
| **Global Ranking** | `global_ranking.py:260/291` → `compute_features()` | ✅ Correct |

### Historique (P3-5, 2026-08-14)

- **B40** (B4+volume, RMSE) : IC 0.0178 (−12 % vs B4) — aide H3 (+40 %) mais détruit H10-H20 en RMSE.
- **B41** (B25+volume, YetiRank) : **IC 0.0260 (+7.9 %), IR 1.55 record** — 5/5 horizons gagnés vs B25.
- **B42** (B20+volume, sans CAPM) : IC 0.0250 ; **H10 = 0.0282 (IR 1.60) = record H10 de la série**. Volume seul > CAPM seul.

---

## 🏛️ Gouvernance & Contrôle

> Flags de pilotage de l'entraînement et de la sélection des modèles. N'affectent ni les features ni la target.

### `--select-champion`
Active la sélection automatique du champion parmi les modèles éligibles (LSTM, LightGBM, CatBoost, Global). Déclenche `select_champion()` dans `champion_selection.py`.

### `--walkforward` / `--no-walkforward`
Active/désactive l'évaluation walk-forward avant l'entraînement final. Actif par défaut (Phase 4.2.g).

### `--compare-lightgbm`
Ajoute LightGBM comme challenger (baseline tabulaire).

### `--enable-catboost`
Ajoute CatBoost comme challenger (baseline tabulaire).

### `--enable-global-model`
Ajoute le Global Model (cross-symbol) comme challenger.

### `--enable-global-stacking`
Utilise la prédiction du Global Model comme feature (Approche 2 — Stacking).

### `--default-champion`
Modèle servi par défaut si aucun champion n'a été sélectionné. Valeurs : `lstm_attention`, `lightgbm`, `catboost`, `global_model`.

### `--ml-mode`
Stratégie d'entraînement : `rebuild-all` (tout réentraîner), `rebuild-missing` (seulement les symboles sans `config.json`), `refresh-stale` (symboles dont le contrat de features ou la date de début a changé).

### `--training-mode`
Mode d'entraînement : `per_symbol` (1 modèle par symbole) ou `per_sector` (1 modèle par secteur GICS).

### `--calibration-method` / `--calibration-min-samples` / `--calibration-max-iter`
Calibration des probabilités : `none` ou `platt` (Platt scaling). Min samples et max itérations pour la régression logistique.

### `--champion-min-runs` / `--champion-min-days`
Quarantaine champion : nombre minimum de runs walk-forward / jours d'observation avant qu'un nouveau champion soit servi.

### `--accelerator`
Backend d'accélération : `auto`, `cpu`, `gpu`.

### `--max-workers`
Nombre de workers parallèles pour l'entraînement per-symbol.

### `--feature-set`
Ensemble de features : `v1` (base OHLCV) ou `expert` (OHLCV + momentum multi-horizons + régime + interactions).

### `--forecast-horizons`
Horizons de prédiction : ex. `3,5,10,15,20`. L'horizon max détermine `forecast_horizon`.

### `--benchmark-symbol`
Symbole benchmark pour les features de marché (défaut : `SPY`).

### `--symbol-source`
Source des symboles : `tradable-universe`, `ticket-recherche`, etc.

### `--target-mode`
Mode de target : `regression`, `binary`, `ternary`, `swing_cash`.

### `--target-up-threshold` / `--target-down-threshold`
Seuils de rendement futur pour les modes `binary`/`ternary`/`swing_cash`.

### `--decision-threshold`
Seuil de probabilité pour émettre un signal long en classification.

### `--optimize-thresholds`
Recherche automatique du meilleur seuil de décision (post-entraînement). Teste plusieurs candidats et sélectionne celui qui maximise les métriques.

### `--optimize-target`
Optimisation automatique des paramètres de target (horizon, seuils up/down, triple barrière). Teste plusieurs combinaisons et sélectionne celle qui maximise les métriques sur la validation.

### `--wf-min-train-size` / `--wf-val-size` / `--wf-test-size` / `--wf-step-size` / `--wf-max-splits`
Configuration des splits walk-forward (taille train/val/test, pas, nombre max de splits).

### `--lgbm-*` / `--catboost-*`
Hyperparamètres des baselines LightGBM et CatBoost.

---

## 17. `--enable-cross-sectional`

### Rôle
Ajoute les features cross-sectionnelles : rangs percentiles intra-date, agrégats sectoriels, neutralisation sectorielle, et z-score sectoriel. Permet au modèle de positionner un titre relativement à son univers.

### Features concernées (~49)
| Famille | Nb | Exemples |
|:--------|:--|:---------|
| **Rangs percentiles** | 8 | `ret_20_rank`, `ret_60_rank`, `volatility_20_rank`, `dollar_volume_20_rank`, `relative_strength_20_rank`, `relative_strength_60_rank`, `volume_ratio_20_rank_xs`, `range_position_20_rank` |
| **Sectorielles** | 8 | `sector_ret_20`, `sector_ret_60`, `sector_vol_20`, `sector_relative_strength_20`, `sector_dollar_volume_20`, `sector_symbol_count`, `stock_vs_sector_ret_20`, `stock_vs_sector_ret_60` |
| **Sector-neutral** | ~16 | `momentum_20_sector_neutral`, `fund_pe_ratio_sector_neutral`... (médiane secteur soustraite) |
| **Sector z-score** | ~13 | `fund_pe_ratio_sector_zscore`... (normalisation (valeur−médiane)/MAD par secteur) |
| **Global rank** (si stacking) | 4 | `global_rank_3`, `global_rank_5`, `global_rank_10`, `global_rank` |

### Data loading par mode

| Mode | Point de calcul | Statut |
|:-----|:----------------|:-------|
| **Per-symbol** | `orchestrator.py` — `build_cross_sectional_features_from_db()` → cache global | ✅ Correct |
| **Per-sector** | `trainer_sector.py:115` — cache XS construit une fois dans `run_per_sector_batch` | ✅ **Corrigé 2026-08-04** |
| **Global model** | `global_model.py` — `build_cross_sectional_features()` sur `universe_df` | ✅ Correct |
| **Global Ranking** | `global_ranking.py` — `build_cross_sectional_features()` | ✅ Correct |

### Architecture
Les features XS nécessitent les barres de **tous** les symboles pour calculer rangs et médianes. Deux mécanismes :
- **Cache global** (per-symbol/per-sector) : `build_cross_sectional_features_from_db()` charge tout l'univers une fois
- **Calcul direct** (global model/ranking) : `build_cross_sectional_features()` sur `universe_df` déjà en mémoire

> Historique : en per-sector, avant le fix Action 1.1 (2026-08-04), `universe_df=None` → toutes les colonnes XS étaient remplies de valeurs neutres (0.5/0.0) → ~30 features inactives.

---

## 📋 Résumé des statuts

| Paramètre | Features | Per-symbol | Per-sector | Global Model | Global Ranking | Bug ? |
|:----------|---------:|:-----------|:-----------|:-------------|:---------------|:------|
| `--include-short-score` | 1 | ✅ | 🔴→✅ fix | ✅ | ✅ | Corrigé |
| `--include-screener-scores` | 22 | ✅ | 🔴→✅ fix | ✅ | ✅ | Corrigé |
| `--include-sentiment` | 5 | ✅ | 🔴→✅ fix | ✅ | ⚪ désactivé | Corrigé |
| `--target-excess-vs-spy` | 0 (target) | ✅ | ✅ | ✅ | ⚪ N/A | Aucun |
| `--target-skip-vol-scaling` | 0 (target) | ✅ | ✅ | ✅ | ⚪ N/A | Aucun |
| `--target-intra-sector-rank` | 0 (target) | ⚪ N/A | ✅ | ⚪ N/A | ⚪ N/A | Aucun |
| `--target-ternary-intra-sector` | 0 (target) | ⚪ N/A | ✅ | ⚪ N/A | ⚪ N/A | Aucun |
| `--enable-cross-sectional` | ~49 | ✅ | ✅ fix | ✅ | ✅ | Corrigé |
| `--include-macro-vix` | 2 | ✅ | ✅ | ✅ | ⚪ blacklisté | Aucun |
| `--include-macro-vxn` | 2 | ✅ | ✅ | ✅ | ⚪ blacklisté | Aucun |
| `--include-macro-vix3m` | 3 | ✅ | ✅ | ✅ | ⚪ blacklisté | Aucun |
| `--include-macro-move` | 1 | ✅ | ✅ | ✅ | ⚪ blacklisté | Aucun |
| `--include-fundamentals` | 22 | ✅ | ✅ | ⚪ exclu | ✅ | Aucun |
| `--include-factors` | 4 | ✅ | ✅ | ⚪ exclu | ⚠️ partiel | Aucun |
| `--include-macro-regime` | 2 | ✅ | ✅ | ⚪ exclu | ⚪ blacklisté | Aucun |
| `--include-score-components` | 9 | ⚪ désactivé | 🔴→✅ fix | 🔴→✅ fix | 🔴→✅ fix | Corrigé |
| `--include-volume-features` | 10 | ✅ | ✅ | ✅ | ✅ | Aucun |

> **Légende** : ✅ = OK | 🔴 = bug | ⚪ = non applicable par design
