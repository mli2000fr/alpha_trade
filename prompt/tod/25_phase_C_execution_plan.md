# 25 — Plan d'exécution Phase C (S14 → S18)

> Établi le 2026-05-06 sur la base de `22_plan_10_10.md` (Phase C) et de
> l'état post-Phase B (rapport `23_sprint_S12_S13_delivery_report.md`,
> `24_phase_A_delivery_report.md`).
>
> Objectif : 9.0 → 10.0 sur 5 sprints (S14 → S18).
>
> **Contrainte transverse** : tout livrable Phase C doit être exécutable
> sans dépendance infra externe (Redis, Neo4j, TWS, Vault, TLAPS, Slack).
> Les intégrations live sont fournies en option via interface
> pluggable + adaptateur stub par défaut.

---

## TL;DR

Phase C amène la note 9.0 → 10.0 sur 10 semaines (5 sprints). Le baseline
(Phases A/B livrées) fournit déjà l'audit chain HMAC, le multi-broker
(Alpaca + IBKR + Mock), DR, parité backtest/live et calibration
trimestrielle. La Phase C ajoute :

- **qualité formelle** (mutation testing + Z3/TLA+),
- **conformité** (reporting mensuel, tax, lineage),
- **performance** (benchmarks, cache, async DB),
- **finition** (doc C4, SBOM, API stable).

**Stratégie clé** : tout ce qui exige une infra externe (Redis, Neo4j,
TLAPS, Vault) est livré en pur Python avec un **adaptateur stub local
par défaut** + interface pluggable, pour rester exécutable en CI sans
services tiers.

---

## Baseline observé (à ne pas refaire)

| Élément déjà présent | Réutilisation Phase C |
|---|---|
| `backtesting/attribution.py` | Étendre vers Brinson-Fachler sectoriel (S16.2) |
| `service/alpaca/{statements,reconciliation}.py` + table `broker_statements` | Source de vérité rapport mensuel S16.1 |
| `database/audit_chain.py` + `verify_audit_chain.py` | Source HMAC pour signer rapports S16.1 |
| `scripts/generate_data_lineage.py` | Brancher exporter graphe (S16.4) |
| `core/interfaces.py::BrokerClient` + `MockBroker` | Réutilisé pour fuzzing différentiel S15.2 |
| `corporate_actions/models.py::compute_idempotency_key` | Cible invariant formel S15.1.a |
| `execution_engine/oco_manager.py` (ou équivalent) | Cible invariant formel S15.1.b |
| `execution_engine/preflight.py`, `account_state.py` | Cible invariant formel S15.1.c |
| `requirements-dev.txt::pytest-benchmark>=4` | Activer S17.1 |
| `.github/workflows/{ci,dr_drill,sandbox_nightly,...}.yml` | Modèle pour 4 nouveaux workflows |
| `pytest.ini --cov-fail-under=60` | Monter à 80 puis 90 (S14.2 / S18.4) |

---

## Dépendances externes — faisabilité

| Dépendance | Sprint | Statut local | Stratégie |
|---|---|---|---|
| `mutmut>=2.5` | S14 | ✅ pip pur Python | `[dev]`, scope 3 modules |
| `cosmic-ray` | S14 | ⚠️ Lourd | **Écarté** au profit de mutmut |
| `hypothesis` | S14 | ✅ déjà présent | Étendre |
| `z3-solver` | S15 | ✅ pip pur (~50 Mo) | Retenu pour 3 invariants |
| TLA+ / TLAPS | S15 | ❌ JVM + IDE | **Stub** : specs `.tla` versionnées + check syntaxique opt. |
| `reportlab` | S16 | ✅ pip pur | PDF mensuel |
| `neo4j` driver | S16 | ⚠️ serveur requis | **`InMemoryGraphStore`** + adapter Neo4j opt-in |
| `redis` | S17 | ⚠️ serveur requis | **`InMemoryCache`** + `RedisCache` opt-in |
| `aiosqlite` / `asyncpg` | S17 | ✅ pip | aiosqlite testable, asyncpg opt-in |
| `cyclonedx-bom` / `pip-audit` | S18 | ✅ pip pur | SBOM + scan CVE |
| Audit externe humain | S18 | ❌ | **Stub** : `doc/external_audit_checklist.md` |
| Vidéo onboarding | S18 | ❌ | **Stub** : `doc/onboarding_walkthrough.md` |

