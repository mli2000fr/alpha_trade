# 10 — Matrice anomalie → correctif → test → sprint

> Tableau traçable utilisable pour le suivi de Definition of Done. Chaque
> ligne pointe l'anomalie du `03_anomalies_register.md`, le correctif
> proposé, le(s) test(s) à créer/étendre et le sprint d'exécution.

| ID | Sévérité | Description courte | Correctif proposé | Test(s) | Fichier(s) test(s) probable(s) | Sprint |
|---|---|---|---|---|---|---|
| A-001 | P0 | Docstring `corporate_actions/engine.py:34-39` ment (`adjustment="all"`) | Réécrire docstring (split + ledger) | unitaire constantes + parsing docstring | `tests/test_data_adjustment_convention.py` ; étendre `tests/test_eodhd_split_only.py` | S1 |
| A-002 | P0 | `eodhd.enabled: false` jamais lu | Supprimer la clé OU l'implémenter ; ajouter schéma Pydantic config | unitaire config | `tests/test_config_yaml_schema.py` | S1 |
| A-003 | P0 | `README.md:142` runbook obsolète (no-op silencieux si bars_provider=eodhd) | Réécrire README §6 + WARNING + champ `skipped_reason` dans `import_alpaca_bar` | intégration CLI + IHM | `tests/test_import_alpaca_bar_noop.py` ; étendre `tests/test_ihm_eodhd_provider_switch.py` | S1 (doc) + S2 (code) |
| A-004 | P1 | `doc/dataIntegrityEngine.md` bandeau IEX figé | Réécrire bandeau, sous-section rétrocompat | doc parsing | `tests/test_doc_provider_alignment.py` | S1 |
| A-005 | P1 | `doc/data_lineage_matrix.md` cite Alpaca IEX comme producteur primaire | Marquer EODHD primaire + colonne `provider_actif` | doc parsing | `tests/test_doc_provider_alignment.py` | S1 |
| A-006 | P1 | Backtest peut omettre `portfolio_cash_ledger` | Vérifier `backtesting/analytics.py`, intégrer ledger si absent | intégration backtesting | `tests/test_backtest_total_return_with_dividends.py` | S3 |
| A-007 | P1 | Circuit breaker non branché PnL réel | Câbler `PnLSnapshot` depuis snapshots/runs au démarrage `run_risk` | intégration risk | `tests/test_run_risk_circuit_breaker_wired.py` ; étendre `tests/test_circuit_breaker.py` | S3 |
| A-008 | P1 | `run_execution.py` check env ne couvre pas comptes multi-broker | Check contextuel par `--account` | intégration CLI | `tests/test_run_execution_check_env_per_account.py` | S2 |
| A-009 | P1 | `selector_min_weekly_trend_score=1.0` peut vider l'univers | Assouplissement conditionnel ; tests yield univers | intégration selector | `tests/test_capital_preset_universe_yield.py` | S3 |
| A-010 | P1 | Préset 0–5k$ rejets sizing invisibles | Télémétrie `rejected_for_notional` ; éventuel ajustement min_notional | unitaire+intégration risk | `tests/test_position_sizer_telemetry.py` | S3 |
| A-011 | P1 | `risk.max_drawdown/max_daily_loss` non override par préset | Ajouter overrides aux 6 presets | configuration | `tests/test_capital_preset_risk_overrides.py` | S3 |
| A-012 | P2 | Doublon `doc/backetesting.md` | Supprimer/rediriger | structure repo | `tests/test_doc_no_typo_duplicate.py` | S1 |
| A-013 | P2 | `config.yaml` valeurs littérales `"PK..."`/`"..."` | Supprimer, n'autoriser que `${VAR}` | configuration | `tests/test_config_no_literal_secrets.py` | S5 |
| A-014 | P2 | IHM Backtesting concurrent avec pipeline | Verrou IHM | E2E IHM | `tests/test_ihm_pipeline_concurrency_lock.py` | S2 |
| A-015 | P2 | `selector/alpha_scanner.py` 1 421 lignes | Finir extraction Phase 3.3.a | non-régression selector | `tests/test_alpha_scanner.py` extension | S7 |
| A-016 | P2 | `_execution_center.py` 2 550 lignes | Découper `_build_launch_options` | E2E IHM | `tests/test_ihm_pipeline_e2e.py` ; `tests/test_ihm_execution_e2e.py` | S6 |
| A-017 | P2 | Lecture barres ne filtre pas `data_source` | Télémétrie + log mix | intégration data | `tests/test_data_source_consistency_runtime.py` | S2 |
| A-018 | P2 | Watcher post-run optionnel oublié | Flag `--auto-watcher` | intégration execution | `tests/test_run_execution_auto_watcher.py` | S2 |
| A-019 | P2 | Pas d'autogen `data_lineage_matrix` | Implémenter `scripts/generate_data_lineage.py` | utilitaire | `tests/test_data_lineage_autogen.py` | S4 |
| A-020 | P2 | `risk.max_drawdown` libellé ambigu | Renommer `max_portfolio_drawdown_pct` | configuration | inclus dans A-011 | S3 |
| A-021 | P2 | Pas de seuil drift ML → action auto | Policy gate kill ML | intégration ML | `tests/test_ml_drift_policy_gate.py` | S4 |
| A-022 | P2 | `signal_aggregator` double application | Verrou idempotent | intégration sentiment | `tests/test_signal_aggregator_idempotency.py` | S1 |
| A-023 | P2 | Pas de check provider OHLCV homogène au démarrage | Check `% rows par data_source` | intégration data | `tests/test_data_source_consistency_runtime.py` | S2 |
| A-024 | P3 | Bandeau ASCII Windows | Remplacer par texte simple | n/a | n/a | S5 (cosmétique) |
| A-025 | P3 | Logs FR/EN mélangés | Standardiser | n/a | n/a | S6 |
| A-026 | P3 | `run.py` pas de `--port` doc | Documenter | doc | n/a | S5 |
| A-027 | P3 | Pas de `CHANGELOG.md` | Créer | doc | n/a | S5 |
| A-028 | P3 | `pyproject.toml` enrichir | Tags, classifiers | doc | n/a | S5 |
| A-029 | P3 | `.importlinter` non documenté | Documenter contracts | doc | n/a | S6 |
| A-030 | P3 | README §11 omet dossiers | Compléter | doc | n/a | S1 |
| A-031 | P3 | `prompt/` non organisé | Index ou README | doc | n/a | S9 |
| A-032 | P3 | `artifacts/` rétention | Politique documentée | doc | n/a | S4 |

