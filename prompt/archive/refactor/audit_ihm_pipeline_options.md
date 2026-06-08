# Audit IHM ↔ CLI — couverture des options par pipeline

> Vérification exhaustive, **pipeline par pipeline**, des options CLI réellement
> exposées par chaque module backend versus celles paramétrables dans
> `ihm/pages/pipeline.py` (via `ihm/services/pipeline_runner.py`).
>
> Contexte cible : swing trading actions US, horizon 3-15 j, large/mid cap,
> Alpaca free / IEX, MySQL local, IHM Streamlit.
>
> Légende priorités :
> - **P1** = critique (manque empêche un usage swing correct ou défaut inadapté)
> - **P2** = important (option utile, à exposer rapidement)
> - **P3** = cosmétique / avancé (debug, hyperparams fins, rarement modifiés)

## Synthèse exécutive

| Pipeline | Args CLI backend | Exposés IHM | Manquants | Statut |
|---|---:|---:|---:|---|
| 1. import_alpaca_bar | 0 | 0 | — | ✅ (backend sans CLI) |
| 2. data_sanitizer_daily | 0 | 0 | — | ✅ (backend sans CLI) |
| 3. stock_screener | 9 | 9 | 0 | ✅ |
| 4. sync_latest_quotes | 2 | 2 | 0 | ✅ |
| 5. sync_earnings_calendar | 4 | 4 | 0 | ✅ |
| 6. alpha_scanner (selector) | 19 + 1 supprimé | 18 | **1 (P2)** | 🟡 |
| 7. sentiment_pipeline | 3 | 3 | 0 | ✅ |
| 8. signal_aggregator | 8 | 8 | 0 | ✅ |
| 9. ml_train (modelFactory) | ~46 | 12 | **~30 (5 P1, 12 P2, 13 P3)** | 🔴 |
| 10. ml_predict | (partage parser) | 1 | quelques P3 | 🟡 |
| 11. risk_management | 16 | 3 | **13 (4 P1, 7 P2, 2 P3)** | 🔴 |
| 12. execution (run_execution.py) | 15 | 9 | **6 (3 P1, 1 P2, 2 P3)** + 2 défauts inadaptés P1 | 🔴 |
| 12bis. protection_watcher | 13 | n/a (page Supervision Ops) | — | hors page pipeline |
| 13. corporate_actions sync | 8 | 2 forcés (`--portfolio-only`, `--account`) | **6 (1 P2, 5 P3)** | 🟡 |
| 14. corporate_actions apply | 2 | 2 | 0 | ✅ |
| B1. import_alpaca_assets | 0 | 0 | — | ✅ |
| B2. update_sector | 3 | 3 | 0 | ✅ |

**Bilan global** : 8 / 14 pipelines déjà OK. **3 zones rouges critiques**
nécessitent action immédiate : `risk_management`, `modelFactory ml_train`,
`execution`. **2 défauts d'exécution inadaptés au swing cash** sont également
identifiés (P1).

---

## 1. import_alpaca_bar — `python -m dataIntegrityEngine.import_alpaca_bar`

**Backend** : aucun argparse (cf. `dataIntegrityEngine/import_alpaca_bar.py:531`).
La fonction Python `import_alpaca_bars(time_frame, symbols)` accepte des
paramètres mais le `main()` les ignore (univers complet, `TimeFrame.ONE_DAY` en
dur).

**IHM** : aucun paramètre exposé (cohérent avec le backend).

**Action** :
- P3 (backend) : ajouter un argparse pour `--symbols` (debug ciblé) et
  `--timeframe` (`1Day`/`30Min`).
- Une fois fait → exposer dans IHM.

---

## 2. data_sanitizer_daily — `python -m dataIntegrityEngine.data_sanitizer_daily`

**Backend** : aucun argparse.

**IHM** : aucun paramètre.

**Action** : aucune (pipeline canonique sans variantes).

---

## 3. stock_screener — `python -m screener.stock_screener`

**Backend (`screener/stock_screener.py`)** :

