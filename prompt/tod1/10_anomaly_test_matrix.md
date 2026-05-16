# 10 — Matrice Anomalie → Correctif → Test(s) → Sprint — Alpha Trade

> **Date** : mai 2026 | ✅ = Confirmé RÉSOLU par vérification directe du code source

---

## Matrice complète

| ID | Titre | Sévérité | Statut | Correctif | Tests | Sprint |
|---|---|---|---|---|---|---|
| A-001 | max_positions 10 vs "3 lignes" | P1 | ✅ **RÉSOLU Sprint S1** | `risk_max_positions: 3`, `min_notional: 500.0` dans `capital_0_2000_eur` | `test_capital_preset_risk_overrides.py` (5 nouveaux tests) | — |
| A-002 | Noms tables obsolètes lineage matrix | P1 | ✅ **RÉSOLU Sprint S1** | LINEAGE_SPEC corrigé, MD régénéré, CI `--check` vert | `test_data_lineage_autogen.py` (7/7 pass) | — |
| A-003 | model_predictions absence governance ML | P1 | ✅ **RÉSOLU** | `selected_model`, `decision_threshold`, `calibration_method`, `signal_label` présents dans `model_predictions.sql:8-11` + persistés par `db_registry.py:336-363` | `test_model_factory_db_registry.py` | — |
| A-004 | vectorbt mention obsolète DOC_TECHNIQUE | P1 | ✅ **RÉSOLU Sprint S1** (résidu argparse corrigé) | `backtesting/cli/_impl.py:67` description mise à jour | `test_doc_provider_alignment.py` | — |
| A-005 | CA provider ambigu (Alpaca vs EODHD) | P1 | ✅ **RÉSOLU** | Règle documentée : `DOC_FONCTIONNELLE.md:246` + `data_lineage_matrix.md §7:109-111` + factory `corporate_actions/provider.py:402-432` | `test_corporate_actions.py` | — |
| A-006 | PDT rule off sur comptes margin ≥ 25k$ | P2 | ✅ **RÉSOLU Sprint S2** | `pdt_rule: "auto"` sur 3 presets margin (`capital_25001_50000`, `capital_50001_100000`, `capital_100001_plus`) | `test_capital_preset_risk_overrides.py` + `test_execution_config.py` (6 nouveaux) | — |
| A-007 | min_close < 10$ sur presets intermédiaires | P2 | ✅ **RÉSOLU Sprint S2** | `selector_min_close: 10.0` sur capital_0_5000 (was 5.0), capital_5001_10000 (was 7.0), capital_10001_25000 (was 8.0) | `test_capital_preset_risk_overrides.py` (1 nouveau) | — |
| A-008 | Spreads IEX biaisés (~50 bps vs NBBO réel) | P2 | ✅ **RÉSOLU Sprint S4** (doc) | `doc/dataIntegrityEngine.md §3.4` : biais ~50 bps documenté, mitigation `max_spread_bps_iex=65` + `min_quote_size=100`, `DOC_FONCTIONNELLE.md §2.3` corrigé | `test_strict_filter_profiles.py` | S4 |
| A-009 | model_predictions pas d'unicité symbol/date | P2 | ✅ **RÉSOLU** | `UNIQUE KEY uq_symbol_date_run` présent (`model_predictions.sql:14`) + `ON DUPLICATE KEY UPDATE` | `test_model_factory_db_registry.py` | — |
| A-010 | ParquetCache non branché | P2 | ✅ **RÉSOLU Sprint S3** | `--use-cache` ajouté dans CLI `backtesting run` — 3x–10x vitesse backtests > 2 ans | `test_backtesting.py` | S3 |
| A-011 | analytics/statistical_validation non branchés | P2 | ✅ **RÉSOLU Sprint S3** | `--bootstrap-samples N` + `--sensitivity-analysis` exposés en CLI | `test_backtesting.py` | S3 |
| A-012 | SSL MySQL absent | P2 | ✅ **RÉSOLU** | `_read_ssl_connect_args()` dans `database/connection.py:97-111` — TLS activé si `DB_SSL_CA_PATH` défini | `test_connection.py` | — |
| A-013 | Pas d'alerting externe automatique | P2 | ✅ **RÉSOLU Sprint S3** | Email déclenché sur `circuit_breaker_fired` + `kill_switch_activated` via `NotificationService` SMTP | `test_ihm_notifications.py` | S3 |
| A-014 | auto_rebalance off → dérive silencieuse | P2 | ✅ **RÉSOLU Sprint S3** | Bandeau warn IHM si diffs réconciliation non résolus (`BLOCKED`, `MANUAL_REVIEW`) depuis > 24h | `test_execution_engine_reconciliation.py` | S3 |
| A-015 | Market cap stale TTL non alerté | P2 | ✅ **RÉSOLU Sprint S3** | Warning IHM si > 30% symboles avec `market_cap_refreshed_at` > 45 jours | `test_alpha_scanner.py` | S3 |
| A-016 | PDT rule commentaire absent (cash comptes) | P2 | ✅ **RÉSOLU Sprint S1** | Commentaire ajouté sur 4 presets cash dans `config/capital_presets.yaml` | `test_cash_presets_have_pdt_off` (nouveau) | — |
| A-017 | fill_timeout insuffisant lors de gap | P2 | ✅ **RÉSOLU Sprint S2** | `fill_timeout_seconds: 180` (was 120) dans `execution_engine/config.py:85` | `test_execution_config.py` (3 nouveaux) | — |
| A-018 | §1.3 DOC_FONCTIONNELLE step 1 = alpaca | P3 | ✅ **RÉSOLU** | `DOC_FONCTIONNELLE.md:37` nomme EODHD comme provider primaire | `test_doc_provider_alignment.py` | — |
| A-019 | Stooq apikey conditionnelle non testée | P3 | ✅ **RÉSOLU Sprint S4** | Docstring `service/stooq/clientStooq.py` + test `test_stooq_provider_works_without_api_key` — URL sans `apikey` si var absente | `test_macro_providers.py` (1 nouveau) | S4 |
| A-020 | yields désactivés avec provider eodhd | P3 | ✅ **RÉSOLU Sprint S4** (doc) | `doc/dataIntegrityEngine.md §3.3` : tableau quota EODHD par composant — `yields.enabled: false` → Stooq `^TNX`, pas EODHD | Aucun test | S4 |
| A-021 | Pas de PnL quotidien IHM | P3 | ✅ **RÉSOLU Sprint S4** | `compute_daily_pnl()` + `_render_pnl_widget()` section 0 Overview — via `broker_positions_snapshots.unrealized_pnl` | `test_pages_overview.py` (3 nouveaux) | S4 |
| A-022 | Walk-forward limité poids sentiment | P3 | ✅ **RÉSOLU Sprint S4** | `walk_forward_risk_params(returns, param_grid)` — grid-search ATR period / Kelly fraction / correlation threshold, 3 métriques | `test_weights_calibration.py` (5 nouveaux) | S4 |
| A-023 | test_data_lineage_autogen non activé CI | P3 | ✅ **RÉSOLU Sprint S4** (confirmé) | `pytest.ini testpaths = tests` inclut automatiquement le fichier — 7 tests verts confirmés | `test_data_lineage_autogen.py` | S4 |
| A-024 | prompt/ structuration partielle | P3 | ✅ **RÉSOLU Sprint S4** | `prompt/archive/` créé — 13 sous-dossiers historiques (tod/, iex/, execution/, backtest/, etc.) déplacés | Aucun test | S4 |
| A-025 | Compression logs insuffisante | P3 | ✅ **RÉSOLU Sprint S3** | `TimedRotatingFileHandler` quotidien + compression gzip automatique + max 30 fichiers | `test_common_utils.py` | S3 |
| A-026 | test_import_alpaca_bar_noop non documenté | P3 | ✅ **RÉSOLU Sprint S4** (doc) | Référencé dans `doc/dataIntegrityEngine.md §11` — no-op contrôlé quand `bars_provider != 'alpaca'` | `test_import_alpaca_bar_noop.py` | S4 |
| A-027 | Walk-forward : pas de bornes business poids | P3 | ✅ **RÉSOLU Sprint S3** | `validate_walk_forward_weights()` bornes [0.05, 0.40] — clip + WARNING, mode strict `ValueError` | `test_weights_calibration.py` (5 tests S3) | S3 |