## Vue agrégée par sprint

| Sprint | Anomalies traitées | Tests créés (count) | Tests étendus (count) |
|---|---|---|---|
| S1 | A-001, A-002, A-003 (doc), A-004, A-005, A-012, A-022, A-030 | 4 | 1 |
| S2 | A-003 (code), A-008, A-014, A-017, A-018, A-023 | 5 | 1 |
| S3 | A-006, A-007, A-009, A-010, A-011, A-020 | 5 | 2 |
| S4 | A-019, A-021, A-032 | 2 | 0 |
| S5 | A-013, A-024, A-026, A-027, A-028 | 1 | 0 |
| S6 | A-016, A-025, A-029 | 2 | 0 |
| S7 | A-015 | 0 | 1 |
| S8 | (étude empirique) | 2 | 0 |
| S9 | A-031, parité backtest/live | 1 | 0 |

**Total tests créés : 22 ; Tests étendus : 5.**

## Definition of Done par anomalie

Pour chaque anomalie, considérer comme **DONE** uniquement si :

1. Le correctif est mergé en main.
2. Le(s) test(s) listé(s) sont verts en CI.
3. La doc associée (si applicable) est mise à jour dans `doc/`.
4. Aucune régression sur la suite `pytest` complète.
5. Pour P0/P1 : revue par un second développeur senior.

## Liens croisés

- Voir `03_anomalies_register.md` pour le détail complet (preuves, impacts,
  blocs tests).
- Voir `08_sprint_plan.md` pour le plan complet par sprint avec tâches.

