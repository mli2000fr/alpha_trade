# 10 — Matrice traçable Anomalie → Correctif → Test(s) → Sprint

> Pour chaque anomalie : objectif test, type, fichier(s) probable(s),
> scénario Given/When/Then, fixtures, oracle, régression empêchée.

## Légende types
- **U** = unitaire, **I** = intégration, **N** = non-régression, **E** = E2E/IHM,
  **D** = data quality, **S** = SQL/persistance/migrations,
  **C** = configuration, **P** = parité backtest/live.

---

## A-001 — risk_per_trade micro agressif

| Champ | Valeur |
|---|---|
| Objectif | Garantir que `risk_per_trade_pct × risk_max_positions ≤ risk_max_drawdown_pct / 2` pour les tranches 0–5 k$. |
| Type / Priorité | C / haute |
| Fichier | `tests/test_capital_preset_risk_overrides.py` (étendre) |
| Given | Preset `capital_0_2000_eur`, `capital_0_5000` chargés via `common.capital_presets`. |
| When | Calcul `risk_per_trade_pct * risk_max_positions`. |
| Then | Résultat ≤ `risk_max_drawdown_pct / 2`. |
| Fixtures | `capital_presets.yaml` complet. |
| Oracle | Inégalité numérique stricte. |
| Régression empêchée | Augmentation accidentelle du levier risk-per-trade. |
| Existant | Test couvre la monotonie ; étendre cas micro. |
| Sprint | S1 |

## A-002 — Double point d'entrée d'exécution

| Champ | Valeur |
|---|---|
| Objectif | `python -m execution_engine` émet `DeprecationWarning` pour `run`; `cancel-all` reste natif. |
| Type | U + I |
| Fichier | `tests/test_execution_cli_cancel_all.py` (étendre) + nouveau `tests/test_run_execution_vs_facade_parity.py` |
| Given | Façade lancée avec args `run`. |
| When | Exécution. |
| Then | Warning capturé, exit code identique au launcher canonique sur cas équivalents. |
| Régression | Divergence silencieuse entre les deux chemins. |
| Sprint | S1 |

## A-003 — Ordre `event_sentiment` non verrouillé

| Champ | Valeur |
|---|---|
| Objectif | `signal_aggregator` refuse si `news_ingestion_at > relevance_backfill_at`. |
| Type | I |
| Fichier | nouveau `tests/test_event_sentiment_ordering_guard.py` |
| Given | DB seedée avec checkpoints incohérents. |
| When | Appel `signal_aggregator.run()`. |
| Then | `RuntimeError("relevance backfill not up-to-date")`. |
| Fixtures | seed `event_sentiment_checkpoints` table. |
| Régression | Features sentiment partielles silencieuses. |
| Sprint | S2 |

## A-004 — Spread IEX biaisé

| Champ | Valeur |
|---|---|
| Objectif | Produire et exposer `quote_iex_vs_consolidated_bps`. |
| Type | D |
| Fichier | nouveau `tests/test_quote_iex_vs_consolidated_bias.py` |
| Given | Quote IEX + close consolidé EODHD pour 5 small caps + 5 large caps. |
| When | Calcul écart spread. |
| Then | Métrique persistée, exposée IHM, threshold alerting sur écart > 200 bps. |
| Sprint | S2 |

## A-005 — Réconciliation J+1

| Champ | Valeur |
|---|---|
| Objectif | Comparer positions internes vs statement broker J+1, alerter si divergence. |
| Type | I + E |
| Fichier | `tests/test_broker_statement_reconciliation.py` (étendu) + nouveau `tests/test_pages_execution_tca.py` |
| Given | Statement fictif (CSV Alpaca) + state interne. |
| When | Job reconcile lancé. |
| Then | Divergence chiffrée, alert si > 1 bps. |
| Sprint | S3 |

## A-006 — Kelly désactivé partout

| Champ | Valeur |
|---|---|
| Objectif | Décider activation conditionnelle ≥ 25k$ après calibration, documenter "expérimental". |
| Type | U |
| Fichier | `tests/test_kelly_sizer.py` (étendu) |
| Sprint | S6 |

## A-007 — `macro_provider: eodhd` défaut

| Champ | Valeur |
|---|---|
| Objectif | Default `composite` (stooq primaire + eodhd fallback). |
| Type | C + I |
| Fichier | `tests/test_macro_providers.py` (étendu) |
| Sprint | S6 |

## A-008 — `min_close=10$` micro-compte trop restrictif

| Champ | Valeur |
|---|---|
| Objectif | Tests univers selector ≥ N tickers par tranche en regime neutre. |
| Type | D |
| Fichier | `tests/test_capital_preset_universe_yield.py` (étendre) |
| Given | Univers historiques 3 régimes (bull/range/bear) sur 6 mois. |
| Then | `universe_size_p25 ≥ 30` pour 0–2k€. |
| Sprint | S1 |

## A-009 — Parité backtest/live full stack

| Champ | Valeur |
|---|---|
| Objectif | Replay 10 jours live paper → backtest reproduit à ε avec sentiment+ML+macro. |
| Type | P |
| Fichier | nouveau `tests/test_parity_backtest_live_full_stack.py` |
| Given | Snapshot 10 jours `execution_runs` + features sentiment + predictions ML. |
| When | Backtest piloté par mêmes inputs PIT. |
| Then | Écart PnL ≤ 5 bps, écart positions ≤ 1 ticker. |
| Sprint | S4 |

## A-010 — Doc POCs non distincts

| Champ | Valeur |
|---|---|
| Objectif | Bandeau `> ⚠️ POC` obligatoire sur docs POC. |
| Type | U |
| Fichier | `tests/test_doc_index_and_links.py` (étendu) |
| Sprint | S7 |