---

## Détail des tests prioritaires P1 actifs

> ⚠️ **Toutes les anomalies P1/P2 sont maintenant résolues** après Sprint S4. Les 27 anomalies du registre sont toutes ✅ RÉSOLU.

---

## Récapitulatif Sprint S4 — Anomalies résolues

### A-019 ✅ — `test_stooq_provider_works_without_api_key` — RÉSOLU Sprint S4

**Résolution** : docstring `clientStooq.py` clarifiée — Stooq est gratuit sans inscription, `STOOQ_API_KEY` optionnelle. Test ajouté :
```python
# test_macro_providers.py
test_stooq_provider_works_without_api_key()  # URL sans 'apikey' quand var env absente
```

### A-020 ✅ — Documentation quota EODHD — RÉSOLU Sprint S4 (doc)

**Résolution** : `doc/dataIntegrityEngine.md §3.3` ajouté — tableau par composant (bulk EOD, VIX macro, corporate actions, per-symbol fallback). Clarifie que `yields.enabled: false` → Stooq `^TNX`, pas EODHD.

### A-021 ✅ — Widget PnL quotidien IHM — RÉSOLU Sprint S4

**Résolution** : `compute_daily_pnl()` + `_render_pnl_widget()` dans `ihm/pages/overview.py` section 0. `get_daily_pnl_data()` dans `ihm/services/queries.py`. Tests ajoutés :
```python
# test_pages_overview.py
test_compute_daily_pnl_with_positions()      # PnL + % calculés correctement
test_compute_daily_pnl_zero_positions()      # gracieux si paper trading sans allocation
test_compute_daily_pnl_negative_pnl()        # PnL négatif géré correctement
```

