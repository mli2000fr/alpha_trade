# 08 — Plan d'action par sprints

> Objectif : amener Alpha Trade de **7.4/10** à **9.0+/10** (pro-grade
> partiel → pro-grade) pour un usage swing US discipliné. 6 sprints
> structurants + 2 sprints d'amélioration continue.

Convention sprint : 2 semaines, 1 dev temps plein.

---

## Sprint S1 — Durcissement micro-comptes & clarté d'exécution (quick wins critiques)

**Priorité** : 🔴 Haute. **Anomalies traitées** : A-001, A-002, A-008, A-014, A-028.
**Modules impactés** : `config/capital_presets.yaml`, `execution_engine/`,
`run_execution.py`, `ihm/`, `selector/`, doc.

**État au 2026-05-22** : ✅ **livré et revalidé**.

- ✅ `risk_per_trade_pct` abaissé à `0.01` sur `capital_0_2000` et `0.0125` sur `capital_2001_5000`.
- ✅ `selector_max_anomaly_count` remis en monotonie croissante sur l'ensemble des presets (y compris `capital_100001_plus`).
- ✅ Alias `selector_min_ibd_rs_rank` introduit avec compatibilité `selector_min_relative_strength_index`.
- ✅ Bandeau IHM micro-compte présent dans `ihm/pages/settings.py`.
- ✅ `python -m execution_engine` émet bien un `DeprecationWarning` pour le chemin `run`.

**Tâches détaillées** :
1. Réduire `risk_per_trade_pct` à `0.01` pour 0–2k€ et `0.0125` pour 2–5k$ (A-001).
2. Ajuster `selector_max_anomaly_count` : monotonie inversée (15 micro → 22 gros) (A-014).
3. Renommer `selector_min_relative_strength_index` → `selector_min_ibd_rs_rank` (alias maintenu 1 release) (A-028).
4. Bandeau IHM "preset 0–2k€ assume concentration max" (A-008).
5. Déprécier `python -m execution_engine` pour `run` (DeprecationWarning + bandeau doc), conserver `cancel-all` (A-002).
6. Mise à jour `doc/risk_management.md`, `doc/selector.md`, `README.md`.

**Fichiers concernés** : `config/capital_presets.yaml`, `selector/cli.py`,
`selector/strict_filter_profiles.py`, `execution_engine/__main__.py`,
`run_execution.py`, `ihm/pages/settings.py`, `doc/risk_management.md`,
`doc/selector.md`, `README.md`.

**Critères d'acceptation** :
- Tests de monotonie passent et capturent inversion `max_anomaly_count`.
- `python -m execution_engine` émet `DeprecationWarning` testé.
- IHM preset 0–2k€ affiche bandeau warning testé.

**Tests à ajouter / étendre** :
| Test | Type | Fichier | Anomalie |
|---|---|---|---|
| `test_capital_preset_risk_per_trade_micro` | unitaire | `tests/test_capital_preset_risk_overrides.py` | A-001 |
| `test_capital_preset_max_anomaly_count_monotonic` | unitaire | `tests/test_capital_presets.py` | A-014 |
| `test_selector_min_ibd_rs_rank_alias` | unitaire | `tests/test_selector_alpha_scanner.py` | A-028 |
| `test_execution_facade_deprecation_warning` | unitaire | `tests/test_execution_cli_cancel_all.py` | A-002 |
| `test_ihm_settings_micro_preset_banner` | E2E IHM | `tests/test_pages_settings.py` | A-008 |
| **Non-régression** : suite full `tests/test_capital_preset_*` | régression | — | toutes |

**Gain notes** : Configuration 7.5→8.0, execution_engine 7.5→7.8, ihm 7.5→7.7.

---

## Sprint S2 — Verrou ordre `event_sentiment` + observabilité quote IEX

**Priorité** : 🔴 Haute. **Anomalies** : A-003, A-004, A-013, A-019, A-027.

**État au 2026-05-22** : 🟡 **partiellement livré, noyau critique validé**.

- ✅ Garde d'ordre `event_sentiment` visible au runtime (`failure_reason="event_sentiment_ordering_guard"`).
- ✅ Signal `provider_fallback_triggered=true` émis côté run summaries provider.
- ✅ Pré-check quota EODHD avant gros run sentiment.
- ✅ Vue IHM / overview des appels quota EODHD par feature.
- ⏳ Reste à industrialiser la métrique dédiée `quote_iex_vs_consolidated_bps` avec exposition IHM explicite.

