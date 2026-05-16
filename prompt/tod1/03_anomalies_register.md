# 03 — Registre des Anomalies — Alpha Trade

> **Date** : mai 2026 | P0 = critique bloquant | P1 = majeur | P2 = modéré | P3 = mineur/dette tech
>
> **Méthode de vérification** : chaque anomalie a été vérifiée par lecture directe du code source (SQL, Python, YAML). Les anomalies marquées ✅ RÉSOLU ont été confirmées résolues dans le code ; les faux positifs initiaux issus d'une lecture de la seule documentation ont été corrigés.

---

## Résumé du registre

| Total initial | Résolues (code vérifié) | Actives | P0 | P1 | P2 | P3 |
|---|---|---|---|---|---|---|
| 27 | 20 | 7 | 0 | 0 | 1 | 6 |

> **Sprint S1 livré** — 4 anomalies supplémentaires résolues : A-001 ✅, A-002 ✅, A-004-résidu ✅, A-016 ✅  
> **Sprint S2 livré** — 3 anomalies supplémentaires résolues : A-006 ✅, A-007 ✅, A-017 ✅  
> **Sprint S3 livré** — 7 anomalies supplémentaires résolues : A-010 ✅, A-011 ✅, A-013 ✅, A-014 ✅, A-015 ✅, A-025 ✅, A-027 ✅

---

## ~~Anomalies P1 (majeures) — actives~~ → Toutes résolues ✅ (après Sprint S1)

### A-001 ✅ — `capital_0_2000_eur` : `risk_max_positions: 10` incohérent — RÉSOLU (Sprint S1)
- **Sévérité initiale** : P1
- **Domaine** : Configuration / capital_presets
- **Résolution** : `config/capital_presets.yaml:16` — corrigé en `risk_max_positions: 3` et `risk_min_position_notional: 500.0`.
- **Tests ajoutés** : `test_capital_preset_risk_overrides.py` :
  - `test_positions_notional_solvency` — vérifie `max_positions × min_notional ≤ 0.95 × max_equity`
  - `test_micro_account_max_positions_coherent` — vérifie `max_positions ≤ 5` pour `capital_0_2000_eur`
  - `test_micro_account_min_notional_viable` — vérifie `min_notional ≥ 400 USD`
  - `test_positions_increase_with_account_size` — monotonie des positions entre tranches
- **Résultat test** : 13/13 passed ✅

---

### A-002 ✅ — `data_lineage_matrix.md` : noms de tables obsolètes (execution) — RÉSOLU (Sprint S1)
- **Sévérité initiale** : P1
- **Domaine** : Documentation / database
- **Résolution** : `scripts/generate_data_lineage.py` — LINEAGE_SPEC mis à jour :
  - `execution_orders` → `execution_order_requests` + `execution_broker_orders`
  - `execution_audit_events` → `execution_events`
  - PROVIDER_SPEC alpaca : `execution_orders` → `execution_broker_orders`
  - `doc/data_lineage_matrix.md` régénéré via `python scripts/generate_data_lineage.py`
- **Vérification CI** : `python scripts/generate_data_lineage.py --check` → exit 0 ✅
- **Tests** : `test_data_lineage_autogen.py` — 7/7 passed ✅, `test_repo_lineage_matrix_is_in_sync` passe ✅

---

## Anomalies P2 (modérées) — actives

### A-006 ✅ — PDT rule off sur comptes margin ≥ 25k$ — RÉSOLU (Sprint S2)
- **Sévérité initiale** : P2
- **Domaine** : Configuration / capital_presets / execution_engine
- **Résolution** : `config/capital_presets.yaml` — les 3 presets margin passés en `execution_pdt_rule: "auto"` :
  - `capital_25001_50000` (ligne 233)
  - `capital_50001_100000` (ligne 283)
  - `capital_100001_plus` (ligne 333)
- **Tests ajoutés** : `test_capital_preset_risk_overrides.py` :
  - `test_margin_presets_have_pdt_auto` — vérifie que tous les presets margin ont `pdt_rule='auto'`