## A-011 — Fallback levels weights_calibration

| Champ | Valeur |
|---|---|
| Objectif | Vérifier que chaque niveau est consulté en ordre exact + niveau choisi tracé. |
| Type | U |
| Fichier | `tests/test_weights_calibration.py` (étendu) |
| Sprint | S6 |

## A-012 — SMTP non configuré silencieux

| Champ | Valeur |
|---|---|
| Objectif | Bannière IHM + warning startup. |
| Type | E |
| Fichier | nouveau `tests/test_ihm_notifications_smtp_missing_banner.py` |
| Sprint | S6 |

## A-013 — Fallback OHLCV silencieux

| Champ | Valeur |
|---|---|
| Objectif | Alert `provider_fallback_triggered=true` + bandeau IHM + email. |
| Type | I |
| Fichier | `tests/test_eodhd_provider_switch.py` (étendu) |
| Sprint | S2 |

## A-014 — `max_anomaly_count` inversé

| Champ | Valeur |
|---|---|
| Objectif | Monotonie cohérente : plus le compte est petit, plus on tolère peu d'anomalies. |
| Type | C |
| Fichier | `tests/test_capital_presets.py` (étendu) |
| Sprint | S1 |

## A-015 — Pas de verrou pipeline N+1 si N≠SUCCESS

| Champ | Valeur |
|---|---|
| Objectif | IHM désactive étape N+1 tant que N≠SUCCESS. |
| Type | E |
| Fichier | nouveau `tests/test_ihm_pipeline_state_machine_lock.py` |
| Sprint | S3 |

## A-016 — Doctrine broker failover opaque

| Champ | Valeur |
|---|---|
| Objectif | Page IHM "Brokers" + runbook explicite. |
| Type | E |
| Fichier | nouveau `tests/test_ihm_brokers_page_failover_doctrine.py` |
| Sprint | S5 |

## A-017 — Coverage non bloquante

| Champ | Valeur |
|---|---|
| Objectif | Gate ≥ 80 % sur modules critiques. |
| Type | C |
| Fichier | `pyproject.toml` / `pytest.ini` + CI |
| Sprint | S7 |

## A-018 — Couplage Windows fort

| Champ | Valeur |
|---|---|
| Objectif | Test Linux nightly. |
| Type | C |
| Sprint | S8 |

## A-019 — Quota EODHD partagé

| Champ | Valeur |
|---|---|
| Objectif | Tableau de bord "EODHD quota by feature". |
| Type | E |
| Fichier | `tests/test_pages_overview.py` (étendu) |
| Sprint | S2 |

## A-020 — Signature artefacts ML

| Champ | Valeur |
|---|---|
| Objectif | SHA256 manifest signé + vérif au load. |
| Type | I |
| Fichier | `tests/test_ml_artifacts_backup.py` (étendu) |
| Sprint | S5 |

## A-021 — Preflight non bloquant en simulate

| Champ | Valeur |
|---|---|
| Objectif | Preflight bloque WARN en simulate. |
| Type | U |
| Fichier | `tests/test_execution_engine_executor.py` (étendu) |
| Sprint | S5 |

## A-022 — Schéma `stock_bars_daily` mono-source

| Champ | Valeur |
|---|---|
| Objectif | Migration optionnelle `(symbol,date,data_source)`. |
| Type | S |
| Fichier | nouveau `tests/test_data_adjustment_multisource_migration.py` |
| Sprint | S8 |

## A-023 — Runbook incident sentiment provider

| Champ | Valeur |
|---|---|
| Objectif | Doc + check IHM. |
| Type | E |
| Sprint | S6 |

## A-024 — Pas de gel IHM en live

| Champ | Valeur |
|---|---|
| Objectif | Bandeau + désactivation actions destructrices. |
| Type | E |
| Fichier | nouveau `tests/test_ihm_live_mode_locks_destructive_actions.py` |
| Sprint | S3 |

## A-025 — Convention corrélation

| Champ | Valeur |
|---|---|
| Objectif | Documenter close split-adj vs returns dividend-adj + tester les deux. |
| Type | U |
| Fichier | `tests/test_correlation_filter.py` (étendu) |
| Sprint | S4 |

## A-026 — DST market_calendar

| Champ | Valeur |
|---|---|
| Objectif | Test propriété passage DST. |
| Type | U |
| Fichier | `tests/test_market_calendar.py` (étendu) |
| Sprint | S7 |

## A-027 — Pre-check quota EODHD

| Champ | Valeur |
|---|---|
| Objectif | Estimer calls vs remaining_quota, abort si marge insuffisante. |
| Type | I |
| Fichier | `tests/test_clientEodhd.py` (étendu) |
| Sprint | S2 |

## A-028 — Renommage `min_relative_strength_index`

| Champ | Valeur |
|---|---|
| Objectif | Alias + déprecation. |
| Type | U |
| Fichier | `tests/test_selector_alpha_scanner.py` (étendu) |
| Sprint | S1 |

## A-029 — Documenter `max_drawdown_pct` par tranche

| Champ | Valeur |
|---|---|
| Objectif | Docstring + lien doc. |
| Type | U doc |
| Sprint | S6 |

## A-030 — Oracle total return MTM+ledger

| Champ | Valeur |
|---|---|
| Objectif | Test 5 tickers à dividende récurrent vs ground truth externe. |
| Type | D |
| Fichier | `tests/test_backtest_total_return_with_dividends.py` (étendu) |
| Sprint | S4 |

---

## Synthèse couverture test

| Statut | Compte |
|---|---|
| Nouveau test à créer | 11 |
| Test existant à étendre | 17 |
| Aucun test (doc/config only) | 2 |

**Toutes les anomalies P0/P1 ont au moins un test précis associé.** ✅

