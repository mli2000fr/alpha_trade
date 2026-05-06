# Matrice IHM ↔ CLI — couverture des fonctionnalités

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
| `execution_engine` | **`cancel-all` (kill switch)** | ❌ | — | **GAP P1** : aucun bouton « Annuler tous les ordres » dans l'IHM. À ajouter sur page Execution. |
| `run_execution_protection_watch` | (background) | ⚠️ lecture seule | Pipeline (step 12.bis) + Supervision Ops | démarrage/arrêt manuel non exposés (cf. `doc/ihm.md` §4.3.8). |
| `corporate_actions` | `sync` | ✅ | Pipeline (Execution Center BLOCK 8b) | |
| `corporate_actions` | `apply` | ⚠️ | Pipeline (run combiné) | pas de bouton « Apply seul » dans l'IHM. |
| `corporate_actions` | `status` | ❌ | — | **GAP P3** : la page Corporate Actions affiche déjà l'historique mais pas le `status` formaté. Faible impact. |
| `corporate_actions` | `run` (sync+apply) | ✅ | Pipeline | |

## 2. Backtesting

| Sous-commande `python -m backtesting …` | IHM | Page IHM | Note |
|---|---|---|---|
| `run` | ✅ | Backtesting | builder complet via `backtesting_runner.py`. |
| `backfill-scores-history` | ✅ | Backtesting (sous-onglet) | |
| `diagnose-screener` | ❌ | — | **GAP P2** : utile pour comprendre pourquoi un screener retourne 0 candidat. À ajouter en sous-onglet Backtesting → Diagnostics. |
| `recommend-screener` | ❌ | — | **GAP P2** : recommandations automatiques de seuils screener. À ajouter en sous-onglet Backtesting. |
| `calibrate-sentiment-weights` | ❌ | — | **GAP P2** : calibration auto des poids `SentimentBoostConfig`. À ajouter en sous-onglet « Sentiment ». |
| `walk-forward-sentiment` | ❌ | — | **GAP P2** : walk-forward dédié sentiment. À ajouter idem. |

## 3. Scripts ops (dossier `scripts/`)

| Script | Usage | IHM | Cible IHM proposée |
|---|---|---|---|
| `scripts/run_pre_live_checklist.py` | Validation avant passage live | ❌ | **GAP P1** : page Compliance & Audit ou nouvel onglet « Go-Live » sur Execution. |
| `scripts/run_broker_reconciliation.py` | Réconciliation positions broker vs DB | ⚠️ | partiel via page Execution (résultats), pas de relance bouton. |
| `scripts/verify_audit_chain.py` | Audit chain SHA256 | ⚠️ | page Compliance & Audit affiche le résultat mais relance non exposée. |
| `scripts/run_daily_parity.py` | Parité backtest ↔ live quotidienne | ⚠️ | page Parité affiche les rapports mais relance manuelle absente. **GAP P2**. |
| `scripts/run_monthly_broker_report.py` | Rapport mensuel broker | ❌ | page Compliance & Audit. **GAP P3**. |
| `scripts/run_quarterly_weights_calibration.py` | Calibration poids trimestrielle | ❌ | Backtesting → Calibration. **GAP P3**. |
| `scripts/prune_artifacts.py` | Nettoyage artefacts | ❌ | page Paramètres / Santé. **GAP P3**. |
| `scripts/restore_from_backup.py` | Restauration | ❌ | page Administration DB. **GAP P3**. |
| `scripts/scan_cves.py` | Scan vulnérabilités deps | ❌ | page Compliance & Audit. **GAP P3**. |
| `scripts/verify_vault_rotation.py` | Rotation secrets | ❌ | page Paramètres / Santé. **GAP P3**. |
| `dataIntegrityEngine/cross_check_stooq.py` | Cross-check OHLCV | ❌ | page Sandbox health. **GAP P2**. |
| `dataIntegrityEngine/data_source_health.py` | Health providers | ⚠️ | page Sandbox health affiche, relance manquante. |

## 4. Pages IHM existantes — récap

| Page | Module | État | Actions disponibles |
|---|---|---|---|
| Vue d'ensemble | `overview.py` | OK | KPI lecture seule |
| Pipeline | `pipeline.py` + `_workflow/` + `_execution_center/` | OK | Lance les 14 steps + auxiliaires |
| Backtesting | `backtesting/__init__.py` | ⚠️ | Lance `run` + `backfill-scores-history` ; manque diagnose/recommend/calibrate-sentiment/walk-forward-sentiment |
| Screening | `screening.py` | OK | Lecture `stock_scores` |
| Risk | `risk.py` | OK | Lecture décisions risk |
| Execution | `execution.py` | ⚠️ | Lecture runs/fills/positions ; **manque kill switch (`cancel-all`)** |
| Corporate Actions | `corporate_actions.py` | ⚠️ | Lecture seule ; pas de `status` |
| ML / Prédictions | `ml.py` | OK | Lecture runs ML |
| Comptes Alpaca | `alpaca_accounts.py` | OK | CRUD comptes |
| Supervision Ops | `supervision_ops.py` | ⚠️ | Lecture watcher ; pas de start/stop |
| Parité | `parity.py` | ⚠️ | Lecture ; pas de relance |
| Compliance & Audit | `compliance_audit.py` | ⚠️ | Lecture ; pas de pré-live checklist / scan cves |
| Tax Compliance | `tax_compliance.py` | OK | |
| Sandbox health | `sandbox_health.py` | ⚠️ | Lecture ; pas de relance health/cross-check |
| DB Admin | `db_admin.py` | OK | |
| Paramètres / Santé | `settings.py` | ⚠️ | Pas de prune_artifacts ni rotation secrets |
| Glossaire | `glossary.py` | OK | |

---

## 5. Synthèse des gaps prioritaires

| Priorité | Manque | Page IHM cible | Effort estimé |
|---|---|---|---|
| **P1** | Bouton « Kill switch / Annuler tous les ordres » (`execution_engine cancel-all`) | Execution | 1 j |
| **P1** | Bouton « Pré-live checklist » (`scripts/run_pre_live_checklist.py`) | Compliance & Audit ou Execution | 1 j |
| **P2** | Sous-onglets Backtesting : Diagnose / Recommend / Calibrate-sentiment / Walk-forward-sentiment | Backtesting | 2-3 j |
| **P2** | Bouton « Relancer parité quotidienne » | Parité | 0.5 j |
| **P2** | Bouton « Cross-check OHLCV Stooq » + « Health providers » | Sandbox health | 1 j |
| **P3** | Bouton « status corporate_actions » | Corporate Actions | 0.5 j |
| **P3** | Boutons ops (prune, restore, scan_cves, verify_vault_rotation, monthly_report, quarterly_weights) | Settings / Compliance & Audit / DB Admin | 2-3 j |

> Le test contractuel `tests/test_ihm_cli_contract.py` couvre déjà les flags
> du **pipeline** ; il faudrait l'étendre (ou ajouter un test miroir) pour
> détecter les **sous-commandes** absentes (méthode : lister tous
> `add_subparsers().choices` puis vérifier qu'au moins une page IHM les
> mentionne).