---

## Tâches consciemment réduites/stubbées

1. **TLA+ partenariat consultant** → specs TLA+ syntaxiques + preuves Z3 exécutables.
2. **Neo4j live** → `InMemoryGraphStore` (dict + JSON + DOT) ; driver Neo4j optionnel via `skipif`.
3. **Redis** → `InMemoryCache` LRU + TTL ; `RedisCache` opt-in.
4. **Async DB asyncpg** → POC `aiosqlite`, `asyncpg` non câblé en CI.
5. **Audit externe S18.3** → checklist d'auto-audit.
6. **Vidéo onboarding S18.1** → walkthrough textuel + diagrammes Mermaid C4.
7. **Cible mutation 70 %** → 50 % en S14 réaliste, follow-up tracé.

---

## Sprint S14 — Mutation testing + branches > 85 % + Hypothesis

### Fichiers à créer
- `pyproject.toml` → section `[tool.mutmut]`.
- `requirements-dev.txt` → `mutmut>=2.5`, `coverage[toml]>=7`.
- `scripts/run_mutation_testing.py` — wrapper, écrit `artifacts/mutation_runs/<date>/score.json`.
- `.github/workflows/mutation_weekly.yml`.
- `.github/workflows/branch_coverage.yml`.
- `tests/property/test_position_sizer_properties.py`.
- `tests/property/test_circuit_breaker_properties.py`.
- `tests/property/test_synthetic_bracket_properties.py`.
- `doc/mutation_testing.md`.

### Critères d'acceptation
- ≥ 50 % score mutation par module (cible nominale 70 % traçable).
- Branches ≥ 85 % sur 3 modules ; CI fail < 80 %.
- ≥ 3 nouvelles suites property-based vertes.
- `artifacts/mutation_runs/` archivé.

---

## Sprint S15 — Formal verification + fuzzing différentiel

### Fichiers à créer
- `formal/__init__.py`
- `formal/z3_invariants/idempotence_corporate_actions.py`
- `formal/z3_invariants/oco_synthetic_bracket.py`
- `formal/z3_invariants/no_double_execution.py`
- `formal/tla/IdempotenceCA.tla`
- `formal/tla/OCOBracket.tla`
- `formal/tla/NoDoubleExec.tla`
- `formal/tla/README.md`
- `scripts/run_formal_verification.py`
- `tests/formal/test_z3_invariants.py`
- `tests/property/test_backtest_live_differential.py`
- `doc/formal_verification.md`
- `.github/workflows/formal_verification.yml`

### Critères
- 3 preuves Z3 `unsat` sur la négation < 30 s.
- Specs TLA+ parsable (skipif si tla2tools absent).
- Suite stateful 10 000 cas verte ; 0 divergence.
- `doc/formal_verification.md` publié.

---

## Sprint S16 — Reporting mensuel + Brinson + Tax + Lineage

### Fichiers à créer
- `reporting/__init__.py`, `reporting/monthly_report.py`,
  `reporting/pdf_renderer.py`, `reporting/json_schema.py`.
- `backtesting/brinson_fachler.py`.
- `tax/__init__.py`, `tax/wash_sale.py`, `tax/holding_periods.py`,
  `tax/form_1099b_export.py`.
- `ihm/pages/tax_compliance.py`.
- `lineage/__init__.py`, `lineage/graph_store.py`,
  `lineage/neo4j_store.py`, `lineage/event_listener.py`.
- `scripts/run_monthly_broker_report.py`.
- `.github/workflows/monthly_report.yml`.
- Tests : `test_monthly_report.py`, `test_brinson_fachler.py`,
  `test_wash_sale.py`, `test_form_1099b_export.py`,
  `test_lineage_graph_store.py`, `test_tax_compliance_page.py`.