- `test_execution_config.py` (5 nouveaux tests) :
  - `test_pdt_auto_margin_equity_above_threshold_no_block`
  - `test_pdt_auto_margin_equity_below_threshold_blocks`
  - `test_pdt_auto_margin_equity_at_threshold_no_block`
  - `test_pdt_off_margin_never_blocks`
  - `test_pdt_cash_account_never_blocks`
- **Résultat test** : ✅ Pass

---

### A-007 ✅ — `selector_min_close` sous le profil strict canonique — RÉSOLU (Sprint S2)
- **Sévérité initiale** : P2
- **Domaine** : Configuration / selector
- **Résolution** : `config/capital_presets.yaml` — tous les presets ayant `selector_min_close < 10.0` corrigés à `10.0` :
  - `capital_0_5000` : 5.0 → 10.0
  - `capital_5001_10000` : 7.0 → 10.0
  - `capital_10001_25000` : 8.0 → 10.0
- Aligné avec `STRICT_SWING_CASH_FILTERS.min_close = 10.0` (`core/filter_profiles.py:241`)
- **Tests ajoutés** : `test_capital_preset_risk_overrides.py` :
  - `test_all_presets_selector_min_close_gte_10` — vérifie `selector_min_close ≥ 10.0` sur tous les presets
- **Résultat test** : ✅ Pass

---

### A-008 — Quotes IEX biaisées pour le filtre spread_bps
- **Sévérité** : P2
- **Domaine** : dataIntegrityEngine / selector
- **Description** : `stock_quote_snapshots` provient toujours d'Alpaca IEX (même si `bars_provider=eodhd`). Alpaca IEX cite des spreads significativement plus larges (~50 bps) que le NBBO réel pour les mid-caps hors heures de trading. Cela peut faire rejeter des titres exécutables en réalité.
- **Preuve** : `doc/dataIntegrityEngine.md` en-tête : "spreads `stock_quote_snapshots` : toujours Alpaca IEX (~50 bps NBBO)"
- **Recommandation** : Utiliser `max_spread_bps_iex` (déjà défini dans le profil) comme valeur relâchée, documenter le biais dans le rapport d'audit de screens
- **Test à ajouter** : `test_eodhd_phase4_volume_audit.py` — étendre pour valider l'impact du biais IEX sur le taux de rejet spread

---

### A-010 ✅ — ParquetCache non branché par défaut — RÉSOLU (Sprint S3)
- **Sévérité initiale** : P2
- **Domaine** : backtesting
- **Résolution** : `backtesting/cli/_impl.py` — option `--use-cache` ajoutée à `_build_parser()` ; `_run_backtest()` instancie `ParquetCache(base_dir=output_dir/"cache")` si `args.use_cache=True`.
- **Tests ajoutés** : `test_backtesting.py::TestCLI::test_run_backtest_with_use_cache_flag_wires_parquet_cache`
- **Résultat test** : ✅ Pass

---

### A-011 ✅ — analytics.py et statistical_validation.py non branchés à la CLI — RÉSOLU (Sprint S3)
- **Sévérité initiale** : P2
- **Domaine** : backtesting
- **Résolution** : `backtesting/cli/_impl.py` — options `--bootstrap-samples` et `--sensitivity-analysis` ajoutées ; `_run_statistical_validation()` implémentée, appelée après le run principal si l'une des options est activée.
- **Tests ajoutés** : `test_backtesting.py::TestCLI` — tests `--bootstrap-samples` et `--sensitivity-analysis`
- **Résultat test** : ✅ Pass

---

### A-013 ✅ — Alerting automatique email sur circuit_breaker + kill_switch — RÉSOLU (Sprint S3)
- **Sévérité initiale** : P2
- **Domaine** : Observabilité
- **Résolution** :
  - `risk_management/circuit_breaker.py` : `_try_send_alert(event, payload)` injecte `send_notification` depuis `ihm.services.email_notifier`
  - `ihm/services/email_notifier.py` : service email SMTP complet avec templates (`circuit_breaker_fired`, `kill_switch_activated`)
  - Erreurs swallowées — l'alerting ne bloque pas l'exécution critique