| Arg CLI | Type | Default backend | Default IHM | Statut | Reco swing |
|---|---|---|---|---|---|
| `--chunk-size` | int | 500 | 500 | ✅ | OK |
| `--max-workers` | int | None (=auto) | 0 (=auto) | ✅ | OK |
| `--benchmark` | str | SPY | SPY | ✅ | OK |
| `--liquidity-threshold-usd` | float | 10_000_000 | 10_000_000 | ✅ | passer à **30_000_000** (cf. audit_global, large/mid cap) |
| `--min-relative-strength-index` | float | 100.0 | 100.0 | ✅ | OK |
| `--historical-range-lookback-days` | int | 504 (~2 ans) | 504 | ✅ | OK |
| `--min-historical-range-score` | float | 70.0 | 70.0 | ✅ | OK |
| `--first-pass-window-days` | int | 400 | 400 | ✅ | OK |
| `--disable-two-pass-loading` | flag | False | exposé via toggle | ✅ | OK |

**Action** : 
- P2 : remonter le défaut `liquidity_threshold_usd` à `30_000_000` côté IHM
  (`DEFAULT_SCREENER_LIQUIDITY_THRESHOLD_USD` provient de `ScreenerConfig` qui
  reste à 10 M ; on peut surclasser dans `pipeline_runner.py` sans toucher
  backend).

---

## 4. sync_latest_quotes — `python -m dataIntegrityEngine.sync_latest_quotes`

| Arg CLI | Backend | IHM | Statut |
|---|---|---|---|
| `--limit` | None | exposé (0=full) | ✅ |
| `--batch-size` | 200 | 200 | ✅ |

**Action** : aucune.

---

## 5. sync_earnings_calendar — `python -m dataIntegrityEngine.sync_earnings_calendar`

| Arg CLI | Backend | IHM | Statut |
|---|---|---|---|
| `--from-date` | None (défaut J-7) | toggle + date_input | ✅ |
| `--to-date` | None (défaut J+30) | toggle + date_input | ✅ |
| `--limit` | None | exposé | ✅ |
| `--sleep-seconds` | 1.1 | 1.1 | ✅ |

**Action** : aucune.

---

## 6. alpha_scanner — `python -m selector.alpha_scanner`

**Backend (`selector/alpha_scanner.py:1764-1783`)** : 19 args utilisateur + 1
`--preset` masqué.

| Arg CLI | Default backend | Exposé IHM | Reco swing |
|---|---|---|---|
| `--preset` (suppressed) | strict | non | ne pas exposer |
| `--chunk-size` | 500 | ✅ | OK |
| `--selection-size` | 50 | ✅ | OK (15-30 si compte < 100k$) |
| `--max-workers` | None | ✅ (0=auto) | OK |
| `--liquidity-threshold` | None (→ profil strict) | ✅ | OK (déjà aligné `STRICT_SWING_CASH_FILTERS`) |
| `--min-close` | None | ✅ | OK |
| `--max-volatility-ratio` | None | ✅ | OK |
| `--min-relative-strength-index` | None | ✅ | OK (100) |
| `--min-high-52w-proximity` | None | ✅ | OK (0.75) |
| `--min-weekly-trend-score` | None | ✅ | OK |
| `--min-atr-pct-20` | None | ✅ | OK (0.015) |
| `--max-atr-pct-20` | None | ✅ | OK (0.06) |
| `--min-market-cap` | None | ✅ | OK (2 Md$) |
| `--min-beta-126` | None | ✅ | OK |
| `--max-spread-bps` | None | ✅ | **biais IEX** — voir audit_global |
| `--earnings-blackout-days` | None | ✅ | OK (3) |
| **`--require-above-ma200`** | **False (flag)** | **❌ MANQUE** | **True** (Minervini stage 2) |
| `--max-anomaly-count` | 20 | ✅ | OK |
| `--sector-cap-ratio` | 0.30 | ✅ | OK |
| `--log-level` | INFO | ✅ | OK |

**Action P2** : ajouter une checkbox **`Alpha Scanner — exiger close > MA200`**,
default **True** (filtre anti-baissière trend-following standard swing). À placer
dans la section "Alpha Scanner" entre `selector_min_weekly_trend_score` et
`selector_min_atr_pct_20`.

---

## 7. sentiment_pipeline — `python -m event_sentiment`

