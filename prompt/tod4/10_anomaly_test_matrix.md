# 10 — Matrice traçable Anomalie → Correctif → Test(s) → Sprint

Date : mai 2026

---

## Matrice principale

| ID | Titre | Sévérité | Sprint | Correctif | Test(s) associé(s) | Type de test |
|---|---|---|---|---|---|---|
| A-001 | Provider news défaut incohérent doc/doc | P1 | S1 | Aligner toute la doc sur le défaut code | `test_doc_news_provider_consistency.py` | Non-régression doc |
| A-002 | Défaut `bars_provider` code vs doc | P1 | S1 | Changer défaut code à `eodhd` | `test_bars_provider_default.py` | Unitaire |
| A-003 | Run_summary hétérogènes, pas de persistance SQL | P1 | S2 | Table `run_summaries`, persistance uniforme | `test_run_summary_persistence.py`, `test_run_summary_schema.py` | Intégration + Unitaire |
| A-004 | Tables ML dans lineage matrix non confirmées | P1 | S2 | Vérifier et corriger la lineage matrix | `test_lineage_matrix_consistency.py` | SQL |
| A-005 | Pas de validation cohérence presets vs profil strict | P1 | S2 | Test de cohérence automatique | `test_capital_presets_consistency.py` | Config |
| A-006 | Pas de test E2E du pipeline complet | P1 | S3 | Créer un test E2E | `test_pipeline_e2e.py` | E2E |
| A-007 | Pas d'alerting externe | P1 | S5 | Intégrer webhook Slack + email SMTP | `test_alerting.py` | Intégration |
| A-010 | Duplication importeurs barres | P2 | S7 | Factoriser en BaseBarImporter | `test_bar_importers_consistency.py` | Unitaire |
| A-011 | `model_predictions` incomplet | P2 | S7 | Ajouter colonnes gouvernance ML | `test_model_predictions_schema.py` | SQL |
| A-012 | Pas de test MySQL Docker | P2 | S3 | Ajouter configuration Docker Compose | Tests d'intégration MySQL existants | Intégration |
| A-013 | Redondance DOC_FONCTIONNELLE / DOC_TECHNIQUE | P2 | S1 | Réduire duplication, renvoyer | `test_doc_consistency.py` (extension) | Non-régression doc |
| A-014 | Pas de mode read-only IHM | P2 | S8 | Flag `--read-only` | `test_ihm_readonly.py` | E2E IHM |
| A-015 | Pas de parallélisation backtest | P2 | S6 | Ajouter `--parallel` | `test_backtest_parallel.py` | Unitaire |
| A-016 | Cache Parquet non branché | P2 | S6 | Activer par défaut | `test_backtest_cache.py` (étendre) | Unitaire |
| A-017 | Analyse de sensibilité non exposée | P2 | S6 | Exposer via CLI | `test_backtest_sensitivity.py` | Intégration |
| A-018 | Pas de fallback si quotes absentes | P2 | S2 | Ajouter `--skip-spread-filter` | `test_selector_no_quotes_fallback.py` | Unitaire |
| A-019 | Pas de health check providers | P2 | S8 | Ajouter preflight health check | `test_provider_health.py` | Intégration |
| A-020 | Pas d'orchestrateur formel | P2 | S4 | Intégrer Prefect | `test_prefect_flow.py` | Intégration |
| A-021 | Pas de monitoring Prometheus/Grafana | P2 | S5 | Exposer métriques Prometheus | `test_metrics.py` | Unitaire |
| A-022 | Pas de gestion fills partiels | P2 | S3 | Gérer explicitement les fills partiels | `test_executor_partial_fill.py` | Unitaire |
| A-023 | Pool DB modeste | P2 | S4 | Configurer via config.yaml | `test_db_pool_config.py` | Config |
| A-024 | Pas de test parité backtest/live | P2 | S3 | Ajouter test de parité | `test_backtest_live_parity.py` | Intégration |
| A-025 | Alias redondants dans capital_presets.yaml | P2 | S1 | Supprimer alias | `test_capital_presets_consistency.py` (intégré) | Config |
| A-026 | `stock_assets` vs `stock_metadata` dans lineage | P2 | S2 | Corriger le nom | `test_lineage_matrix_consistency.py` (intégré) | SQL |
| A-027 | Documents POC sans bandeau | P2 | S1 | Ajouter bandeau | `test_doc_poc_bandeau.py` | Non-régression doc |
| A-030 à A-040 | Diverses P3 | P3 | S8 | Améliorations documentation, naming, etc. | Tests variés | Divers |