**Tâches** :
1. `signal_aggregator` refuse si `relevance_backfill_at` < `news_ingestion_at` (A-003).
2. Verrou IHM "Sentiment Pipeline" : étapes 1→5 lancées en ordre forcé.
3. Métrique `quote_iex_vs_consolidated_bps` produite quotidiennement et affichée IHM (A-004).
4. Alerter `provider_fallback_triggered=true` (A-013) — bandeau IHM + email.
5. Pré-check quota EODHD avant `event_sentiment --all-symbols` (A-027).
6. Tableau de bord IHM "EODHD quota by feature" (A-019).

**Fichiers** : `event_sentiment/signal_aggregator.py`, `event_sentiment/pipeline.py`,
`ihm/pages/pipeline.py`, `ihm/pages/overview.py`,
`dataIntegrityEngine/import_eodhd_bar.py` (orchestrator + progress),
`service/eodhd/quota.py`, `service/alerting.py`.

**Critères** :
- `signal_aggregator` retourne `RuntimeError` (testé) si ordre violé.
- Métrique quote bias visible run_summary + IHM.
- Quota EODHD bloque preventivement test.

**Tests** :
| Test | Type | Fichier | Anomalie |
|---|---|---|---|
| `test_signal_aggregator_main_emits_blocked_summary_when_ordering_guard_fails` | intégration | `tests/test_event_sentiment_run_summaries.py` | A-003 |
| `test_quote_iex_vs_consolidated_bias` | data quality | `tests/test_quote_iex_vs_consolidated_bias.py` (nv) | A-004 |
| `test_update_missing_sectors_falls_back_to_finnhub_after_eodhd_permission_error` | intégration | `tests/test_update_sector.py` | A-013 |
| `test_eodhd_quota_precheck_blocks_run` | intégration | `tests/test_clientEodhd.py` (étendu) | A-027 |
| `test_build_eodhd_quota_feature_rows_sorts_by_calls_desc` | IHM / helper | `tests/test_pages_overview.py` | A-019 |

**Gain** : event_sentiment 6.5→7.5, observabilité 7.0→7.5, dataIntegrityEngine 8.0→8.3.

---

## Sprint S3 — Réconciliation J+1 + TCA agrégé + gel IHM pendant live

**Priorité** : 🔴 Haute. **Anomalies** : A-005, A-015, A-024.

**État au 2026-05-22** : 🟡 **en cours avancé**.

- ✅ Point d'entrée canonique `python -m execution_engine.reconcile_statement` ajouté.
- ✅ Parsing CSV Alpaca J+1 + persistance du résumé structuré dans `run_business_summaries(step_key='execution_reconciliation_j1')`.
- ✅ Page `ihm/pages/execution.py` enrichie : section **Réconciliation J+1** + **TCA agrégé**.
- ✅ Gel IHM pendant `execution_runs.status='RUNNING' AND broker_mode='live'` sur pages `execution` et `pipeline`.
- ✅ Verrou state-machine IHM : une étape N ne se lance plus si N-1 n'est pas `SUCCESS/COMPLETED`.
- ⏳ Parsing PDF Alpaca : reste à industrialiser si l'export opérateur PDF doit être supporté nativement sans étape CSV intermédiaire.

**Tâches** :
1. Job nightly `execution_engine.reconcile_statement` parsant CSV/PDF Alpaca J+1.
2. Page IHM "Réconciliation J+1" avec divergences chiffrées.
3. Page IHM "TCA" agrégée par compte / par tranche / par mois.
4. Verrou IHM : étape pipeline N+1 désactivée tant que N ≠ SUCCESS (A-015).
5. Bandeau persistant + gel actions destructrices quand `execution_runs.status='RUNNING' AND mode='live'` (A-024).

**Fichiers** : `execution_engine/reconciliation.py` (extend),
`execution_engine/cli.py`, `ihm/pages/execution.py`, `ihm/pages/pipeline.py`,
`ihm/components/`.

