t# Revue d’implémentation P1 — backtest pipeline et live pipeline

Date de revue : 2026-06-03

## Objet

Vérification de l’implémentation des 4 points **P1 — indispensable** mentionnés dans `prompt/audit_backtest.md`, à la fois :

- côté **backtest pipeline**
- côté **live pipeline**

Points vérifiés :

1. **Activer le drawdown breaker portefeuille en backtest pipeline**
2. **Activer un vol targeting**
3. **Mettre un gating dur sur la couverture ML**
4. **Durcir le régime en 2021-2022 style “rates shock”**

---

## Verdict synthétique

| P1 | Backtest pipeline | Live pipeline | Verdict |
|---|---|---|---|
| 1. Drawdown breaker portefeuille | Oui | Oui, avec nuance | **Implémenté** |
| 2. Vol targeting | Oui | Oui | **Implémenté** |
| 3. Gating dur couverture ML | Oui | Oui | **Implémenté** |
| 4. Régime durci “rates shock” 2021-2022 | Oui | Oui | **Implémenté** |

### Conclusion courte

Le **P1 est bien implémenté** des deux côtés :

- **backtest pipeline**
- **live pipeline**

La principale **nuance** concerne le **drawdown breaker côté exécution live pure** (`run_execution.py`) : il existe bien, mais la protection drawdown la plus solide est surtout portée **en amont dans le pipeline risk live** via le `PnLSnapshot` construit depuis les snapshots de compte.

---

## 1. Drawdown breaker portefeuille

## 1.1 Backtest pipeline

### Verdict
**Oui, implémenté et branché.**

### Preuves code

- `backtesting/cli/_impl.py:1425-1434`  
  Le pipeline backtest résout par défaut `max_portfolio_dd_pct` depuis le preset via `backtesting_max_portfolio_dd_pct`.

- `backtesting/cli/_impl.py:2081-2085`  
  Le `DrawdownCircuitBreaker` est instancié avec :
  - `enabled=float(args.max_portfolio_dd_pct) > 0.0`
  - `max_dd_pct=float(args.max_portfolio_dd_pct)`
  - `recovery_pct=float(args.dd_recovery_pct)`

- `backtesting/risk_overlay.py:91-108`  
  Classe `DrawdownCircuitBreaker`.

- `backtesting/simulator.py:535-540`  
  Le breaker est évalué à chaque séance sur `current_equity` et `peak_equity`.

- `backtesting/simulator.py:665-686`  
  Si le breaker est déclenché, les **nouvelles entrées sont bloquées** et tracées dans les diagnostics (`blocked_by_drawdown_breaker`).

### Lecture fonctionnelle

Ce n’est pas seulement une classe présente dans le dépôt : le breaker est **effectivement branché dans le flux backtest pipeline**, alimenté par les presets, et utilisé pour couper les nouvelles entrées.

---

## 1.2 Live pipeline

### Verdict
**Oui, implémenté dans le pipeline risk live.**

### Preuves code

- `risk_management/cli.py:780-816`  
  Construction d’un `PnLSnapshot` live avec :
  - `portfolio_high_watermark`
  - `portfolio_current_value`
  - `daily_pnl`

- `risk_management/cli.py:857-866`  
  Le seuil `max_portfolio_drawdown_pct` est injecté dans `RiskConfig`.

- `risk_management/cli.py:945-946`  
  Instanciation du `CircuitBreaker(config, pnl_snapshot)`.

- `risk_management/cli.py:1046-1048`  
  Le `CircuitBreaker` est injecté dans `PortfolioBuilder`.

- `risk_management/risk_checker.py:36-40`  
  Si le breaker est actif, la taille autorisée est ramenée à `0.0` → rejet de position.

- `ihm/services/pipeline_runner.py:2179-2182`  
  L’orchestrateur IHM transmet bien `--max-portfolio-drawdown-pct`.

### Nuance importante

Dans `run_execution.py`, un `CircuitBreaker` est aussi créé :

- `run_execution.py:864-865`

Mais ce chemin initialise :

- `portfolio_current_value = equity`
- `portfolio_high_watermark = equity`

Donc, **dans `run_execution.py` seul**, on n’a pas le même niveau de persistance historique du drawdown que dans le pipeline risk live basé sur `account_risk_snapshot`.

### Conclusion P1.1

- **Pipeline risk live** : oui, correctement implémenté
- **Exécution live isolée (`run_execution.py`)** : présence du breaker, mais plus faible si considérée seule

---

## 2. Vol targeting

## 2.1 Backtest pipeline

### Verdict
**Oui, implémenté et utilisé.**

### Preuves code

- `backtesting/cli/_impl.py:1457-1465`  
  Le pipeline backtest résout `target_annual_vol` depuis le preset.

- `backtesting/cli/_impl.py:2086-2088`  
  Cette cible est injectée dans `RiskOverlayConfig.target_annual_vol`.

- `backtesting/risk_overlay.py:111-129`  
  `compute_portfolio_vol_scaler(...)` calcule le scaler de vol.

- `backtesting/simulator.py:718-724`  
  Le scaler est calculé à partir de l’historique de l’equity.