- **Tests ajoutés** : `test_circuit_breaker.py` :
  - `test_circuit_breaker_drawdown_calls_send_notification`
  - `test_circuit_breaker_daily_loss_calls_send_notification`
  - `test_circuit_breaker_no_trigger_no_notification`
- **Résultat test** : ✅ Pass

---

### A-014 ✅ — Dérive silencieuse réconciliation — RÉSOLU (Sprint S3)
- **Sévérité initiale** : P2
- **Domaine** : execution_engine / IHM
- **Résolution** : `ihm/pages/execution.py` — `_render_reconciliation_age_warning()` détecte les diffs non résolus (`BLOCKED`, `MANUAL_REVIEW`) datant de plus de 24h et affiche `st.warning()`.
- **Tests ajoutés** : `test_pages_execution.py` :
  - `test_render_reconciliation_age_warning_on_old_unresolved_diffs`
  - `test_render_no_age_warning_when_all_resolved`
- **Résultat test** : ✅ Pass

---

### A-015 ✅ — Market cap Finnhub stale (TTL non enforced) — RÉSOLU (Sprint S3)
- **Sévérité initiale** : P2
- **Domaine** : dataIntegrityEngine / IHM
- **Résolution** : `ihm/pages/screening.py` — appel `get_stale_market_cap_stats(cutoff_days=45)` ; si `stale_pct >= 30` : `st.warning(f"⚠️ {stale_pct:.0f}% des symboles ont un market_cap > 45j")`.
- **Tests ajoutés** : `test_pages_screening.py` :
  - `test_render_screening_warning_on_stale_market_cap`
  - `test_render_screening_no_warning_when_market_cap_fresh`
- **Résultat test** : ✅ Pass

---

### A-016 ✅ — `execution_pdt_rule: "off"` sur presets cash — RÉSOLU (Sprint S1)
- **Sévérité initiale** : P2
- **Domaine** : Configuration / execution_engine
- **Résolution** : Commentaire ajouté sur tous les presets cash (`capital_0_2000_eur`, `capital_0_5000`, `capital_5001_10000`, `capital_10001_25000`) :
  ```yaml
  execution_pdt_rule: "off"  # PDT N/A sur compte cash (règle margin only — cf. execution_engine/config.py:effective_pdt_rule)
  ```
- **Test ajouté** : `test_cash_presets_have_pdt_off` dans `test_capital_preset_risk_overrides.py` — vérifie que tous les presets cash ont `pdt_rule='off'` ✅

---

### A-017 ✅ — `fill_timeout_seconds` insuffisant lors de gap down/up — RÉSOLU (Sprint S2)
- **Sévérité initiale** : P2
- **Domaine** : execution_engine
- **Résolution** : `execution_engine/config.py:85` — `fill_timeout_seconds: int = 180` (was 120)
  - Paper mode : 180 secondes (augmenté de 50 %)
  - Live mode : recommandé 300 secondes (configurable via preset ou config)
- **Tests ajoutés** : `test_execution_config.py` (classe `TestFillTimeout`) :
  - `test_fill_timeout_default_is_180_seconds`
  - `test_fill_timeout_configurable_for_live`
  - `test_fill_timeout_must_be_positive`
- **Résultat test** : ✅ Pass

---

## Anomalies P3 (mineures / dette technique) — actives

### A-019 — Stooq client : logique `apikey` conditionnelle non testée sans clé
- **Sévérité** : P3
- **Domaine** : service/stooq
- **Description** : `service/stooq/clientStooq.py` ajoute `apikey` si `STOOQ_API_KEY` est défini. Stooq est gratuit sans clé — l'ajout d'une clé invalide peut générer des requêtes rejetées silencieusement.
- **Recommandation** : Documenter que Stooq est utilisé sans clé et que `STOOQ_API_KEY` n'est à définir que si Stooq modifie son API dans le futur

---

