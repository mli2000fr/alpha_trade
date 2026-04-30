# Synthèse — Sources de données alpha_trade après Phase 6 EODHD

> **Date** : 2026-04-29 (post smoke EODHD All-In-One + patch IHM provider switch).
> **Référence** : `prompt/iex/plan_eodhd.md`, `prompt/iex/phase4_runbook.md`, `doc/data_lineage_matrix.md`.

---

## A. Sources de données — état réel

| Source | Module(s) clients | Tables alimentées | Réellement utilisé en prod ? | Provenance |
|---|---|---|---|---|
| **Alpaca Market Data (IEX)** | `service/alpaca/clientAlpaca.py`, `import_alpaca_bar.py`, `sync_latest_quotes.py`, `import_alpaca_assets.py` | `stock_bars`, `stock_bars_daily`, `stock_metadata`, `stock_quote_snapshots` | ✅ OUI — pipeline daily si `bars_provider=alpaca` (défaut historique) | Présent depuis l'origine |
| **Alpaca Trading API** | `execution_engine/`, `risk_management/` | `execution_orders`, `execution_positions`, `execution_runs` | ✅ OUI — broker exclusif (jamais migré) | — |
| **Alpaca Corporate Actions API** | `corporate_actions/provider.py::AlpacaCorporateActionProvider` | `corporate_actions_events` | ✅ OUI si `bars_provider=alpaca` (factory `build_corporate_action_provider`) | — |
| **EODHD `/eod-bulk-last-day/US`** | `dataIntegrityEngine/import_eodhd_bar.py` (Phase 3) | `stock_bars`, `stock_bars_daily` | 🟡 PRÊT — actif si `bars_provider=eodhd` (cutover non encore fait) | Phase 3 |
| **EODHD `/eod/{ticker}.US`** | `backfill_eodhd_history.py` + recovery dans `import_eodhd_bar.py` | `stock_bars`, `stock_bars_daily` | 🟡 PRÊT — backfill historique sur demande | Phase 5 |
| **EODHD `/splits/{ticker}.US`** | `service/eodhd/clientEodhd.py` (cache 7j) | utilisé pour reconstruction split-only + corporate_actions | 🟡 PRÊT (smoke 200 OK 2026-04-29) | Phase 2 |
| **EODHD `/div/{ticker}.US`** | `corporate_actions/provider.py::EodhdCorporateActionProvider` | `corporate_actions_events` | 🟡 PRÊT — actif si `bars_provider=eodhd` (factory) | Phase 6 |
| **Finnhub** | `dataIntegrityEngine/update_sector.py`, `sync_earnings_calendar.py` | `stock_metadata.sector`, `stock_metadata.market_cap`, `earnings_calendar` | ✅ OUI — hebdo / daily | — |
| **Stooq** | `service/stooq/clientStooq.py` ; `dataIntegrityEngine/cross_check_stooq.py` | `cleaning_audit_runs.cross_check_anomalies` (JSON) | ⚠️ **Activé seulement quand `bars_provider=eodhd`** (Phase 4 §5.7). En mode Alpaca par défaut → toujours code mort. | Présent depuis longtemps mais **non câblé tant que provider=alpaca** |
| **Yahoo (yfinance)** | `corporate_actions/cross_check_yahoo.py` | annotation cross-check dans `corporate_actions_audit_runs` | ✅ OUI — toujours actif en triangulation dividendes (cf. `corporate_actions/cli.py::_run_cross_check_yahoo`) | — |
| **Alpaca News** | `event_sentiment/` | `news_articles`, `sentiment_scores` | ✅ OUI | — |
| **Tiingo** | (dossier `service/tiingo/` supprimé Phase 6) | aucune | ❌ NON — n'a jamais existé en prod | Supprimé 2026-04-29 |

---

## B. Quels usages, par couche