| Arg CLI | Default | IHM | Statut |
|---|---|---|---|
| `--start-utc` | None | ✅ | OK |
| `--end-utc` | None | ✅ | OK |
| `--symbols` | None | ✅ | OK |

**Action** : aucune.

---

## 8. signal_aggregator — `python -m event_sentiment.signal_aggregator`

| Arg CLI | Default | IHM | Statut |
|---|---|---|---|
| `--trade-date` | aujourd'hui | global trade_date | ✅ |
| `--all-symbols` | False | ✅ | OK |
| `--sentiment-weight` | 0.15 | 0.15 | ✅ |
| `--macro-weight` | 0.10 | 0.10 | ✅ |
| `--lookback-days` | 5 | 5 | ✅ |
| `--min-news-count` | 2 | 2 | ✅ |
| `--time-decay-half-life-days` | 2.0 | 2.0 | ✅ |
| `--log-level` | INFO | ✅ | OK |

**Action** : aucune. La cohérence quant_weight = 1 - sent - macro est déjà
calculée et affichée dans l'IHM (ligne ~1188 `pipeline.py`).

---

## 9. ml_train — `python -m modelFactory --mode train` 🔴

**Backend (`modelFactory/cli.py`)** : ~46 args.

| Arg CLI | Default backend | Exposé IHM | Reco swing | Priorité |
|---|---|---|---|---|
| `--mode` | (required) | injecté = train | — | — |
| `--symbols` | None (= candidats) | ❌ | None | P3 |
| `--max-workers` | 4 | ❌ | 4 | P2 |
| `--max-epochs` | 50 | ❌ | 50 (LSTM) | P2 |
| `--sequence-length` | 60 | ❌ | 60 | P3 |
| **`--forecast-horizon`** | 5 | **❌** | **5 (3-10 swing)** | **P1** |
| `--batch-size` | 64 | ❌ | 64 | P3 |
| `--hidden-size` | 128 | ❌ | 128 | P3 |
| `--artifacts-dir` | artifacts/models | ❌ | défaut | P3 |
| `--include-sentiment` | False | ✅ | True | OK |
| `--enable-cross-sectional` | False | ✅ | False | OK |
| `--cross-sectional-min-universe` | 20 | ❌ | 20 | P3 |
| `--feature-set` | v1 (`v1`/`expert`) | ❌ | v1 | P2 |
| `--benchmark-symbol` | SPY | ❌ | SPY | P3 |
| **`--target-mode`** | binary (`binary`/`swing_cash`) | **❌** | **swing_cash** | **P1** |
| `--target-up-threshold` | 0.0 | ❌ | 0.02 (2 %) | P2 |
| `--target-down-threshold` | 0.0 | ❌ | -0.01 | P2 |
| `--decision-threshold` | 0.5 | ❌ | 0.55 | P2 |
| `--calibration-method` | none (`none`/`platt`) | ❌ | platt | P2 |
| `--calibration-min-samples` | 64 | ❌ | 64 | P3 |
| `--calibration-max-iter` | 100 | ❌ | 100 | P3 |
| **`--walkforward`** | False | **❌** | **True** (audit_global) | **P1** |
| `--wf-min-train-size` | 504 | ❌ | 504 | P2 (dépend `--walkforward`) |
| `--wf-val-size` | 126 | ❌ | 126 | P2 |
| `--wf-test-size` | 126 | ❌ | 126 | P2 |
| `--wf-step-size` | 126 | ❌ | 126 | P2 |
| `--wf-max-splits` | 3 | ❌ | 3 | P2 |
| `--compare-lightgbm` | False | ✅ | True | OK |
| `--enable-catboost` | False | ✅ | True | OK |
| `--enable-global-model` | False | ✅ | False (option) | OK |
| `--global-model-name` | catboost | ✅ | catboost | OK |
| `--global-artifact-symbol` | __GLOBAL__ | ❌ | défaut | P3 |
| `--select-champion` | False | ✅ | True | OK |
| `--default-champion` | lstm_attention | ❌ | défaut | P3 |
| `--champion-selection-metric` | selection_score | ✅ | selection_score | OK |
| `--lgbm-max-depth` | 4 | ❌ | 4 | P3 |
| `--lgbm-n-estimators` | 200 | ❌ | 200 | P3 |
| `--lgbm-learning-rate` | 0.05 | ❌ | 0.05 | P3 |
| `--catboost-depth` | 6 | ❌ | 6 | P3 |
| `--catboost-iterations` | 300 | ❌ | 300 | P3 |
| `--catboost-learning-rate` | 0.03 | ❌ | 0.03 | P3 |
| `--optimize-target` | False | ✅ | False (à activer si grid) | OK |
| `--candidate-horizons` | 3,5,10,15 | ❌ | 3,5,10,15 | P2 (visible si --optimize-target) |
| `--candidate-up-thresholds` | 0.0,0.01,0.02 | ❌ | défaut | P2 |
| `--candidate-down-thresholds` | 0.0,-0.005,-0.01 | ❌ | défaut | P2 |
| `--min-trades-fraction` | 0.15 | ❌ | 0.15 | P3 |
| `--optimize-thresholds` | False | ✅ | True | OK |
| `--candidate-decision-thresholds` | 0.50→0.70 | ❌ | défaut | P2 |
| `--min-action-rate` | 0.03 | ❌ | 0.03 | P2 |
| `--max-action-rate` | 0.35 | ❌ | 0.20 (swing prudent) | P2 |
| `--min-precision-long` | 0.52 | ❌ | 0.55 (swing) | P2 |
| `--accelerator` | auto | ✅ | auto | OK |
| `--log-level` | INFO | ❌ | INFO | P2 |