### A-020 — `market_regimes.macro_provider: eodhd` mais yields désactivés
- **Sévérité** : P3
- **Domaine** : Configuration
- **Description** : `config.yaml:62 macro_provider: eodhd` + `yields.enabled: false`. Le provider EODHD est configuré mais les yields ne sont pas utilisés. Consommation quota EODHD potentielle pour VIX uniquement.
- **Recommandation** : Documenter la consommation quota par le macro provider EODHD (VIX uniquement quand yields.enabled=false)

---

### A-021 — Pas de PnL quotidien visible dans l'IHM principale
- **Sévérité** : P3
- **Domaine** : IHM
- **Description** : Il n'y a pas de widget PnL quotidien (MTM positions + cash_ledger) dans la page Overview. L'opérateur doit consulter les tables DB manuellement.
- **Recommandation** : Ajouter un widget PnL "today" dans la page Overview en lisant `execution_positions × close_daily` + `portfolio_cash_ledger`

---

### A-022 — Walk-forward backtest limité aux poids sentiment (pas aux paramètres risque)
- **Sévérité** : P3
- **Domaine** : backtesting
- **Description** : Le walk-forward couvre les poids sentiment uniquement (`walk_forward.py`). L'optimisation out-of-sample des paramètres ATR, Kelly, correlation_threshold n'est pas implémentée.
- **Recommandation** : Étendre `walk_forward.py` pour supporter les paramètres risk (ATR period, Kelly, correlation)

---

### A-023 — `test_data_lineage_autogen.py` non activé en CI
- **Sévérité** : P3
- **Domaine** : Qualité logicielle / CI
- **Description** : Le test de vérification de la lineage matrix existe dans les tests (`tests/test_data_lineage_autogen.py`) mais son activation en CI (`--check`) n'est pas confirmée. Si désactivé, les incohérences de tables (cf. A-002) peuvent persister.
- **Recommandation** : S'assurer que `test_data_lineage_autogen.py` est inclus dans la suite CI principale

---

### A-024 — `prompt/` structuration partielle
- **Sévérité** : P3
- **Domaine** : Dette technique / documentation interne
- **Description** : `doc/DOC_TECHNIQUE.md §8` note que plusieurs sous-dossiers dans `prompt/` contiennent du contexte de sprint informel non exploitable par un opérateur tiers.
- **Recommandation** : Archiver les prompts de sprints précédents dans `prompt/archive/` et conserver uniquement les livrables actifs dans `prompt/tod1/`

---

### A-025 ✅ — Compression logs non configurée — RÉSOLU (Sprint S3)
- **Sévérité initiale** : P3
- **Domaine** : Observabilité
- **Résolution** : `common/logging_setup.py` — `configure_root_logging(use_timed_rotation=True, ...)` utilise `TimedRotatingFileHandler(when="midnight", backupCount=14)` + `_gzip_rotator` + `_gzip_namer` pour compression automatique des logs rotatifs.
- **Tests ajoutés** : `test_common_utils.py` :
  - `test_timed_rotation_creates_timed_rotating_file_handler`
  - `test_gzip_namer_appends_gz_suffix`
  - `test_default_rotation_uses_rotating_file_handler`
- **Résultat test** : ✅ Pass

---

### A-026 — `test_import_alpaca_bar_noop.py` : couverture du switch provider complète mais non documentée
- **Sévérité** : P3
- **Domaine** : Tests
- **Description** : `test_import_alpaca_bar_noop.py` teste que `import_alpaca_bar` est un no-op quand `bars_provider=eodhd`. Ce test est bon mais non documenté publiquement — un contributeur peut ignorer ce garde-fou.
- **Recommandation** : Documenter ce test dans `doc/dataIntegrityEngine.md` section tests

---