**Tests** :
| Test | Type | Fichier | Anomalie |
|---|---|---|---|
| `test_broker_statement_reconciliation_j1` | intégration | `tests/test_broker_statement_reconciliation.py` (étendu) | A-005 |
| `test_ihm_pipeline_state_machine_lock` | E2E IHM | nouveau | A-015 |
| `test_ihm_live_mode_locks_destructive_actions` | E2E IHM | nouveau | A-024 |
| `test_tca_dashboard_aggregates` | E2E IHM | nouveau `tests/test_pages_execution_tca.py` | A-005 |

**Gain** : execution_engine 7.5→8.2, ihm 7.7→8.0, observabilité 7.5→8.0.

> ✅ **À partir de la fin du Sprint S3, l'application est considérée comme
> robuste pour un swing trading réel discipliné sur compte ≥ 10 k$.**

---

## Sprint S4 — Parité backtest/live full-stack + oracle total return

**Priorité** : 🟠 Moyenne-haute. **Anomalies** : A-009, A-030, A-025.

**État au 2026-05-22** : 🟡 **en cours avancé**.

- ✅ Convention de corrélation explicitée dans le code via `risk_management.correlation_filter.build_return_matrix(...)` :
  `price_only_close_split_adjusted` vs `total_return_with_cash_dividends`.
- ✅ Oracle total return ajouté via `backtesting.analytics.compare_total_return_to_oracle(...)` avec tolérance en bps.
- ✅ Couverture de tests étendue sur l'oracle et les conventions de corrélation.
- ✅ La brique full-stack `compare_to_live` existante dans `backtesting/fidelity.py` reste le socle de parité multi-couches (candidats, risk, portfolio, execution, fills, exits, pnl).
- ✅ Test dédié `tests/test_parity_backtest_live_full_stack.py` ajouté pour verrouiller la parité multi-couches sur le socle `compare_to_live`.
- ⏳ Reste possible : brancher un oracle externe réellement téléchargé (Yahoo/Bloomberg-like) en nightly automatique plutôt qu'un helper pur comparatif.

**Tâches** :
1. Nightly job "replay 10 jours live paper → backtest reproduit à ε" (sentiment + ML + macro activés).
2. Oracle "MTM + ledger == total return Bloomberg-like" sur 5 tickers à dividende récurrent (KO, JNJ, PG, MSFT, AAPL).
3. Documenter convention corrélation (close split-adj vs returns dividend-adj) + test (A-025).
4. Calibration empirique poids conviction (déclencher job trimestriel `tests/test_quarterly_calibration_job.py`).

**Fichiers** : `backtesting/parity.py`, `backtesting/signal_replay.py`,
`backtesting/fidelity.py`, `risk_management/correlation_filter.py`,
`risk_management/audit.py`, `corporate_actions/engine.py` (oracle test).

**Tests** :
| Test | Type | Fichier | Anomalie |
|---|---|---|---|
| `test_parity_backtest_live_full_stack` | parité | nouveau | A-009 |
| `test_total_return_oracle_dividends` | data quality | `tests/test_backtest_total_return_with_dividends.py` (étendu) | A-030 |
| `test_correlation_filter_convention` | propriété | `tests/test_correlation_filter.py` (étendu) | A-025 |

**Gain** : backtesting 7.5→8.5, corporate_actions 8.0→8.5, risk_management 7.5→8.0.

---

## Sprint S5 — Sécurité, signature artefacts, broker failover doctrine

**Priorité** : 🟠 Moyenne. **Anomalies** : A-016, A-020, A-021.

**État au 2026-05-22** : 🟡 **majoritairement livré et validé**.

- ✅ Manifestes SHA256 d'artefacts ML générés côté `trainer` / `orchestrator` puis vérifiés côté `predictor`.
- ✅ Doctrine failover opérateur exposée dans `ihm/pages/alpaca_accounts.py` + runbook `doc/runbook_broker_failover.md`.
- ✅ Préflight exécuté aussi en `simulate` avec downgrade non bloquant en `WARN` dans `run_execution.py`.
- ✅ Validation ciblée S5/S6 : `97 passed` sur les suites dédiées le 2026-05-22.
- ⏳ Reste hors livraison actuelle : profil DB read-only explicite pour l'IHM et doc formelle de rotation de secrets.

