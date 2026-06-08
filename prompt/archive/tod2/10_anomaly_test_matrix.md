# 10 — Matrice anomalie → correctif → tests → sprint

| Anomalie | Correctif principal | Tests associés | Sprint |
|---|---|---|---|
| A-001 | Implémenter ou supprimer `fallback_on_failure` | `test_fallback_on_failure_is_effective_or_rejected` | S0 |
| A-002 | Corriger doc lineage ou migrer PK source | `test_stock_bars_daily_source_versioning_policy` | S1 |
| A-003 | Réécrire runbooks provider-aware | `test_no_unqualified_import_alpaca_bar_runbook` | S0 |
| A-004 | Preflight backtest source EODHD | `test_backtest_refuses_non_eodhd_source_in_pipeline_mode` | S1/S4 |
| A-005 | Clarifier `market_regimes.enabled` et affichage IHM | `test_market_regime_default_visible_in_execution_prefight` | S3/S6 |
| A-006 | Réviser preset micro-compte | `test_micro_account_executability_and_concentration` | S3 |
| A-007 | Durcir spread petits comptes / quote size | `test_selector_spread_iex_requires_quote_size` | S2/S3 |
| A-008 | Ajouter quote quality/staleness gates | `test_alpha_scanner_rejects_stale_quote_snapshot` | S2 |
| A-009 | Estimation coût sync historique quotes | `test_quote_history_large_scope_requires_confirmation` | S2/S6 |
| A-010 | Preflight snapshot positions CA | `test_ca_apply_requires_fresh_position_snapshot` | S5 |
| A-011 | Interdire sync globale EODHD implicite | `test_eodhd_ca_provider_requires_explicit_symbols` | S5 |
| A-012 | Reprise/failed state subprocess | `test_pipeline_process_kill_marks_run_failed` | S6 |
| A-013 | Profil production parity backtesting | `test_backtest_live_parity_golden` | S4 |
| A-014 | ML drift gate / fallback quant-only | `test_risk_fallback_quant_only_when_ml_gate_fails` | S7 |
| A-015 | Coverage artifact complet uniquement | `test_coverage_artifact_is_complete_run` | S6 |
| A-016 | Policy secrets live + approval token + run plan immuable | `test_live_requires_vault_or_env_policy`, `test_execution_live_requires_approval_token`, `test_execution_live_plan_immutable` | S8 |
| A-017 | Commentaire sanitizer provider-agnostique | `test_docs_no_obsolete_provider_comment_in_canonical_paths` | S0 |
| A-018 | Mode preset verrouillé / diff commande | `test_pipeline_locked_preset_displays_command_diff` | S6 |

## Détail des catégories de tests à renforcer

| Catégorie | Priorité | Exemples |
|---|---|---|
| Unitaires | Haute | adapters EODHD split-only, `ExecutionConfig`, risk sizing, selector filters. |
| Intégration | Haute | import EODHD → DB → screener → selector, CA sync/apply, risk→execution. |
| Non-régression | Très haute | provider switch EODHD/Alpaca, no-op, `data_adjustment='split'`. |
| E2E/IHM | Haute | workflow 1→14 en dry-run/subprocess mocké, options capital, confirmations live. |
| Data quality | Très haute | source EODHD récente, quote staleness, fills daily, anomalies counts. |
| SQL/migrations | Haute | PK/unique constraints, account_id CA/execution, ledger idempotence. |
| Backtest-live parity | Très haute | production parity profile, golden fills, constraints cash/swing. |
| Sécurité/config | Haute | secrets env, forbidden literals, live preflight, policy Vault/env, approval token, run plan immuable, config keys consumed. |

## Preuves de sécurité S8 déjà automatisées

- `tests/test_live_requires_vault_or_env_policy.py`
- `tests/test_execution_live_requires_approval_token.py`
- `tests/test_execution_live_plan_immutable.py`
- `tests/test_pre_live_checklist.py`
- `tests/test_config_loader_vault.py`
- `tests/test_security_scripts.py`

## Résiduel explicite

- Les scans et garde-fous sécurité existent dans le repo et sont testés, **mais aucun workflow CI security versionné dans `.github/workflows/` n’a été trouvé** dans l’état audité du dépôt.

## Oracle général de validation d’un sprint

Un sprint ne doit être accepté que si :

1. l’anomalie corrigée a au moins un test automatisé ;
2. les tests critiques existants du module passent ;
3. la documentation correspond au code réel ;
4. l’IHM affiche le comportement effectif, pas seulement théorique ;
5. un run summary permet à l’opérateur de diagnostiquer l’état final.