### A-027 ✅ — Absence de test de régression des poids walk-forward — RÉSOLU (Sprint S3)
- **Sévérité initiale** : P3
- **Domaine** : backtesting / tests
- **Résolution** : `backtesting/walk_forward.py` — `validate_walk_forward_weights(w, strict=False)` avec `WEIGHT_MIN=0.05`, `WEIGHT_MAX=0.40`. En mode non-strict : clip silencieux. En mode strict : `ValueError("hors bornes")`. Intégré dans `resolve_latest_walk_forward_weights()`.
- **Tests ajoutés** : `test_weights_calibration.py` :
  - `test_validate_walk_forward_weights_clips_above_max`
  - `test_validate_walk_forward_weights_clips_below_min`
  - `test_validate_walk_forward_weights_strict_raises`
  - `test_validate_walk_forward_weights_valid_unchanged`
  - `test_validate_walk_forward_weights_preserves_metadata`
- **Résultat test** : ✅ Pass

---

## Anomalies RÉSOLUES ✅ (vérifiées dans le code source)

> Ces anomalies étaient documentées sur la base de lectures documentaires. La vérification directe du code source confirme qu'elles sont résolues dans l'implémentation actuelle.

---

### A-003 ✅ — `model_predictions` DB : gouvernance ML — RÉSOLU
- **Sévérité initiale** : P1
- **Domaine** : modelFactory / database
- **Résolution confirmée** :
  - `database/sql/ml/model_predictions.sql:8-11` — `selected_model VARCHAR(32)`, `decision_threshold DOUBLE`, `signal_label VARCHAR(32)`, `calibration_method VARCHAR(32)` avec COMMENTs détaillés.
  - `database/sql/ml/model_predictions.sql:14` — `UNIQUE KEY uq_symbol_date_run (symbol, prediction_date, run_id)` présent.
  - `modelFactory/db_registry.py:336-363` — `insert_predictions()` écrit ces 4 colonnes via `ON DUPLICATE KEY UPDATE`.
- **Ce qui reste** : Aucune action requise.

---

### A-004 ✅ — `DOC_TECHNIQUE.md §9` : mention "vectorbt" — RÉSOLU (résidu argparse corrigé Sprint S1)
- **Sévérité initiale** : P1 (documentation)
- **Domaine** : documentation
- **Résolution confirmée** : `doc/DOC_TECHNIQUE.md:497` — "simulateur custom PIT — aucune dépendance vectorbt ; moteur `BacktestEngine` dans `backtesting/simulator.py`".
- **Résidu Sprint S1 corrigé** : `backtesting/cli/_impl.py:67` — `description="Backtest intégré Alpha Trade (simulateur custom PIT)"` ✅ (était "vectorbt"). Entièrement résolu.

---

### A-005 ✅ — `corporate_actions` provider CA ambigu — RÉSOLU
- **Sévérité initiale** : P1
- **Domaine** : corporate_actions / documentation
- **Résolution confirmée** :
  - `doc/DOC_FONCTIONNELLE.md:246` — "`EodhdCorporateActionProvider` si `market_data.bars_provider=eodhd` (défaut), `AlpacaCorporateActionProvider` sinon (factory `build_corporate_action_provider`)".
  - `doc/data_lineage_matrix.md §7:109-111` — règle de sélection explicitement documentée.
  - `corporate_actions/provider.py:402-432` — factory `build_corporate_action_provider()` correctement implémentée avec fallback `alpaca` par défaut.

---

### A-009 ✅ — `model_predictions` table : absence de contrainte UNIQUE — RÉSOLU
- **Sévérité initiale** : P2
- **Domaine** : modelFactory / database
- **Résolution confirmée** :
  - `database/sql/ml/model_predictions.sql:14` — `UNIQUE KEY uq_symbol_date_run (symbol, prediction_date, run_id)`.
  - `modelFactory/db_registry.py:342-348` — `ON DUPLICATE KEY UPDATE` garantit l'idempotence.

---

### A-012 ✅ — SSL MySQL absent par défaut — RÉSOLU
- **Sévérité initiale** : P2
- **Domaine** : Sécurité / database
- **Résolution confirmée** :
  - `database/connection.py:97-111` — `_read_ssl_connect_args()` lit `DB_SSL_CA_PATH` et active TLS si la variable est définie.
  - `database/connection.py:138,159` — `connect_args=_read_ssl_connect_args()` passé à `create_engine()`.
  - Conforme à l'audit_database §3 (TLS optionnel, LAN dev non cassé).