- `doc/monthly_report_spec.md`, `doc/tax_compliance.md`,
  `doc/lineage_neo4j.md`.

### Critères
- Rapport mensuel (PDF + JSON + HMAC sig) sur fixture.
- Brinson-Fachler décomposé en 3 effets, somme = total alpha (< 1e-6).
- Page IHM Tax affiche ≥ 1 wash sale détectée.
- `InMemoryGraphStore` génère ≥ 50 nodes sur run pipeline test ; export DOT valide.

---

## Sprint S17 — Performance + scale

### Fichiers à créer
- `tests/benchmarks/test_selector_benchmark.py`,
  `test_screener_benchmark.py`, `test_executor_benchmark.py`.
- `scripts/run_benchmarks.py`.
- `.github/workflows/benchmarks_nightly.yml`.
- `service/cache/__init__.py`, `in_memory.py`, `redis_cache.py`,
  `factory.py`.
- `database/async_io.py`.
- `doc/performance_profiling.md`.
- Tests cache + async DB.

### Critères
- 3 suites benchmark vertes ; baseline archivée.
- 3 hotspots optimisés, gain ≥ 30 % cumulé.
- `InMemoryCache` couvert ≥ 95 %.
- POC async DB démontre gain ≥ 2× sur fixture.

---

## Sprint S18 — Polish + certification interne

### Fichiers à créer
- `doc/architecture/c4_context.md`, `c4_container.md`,
  `c4_component.md` (Mermaid).
- `doc/runbook_24_7.md`, `doc/onboarding_operator.md`,
  `doc/onboarding_walkthrough.md`.
- `doc/external_audit_checklist.md`.
- `doc/api_v1_stability_policy.md`.
- `core/_deprecation.py`.
- `scripts/generate_sbom.py`, `scripts/scan_cves.py`,
  `scripts/check_no_todo.py`.
- `.github/workflows/security_scan.yml`,
  `.github/workflows/coverage_gate.yml`.
- `tests/test_api_v1_stability.py` + `tests/golden/api_v1_signatures.json`.
- `tests/test_no_todo_in_app_code.py`.

### Critères
- C4 + runbook + onboarding livrés (≥ 3 diagrammes Mermaid).
- API v1.0 verrouillée golden file.
- SBOM CycloneDX généré + 0 CVE critique.
- Couverture ≥ 90 % (CI bloquante).
- 0 `TODO/FIXME/XXX` hors `tests/`, `prompt/`, `doc/`.
- Auto-audit complet (50/50 items).

---

## Ordre d'exécution

1. S14 (mutation + branches + hypothesis).
2. S15 (Z3 + fuzzing).
3. S16 (reporting + tax + lineage).
4. S17 (cache + benchmarks + async).
5. S18 (polish + SBOM + doc + couverture).

---

## Quick wins (~10 j, sans infra)

| # | Action | Sprint |
|---|---|---|
| QW1 | `pytest-benchmark` + 1 suite démo | S17.1 |
| QW2 | `scripts/check_no_todo.py` + workflow | S18.5 |
| QW3 | `scripts/generate_sbom.py` (cyclonedx) | S18.6 |
| QW4 | `scripts/scan_cves.py` (pip-audit) | S18.6 |
| QW5 | Hypothesis sur `position_sizer` | S14.3 |
| QW6 | Z3 prove `compute_idempotency_key` | S15.1.a |
| QW7 | `InMemoryCache` LRU+TTL | S17.3 |
| QW8 | `lineage/graph_store.py` InMemory + DOT | S16.4 |
| QW9 | `tax/wash_sale.py` + tests | S16.3 |
| QW10 | C4 Mermaid (3 diagrammes) | S18.1 |
| QW11 | `mutmut` sur `corporate_actions/` | S14.1 |
| QW12 | `monthly_report.json` (sans PDF) signé HMAC | S16.1 |

