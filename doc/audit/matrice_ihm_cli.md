# Matrice IHM ↔ CLI — couverture des fonctionnalités

> **Sprint S26 — gaps comblés (2026-05-06)** : tous les gaps P1, P2 et P3
> listés en §5 sont désormais exposés dans l'IHM via le service unifié
> `ihm/services/ops_runner.py` + composant `ihm/components/ops_command_panel.py`.
> Voir aussi `tests/test_ihm_cli_contract.py` qui couvre désormais toutes
> les commandes du catalogue ops.
>
> **Sprint S26** — audit ciblé pour identifier les commandes CLI **non
> exposées** dans l'IHM Streamlit. Source : introspection des `argparse` (cf.
> `tests/test_ihm_cli_contract.py`) + lecture des pages IHM
> (`F:\projets\ihm\pages\`) et du builder de commandes
> `ihm/services/pipeline_runner.py::build_pipeline_command`.

Légende : ✅ exposé · ⚠️ exposé partiellement · ❌ absent de l'IHM.

---

## 1. Pipeline data → screener → selector → ML → risk → execution

| Module CLI | Sous-commande / mode | IHM | Page IHM | Note |
|---|---|---|---|---|
| `dataIntegrityEngine.import_alpaca_assets` | (default) | ✅ | Pipeline (step 1) | tous flags `--*` couverts (test contractuel). |
| `dataIntegrityEngine.import_alpaca_bar` (ou `import_eodhd_bar`) | (default) | ✅ | Pipeline (step 2) | provider switch via `market_data.bars_provider`. |
| `dataIntegrityEngine.data_sanitizer_daily` | (default) | ✅ | Pipeline (step 3) | |
| `dataIntegrityEngine.update_sector` | (default) | ✅ | Pipeline (step 4) | |
| `dataIntegrityEngine.sync_latest_quotes` | (default) | ✅ | Pipeline (step B1) | |
| `dataIntegrityEngine.sync_earnings_calendar` | (default) | ✅ | Pipeline (step B2) | |
| `screener.stock_screener` | (default) | ✅ | Pipeline (step 5) | |
| `selector.alpha_scanner` | (default) | ✅ | Pipeline (step 6) | |
| `event_sentiment` (ingest) | `--mode ingest` | ✅ | Pipeline (step 7) | |
| `event_sentiment.signal_aggregator` | (default) | ✅ | Pipeline (step 8) | |
| `modelFactory` train/predict | `--mode rebuild-all\|missing\|stale` | ✅ | Pipeline (steps 9-10) + page ML | |
| `risk_management` | (default) | ✅ | Pipeline (step 11) + page Risk | |
| `execution_engine` | `run` | ✅ | Pipeline (step 12) + page Execution | toutes options sizing/protection. |
| `execution_engine` | **`cancel-all` (kill switch)** | ✅ | Execution | Sprint S26 — bouton « Kill switch » câblé sur `ops_runner` (`execution_kill_switch`). |
| `run_execution_protection_watch` | (background) | ⚠️ lecture seule | Pipeline (step 12.bis) + Supervision Ops | démarrage/arrêt manuel non exposés (cf. `doc/ihm.md` §4.3.8). |
| `corporate_actions` | `sync` | ✅ | Pipeline (Execution Center BLOCK 8b) | |
| `corporate_actions` | `apply` | ✅ | Corporate Actions | Sprint S26 — bouton « apply » avec champ `as-of`. |
| `corporate_actions` | `status` | ✅ | Corporate Actions | Sprint S26 — bouton « status » via `ops_runner`. |
| `corporate_actions` | `run` (sync+apply) | ✅ | Pipeline | |

## 2. Backtesting

| Sous-commande `python -m backtesting …` | IHM | Page IHM | Note |
|---|---|---|---|
| `run` | ✅ | Backtesting | builder complet via `backtesting_runner.py`. |
| `backfill-scores-history` | ✅ | Backtesting (sous-onglet) | |
| `diagnose-screener` | ✅ | Backtesting (sous-onglet) | Sprint S26 — onglet « 🧪 Diagnose screener ». |
| `recommend-screener` | ✅ | Backtesting (sous-onglet) | Sprint S26 — onglet « 🎯 Recommend screener ». |
| `calibrate-sentiment-weights` | ✅ | Backtesting (sous-onglet) | Sprint S26 — onglet « 📰 Calibrate sentiment ». |
| `walk-forward-sentiment` | ✅ | Backtesting (sous-onglet) | Sprint S26 — onglet « 🚶 Walk-forward sentiment ». |

## 3. Scripts ops (dossier `scripts/`)

| Script | Usage | IHM | Cible IHM proposée |
|---|---|---|---|
| `scripts/run_pre_live_checklist.py` | Validation avant passage live | ✅ | Compliance & Audit (Sprint S26 — onglet « 🚦 Pré-live checklist »). |
| `scripts/run_broker_reconciliation.py` | Réconciliation positions broker vs DB | ✅ | Compliance & Audit (Sprint S26 — onglet « 🧮 Réconciliation broker »). |
| `scripts/verify_audit_chain.py` | Audit chain SHA256 | ✅ | Compliance & Audit (Sprint S26 — onglet « 🔐 Audit chain »). |
| `scripts/run_daily_parity.py` | Parité backtest ↔ live quotidienne | ✅ | Parité (Sprint S26 — relance via `ops_runner`). |
| `scripts/run_monthly_broker_report.py` | Rapport mensuel broker | ✅ | Compliance & Audit (Sprint S26 — onglet « 📅 Rapport mensuel broker »). |
| `scripts/run_quarterly_weights_calibration.py` | Calibration poids trimestrielle | ✅ | Backtesting (Sprint S26 — onglet « 🎛️ Calibration trimestrielle »). |
| `scripts/prune_artifacts.py` | Nettoyage artefacts | ✅ | Settings (Sprint S26 — section « 🧹 Nettoyage artefacts »). |
| `scripts/restore_from_backup.py` | Restauration | ✅ | DB Admin (Sprint S26 — section « ♻️ Restauration depuis backup »). |
| `scripts/scan_cves.py` | Scan vulnérabilités deps | ✅ | Compliance & Audit (Sprint S26 — onglet « 🛡️ Scan CVE »). |
| `scripts/verify_vault_rotation.py` | Rotation secrets | ✅ | Settings (Sprint S26 — section « 🗝️ Rotation des secrets »). |
| `dataIntegrityEngine/cross_check_stooq.py` | Cross-check OHLCV | ✅ | Sandbox health (Sprint S26 — onglet « 📊 Cross-check Stooq »). |
| `dataIntegrityEngine/data_source_health.py` | Health providers | ✅ | Sandbox health (Sprint S26 — onglet « 💚 Health providers »). |

## 4. Pages IHM existantes — récap

| Page | Module | État | Actions disponibles |
|---|---|---|---|
| Vue d'ensemble | `overview.py` | OK | KPI lecture seule |
| Pipeline | `pipeline.py` + `_workflow/` + `_execution_center/` | OK | Lance les 14 steps + auxiliaires |
| Backtesting | `backtesting/__init__.py` | OK | Lance `run` + `backfill-scores-history` + `diagnose-screener` + `recommend-screener` + `calibrate-sentiment-weights` + `walk-forward-sentiment` + `quarterly_weights_calibration` (S26). |
| Screening | `screening.py` | OK | Lecture `stock_scores` |
| Risk | `risk.py` | OK | Lecture décisions risk |
| Execution | `execution.py` | OK | Lecture runs/fills/positions + **kill switch (`cancel-all`)** câblé S26. |
| Corporate Actions | `corporate_actions.py` | OK | Lecture + status / apply CLI exposés (S26). |
| ML / Prédictions | `ml.py` | OK | Lecture runs ML |
| Comptes Alpaca | `alpaca_accounts.py` | OK | CRUD comptes |
| Supervision Ops | `supervision_ops.py` | ⚠️ | Lecture watcher ; pas de start/stop |
| Parité | `parity.py` | OK | Lecture + relance via `ops_runner` (S26). |
| Compliance & Audit | `compliance_audit.py` | OK | Lecture + pré-live + audit chain + scan CVE + vault + rapport mensuel + réconciliation (S26). |
| Tax Compliance | `tax_compliance.py` | OK | |
| Sandbox health | `sandbox_health.py` | OK | Lecture + cross-check Stooq + health providers (S26). |
| DB Admin | `db_admin.py` | OK | + restore_from_backup (S26). |
| Paramètres / Santé | `settings.py` | OK | + prune_artifacts + verify_vault_rotation (S26). |
| Glossaire | `glossary.py` | OK | |

---

## 5. Synthèse des gaps prioritaires — **résolus (Sprint S26, 2026-05-06)**

Tous les gaps P1, P2 et P3 listés initialement sont désormais comblés via le
service unifié `ihm/services/ops_runner.py` + composant
`ihm/components/ops_command_panel.py`. Le tableau historique reste ci-dessous
pour traçabilité du travail effectué.

| Priorité | Manque | Page IHM cible | Statut |
|---|---|---|---|
| **P1** | Bouton « Kill switch / Annuler tous les ordres » (`execution_engine cancel-all`) | Execution | ✅ |
| **P1** | Bouton « Pré-live checklist » (`scripts/run_pre_live_checklist.py`) | Compliance & Audit | ✅ |
| **P2** | Sous-onglets Backtesting : Diagnose / Recommend / Calibrate-sentiment / Walk-forward-sentiment | Backtesting | ✅ |
| **P2** | Bouton « Relancer parité quotidienne » | Parité | ✅ |
| **P2** | Bouton « Cross-check OHLCV Stooq » + « Health providers » | Sandbox health | ✅ |
| **P3** | Bouton « status corporate_actions » | Corporate Actions | ✅ |
| **P3** | Boutons ops (prune, restore, scan_cves, verify_vault_rotation, monthly_report, quarterly_weights) | Settings / Compliance & Audit / DB Admin / Backtesting | ✅ |

> Le test contractuel `tests/test_ihm_cli_contract.py` a été étendu (Sprint S26)
> pour couvrir l'ensemble des commandes du catalogue
> `OPS_COMMAND_CATALOG` : émission d'une commande `python -u …` valide pour
> chaque clé + vérification que les flags du kill switch sont bien reconnus
> par l'argparse de `execution_engine.cli`.