- `backtesting/simulator.py:799-800`  
  Le `target_weight_pct` des nouvelles entrées est multiplié par le `vol_target_scaler`.

### Lecture fonctionnelle

Le vol targeting est réellement appliqué au sizing en backtest pipeline, pas seulement exposé comme option de config.

---

## 2.2 Live pipeline

### Verdict
**Oui, implémenté et branché.**

### Preuves code

- `risk_management/config.py:28-29`  
  `target_annual_vol` et `vol_target_lookback_days` existent dans `RiskConfig`.

- `risk_management/cli.py:867-872`  
  Ces paramètres sont injectés dans la config live.

- `risk_management/cli.py:898-916`  
  Le pipeline live évalue le vol targeting avant la construction du portefeuille.

- `risk_management/cli.py:33`  
  Le benchmark utilisé est `SPY`.

- `risk_management/live_pipeline_guards.py:110-168`  
  `evaluate_vol_target(...)` calcule la vol réalisée et le scaler.

- `risk_management/live_pipeline_guards.py:171-179`  
  `apply_vol_target_to_risk_config(...)` applique la réduction de risque via :
  - `risk_multiplier`
  - `max_gross_exposure`

- `ihm/services/pipeline_runner.py:2183-2189`  
  L’IHM transmet bien :
  - `--target-annual-vol`
  - `--vol-target-lookback-days`

### Nuance

La logique live est un **de-risking uniquement** :

- `effective_scaler = min(scaler, 1.0)`

Donc le système ne sur-alloue pas si la vol réalisée est plus faible que la cible ; il ne fait que **réduire** l’exposition quand la vol est trop haute.

### Conclusion P1.2

Le vol targeting est **implémenté des deux côtés**.

---

## 3. Gating dur sur la couverture ML

## 3.1 Backtest pipeline

### Verdict
**Oui, implémenté avec fail-fast dur pour les runs pipeline.**

### Preuves code

- `backtesting/cli/_impl.py:1467-1475`  
  Le seuil `min_ml_coverage_ratio` est résolu depuis le preset via `backtesting_min_ml_coverage_ratio`.

- `backtesting/cli/_impl.py:1478-1510`  
  `_enforce_ml_coverage_gate(...)` implémente le fail-fast.

- `backtesting/cli/_impl.py:1831-1836`  
  Cette fonction est réellement appelée dans le flux du backtest.

- `backtesting/fidelity.py:2793-2863`  
  `evaluate_ml_coverage_gate(...)` calcule :
  - `coverage_ratio`
  - `required_ratio`
  - `allowed`

- `backtesting/cli/_impl.py:1503-1510`  
  Si le gate est actif et non respecté, le run s’arrête avec `sys.exit(1)`.

### Conditions d’activation

Le gating backtest est actif seulement si :

- `engine_mode == "pipeline"`
- `ml_mode != "off"`
- `min_ml_coverage_ratio > 0`

### Lecture fonctionnelle

Donc :

- **pipeline backtest** : gate dur effectivement branché
- **research mode** : non, par design

---

## 3.2 Live pipeline

### Verdict
**Oui, implémenté, avec double protection.**

### Couche A — gate dur sur la couverture ML

#### Preuves code

- `risk_management/live_pipeline_guards.py:59-107`  
  `evaluate_ml_coverage_gate(...)`

- `risk_management/cli.py:979-998`  
  Si la couverture ML est insuffisante, le pipeline quitte avec `SystemExit(...)`.

- `ihm/services/pipeline_runner.py:2190-2191`  
  L’IHM transmet `--min-ml-coverage-ratio`.

### Couche B — kill-switch ML séparé

#### Preuves code

- `risk_management/ml_gate.py:83-124`  
  `resolve_ml_gate_state(...)` combine feature flag + décision drift.

- `risk_management/ml_gate.py:127-135`  
  Si le ML gate est fermé, le système force un mode :
  - `score_weight = 1.0`
  - `prediction_weight = 0.0`

- `risk_management/db_io.py:416-423`  
  Si le ML gate est fermé, les prédictions ML ne sont même plus chargées.

### Lecture fonctionnelle

Le live pipeline a donc :

1. un **kill-switch ML** structurel
2. un **gating dur de couverture** avant publication de nouvelles cibles

### Conclusion P1.3

Le gating dur couverture ML est **implémenté en backtest pipeline et en live pipeline**.

---

## 4. Régime durci “rates shock” 2021-2022

## 4.1 Configuration de durcissement

### Verdict
**Oui, le durcissement est bien présent dans la configuration centrale.**

### Preuves config

Dans `config.yaml:76-101` :

- `block_sectors` inclut désormais :
  - `Technology`
  - `Tech`
  - `Growth`
  - `Real Estate`
  - `Consumer Cyclical`
  - `Financial Services`

- `risk_mult: 0.45`
- `soft_max_positions: 2`
- `soft_max_position_weight: 0.20`
- `soft_max_sector_weight: 0.25`
- `soft_max_gross_exposure: 0.50`