> **Note d'implémentation** : aucune migration SQL / `ALTER TABLE` n'a été nécessaire pour A-020 ; la signature des artefacts est implémentée sous forme de manifestes JSON sur le filesystem, adjacents aux artefacts.

**Tâches** :
1. Signature SHA256 manifest des artefacts `models/` au champion selection (A-020).
2. Vérification signature au load par `predictor.py`.
3. Runbook IHM "Broker primaire / secondaire" + page "Brokers" (A-016).
4. Préflight bloquant aussi en `simulate` mais avec downgrade `WARN` (A-021).
5. Profil DB read-only pour IHM, doc rotation secrets.

**Fichiers** : `modelFactory/champion_selection.py`, `modelFactory/predictor.py`,
`service/broker_failover.py`, `ihm/pages/`, `doc/runbook_broker_failover.md` (nv),
`database/connection.py` (profil RO).

**Tests** :
| Test | Type | Fichier | Anomalie |
|---|---|---|---|
| `test_ml_artifacts_signature_verification_detects_mismatch` | intégration | `tests/test_ml_artifacts_backup.py` | A-020 |
| `test_predict_symbol_returns_none_when_required_artifact_signature_mismatches` | intégration | `tests/test_model_factory_predictor.py` | A-020 |
| `test_ihm_brokers_page_failover_doctrine` | IHM / helper | `tests/test_pages_alpaca_accounts.py` | A-016 |
| `test_simulate_mode_warns_on_preflight_fail_but_does_not_abort` | unitaire | `tests/test_run_execution_blocks_on_preflight_fail.py` | A-021 |

**Gain** : sécurité 7.5→8.5, modelFactory 7.0→7.5.

---

## Sprint S6 — Calibration Kelly conditionnelle, defaults macro, doc

**Priorité** : 🟡 Moyenne-basse. **Anomalies** : A-006, A-007, A-011, A-012, A-023, A-029.

**État au 2026-05-22** : 🟡 **majoritairement livré**.

- ✅ `market_regimes.macro_provider` basculé à `composite`.
- ✅ `risk_enable_kelly` activé uniquement sur les presets `>= 25 k$`.
- ✅ Ordre configuré de `fallback_levels` verrouillé par test.
- ✅ Bandeau IHM explicite quand SMTP n'est pas configuré.
- ✅ Documentation `doc/risk_management.md` enrichie sur Kelly conditionnel et convention `risk_max_drawdown_pct`.
- ⏳ Reste à publier un runbook dédié "incident sentiment provider" (A-023) si l'on veut fermer tout le sprint au sens documentaire strict.

**Tâches** :
1. Décision explicite Kelly : activer sur tranche ≥ 25 k$ après calibration (A-006).
2. Default `macro_provider: composite` (A-007).
3. Test propriété `fallback_levels` weights_calibration (A-011).
4. Bandeau IHM "SMTP non configuré → aucune notification" (A-012).
5. Runbook incident sentiment provider (A-023).
6. Documenter convention `risk_max_drawdown_pct` par tranche (A-029).

**Fichiers** : `config.yaml`, `config/capital_presets.yaml`,
`risk_management/kelly.py`, `service/market/`, `risk_management/weights_calibration*`,
`ihm/services/notifications.py`, `doc/runbook_provider_incident.md`,
`doc/risk_management.md`.

**Tests** : `tests/test_capital_preset_risk_overrides.py`, `tests/test_macro_providers.py`,
`tests/test_weights_calibration.py`, `tests/test_ihm_notifications_smtp_missing_banner.py`.

**Gain** : configuration 8.0→8.5, risk_management 8.0→8.3, doc 7.5→8.5.

---

## Sprint S7 — Documentation, POC scoping, INDEX conventions

**Priorité** : 🟡 Basse. **Anomalies** : A-010, A-026.

**Tâches** :
1. Page `doc/CONVENTIONS.md` unique listant les conventions en vigueur (split-only, provider primaire, cash settled, swing_only, etc.).
2. Déplacement POCs vers `doc/_poc/` ou bandeau "POC non activé" (A-010).
3. Test propriété DST sur `market_calendar.py` (A-026).
4. CHANGELOG `doc/CHANGELOG.md`.
5. Mise à jour `DOC_FONCTIONNELLE.md` / `DOC_TECHNIQUE.md` pour refléter sprints S1–S6.