| Couche | Source primaire (provider=alpaca) | Source primaire (provider=eodhd) | Cross-check |
|---|---|---|---|
| **Univers / metadata** | Alpaca Assets + Finnhub | **idem (inchangé)** | — |
| **OHLCV daily ingestion** | Alpaca/IEX | **EODHD bulk** (1 call = 100 cost) | Stooq best-effort (uniquement actif en mode eodhd) |
| **OHLCV historique long** | Alpaca/IEX (limité ~5 ans) | **EODHD `/eod`** (jusqu'à 30 ans) | — |
| **Quotes temps réel** | Alpaca/IEX | **Alpaca/IEX (inchangé)** — EODHD n'est pas RT | — |
| **Splits & dividendes** | Alpaca CA | **EODHD `/div` + `/splits`** | Yahoo (toujours appelé) + Alpaca en alternative |
| **Exécution / fills / portefeuille** | Alpaca | **Alpaca (inchangé)** | — |
| **Earnings calendar** | Finnhub | **Finnhub (inchangé)** | — |
| **News / sentiment** | Alpaca News + FinBERT | **idem** | — |
| **Indicateurs (RSI/ATR/VCP)** | calcul local | **calcul local** (refus de l'API `/technical/` EODHD) | — |

---

## C. Sources réellement utilisées vs cosmétiques

| Source | Verdict honnête |
|---|---|
| **Alpaca** | ✅ **Indispensable** : metadata + exécution + (avant EODHD) bars |
| **Finnhub** | ✅ **Indispensable** : seule source de `sector` + `market_cap` + earnings |
| **EODHD** | ✅ **Devient indispensable** dès cutover `bars_provider=eodhd` (en attente J+5 shadow + go/no-go audit) |
| **Yahoo** | ✅ **Réellement utilisé** : `cross_check_yahoo.py` est appelé dans `corporate_actions/cli.py:334,475` |
| **Stooq** | ⚠️ **Code mort tant que provider=alpaca**. Devient utile au cutover EODHD (Phase 4 §5.7 l'active dans `import_eodhd_bar.py`). Si tu restes sur Alpaca, Stooq n'est jamais appelé. |
| **Alpaca News** | ✅ **Utilisé** dans `event_sentiment/` |
| **Tiingo** | 🗑️ **Supprimé 2026-04-29** (code mort) |

---

## D. Procédure mise à jour pour lancer EODHD via IHM (après patch addendum)

| Avant le patch (cassé) | Après le patch (Phase 6 + addendum 2026-04-29) |
|---|---|
| IHM lance `import_alpaca_bar` → si `bars_provider=eodhd` devient no-op → **AUCUNE ingestion** | IHM résout dynamiquement : `bars_provider=alpaca` → `import_alpaca_bar` ; `=eodhd` → **`import_eodhd_bar --write`** |
| Backfill historique EODHD : ligne de commande uniquement | **✅ Exposé en étape auxiliaire B3** "Backfill historique EODHD" (options : years, symbols CSV, resume, write) |
| Audit go/no-go : ligne de commande | (idem CLI : `python scripts/eodhd_phase4_volume_audit.py --lookback-days 60`) |
| Corporate actions sync IHM disait "Alpaca uniquement" | ✅ Description mise à jour : routage automatique alpaca/eodhd via factory `build_corporate_action_provider` |

---

## D-bis. Audit complet de toutes les étapes IHM vs Phases EODHD

| # | Étape IHM (`pipeline_runner.py`) | Source réelle | Aligné EODHD ? |
|---|---|---|---|
| 1 | `import_alpaca_bar` (renommé "Import Bars (Alpaca / EODHD)") | Alpaca **OU** EODHD via routing dynamique `_resolve_bars_provider_for_ihm()` | ✅ |
| 2 | `data_sanitizer_daily` | lit `stock_bars` (toute provenance) | ✅ transparent |
| 3 | `stock_screener` | lit `stock_bars_daily` (toute provenance) | ✅ transparent |
| 4 | `sync_latest_quotes` | Alpaca RT (jamais migré, conforme plan) | ✅ |
| 5 | `sync_earnings_calendar` | Finnhub (inchangé) | ✅ |
| 6-10 | alpha_scanner, sentiment, signal_aggregator, ml_train, ml_predict | pure compute | ✅ |
| 11 | `risk_management` | Alpaca buying_power (jamais migré) | ✅ |
| 12 | `execution` | Alpaca broker (jamais migré) | ✅ |
| 13 | `corporate_actions_sync` | factory → Alpaca **OU** EODHD selon `bars_provider` ; Yahoo cross-check toujours appelé | ✅ |
| 14 | `corporate_actions_apply` | post-traitement local | ✅ |
| B1 | `import_alpaca_assets` | Alpaca (univers, conforme) | ✅ |
| B2 | `update_sector` | Finnhub (sector + market_cap) | ✅ |
| **B3** | **`eodhd_backfill_history`** *(ajouté addendum)* | **EODHD `/eod`** historique long, bookmark idempotent | ✅ NOUVEAU |

---

## E. Réponses aux questions opérationnelles

| Question | Réponse |
|---|---|
| EODHD limité à l'univers Alpaca éligible ? | **OUI** — `_get_active_tradable_symbols(session)` applique `build_eligible_stock_metadata_filters` (status=active, tradable, bars_available, asset_class=us_equity, history_status éligible). Bulk EODHD = ~50k entrées mais on n'écrit que les ~3000 du périmètre Alpaca. |
| "10 ans" par défaut sur import_bar ? | **N'existe pas en dur.** `import_alpaca_bar` est purement incrémental (pas de param `--years`). `import_eodhd_bar` traite J-1 uniquement. Seul `backfill_eodhd_history.py:71` a `DEFAULT_YEARS = 5` (override `--years 10` via CLI). |
| IHM sait lancer EODHD ? | **APRÈS patch addendum 2026-04-29 : OUI** — bascule transparente selon `config.yaml::market_data.bars_provider`. Aucun changement IHM côté utilisateur, juste éditer `config.yaml` puis l'IHM route automatiquement. |

---

## F. Coût API quotidien estimé en cible (provider=eodhd, ~3 000 symboles)

| Pipeline | Calls / jour | % quota 100k |
|---|---|---|
| Daily bulk + recovery | ~200 | 0.2 % |
| CA dividendes (sync J+1) | ~3 000 | 3.0 % |
| CA splits (cache 7j amorti) | ~430 | 0.4 % |
| **Total** | **~3 700** | **3.7 %** |

Backfill 5 ans one-shot : ~6 000 calls = 6 % d'un quota journalier.

---

## G. Tests cumulés EODHD (Phases 1 → 6 + addendum IHM)

| Suite | Tests |
|---|---|
| Phase 2 socle service | 52 |
| Phase 3 ingestion shadow | 8 |
| Phase 4 bascule + audit | 15 |
| Phase 5 backfill historique | 12 |
| Phase 6 corporate actions | 25 |
| Addendum 2026-04-29 — IHM provider switch | 5 |
| **Total EODHD + IHM** | **117** |

Non-régression projet : 109 / 109 ✅.