**Actions IHM (regroupement proposé)** : créer 4 sous-sections sous "Paramètres
Model Factory" :

1. **Cible / horizon swing (P1)** :
   - `--target-mode` (selectbox `binary` / `swing_cash`, default **swing_cash**)
   - `--forecast-horizon` (number_input int, default **5**, range 3..15)
   - `--target-up-threshold`, `--target-down-threshold`, `--decision-threshold`

2. **Walk-forward (P1)** :
   - `--walkforward` (checkbox, default **True**)
   - 5 number_input `--wf-*` (visibles si activé)

3. **Optimisation seuils (P2, conditionnels)** :
   - `--candidate-decision-thresholds` (text CSV)
   - `--min-action-rate`, `--max-action-rate`, `--min-precision-long`

4. **Hyperparams ML (P2/P3, expander avancé)** :
   - `--max-workers`, `--max-epochs`, `--feature-set`, `--calibration-method`,
     `--log-level`
   - LightGBM/CatBoost hyperparams en P3

---

## 10. ml_predict — `python -m modelFactory --mode predict`

Le backend partage le même parser que `train`. La majorité des args sont
ignorés en mode predict (pas d'entraînement). Options réellement utiles :

| Arg | IHM | Reco |
|---|---|---|
| `--mode` | injecté | — |
| `--accelerator` | ✅ | OK |
| `--symbols` | ❌ | P3 (ciblage debug) |
| `--artifacts-dir` | ❌ | P3 |
| `--log-level` | ❌ | P2 |

**Action** : P2 ajouter `--log-level`. Le reste hérite du formulaire ml_train.

---

## 11. risk_management — `python -m risk_management` 🔴

**Backend (`risk_management/cli.py`)** : 16 args.

| Arg CLI | Default backend | Exposé IHM | Reco swing | Priorité |
|---|---|---|---|---|
| `--account-equity` | 100_000 | ✅ | OK (équité réelle) | OK |
| **`--risk-per-trade-pct`** | 0.01 | **❌** | **0.01 (1%)** | **P1** |
| **`--max-positions`** | 20 | **❌** | **15** (swing 100k$) | **P1** |
| **`--max-position-weight`** | 0.10 | **❌** | **0.08** (8%) | **P1** |
| **`--max-sector-weight`** | 0.30 | **❌** | **0.30** | **P1** |
| `--trade-date` | aujourd'hui | global | OK | OK |
| `--dry-run` | False | ❌ | False | P2 |
| `--log-level` | INFO | ❌ | INFO | P2 |
| `--correlation-threshold` | 0.80 | ❌ | 0.80 | P2 |
| `--correlation-lookback-days` | 60 | ❌ | 60 | P2 |
| `--correlation-min-overlap` | 40 | ❌ | 40 | P3 |
| `--enable-kelly-sizing` | False | ❌ | False (à évaluer) | P2 |
| `--assumed-payoff-ratio` | 1.5 | ❌ | 1.5 | P3 |
| `--kelly-fraction-multiplier` | 0.25 | ❌ | 0.25 | P3 |
| `--score-weight` | 0.40 | ❌ | 0.40 | P2 |
| `--prediction-weight` | 0.60 | ❌ | 0.60 | P2 |
| `--account` | None | ✅ (sidebar) | OK | OK |

**Actions IHM (regroupement proposé)** : créer une section **"Paramètres Risk
Management"** sous "Equity pour le module Risk", avec 3 colonnes :

1. **Sizing (P1)** : `--risk-per-trade-pct`, `--max-positions`,
   `--max-position-weight`, `--max-sector-weight`.
2. **Conviction & Kelly (P2)** : `--score-weight`, `--prediction-weight`
   (ensemble doit sommer ≈ 1.0, afficher contrôle), `--enable-kelly-sizing`
   (+ Kelly P3 sous expander).
3. **Corrélation (P2)** : `--correlation-threshold`, `--correlation-lookback-days`.
4. **Avancé (P2/P3)** : `--dry-run`, `--log-level`,
   `--correlation-min-overlap`, `--assumed-payoff-ratio`,
   `--kelly-fraction-multiplier` (sous expander).

---

## 12. execution — `python run_execution.py <mode>` 🔴

**Backend (`run_execution.py`)** : 15 args (+ `mode` positionnel).

| Arg CLI | Default backend | Exposé IHM | Default IHM | Reco swing | Priorité |
|---|---|---|---|---|---|
| `mode` (positional) | menu interactif | ✅ | simulate | simulate (dev) | OK |
| `--date` | None (auto) | ✅ | global | OK | OK |
| `--run-id` | None | ✅ | "" | OK | OK |
| `--debug` | False | ❌ | — | False | P3 |
| `--allow-outside-rth` | False | ✅ | False | False (true le WE) | OK |
| `--auto-rebalance` | False | ✅ | False | False | OK |
| `--account` | None | ✅ (sidebar) | — | OK | OK |
| `--account-type` | **cash** | ✅ | **margin** ⚠️ | **cash** (swing cash) | **P1 défaut** |
| `--pdt-rule` | **off** | ✅ | **auto** ⚠️ | **off** (cohérent cash) | **P1 défaut** |
| `--swing-only` | **True** (BooleanOptionalAction) | ✅ | **False** ⚠️ | **True** | **P1 défaut** |
| **`--submission-window`** | None (`post_close`/`pre_open`/`both`) | **❌** | — | **`both`** (swing batch hors RTH) | **P1** |
| **`--trailing-activation-trigger`** | None (`multiple_r`/`profit_pct`) | **❌** | — | **`multiple_r`** | **P1** |
| **`--trailing-activation-r-multiple`** | None | **❌** | — | **1.0** | **P1** |
| `--trailing-activation-profit-pct` | None | ❌ | — | 0.03 (si trigger=profit_pct) | P2 |
| `--protection-transition-timeout-seconds` | None | ❌ | — | 30 | P3 |
| `--protection-transition-poll-interval-seconds` | None | ❌ | — | 2.0 | P3 |

**Actions IHM (regroupement proposé)** : 
1. **Corriger les défauts P1** dans `_apply_execution_prefills` /
   `PipelineLaunchOptions` :
   - `execution_account_type` → `cash` par défaut
   - `execution_swing_only` → `True` par défaut
2. Créer une section **"Stratégie de protection (sortie)"** sous le bloc
   exécution avec :
   - `--submission-window` (selectbox `post_close`/`pre_open`/`both`,
     default `both`)
   - `--trailing-activation-trigger` (selectbox, default `multiple_r`)
   - `--trailing-activation-r-multiple` (number_input float, default 1.0,
     visible si trigger=multiple_r)
   - `--trailing-activation-profit-pct` (visible si trigger=profit_pct)
3. **Avancé (P3, expander)** : `--debug`,
   `--protection-transition-timeout-seconds`,
   `--protection-transition-poll-interval-seconds`.

> ⚠️ **Note** : `execution_engine/cli.py` (séparé de `run_execution.py`) expose
> ~26 options additionnelles (entry-order-type, profit-taker-pct,
> trailing-stop-pct, max-slippage-bps, …) qui ne sont **pas** transmissibles
> via `run_execution.py`. Elles relèvent d'une refonte backend (P2 architecture
> à part). Cf. `audit_execution.md`.

