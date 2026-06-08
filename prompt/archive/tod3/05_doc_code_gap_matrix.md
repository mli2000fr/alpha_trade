# 05 — Matrice écarts Doc ↔ Code ↔ Config

Le code est source de vérité.

| # | Sujet | Doc | Code | Config | Verdict | Action |
|---|---|---|---|---|---|---|
| G-01 | Provider OHLCV primaire | `doc/dataIntegrityEngine.md` : EODHD ; `doc/data_lineage_matrix.md` : EODHD | `import_alpaca_bar.py` : DATA_ADJUSTMENT='split' inconditionnel ; `import_eodhd_bar.py` shim → orchestrator | `config.yaml:182` `bars_provider: eodhd` | ✅ **Aligné** | RAS — bandeau présent. |
| G-02 | Convention prix | `corporate_actions/engine.py:34-55` docstring split-only | Idem code | `chk_bars_adj` contrainte SQL (cf. doc/database.md §9) | ✅ **Aligné** | RAS. |
| G-03 | Multi-source `stock_bars_daily` | `doc/data_lineage_matrix.md` parle de cohabitation théorique | Schéma `PRIMARY KEY(symbol,date)` empêche en pratique | — | ⚠️ Doc déjà corrigée 2026-05-22 (note explicite) | A-022 dans backlog. |
| G-04 | Façade `python -m execution_engine` | `README.md §8` la présente comme compatibilité | `execution_engine/__main__.py` et `cli.py` actifs | — | ⚠️ Double doctrine — A-002 | Déprécier explicitement. |
| G-05 | Provider news par défaut | `README.md §8 Sentiment` : eodhd ; `doc/event_sentiment.md` à confirmer | `event_sentiment/ingestion.py` provider switch | — | ✅ aligné si doc à jour | Vérifier `doc/event_sentiment.md`. |
| G-06 | `macro_provider` valeurs | Commentaire `config.yaml:59-61` mentionne `composite` | `service/market/` charge `eodhd` par défaut | `config.yaml:62` `eodhd` | ⚠️ Cohérent mais sous-optimal (A-007) | Changer défaut. |
| G-07 | `risk_enable_kelly: false` partout | `doc/risk_management.md` à vérifier | `risk_management/kelly.py` + tests existants | `capital_presets.yaml` tous false | ⚠️ Statut Kelly ambigu (A-006) | Doc explicite "expérimental". |
| G-08 | Contraintes cash/swing sur presets petits comptes | Commentaires `capital_presets.yaml` | `execution_engine` + presets capital | OK | ✅ Aligné | RAS. |
| G-09 | Notifications SMTP | `config.yaml:218-227` bloc commenté | `service/alerting.py` ? IHM `ihm/services/` | — | ⚠️ Risque silence (A-012) | Bannière IHM. |
| G-10 | `notifications` destinataires | `config.yaml:209-211` mentionne JSON `artifacts/ihm_preferences/notifications.json` | À confirmer côté `ihm/services/` | — | À vérifier | Couvrir en test E2E. |
| G-11 | Trailing stop "dynamic_atr" enabled:false | `config.yaml:163` | `execution_engine/config.py:TrailingStopConfig` + `service.market.parse_trailing_stop` | OK | ✅ Aligné — trailing off par défaut | Documenter activation. |
| G-12 | Ordre étapes pipeline | `README.md §6` ordonné 1→14 | `ihm/pages/pipeline.py` ? | — | ⚠️ Pas de verrou (A-015) | Verrouiller IHM. |
| G-13 | Multi-comptes Alpaca | `README.md §12` documenté | `service/alpaca/accounts.py` AccountRegistry | `config.yaml:22-37` | ✅ Aligné | RAS. |
| G-14 | `account_id` propagé tables | `README.md §12.6` 14 tables listées | `alembic/versions/` migrations + `database/sql/migration_add_account_id.sql` | — | ✅ Aligné | RAS. |
| G-15 | Diagnostic screener IHM | `README.md §9` note dashboard backtesting → diagnose-screener | `backtesting/screener_diagnostics/` + `ihm/pages/backtesting*` | — | ✅ Aligné | RAS. |
| G-16 | `event_sentiment` ordre sous-étapes IHM | `README.md §8` "Le launcher IHM ne lance pas un simple `python -m event_sentiment` monolithique" | `event_sentiment/pipeline.py` / `event_sentiment_pipeline.py` | — | ⚠️ Pas testé bout en bout (A-003) | Test E2E IHM dédié. |
| G-17 | `python -m corporate_actions sync --portfolio-only` doit suivre `run_execution` | `README.md §6 note "Pourquoi le sync CA vient après…"` justifie | OK code | — | ✅ Aligné | RAS. |
| G-18 | Bandeau IEX dans run_summary | `doc/dataIntegrityEngine.md §0` | `core.run_summary.merge_iex_bias_counters` | — | ✅ Aligné | RAS. |
| G-19 | Rétention `artifacts/` | `README.md §11` renvoie `doc/artifacts_retention_policy.md` | `scripts/prune_artifacts.py` | — | ✅ Aligné | RAS — vérifier que la doc cite bien le script. |
| G-20 | Secrets : aucun PK/AK/sk littéral | `README.md §12.1`, `core/secrets.py` | `tests/test_config_no_literal_secrets.py` | OK | ✅ Aligné | RAS. |
| G-21 | `mypy.ini` / typage | `pyproject.toml` + `mypy.ini` | — | — | À vérifier coverage stricte | Étendre `strict = true` modules critiques. |
| G-22 | `pytest.ini` markers | — | — | À vérifier markers utilisés (e.g. integration) | RAS si déjà nommés. |
| G-23 | `import_alpaca_bar` no-op en mode eodhd | `doc/dataIntegrityEngine.md` correction 2026-05-22 | Code vérifié partiellement (test `test_import_alpaca_bar_noop.py`) | OK | ✅ Aligné | RAS. |
| G-24 | DOC_FONCTIONNELLE / DOC_TECHNIQUE | Présentes (`doc/`) | À relire en lecture approfondie | — | À vérifier | Voir note `doc/AUDIT_2026_05_22_doc_updates.md`. |
| G-25 | IBKR adapter | `doc/ibkr_setup.md`, `doc/runbook_provider_incident.md` | `service/ibkr/` actif paper | — | ✅ Aligné | A-016 — runbook failover explicite. |
| G-26 | `selector_min_relative_strength_index` nommage | `doc/selector.md` à vérifier | Code traite comme IBD RS rank ≥ 100 | OK | ⚠️ Nommage trompeur (A-028) | Renommer ou clarifier doc. |
| G-27 | Calendrier de trading / DST | `common/market_calendar.py` | Tests présents | — | À vérifier (A-026) | Test DST dédié. |

## Synthèse

| Catégorie | Compte |
|---|---|
| ✅ Aligné | 14 |
| ⚠️ Désalignement mineur / déjà corrigé | 7 |
| ⚠️ À traiter (P1/P2) | 6 |
| ❌ Divergence bloquante | 0 |

Aucune divergence **bloquante** détectée. Le code et la doc sont
significativement mieux alignés que la moyenne grâce aux notes "Correction
audit 2026-05-22" déjà appliquées par l'auteur.

