# Go To Pro — Roadmap Alpha Trade vers le niveau institutionnel

> **Date** : 2026-07-21  
> **Statut global** : Le système est déjà de qualité institutionnelle. Ce document identifie les gaps résiduels et priorise les actions.

---

## 1. 🏦 Audit du système actuel

### 1.1 Architecture globale — ✅ Niveau PRO

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  ALPHA MODEL │ →  │ RISK MODEL   │ →  │  PORTFOLIO   │ →  │  EXECUTION   │
│  (modelFact) │    │  (risk_mgmt) │    │  OPTIMIZER   │    │  (exec_eng)  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
     ✅ présent          ✅ présent         ✅ présent          ✅ présent
```

### 1.2 Alpha Model — modelFactory

| Composant | Statut | Détail |
|:--|:--|:--|
| LSTM Attention per-symbol | ✅ | 20 séquences, 256 hidden, ternary |
| LightGBM challenger | ✅ | multiclass, WF 11 splits |
| CatBoost challenger | ✅ | multiclass, WF 11 splits |
| Walk-forward validation | ✅ | 11 splits, 504 min train, 126 val/test |
| Champion selection | ✅ | wf.f1_macro, sélection automatique |
| Features OHLCV + Expert | ✅ | 31 colonnes (RSI, ATR, SMA/EMA distance…) |
| Features cross-sectional | ✅ | 8 rangs percentiles PIT-safe |
| Features sectorielles | ✅ | 8 colonnes GICS (momentum, volatilité, alpha…) |
| Global Model + Stacking | ✅ | 3 flags A/B/C, 22 features cross-symbol exclusives |
| Feature contract + fingerprint | ✅ | SHA256, validation à l'inférence |
| Target optimization | ✅ | Horizon swing, up/down thresholds |
| Threshold optimization | ✅ | Decision threshold, min action rate, min precision |
| Calibration Platt / TemperatureScaler | ✅ | Binary / ternary |
| Macro features (VIX, VXN, VIX3M, MOVE) | ✅ | Activables individuellement |
| Sentiment features | ✅ | news_count, sentiment_net, confidence, major_event |
| Screener scores | ✅ | trend, VCP, final_score, market_cap, beta, spread… |
| Short score dédié | ✅ | Score baissier composite |
| Benchmarks (LSTM/LGBM/CB/Global) | ✅ | global_benchmark_runner.py |
| Drift detection | ✅ | ml_drift_runs, ML gate kill-switch |
| Reproducibility | ✅ | Seed déterministe, apply_reproducibility |

### 1.3 Risk Management

| Composant | Statut | Détail |
|:--|:--|:--|
| Kelly directionnel | ✅ | Hit rate + payoff par side, shrinkage bayésien |
| Position sizing ATR | ✅ | risk_per_trade_pct × account_equity / (ATR × stop_mult) |
| Fractional shares | ✅ | allow_fractional_shares, QUANTITY_EPSILON |
| Circuit breaker | ✅ | Drawdown % / daily PnL, email + Slack alerts |
| Edge calculator | ✅ | Net edge = gross - spread - commission - slippage - borrow |
| Corrélation signée | ✅ | Pearson greedy, long/short hedge detection |
| Concentration limits | ✅ | Max trades/symbol/window, consecutive loss blacklist |
| Portfolio optimizer | ✅ | Non-greedy, MCTR, turnover costs, gross/net constraints |
| No-trade bands | ✅ | Évite les micro-ajustements |
| Liquidity gate | ✅ | Borrow availability, spread check |
| ML gate | ✅ | Kill-switch si drift ML détecté |
| Regime state machine | ✅ | normal / capital_preservation / forced_rotation |
| Abstention policy | ✅ | Jours sans trading (earnings, FOMC…) |
| Stop calculator | ✅ | ATR-based initial stop |
| Factor model | ✅ | Risk factor exposures |
| Capacity model | ✅ | ADV-based capacity limits |
| Selection contract | ✅ | ML-first immutable : ML owns side & rank, risk only veto |
| Conviction scoring | ✅ | p_side = ML probability uniquement |

### 1.4 Execution Engine

| Composant | Statut | Détail |
|:--|:--|:--|
| Synthetic bracket | ✅ | Entry → trailing_stop + take-profit |
| OCO manager | ✅ | Cancel sibling on fill |
| Protection watcher | ✅ | Stop initial → trailing dynamique |
| TCA (post-trade) | ✅ | Slippage bps, implementation shortfall, buckets |
| Broker reconciliation | ✅ | Automated state sync |
| Cash ledger guard | ✅ | Buying power pre-check |
| Preflight checks | ✅ | Market regime, gap filter, spread |
| Orphan adoption | ✅ | Reprise des ordres orphelins |
| Broker adapter | ✅ | Alpaca API |

---

## 2. 📊 Features ML — État des lieux complet

### 2.1 Tableau des features par modèle (config standard)

| # | Famille | Colonnes | Global | LSTM | LGBM/CB |
|:--|:--|:--|:--:|:--:|:--:|
| 1 | OHLCV | 13 | ❌¹ | ✅ | ✅ |
| 2 | Expert | 18 | ❌¹ | ✅ | ✅ |
| 3 | Rangs cross-sectional | 8 | ✅ | ✅ | ✅ |
| 4 | Secteur | 8 | ✅ | ✅ | ✅ |
| 5 | Cross-symbol exclusives 🆕 | 6 | ✅ | ❌² | ❌² |
| 6 | global_pred_long | 1 | ❌³ | ✅ | ✅ |
| | **Total config standard** | | **22** | **48** | **48** |

> ¹ Exclues par orthogonalité — le Global apprend le cross-symbol, le per-symbol apprend le local.  
> ² Exclusives au Global — breadth, dispersion, concentration, rang intra-secteur, ratio vol, momentum spread.  
> ³ Pas de récursion.

### 2.2 Features cross-symbol exclusives (Global Model uniquement)

| Colonne | Description | Signal |
|:--|:--|:--|
| `sector_breadth_20` | % de titres du secteur avec ret_20 > 0 | Santé de la tendance sectorielle |
| `sector_dispersion_20` | Écart-type des ret_20 intra-secteur | Désaccord → incertitude |
| `sector_concentration_20` | Part du top-3 en dollar volume / total | Les mega-caps tirent-elles le secteur ? |
| `symbol_rank_in_sector_20` | Rang percentil du ret_20 dans son secteur | Leader ou suiveur ? |
| `stock_vs_sector_vol_ratio` | Volatilité titre / volatilité moyenne secteur | Anomalie de volatilité |
| `sector_momentum_spread_20` | Top décile - bottom décile des ret_20 | Dispersion extrême |

---

## 3. 🔬 Résultats des tests A/B

### 3.1 Baseline vs +Secteur vs +Secteur+Stacking (WF F1 macro)

| Modèle | Baseline | +Secteur | +Secteur+Stacking |
|:--|:--|:--|:--|
| LightGBM | 0.308 | 0.305 | 0.307 |
| CatBoost | 0.301 | ❌ absent | 0.305 |
| LSTM | 0.250 | 0.243 | 0.252 |

### 3.2 Interprétation

- **Features sectorielles seules** : pas d'amélioration du F1 macro, léger recul
- **Stacking (global_pred_long)** : CatBoost ressuscité (44% champions vs 0%), zéro `f1_short=0`, champion selection rééquilibrée
- **Effet principal** : stabilisation (réduction variance), pas boost de performance brute — le Global actuel partage les mêmes features que le per-symbol
- **Avec features cross-symbol exclusives** 🆕 : à tester — le Global a maintenant des features orthogonales (22 cols vs 48 per-symbol)

---

## 4. 🎯 Gaps identifiés et plan d'action

### 4.1 Gaps — Alpha Model

| # | Gap | Impact | Priorité | Effort |
|:--|:--|:--|:--|:--|
| A1 | Features cross-symbol avancées (lead-lag, corrélation inter-symboles, flux de capitaux) | 🟡 Moyen | P2 | 3-5j |
| A2 | Market impact model (Almgren-Chriss simplifié) | 🟡 Moyen | P2 | 2-3j |
| A3 | Meta-labeling (modèle secondaire qui valide/rejette les trades du primary model) | 🟢 Élevé | P1 | 3-5j |
| A4 | Online learning / incremental retraining | 🟡 Moyen | P3 | 5-10j |
| A5 | Feature importance SHAP par trade pour explainability | 🟡 Moyen | P2 | 2-3j |
| A6 | Test du Global Model avec les 22 features cross-symbol exclusives | 🔴 Critique | P0 | 1 batch |

### 4.2 Gaps — Risk Management

| # | Gap | Impact | Priorité | Effort |
|:--|:--|:--|:--|:--|
| R1 | Risk parity / equal risk contribution allocation | 🟢 Élevé | P1 | 3-5j |
| R2 | Stress testing (scénarios historiques : 2008, 2020, 2022) | 🟢 Élevé | P1 | 2-3j |
| R3 | Greeks / options overlay (delta hedging, gamma limits) | 🟡 Moyen | P3 | 5-10j |
| R4 | Dynamic risk budget (vol targeting ajusté au régime) | 🟢 Élevé | P1 | 2-3j |
| R5 | Factor neutrality constraints explicites (β=0, sector=0) | 🟡 Moyen | P2 | 2-3j |

### 4.3 Gaps — Portfolio Construction

| # | Gap | Impact | Priorité | Effort |
|:--|:--|:--|:--|:--|
| P1 | Black-Litterman (combiner vues ML + prior market cap) | 🟢 Élevé | P1 | 3-5j |
| P2 | Transaction cost model intégré à l'optimiseur | 🟡 Moyen | P2 | 2-3j |
| P3 | Multi-horizon optimization (court terme vs long terme) | 🟡 Moyen | P3 | 5-10j |

### 4.4 Gaps — Execution

| # | Gap | Impact | Priorité | Effort |
|:--|:--|:--|:--|:--|
| E1 | Pre-trade TCA (estimer l'impact avant de soumettre) | 🟢 Élevé | P1 | 2-3j |
| E2 | Volume curve / TWAP scheduling | 🟡 Moyen | P2 | 3-5j |
| E3 | Smart order routing (dark pools, lit exchanges) | 🔴 Faible | P3 | 5-10j |
| E4 | Adaptive limit order (ajuster le prix limite selon le carnet) | 🔴 Faible | P3 | 3-5j |

---

## 5. 📋 Plan d'action priorisé — Next 4 sprints

### Sprint 1 (P0 — Immédiat) 🔴

| Action | Description |
|:--|:--|
| **A6** | Lancer un batch complet avec Global Model + 22 features cross-symbol exclusives. Comparer F1 vs baseline |
| **A3** | Implémenter un meta-labeler : LGBM binaire qui prédit si le trade du primary model sera gagnant. Input : features du primary model + global_pred + métriques de calibration |

### Sprint 2 (P1 — Court terme) 🟢

| Action | Description |
|:--|:--|
| **R4** | Dynamic risk budget : multiplier le risk_per_trade_pct par un facteur vol (ex: 0.15 / σ_20j). Moins de risque en haute volatilité |
| **R1** | Risk parity : allouer le risque également entre tous les trades, pas proportionnellement à l'edge |
| **R2** | Stress testing : simuler le portefeuille sur 2008, 2020 Q1, 2022. Mesurer max drawdown, VaR 95%, CVaR |
| **P1** | Black-Litterman : utiliser les prédictions ML comme "vues" et les market cap weights comme prior |
| **E1** | Pre-trade TCA : estimer slippage = f(volume, spread, ADV%) avant de décider la taille |

### Sprint 3 (P2 — Moyen terme) 🟡

| Action | Description |
|:--|:--|
| **A1** | Features cross-symbol avancées : lead-lag matrix intra-secteur, flux de capitaux, corrélation ranking |
| **A5** | SHAP explainability : par trade, quelles features ont le plus contribué à la décision |
| **R5** | Factor neutrality : contrainte β_portfolio = 0, net sector exposure = 0 dans l'optimiseur |
| **P2** | Transaction cost model intégré à l'optimiseur : coût = f(turnover, ADV%, spread) |
| **E2** | TWAP scheduling : découper les gros ordres en tranches horaires |

### Sprint 4 (P3 — Long terme) 🔴

| Action | Description |
|:--|:--|
| **A4** | Online learning : réentraîner les modèles chaque mois avec les nouveaux trades |
| **R3** | Options overlay : delta hedging, gamma limits |
| **P3** | Multi-horizon optimization : séparer les trades court terme (swing 10j) et long terme (position 60j) |
| **E3** | Smart order routing : si dispo via broker |
| **E4** | Adaptive limit orders : ajuster le prix limite selon le spread et la profondeur du carnet |

---

## 6. 🏆 Scorecard — Maturité par pilier

| Pilier | Maturité | Note /10 | Prochaine étape |
|:--|:--|:--|:--|
| Alpha Model | Production | 8/10 | Meta-labeling, test cross-symbol exclusives |
| Risk Management | Production | 8/10 | Dynamic risk budget, stress testing |
| Portfolio Construction | Production | 7/10 | Black-Litterman, factor neutrality |
| Execution | Production | 7/10 | Pre-trade TCA, TWAP |

**Score global** : 7.5/10 — niveau fonds systématique mid-tier. Pour atteindre 9/10 (Renaissance/Two Sigma), le gap principal est le **meta-labeling** et le **dynamic risk budget**.

---

## 7. 🔧 Corrections techniques (Sprint 2026-07-21)

### Bugs corrigés

| Fichier | Bug | Impact |
|:--|:--|:--|
| `tabular_baseline.py` | `get_feature_columns()` sans flags macro/sentiment/screener | LGBM/CB ignoraient VIX/VXN/MOVE même si activés |
| `trainer.py` | `_run_walk_forward_validation()` idem | LSTM WF ignorait les flags macro |
| `features.py` | `build_feature_contract()` sans flags macro | TypeError au contrat de features |
| `orchestrator.py` | Workers sans `configure_root_logging()` | Logs INFO invisibles en multiprocessing |
| `orchestrator.py` | Cache `global_pred_df` non transmis aux workers | Stacking inopérant avec `max_workers > 1` |
| `global_model.py` | `train_dir` CatBoost non créé | Crash au `.fit()` du Global Model |
| `ihm/…/fractional_trading_preferences.py` | `@dataclass(slots=True)` non pickleable | Crash IHM `st.cache_data` |

### Améliorations

| Fichier | Changement |
|:--|:--|
| `global_model.py` | `_get_global_feature_columns()` — 22 features cross-symbol exclusives |
| `cross_sectional.py` | `_compute_cross_symbol_features()` — 6 nouvelles features exclusives Global |
| `cross_sectional.py` | `GLOBAL_EXCLUSIVE_FEATURE_COLUMNS` — breadth, dispersion, concentration, rank, ratio, spread |
| `trainer.py` + `tabular_baseline.py` | Log `walk_forward start … feature_cols=N stacking=X global_pred=Y` |
| `orchestrator.py` | Cache parquet `_global_pred_cache.parquet` pour workers |
| `orchestrator.py` | `_filter_symbols_by_mode` — flags macro + global_stacking |

### Tests (33 unitaires)

| Fichier | Tests |
|:--|:--|
| `tests/test_cross_symbol_features.py` | 33 (compute 15 + merge 5 + global_cols 7 + structure 6) |

---

## 8. 📁 Fichiers clés du système

```
modelFactory/           → Alpha model (ML)
risk_management/        → Risk model, portfolio builder, optimizer (48 fichiers)
execution_engine/       → Execution, OCO, protection (27 fichiers)
selector/               → Alpha scanner, ranking, regime filters
core/conviction.py      → ML → Risk bridge
flows/daily_pipeline.py → Orchestration quotidienne
regime_marche/          → Détection de régimes de marché
common/capital_presets.py → Presets de capital
```