### A-022 ✅ — Walk-forward paramètres risk — RÉSOLU Sprint S4

**Résolution** : `walk_forward_risk_params(returns_series, param_grid)` ajouté dans `backtesting/walk_forward.py`. Grid-search Sharpe/Sortino/hit-rate. `RiskParamResult` dataclass. Tests ajoutés :
```python
# test_weights_calibration.py
test_walk_forward_risk_params_returns_best_combo_sharpe()   # best combo sur dataset test
test_walk_forward_risk_params_sortino_metric()              # metric='sortino'
test_walk_forward_risk_params_hit_rate_metric()             # metric='hit_rate'
test_walk_forward_risk_params_raises_on_unknown_metric()    # ValueError metric inconnu
test_walk_forward_risk_params_raises_on_too_few_observations()  # ValueError obs insuffisantes
```

### A-023 ✅ — Lineage test CI confirmé — RÉSOLU Sprint S4 (confirmé)

**Résolution** : `pytest.ini testpaths = tests` inclut automatiquement `test_data_lineage_autogen.py`. Confirmé 7/7 tests verts. Référencé dans `doc/dataIntegrityEngine.md §11`.

### A-024 ✅ — Archivage prompts — RÉSOLU Sprint S4

**Résolution** : `prompt/archive/` créé. 13 sous-dossiers déplacés (tod/, iex/, execution/, backtest/, dataIntegrityEngine/, ml/, parttern/, refactor/, risk/, screener/, selector/, sentiment/, fix_swing/). Seuls `prompt/tod1/` et les fichiers racine conservés.

### A-026 ✅ — Test no-op documenté — RÉSOLU Sprint S4 (doc)

**Résolution** : `test_import_alpaca_bar_noop.py` référencé dans `doc/dataIntegrityEngine.md §11` (section "Ce que ces tests couvrent bien") avec description du comportement no-op contrôlé.

### A-008 ✅ — Spreads IEX documentés — RÉSOLU Sprint S4 (doc)

**Résolution** : `doc/dataIntegrityEngine.md §3.4` ajouté — tableau biais ~50 bps IEX, mitigation `max_spread_bps_iex=65` + `min_quote_size=100`. `DOC_FONCTIONNELLE.md §2.3` : `spread_bps <= 40` (corrigé depuis 25 bps).

---

## Détail des tests P1/P2 RÉSOLUS ✅

### A-001 ✅ — `test_capital_preset_risk_overrides.py` — RÉSOLU Sprint S1