**Tests** : `test_doc_index_and_links.py` (étendu pour POC), `test_market_calendar.py` (étendu DST).

**Gain** : doc 8.5→9.0.

---

## Sprint S8 — Multi-source `stock_bars_daily` (optionnel)

**Priorité** : 🟢 Optionnel (recherche). **Anomalies** : A-022.

**Tâches** :
1. Migration Alembic feature-flagged `PRIMARY KEY (symbol, date, data_source)`.
2. Mode shadow Alpaca + EODHD same-day + tableau d'écarts IHM.
3. Test régression `test_data_adjustment_multisource_migration.py`.

**Gain** : dataIntegrityEngine 8.3→8.7, database 8.0→8.5.

---

## Matrice anomalie → sprint

| Anomalie | Sprint | Sprint | Sprint |
|---|---|---|---|
| A-001 / A-008 / A-014 / A-028 | S1 | | |
| A-002 | S1 | | |
| A-003 / A-004 / A-013 / A-019 / A-027 | S2 | | |
| A-005 / A-015 / A-024 | S3 | | |
| A-009 / A-025 / A-030 | S4 | | |
| A-016 / A-020 / A-021 | S5 | | |
| A-006 / A-007 / A-011 / A-012 / A-023 / A-029 | S6 | | |
| A-010 / A-026 | S7 | | |
| A-017 / A-018 | S7 / S8 | | |
| A-022 | S8 (optionnel) | | |

## Trajectoire de notes

| Module | Avant | Après S3 | Après S6 | Après S8 |
|---|---:|---:|---:|---:|
| Configuration | 7.5 | 8.0 | 8.5 | 8.5 |
| dataIntegrityEngine | 8.0 | 8.3 | 8.3 | 8.7 |
| database | 8.0 | 8.0 | 8.0 | 8.5 |
| selector | 7.0 | 7.5 | 7.5 | 7.5 |
| event_sentiment | 6.5 | 7.5 | 7.7 | 7.7 |
| risk_management | 7.5 | 8.0 | 8.3 | 8.3 |
| execution_engine | 7.5 | 8.2 | 8.2 | 8.2 |
| backtesting | 7.5 | 7.5 | 8.5 | 8.5 |
| ihm | 7.5 | 8.0 | 8.2 | 8.2 |
| observabilité | 7.0 | 8.0 | 8.0 | 8.0 |
| sécurité | 7.5 | 7.5 | 8.5 | 8.5 |
| modelFactory | 7.0 | 7.0 | 7.5 | 7.5 |
| corporate_actions | 8.0 | 8.0 | 8.5 | 8.5 |
| documentation | 7.5 | 7.5 | 8.5 | 9.0 |
| **Note globale** | **7.4** | **7.9** | **8.4** | **8.6** |

## "Reste pour atteindre un vrai 10/10 pro-grade"

1. **Multi-broker production** : Alpaca + IBKR + secondaire failover live testé bout en bout sur compte réel.
2. **Latence intraday < 200 ms** sur watcher : observabilité Prometheus / Grafana standardisée.
3. **Réplica DB lecture** pour soulager IHM en prod.
4. **Mutation testing** nightly bloquant en CI publique.
5. **Capacity planning** documenté (max symboles, max comptes simultanés, RTO/RPO).
6. **Audit externe indépendant** signé (preuves dans `doc/external_audit/`).
7. **Conformité fiscale étendue** (1099, FATCA, wash sale multi-comptes) — partiellement présent (`tax/`).
8. **Data lineage cryptographique** (signature des bars ingérées, vérifiable a posteriori).

## "À partir de quel sprint l'application devient suffisamment robuste pour un swing trading réel discipliné"

> ✅ **Fin de Sprint S3** : application **suffisamment robuste pour un swing
> trading réel discipliné** sur compte ≥ 10 k$.
>
> ✅ **Fin de Sprint S6** : application **pro-grade partiel** pour usage
> autonome discipliné multi-comptes, y compris compte 100 k$+.
>
> ⚠️ **Sous 5 k$** : restera "éducatif" même après S8 si l'opérateur prend
> les défauts micro-compte comme acquis sans discipline particulière.

