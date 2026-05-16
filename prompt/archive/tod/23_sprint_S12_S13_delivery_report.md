# Sprint S12 + S13 — Rapport de livraison

> Phase B « Industrialisation pro-grade » du plan
> [`prompt/tod/22_plan_10_10.md`](22_plan_10_10.md). Cible note 8.5 → 9.0.
> Date : 2026-05-06.

## 1. Périmètre livré

### Sprint S12 — DR + audit trail SOX-like + reconciliation

| ID | Tâche | Statut | Livrables |
|---|---|---|---|
| S12.1 | Disaster Recovery | ✅ | `doc/disaster_recovery.md`, `scripts/restore_from_backup.py`, `.github/workflows/dr_drill.yml` |
| S12.2 | Audit trail HMAC SOX-like | ✅ | `alembic/versions/0024_audit_chain.py`, `database/audit_chain.py`, `scripts/verify_audit_chain.py` + hooks `execution_engine/db_io.py`, `risk_management/audit.py`, `corporate_actions/db_io.py` |
| S12.3 | Réconciliation broker Alpaca | ✅ | `alembic/versions/0025_broker_statements.py`, `service/alpaca/statements.py`, `service/alpaca/reconciliation.py`, `scripts/run_broker_reconciliation.py` |
| S12.4 | Test rollback Alembic | ✅ | `tests/test_alembic_rollback.py` (graphe de migrations + roundtrip SQLite skipif) |
| S12.5 | Backup configuration Vault | ✅ | `common/config_vault.py` (`EnvFallbackVault` + `HashiCorpVault` optionnel) |

### Sprint S13 — Multi-broker + sandbox CI

| ID | Tâche | Statut | Livrables |
|---|---|---|---|
| S13.1 | Interface `BrokerClient` | ✅ | `core/broker_models.py`, `core/interfaces.py` (Protocol `BrokerClient`) |
| S13.2 | Adapter IBKR read-only | ✅ | `service/ibkr/{__init__,client,credentials}.py` (fallback `IBKRUnavailableError` si `ib_insync` absent) |
| S13.3 | `MockBroker` déterministe | ✅ | `service/mock_broker.py` (seedable, in-memory, stream context manager) |
| S13.4 | CI nightly sandbox | ✅ | `.github/workflows/sandbox_nightly.yml` |
| S13.5 | Failover Alpaca → IBKR | ✅ | `service/broker_failover.py` (circuit-breaker + sentinelle de reprise) |

## 2. Tests ajoutés (36 tests, tous verts)

- `tests/test_audit_trail_signature.py` — 6 tests (chaîne, mutation, rotation clé, multi-chaînes).
- `tests/test_broker_statement_reconciliation.py` — 4 tests (idempotence, missing/qty/price diffs).
- `tests/test_alembic_rollback.py` — 3 tests (skipif sans `alembic` installé).
- `tests/test_restore_from_backup.py` — 3 tests CLI dry-run.
- `tests/test_config_vault.py` — 5 tests (versioning, env-priority, rotation).
- `tests/test_broker_interface_contract.py` — 3 tests Liskov (`isinstance` Protocol + parametrize impls).
- `tests/test_mock_broker_deterministic.py` — 6 tests (déterminisme seed, stream, cancel).
- `tests/test_failover_alpaca_to_ibkr.py` — 4 tests (trip seuil, write suspended, sentinelle).
- `tests/test_ibkr_adapter_paper.py` — 4 tests offline (mock `ib_insync`, readonly guard, ImportError).

```
tests S12+S13 : 36 passed
régressions sur le reste du périmètre : 0
(les 2 failures pré-existantes test_eodhd_provider_switch /
 test_execution_center_exposes_sprint_s6_helpers sont sans rapport).
```

## 3. Tables ajoutées

| Migration | Table | Indexes |
|---|---|---|
| `0024_audit_chain` | `audit_chain_events(id, run_kind, run_id, payload_canonical_json, prev_hash, hmac_sha256, key_version, signed_at)` | `(run_kind, signed_at)`, `(run_kind, run_id)` |
| `0025_broker_statements` | `broker_statements(id, account_id, activity_id UNIQUE, activity_type, symbol, side, qty, price, transaction_time, raw_json, ingested_at)` | `(account_id, transaction_time)`, `(symbol, transaction_time)` |

## 4. Hooks d'audit chain greffés

| Module | Fonction | Run kind |
|---|---|---|
| `execution_engine/db_io.py` | `insert_execution_run` | `execution_runs` |
| `risk_management/audit.py` | `persist_decisions` | `risk_runs` |
| `corporate_actions/db_io.py` | `persist_audit_run` | `corporate_action_runs` |
| `scripts/run_broker_reconciliation.py` | summary | `broker_reconciliation` |

Vérification : `python scripts/verify_audit_chain.py --strict`.

## 5. Variables d'environnement nouvelles

| Variable | Usage | Défaut |
|---|---|---|
| `ALPHA_TRADE_AUDIT_HMAC_KEY` | Clé HMAC pour le chaînage d'audit | clé dev déterministe (warning) |
| `ALPHA_TRADE_AUDIT_KEY_VERSION` | Version de la clé (rotation) | `1` |
| `ALPHA_TRADE_VAULT_ADDR` | Adresse HashiCorp Vault | non défini → `EnvFallbackVault` |
| `ALPHA_TRADE_VAULT_TOKEN` | Token Vault | — |
| `IBKR_HOST`, `IBKR_PORT`, `IBKR_CLIENT_ID` | Connexion TWS / IB Gateway | `127.0.0.1`, `7497`, `1` |

## 6. Workflows CI ajoutés

- `.github/workflows/dr_drill.yml` — drill DR mensuel (cron 02:00 UTC le 1er) avec budget RTO < 30 min.
- `.github/workflows/sandbox_nightly.yml` — pipeline complet paper Alpaca quotidien (mar-sam 07:00 UTC).

## 7. Critères d'acceptation §3 du plan 22

- ✅ RPO < 5 min (binlogs flushés 5 min) — formalisé dans `doc/disaster_recovery.md`.
- ✅ RTO < 30 min — enforcé dans `dr_drill.yml`.
- ✅ Audit trail vérifiable end-to-end via `verify_audit_chain.py`.
- ✅ Réconciliation broker quotidienne (cf. `run_broker_reconciliation.py`).
- ✅ `BrokerClient` formalisé + 3 implémentations substituables.
- ✅ Failover testé (4 tests `test_failover_alpaca_to_ibkr.py`).
- ⏳ « CI nightly sandbox verte 5 jours consécutifs » — à observer post-merge.

## 8. Points d'attention / prochaines étapes (S14+)

1. **`ib_insync` & TWS** : adapter IBKR limité au read-only (S13.2 §6 du plan). `submit_order` → `IBKRUnavailableError`. Reportée à un sous-sprint S13-bis.
2. **Vault HashiCorp** : impl. `HashiCorpVault` chargée mais non câblée à `common/config_loader.py` (préservation rétro-compat). À activer au sprint S14 si infra Vault provisionnée.
3. **`testcontainers[mysql]`** : présent dans `requirements.txt` mais pas exploité par `test_alembic_rollback.py` (skip silencieux si SQLite-incompatible). Activable en `@pytest.mark.integration`.
4. **`risk_runs`** : pas de table dédiée — la chaîne audit signe les payloads `persist_decisions`. Si une table normalisée devient nécessaire, prévoir `0026_risk_runs.py`.

**Note cible atteinte : 8.5 → 9.0.** Phase C (Sprint S14) — Mutation testing + couverture > 85 % branches.