**Résolution** : 5 nouveaux tests ajoutés et passent tous. `risk_max_positions: 3`, `min_notional: 500.0` confirmés.

Tests ajoutés :
```python
test_positions_notional_solvency()          # max_pos × min_notional ≤ 0.95 × max_equity
test_micro_account_max_positions_coherent() # capital_0_2000_eur.max_positions ≤ 5
test_micro_account_min_notional_viable()    # capital_0_2000_eur.min_notional ≥ 400 USD
test_positions_increase_with_account_size() # monotonie des positions entre tranches
test_cash_presets_have_pdt_off()            # pdt_rule='off' sur tous les presets cash
```

---

### A-002 ✅ — `test_data_lineage_autogen.py` — RÉSOLU Sprint S1

**Résolution** : `scripts/generate_data_lineage.py` LINEAGE_SPEC corrigé :
- `execution_orders` → `execution_order_requests` + `execution_broker_orders`
- `execution_audit_events` → `execution_events`

`doc/data_lineage_matrix.md` régénéré. `test_repo_lineage_matrix_is_in_sync` passe. 7/7 tests verts.

---

### A-003 ✅ — `test_model_factory_db_registry.py` — RÉSOLU (avant Sprint S1)

**Résolution confirmée** : `model_predictions.sql:8-11` contient les 4 colonnes. `db_registry.py:336-363` les persiste. Tests verts.

---

### A-004 ✅ — `test_doc_provider_alignment.py` — RÉSOLU Sprint S1

**Résolution** : `backtesting/cli/_impl.py:67` : `description="Backtest intégré Alpha Trade (simulateur custom PIT)"`. Plus aucun résidu "vectorbt".

---

### A-005 ✅ — `test_corporate_actions.py` — RÉSOLU (avant Sprint S1)

**Résolution confirmée** : Factory `build_corporate_action_provider()` correctement implémentée. Tests de non-régression à conserver en CI.

---

### A-016 ✅ — `test_cash_presets_have_pdt_off` — RÉSOLU Sprint S1

**Résolution** : 4 presets cash annotés avec commentaire explicatif. Test de régression ajouté dans `test_capital_preset_risk_overrides.py`.

---

### A-006 ✅ — `test_margin_presets_have_pdt_auto` — RÉSOLU Sprint S2

**Résolution** : `execution_pdt_rule: "auto"` appliqué sur les 3 presets margin. Tests ajoutés :
```python
# test_capital_preset_risk_overrides.py
test_margin_presets_have_pdt_auto()             # tous les presets margin ont pdt_rule='auto'

# test_execution_config.py — classe TestPDTRuleMarginDrawdown
test_pdt_auto_margin_equity_above_threshold_no_block()  # equity > 25k$ → pas de blocage
test_pdt_auto_margin_equity_below_threshold_blocks()    # equity < 25k$ → blocage PDT
test_pdt_auto_margin_equity_at_threshold_no_block()     # equity = 25k$ = seuil exclusif
test_pdt_off_margin_never_blocks()              # pdt=off sur margin → jamais bloqué
test_pdt_cash_account_never_blocks()            # cash account → effective_pdt='off'
```

---

### A-007 ✅ — `test_all_presets_selector_min_close_gte_10` — RÉSOLU Sprint S2

**Résolution** : `selector_min_close: 10.0` appliqué sur capital_0_5000 (was 5.0), capital_5001_10000 (was 7.0), capital_10001_25000 (was 8.0). Test ajouté :
```python
# test_capital_preset_risk_overrides.py
test_all_presets_selector_min_close_gte_10()    # tous les presets ont min_close >= 10.0
```

---

### A-017 ✅ — `test_fill_timeout_default_is_180_seconds` — RÉSOLU Sprint S2

**Résolution** : `fill_timeout_seconds: 180` dans `execution_engine/config.py:85` (was 120). Tests ajoutés :
```python
# test_execution_config.py — classe TestFillTimeout
test_fill_timeout_default_is_180_seconds()   # valeur par défaut 180s
test_fill_timeout_configurable_for_live()    # configurable à 300s pour live
test_fill_timeout_must_be_positive()         # validation > 0
```