- `hard_relative_spike_threshold: 0.08`
- `hard_risk_mult: 0.30`
- `hard_mode_live: close_only`
- `hard_mode_backtest: cash_only`
- `hard_max_positions: 1`
- `hard_max_position_weight: 0.15`
- `hard_max_sector_weight: 0.20`
- `hard_max_gross_exposure: 0.35`
- `hard_requires_vix_high: true`
- `hard_requires_sentiment_warning: true`

---

## 4.2 Backtest pipeline

### Verdict
**Oui, implémenté et réellement branché via `market_regimes`.**

### Preuves code

- `backtesting/cli/_impl.py:1881-1938`  
  Le backtest pipeline charge `market_regimes` depuis `config.yaml` et injecte cette config dans `build_phase2_risk_result(...)`.

- `backtesting/risk_bridge.py:301-326`  
  Un snapshot de régime est construit pour chaque date, appliqué à `RiskConfig`, et les entrées sont bloquées si `allow_new_entries == False`.

- `risk_management/regime_apply.py:30-70`  
  Le snapshot ajuste effectivement :
  - `risk_multiplier`
  - `effective_max_positions_override`
  - `max_position_weight`
  - `max_sector_weight`
  - `max_gross_exposure`

- `service/market/regime_manager.py:323-345`  
  Le yield spike “soft” applique déjà blocages sectoriels et réduction de risque.

- `service/market/regime_manager.py:486-560`  
  Le “hard shock” applique :
  - escalade de mode (`hard_mode_backtest` / `hard_mode_live`)
  - `hard_block_sectors`
  - `hard_risk_mult`
  - `hard_max_positions`
  - `hard_max_position_weight`
  - `hard_max_sector_weight`
  - `hard_max_gross_exposure`

### Point important

Le petit filtre SMA de `backtesting/risk_overlay.RegimeFilterConfig` existe toujours, mais il **ne constitue pas** le vrai durcissement “rates shock” P1.

Le vrai P1 est porté par le stack :

- `config.yaml`
- `service/market/regime_manager.py`
- `backtesting/risk_bridge.py`
- `risk_management/regime_apply.py`

---

## 4.3 Live pipeline

### Verdict
**Oui, implémenté et branché.**

### Preuves code

- `risk_management/cli.py:874-884`  
  Le snapshot de régime live est résolu puis appliqué à `RiskConfig`.

- `risk_management/cli.py:931-1103`  
  Si le snapshot interdit les nouvelles entrées, le pipeline n’en construit pas.

- `run_execution.py:917-979`  
  Le snapshot de régime est aussi propagé au moteur d’exécution via `ExecutionConfig.entry_mode`.

- `execution_engine/market_regime_preflight.py:50-57`  
  Le mapping vers les modes d’exécution est explicite :
  - `normal`
  - `close_only`
  - `cash_only`
  - `capital_preservation`

### Lecture fonctionnelle

Le durcissement “rates shock” n’est donc pas seulement analytique ; il est capable de :

- réduire le risque
- réduire l’exposition brute
- baisser le nombre de positions
- resserrer les caps ligne/secteur
- bloquer les nouvelles entrées selon le mode

### Conclusion P1.4

Le régime durci “rates shock” est **implémenté des deux côtés**.

---

## Tests exécutés pendant la revue

## Tests ciblés P1

Exécutés avec succès fonctionnel :

- `tests/test_circuit_breaker.py`
- `tests/test_live_pipeline_guards.py`
- `tests/test_risk_ml_weight_gate.py`
- `tests/test_risk_regime_apply.py`
- `tests/test_market_regime.py`

Une première exécution a remonté un échec sur le **seuil global de coverage du dépôt**, mais **pas** sur les fonctionnalités testées elles-mêmes. Une relance avec `--cov-fail-under=0` a confirmé que les tests ciblés passaient bien.

## Test backtest ML gate

Exécuté avec succès :

- `tests/test_backtesting.py -k "enforce_ml_coverage_gate_fails_fast_for_pipeline or capital_preset_applies_pipeline_defaults"`

Cela confirme notamment :

- le **fail-fast du gating ML** côté backtest pipeline
- l’**application des defaults pipeline issus des presets**

---

## Conclusion finale

### Réponse opérationnelle

Les 4 points **P1** de l’audit sont désormais **bien implémentés** dans le code :

1. **Drawdown breaker portefeuille** → oui
2. **Vol targeting** → oui
3. **Gating dur couverture ML** → oui
4. **Régime “rates shock” durci** → oui

### Réserve principale

La seule réserve pratique porte sur la distinction entre :

- **pipeline live complet** : robuste, bien branché
- **runner d’exécution live isolé (`run_execution.py`)** : drawdown breaker présent mais moins convaincant s’il est évalué seul sans historique de high-water mark persisté

### Conclusion de revue

Si l’objectif est de savoir si le **P1 demandé par l’audit** est bien passé du stade “recommandation” au stade “implémentation effective”, la réponse est :

> **Oui, globalement P1 est bien en place côté backtest pipeline et côté live pipeline.**

Avec la réserve suivante :

> le **drawdown breaker live** est surtout solide dans le **pipeline risk live**, davantage que dans le runner d’exécution isolé.