---

## Couverture des tests par catégorie

| Catégorie | Fichiers de test | Anomalies couvertes |
|---|---|---|
| Unitaire | `test_bars_provider_default.py`, `test_bar_importers_consistency.py`, `test_selector_no_quotes_fallback.py`, `test_executor_partial_fill.py`, `test_backtest_cache.py`, `test_backtest_parallel.py`, `test_metrics.py` | A-002, A-010, A-018, A-022, A-016, A-015, A-021 |
| Intégration | `test_run_summary_persistence.py`, `test_pipeline_e2e.py`, `test_backtest_live_parity.py`, `test_alerting.py`, `test_backtest_sensitivity.py`, `test_provider_health.py`, `test_prefect_flow.py` | A-003, A-006, A-024, A-007, A-017, A-019, A-020 |
| SQL / Persistance | `test_lineage_matrix_consistency.py`, `test_model_predictions_schema.py`, `test_run_summary_schema.py` | A-004, A-011, A-003, A-026 |
| Configuration | `test_capital_presets_consistency.py`, `test_db_pool_config.py` | A-005, A-025, A-023 |
| Non-régression documentation | `test_doc_news_provider_consistency.py`, `test_doc_consistency.py`, `test_doc_poc_bandeau.py` | A-001, A-013, A-027 |
| E2E / IHM | `test_ihm_readonly.py` | A-014 |

---

## Tests existants à étendre

| Test existant | Extension | Sprint |
|---|---|---|
| `tests/test_import_alpaca_bar.py` | Vérifier le no-op avec le nouveau défaut `eodhd` | S1 |
| `tests/test_import_eodhd_bar.py` | Vérifier le défaut `eodhd` | S1 |
| `tests/test_config_no_literal_secrets.py` | Vérifier que tous les presets ne contiennent pas de secrets | S1 |
| `tests/test_capital_preset_risk_overrides.py` | Ajouter la validation de cohérence avec le profil strict | S2 |
| `tests/test_data_integrity_run_summaries.py` | Valider le nouveau schéma commun | S2 |
| `tests/test_backtest_cache.py` | Activer et valider le cache par défaut | S6 |

---

## Script CI recommandé

```bash
# Sprint 1
python -m pytest tests/test_doc_news_provider_consistency.py tests/test_bars_provider_default.py -v

# Sprint 2
python -m pytest tests/test_run_summary_persistence.py tests/test_run_summary_schema.py tests/test_lineage_matrix_consistency.py tests/test_capital_presets_consistency.py -v

# Sprint 3 (E2E + intégration)
python -m pytest tests/test_pipeline_e2e.py tests/test_backtest_live_parity.py -v --timeout 300

# Sprint 4 (Orchestrateur)
python -m pytest tests/test_prefect_flow.py -v

# Sprint 5 (Alerting + monitoring)
python -m pytest tests/test_alerting.py tests/test_metrics.py -v

# Sprint 6 (Backtesting)
python -m pytest tests/test_backtest_cache.py tests/test_backtest_sensitivity.py tests/test_backtest_parallel.py -v

# Sprint 7 (ML + refactor)
python -m pytest tests/test_model_predictions_schema.py tests/test_model_walk_forward.py tests/test_bar_importers_consistency.py -v

# Sprint 8 (Sécurité + Docker)
python -m pytest tests/test_ihm_readonly.py tests/test_provider_health.py -v
```