---

## 12bis. protection_watcher

Hors page `pipeline` (exposé en page **Supervision Ops** + handoff panel).
13 args CLI : `--mode`, `--exec-run-id`, `--account`, `--limit`,
`--broker-mode`, `--trailing-stop-pct`, `--trailing-activation-trigger`,
`--trailing-activation-r-multiple`, `--trailing-activation-profit-pct`,
`--service-interval-seconds`, `--idle-interval-seconds`,
`--heartbeat-interval-seconds`, `--max-iterations`, `--stop-when-idle`,
`--max-consecutive-failures`, `--log-level`. Voir `audit_watcher.md`.

---

## 13. corporate_actions sync — `python -m corporate_actions sync`

**Backend (`corporate_actions/cli.py`)** : 8 args.

| Arg CLI | Default | IHM | Reco | Priorité |
|---|---|---|---|---|
| `--symbols` | None | ❌ | None (filtre debug) | P3 |
| `--all-symbols` | False | ❌ | False | P3 |
| `--portfolio-only` | False | ✅ **forcé True** | True | OK |
| `--skip-existing` | False | ❌ | False (défaut) ; True optionnel pour perf | P2 |
| `--batch-size` | 25 | ❌ | 25 | P3 |
| `--start` | -10 ans | ❌ | None | P3 |
| `--end` | aujourd'hui | ❌ | None | P3 |
| `--account` | None | ✅ (sidebar) | OK | OK |

