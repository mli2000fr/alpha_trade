# Matrice Data Lineage — table ↔ producteur ↔ consommateurs (Phase 7.6)

> **Audience** : développeurs et opérateurs.
> **Objectif** : référencer pour chaque table métier qui l'écrit, qui la lit,
> et la criticité opérationnelle. Mise à jour requise à chaque ajout de table
> (cf. `doc/guide_add_new_table.md`).

> **Maintenance** : édité à la main pour l'instant (≤ 30 tables). À terme,
> auto-générer via `scripts/generate_data_lineage.py` (grep des
> `INSERT`/`SELECT` dans `database/repositories/`).

---

## Légende

- **Fréquence** : `daily` / `intraday` / `on-event` / `manual`.
- **Criticité** : `P1` (live trading bloque sans), `P2` (pipeline dégradé),
  `P3` (analytics / audit uniquement).

---

## 1. Données de marché

| Table | Producteur (CLI / module) | Consommateurs | Source upstream | Fréquence | Criticité |
|---|---|---|---|---|---|
| `stock_assets` | `dataIntegrityEngine.import_alpaca_assets` | screener, selector, ihm | Alpaca | daily | P1 |
| `stock_bars_daily` | `dataIntegrityEngine.import_alpaca_bar` | screener, selector, modelFactory, backtesting | Alpaca IEX | daily | P1 |
| `stock_bars` | `dataIntegrityEngine.import_alpaca_bar` (intraday) | execution_engine.tca | Alpaca IEX | intraday | P2 |
| `stock_quote_snapshots` | `dataIntegrityEngine.sync_latest_quotes` | selector (`spread_bps`) | Alpaca IEX | daily | P1 |
| `stock_metadata` | `dataIntegrityEngine.update_sector` | screener, selector (filtres market_cap, sector) | Finnhub | weekly | P2 |
| `earnings_calendar` | `dataIntegrityEngine.sync_earnings_calendar` | selector, risk_management (blackout) | Finnhub | daily | P2 |

## 2. Scoring & sélection

| Table | Producteur | Consommateurs | Source upstream | Fréquence | Criticité |
|---|---|---|---|---|---|
| `stock_scores` | `screener` | selector, risk_management, backtesting | computed | daily | P1 |
| `selector_alpha_candidates` | `selector.alpha_scanner` | risk_management, ihm | computed | daily | P1 |
| `screener_run_summaries` | `screener` | ihm (audit) | computed | daily | P3 |

## 3. Sentiment & ML

| Table | Producteur | Consommateurs | Source upstream | Fréquence | Criticité |
|---|---|---|---|---|---|
| `news_articles` | `event_sentiment.importer` | sentiment_pipeline | Alpaca News | daily | P2 |
| `sentiment_scores` | `event_sentiment.signal_aggregator` | risk_management | computed (FinBERT) | daily | P2 |
| `model_predictions` | `modelFactory.run_predict` | risk_management | computed (LightGBM/CatBoost/LSTM) | daily | P1 |
| `model_governance` | `modelFactory.champion_selection` | run_predict | computed | weekly | P1 |
| `model_metrics_full` | `modelFactory.evaluation` | governance, ihm | computed | weekly | P3 |
| `ml_drift_runs` *(Phase 7.4)* | `modelFactory.drift_monitor` | ops alerting | computed | daily | P2 |

## 4. Risk & exécution

| Table | Producteur | Consommateurs | Source upstream | Fréquence | Criticité |
|---|---|---|---|---|---|
| `risk_runs` | `risk_management` | execution_engine, ihm | computed | daily | P1 |
| `risk_decisions` | `risk_management` | execution_engine | computed | daily | P1 |
| `execution_runs` | `execution_engine.executor` | reconciliation, ihm, watcher | computed | daily | P1 |
| `execution_orders` | `execution_engine.executor` | reconciliation, tca | broker (Alpaca) | intraday | P1 |
| `execution_positions` | `execution_engine.executor` | risk_management (J+1 equity) | broker | intraday | P1 |
| `execution_audit_events` | `execution_engine.executor` | reconciliation | computed | on-event | P2 |
| `execution_kill_switch_runs` *(Phase 5.2.c)* | `execution_engine cancel-all` | watcher, ihm | computed | manual | P1 |
| `execution_locks` | watcher / executor | mutual exclusion | computed | on-event | P1 |
| `watcher_heartbeats` *(Phase 1.2)* | `watcher.protection_watcher` | ihm, alerting | computed | continuous | P1 |
| `shadow_drift_runs` *(Phase 7.7)* | `risk_management.shadow_compare` | ops review | computed | manual | P3 |

## 5. Corporate actions

| Table | Producteur | Consommateurs | Source upstream | Fréquence | Criticité |
|---|---|---|---|---|---|
| `corporate_actions_events` | `corporate_actions.engine` | reconciliation, accounting | Alpaca CA, Yahoo (cross-check) | daily | P1 |
| `corporate_actions_audit_runs` *(Phase 5.3.b)* | `corporate_actions.reconciliation` | ops | computed | daily | P2 |
| `portfolio_cash_ledger` | `corporate_actions.processors` | backtesting (`total_return_with_dividends`) | computed | on-event | P2 |

## 6. Backtesting & calibration

| Table | Producteur | Consommateurs | Source upstream | Fréquence | Criticité |
|---|---|---|---|---|---|
| `backtest_runs` | `backtesting.cli` | ihm | computed | manual | P3 |
| `weights_calibration_runs` *(Phase 7.2)* | `backtesting.weights_calibration` | risk_management (poids cible) | computed | weekly | P3 |
| `cleaning_audit_runs` | `dataIntegrityEngine.data_sanitizer_daily` | ops, ihm | computed | daily | P2 |
| `cleaning_audit_quotes_runs` *(Phase 3.1)* | `sync_latest_quotes` | ops | computed | daily | P2 |
| `cleaning_audit_earnings_runs` *(Phase 3.1)* | `sync_earnings_calendar` | ops | computed | daily | P3 |

---

## 7. Notes de couplages critiques

- **SPY = univers + calendrier** : la migration vers
  `pandas_market_calendars` (Phase 3.1) a découplé le calendrier ; SPY reste
  utilisé comme benchmark / univers ML.
- **`stock_metadata.market_cap`** : Finnhub free figé ; consommé avec TTL via
  `market_cap_refreshed_at` depuis Phase 3.
- **Convention `data_adjustment='split'`** matérialisée par CHECK SQL depuis
  Phase 1.1 sur `stock_bars` et `stock_bars_daily`.
- **Cross-check Stooq** *(Phase 7.3)* : best-effort, anomalies persistées
  dans `cleaning_audit_runs.cross_check_anomalies` (JSON).

---

**Réf.** : audit_global §7.6, §7.9 ; `doc/database.md` ; `doc/guide_add_new_table.md`.