- **Ce qui reste** : Ajouter le test `test_connection.py` vérifiant SSL si `DB_SSL_CA_PATH` est défini (recommandé, non bloquant).

---

### A-018 ✅ — `DOC_FONCTIONNELLE.md §1.3` : script "import_alpaca_bar" — RÉSOLU
- **Sévérité initiale** : P3
- **Domaine** : Documentation
- **Résolution confirmée** : `doc/DOC_FONCTIONNELLE.md:37` — "Ingestion des barres OHLCV journalières depuis **EODHD** (provider primaire par défaut, `market_data.bars_provider=eodhd`) ou Alpaca IEX (mode rétrocompatibilité, `bars_provider=alpaca`)."

---

## Guide de priorisation pour correction

| Ordre | Anomalie | Action | Fichier(s) | Statut |
|---|---|---|---|---|
| **1** | A-001 | Corriger `risk_max_positions: 3` + `risk_min_position_notional: 500` | `config/capital_presets.yaml` | ✅ Sprint S1 |
| **2** | A-002 | Corriger noms de tables dans LINEAGE_SPEC + régénérer | `scripts/generate_data_lineage.py` | ✅ Sprint S1 |
| **3** | A-016 | Ajouter commentaire PDT off cash | `config/capital_presets.yaml` | ✅ Sprint S1 |
| **4** | A-004 résidu | Corriger description argparse "vectorbt" | `backtesting/cli/_impl.py:67` | ✅ Sprint S1 |
| **5** | A-006 | Passer PDT rule `"auto"` sur presets margin ≥ 25k$ | `config/capital_presets.yaml` | ✅ Sprint S2 |
| **6** | A-007 | `selector_min_close: 10.0` sur tous les presets | `config/capital_presets.yaml` | ✅ Sprint S2 |
| **7** | A-017 | `fill_timeout_seconds` → 180 | `execution_engine/config.py` | ✅ Sprint S2 |
| **8** | A-010 | Brancher `ParquetCache` via `--use-cache` | `backtesting/cli/_impl.py` | ✅ Sprint S3 |
| **9** | A-011 | Brancher analytics/statistical_validation CLI | `backtesting/cli/_impl.py` | ✅ Sprint S3 |
| **10** | A-013 | Alerting externe circuit breaker | `risk_management/circuit_breaker.py` + `ihm/services/email_notifier.py` | ✅ Sprint S3 |
| **11** | A-014 | Alerte IHM dérive réconciliation > 24h | `ihm/pages/execution.py` | ✅ Sprint S3 |
| **12** | A-015 | Alerte IHM TTL market_cap stale | `ihm/pages/screening.py` | ✅ Sprint S3 |
| **13** | A-025 | TimedRotatingFileHandler + gzip | `common/logging_setup.py` | ✅ Sprint S3 |
| **14** | A-027 | Bornes business poids walk-forward [0.05, 0.40] | `backtesting/walk_forward.py` | ✅ Sprint S3 |
| **15** | A-008 | Documenter biais IEX spread_bps + max_spread_bps_iex | `doc/dataIntegrityEngine.md` | 🔴 Sprint S4 |
| **16** | A-019 | Documenter Stooq sans clé API | `doc/` | 🔴 Sprint S4 |
| **17** | A-020 | Documenter quota EODHD macro provider | `doc/` | 🔴 Sprint S4 |
| **18** | A-021 | Widget PnL quotidien page Overview | `ihm/pages/overview.py` | 🔴 Sprint S4 |
| **19** | A-022 | Walk-forward paramètres risque (ATR, Kelly) | `backtesting/walk_forward.py` | 🔴 Sprint S4 |
| **20** | A-023 | Activer `test_data_lineage_autogen.py` en CI | `pytest.ini` / CI | 🔴 Sprint S4 |
| **21** | A-024 | Archiver prompts anciens sprints | `prompt/archive/` | 🔴 Sprint S4 |
| **22** | A-026 | Documenter test no-op import_alpaca_bar | `doc/dataIntegrityEngine.md` | 🔴 Sprint S4 |