**Actions** :
- P2 : exposer `--skip-existing` en checkbox dans la section corporate actions
  (utile pour accélérer les syncs après réinitialisation).
- P3 : exposer `--start`/`--end` (date_input) dans un expander pour les
  resynchronisations historiques ponctuelles.
- P3 : `--symbols` / `--all-symbols` / `--batch-size` rarement utiles, à
  laisser hors IHM (pilotables CLI).

---

## 14. corporate_actions apply — `python -m corporate_actions apply`

| Arg CLI | Default | IHM | Statut |
|---|---|---|---|
| `--as-of` | aujourd'hui | global trade_date | ✅ |
| `--account` | None | sidebar | ✅ |

**Action** : aucune.

---

## B1. import_alpaca_assets — aucune option backend → ✅
## B2. update_sector — `--limit`, `--sleep-seconds`, `--log-every` tous exposés → ✅

---

## Récap des changements à implémenter dans IHM

### Phase P1 (à livrer immédiatement)

#### `ihm/services/pipeline_runner.py`

1. **Ajouter constantes par défaut** :
   ```python
   # Risk
   DEFAULT_RISK_PER_TRADE_PCT = 0.01
   DEFAULT_RISK_MAX_POSITIONS = 15
   DEFAULT_RISK_MAX_POSITION_WEIGHT = 0.08
   DEFAULT_RISK_MAX_SECTOR_WEIGHT = 0.30
   DEFAULT_RISK_SCORE_WEIGHT = 0.40
   DEFAULT_RISK_PREDICTION_WEIGHT = 0.60
   DEFAULT_RISK_CORRELATION_THRESHOLD = 0.80
   DEFAULT_RISK_CORRELATION_LOOKBACK_DAYS = 60
   # Execution
   DEFAULT_EXEC_SUBMISSION_WINDOW = "both"
   DEFAULT_EXEC_TRAILING_TRIGGER = "multiple_r"
   DEFAULT_EXEC_TRAILING_R_MULTIPLE = 1.0
   # ML
   DEFAULT_ML_TARGET_MODE = "swing_cash"
   DEFAULT_ML_FORECAST_HORIZON = 5
   DEFAULT_ML_WALKFORWARD = True
   ```

2. **Étendre `PipelineLaunchOptions`** (P1 fields) :
   ```python
   # ML
   ml_target_mode: Literal["binary","swing_cash"] = "swing_cash"
   ml_forecast_horizon: int = 5
   ml_walkforward: bool = True
   # Risk
   risk_per_trade_pct: float = 0.01
   risk_max_positions: int = 15
   risk_max_position_weight: float = 0.08
   risk_max_sector_weight: float = 0.30
   risk_score_weight: float = 0.40
   risk_prediction_weight: float = 0.60
   risk_correlation_threshold: float = 0.80
   risk_correlation_lookback_days: int = 60
   # Execution
   execution_submission_window: Literal["post_close","pre_open","both"] = "both"
   execution_trailing_trigger: Literal["multiple_r","profit_pct"] = "multiple_r"
   execution_trailing_r_multiple: float = 1.0
   # Selector
   selector_require_above_ma200: bool = True
   ```

3. **Corriger défauts existants** :
   ```python
   execution_account_type: Literal["margin","cash"] = "cash"   # était margin
   execution_swing_only: bool = True                            # était False
   ```

4. **Étendre `build_pipeline_command`** :
   - `risk_management` : injecter les 8 nouveaux flags.
   - `execution` : injecter `--submission-window`,
     `--trailing-activation-trigger`, `--trailing-activation-r-multiple`.
   - `ml_train` : injecter `--target-mode`, `--forecast-horizon`,
     `--walkforward` (et les 5 `--wf-*` quand activé).
   - `alpha_scanner` : injecter `--require-above-ma200` quand True.

#### `ihm/pages/pipeline.py`

1. Mettre à jour les `st.selectbox` / `st.checkbox` pour refléter les nouveaux
   défauts (`account_type=cash`, `swing_only=True`).
2. Ajouter une section **"Paramètres Risk Management"** (4 colonnes).
3. Ajouter une section **"Stratégie de protection (Execution)"** (3 colonnes).
4. Étendre la section **"Paramètres Model Factory"** avec un sous-bloc
   "Cible swing (target/horizon/walkforward)".
5. Ajouter une checkbox **"Alpha Scanner — exiger close > MA200"**.

### Phase P2 (sprint suivant)

- ML : `--max-workers`, `--max-epochs`, `--feature-set`, `--calibration-method`,
  thresholds `--candidate-decision-thresholds`, `--min/max-action-rate`,
  `--min-precision-long`, `--log-level` (predict + train).
- Risk : `--dry-run`, `--enable-kelly-sizing`, `--log-level`.
- Execution : `--trailing-activation-profit-pct` (visible si trigger=profit_pct).
- Corporate actions sync : `--skip-existing` (checkbox).
- Screener : remonter défaut liquidité à 30 M$ pour aligner audit_global.

### Phase P3 (à laisser hors IHM, pilotable CLI)

Tous les hyperparams ML fins (LightGBM/CatBoost), `--debug`,
`--protection-transition-*`, calibration min-samples/max-iter,
`--correlation-min-overlap`, etc.

---

## Annexes

### A. Helpers IHM réutilisables proposés

Pour réduire la duplication dans `pipeline.py` (~2090 lignes), introduire dans
`ihm/components/forms.py` :

- `render_number_input_with_default(label, key, default, ...)`
- `render_log_level_selectbox(key, default="INFO")`
- `render_walkforward_block(prefix, defaults)`
- `render_risk_sizing_block(defaults)`
- `render_execution_protection_block(defaults)`

### B. Centralisation suggérée dans `ihm/services/account_defaults.py`

Définir un dataclass `SwingTradeDefaults` regroupant tous les défauts P1
identifiés ci-dessus, importé à la fois par `pipeline_runner.py` et
`pipeline.py`. Évite la divergence de constantes.

### C. Tests à ajouter

- `tests/test_pipeline_runner_build_command.py` : assertions sur la présence
  des nouveaux flags pour `risk_management`, `execution`, `ml_train`,
  `alpha_scanner`.
- `tests/test_pipeline_runner_swing_defaults.py` : vérifier que
  `PipelineLaunchOptions()` produit `--account-type cash --pdt-rule off
  --swing-only`, `--target-mode swing_cash`, `--walkforward`,
  `--require-above-ma200`.

