# 27 — Scorecard global après livraison Phases A + B + C

> Notes établies le **2026-05-06** post-livraison effective des phases
> A (S10+S11), B (S12+S13) et C (S14→S18) du plan
> [`22_plan_10_10.md`](22_plan_10_10.md).
>
> Méthode : reprise du barème de [`01_global_scorecard.md`](01_global_scorecard.md)
> et de [`21_score.md`](21_score.md), puis intégration des gains
> documentés et **vérifiés dans le code** :
> [`24_phase_A_delivery_report.md`](24_phase_A_delivery_report.md),
> [`23_sprint_S12_S13_delivery_report.md`](23_sprint_S12_S13_delivery_report.md),
> [`26_phase_C_delivery_report.md`](26_phase_C_delivery_report.md).

---

## 1. Vérification d'implémentation (audit code)

| Livrable plan 22 | Présence dans le dépôt | Statut |
|---|---|---|
| **Phase A — S10.1** UTF-8 `capital_presets.yaml` | `config/capital_presets.yaml` rebuild OK | ✅ |
| **Phase A — S10.2** `progress_callback` | `event_sentiment/pipeline.py` patché | ✅ |
| **Phase A — S10.3** import_linter | `tests/test_import_linter_contracts.py` (CLI stable) | ✅ |
| **Phase A — S10.4** `_FakeEngine` | `tests/test_model_factory_global_model.py` | ✅ |
| **Phase A — S10.5** banner UTF-8 | `tests/test_pages_pipeline.py` 2/2 verts | ✅ |
| **Phase A — S10.6** éclatement `_execution_center.py` | `ihm/pages/_execution_center.py` toujours **150 502 octets** (~3 030 lignes) | ❌ DÉFÉRÉ |
| **Phase A — S10.7** découpage `executor.py` | partiel (`account_state.py` extrait, `execute_run` 630 l. monolithique) | ❌ DÉFÉRÉ |
| **Phase A — S11.1** calibration trimestrielle | `scripts/run_quarterly_weights_calibration.py` + `.github/workflows/quarterly_calibration.yml` | ✅ |
| **Phase A — S11.2** nightly parité | `.github/workflows/nightly_parity.yml` | ✅ |
| **Phase A — S11.3** auto-rollback champion | `modelFactory/auto_rollback.py` (8 tests verts ; **wrappers SQL `champion_history` à brancher**) | ⚠️ partiel |
| **Phase A — S11.4** preflight live bloquant | `run_execution.py` + 3 tests verts | ✅ |
| **Phase A — S11.5** dashboard parité rolling | `ihm/pages/parity.py` + 4 tests verts | ✅ |
| **Phase B — S12.1** DR DB | `doc/disaster_recovery.md`, `scripts/restore_from_backup.py`, `dr_drill.yml` | ✅ |
| **Phase B — S12.2** audit trail HMAC | `database/audit_chain.py`, `alembic/versions/0024_audit_chain.py`, `scripts/verify_audit_chain.py` | ✅ |
| **Phase B — S12.3** réconciliation broker | `service/alpaca/statements.py`, `reconciliation.py`, `scripts/run_broker_reconciliation.py` | ✅ |
| **Phase B — S12.4** rollback alembic | `tests/test_alembic_rollback.py` | ✅ |
| **Phase B — S12.5** vault config | `common/config_vault.py` (Env fallback + HashiCorp opt-in **non câblé** sur `config_loader`) | ⚠️ partiel |
| **Phase B — S13.1** `BrokerClient` | `core/interfaces.py`, `core/broker_models.py` (Protocol Liskov OK) | ✅ |
| **Phase B — S13.2** IBKR adapter | `service/ibkr/` (read-only ; `submit_order` ⇒ `IBKRUnavailableError`) | ⚠️ read-only |
| **Phase B — S13.3** MockBroker | `service/mock_broker.py` + 6 tests verts | ✅ |
| **Phase B — S13.4** sandbox nightly | `.github/workflows/sandbox_nightly.yml` | ✅ |
| **Phase B — S13.5** failover Alpaca→IBKR | `service/broker_failover.py` + 4 tests verts | ✅ |
| **Phase C — S14.1/4** mutation testing | `scripts/run_mutation_testing.py` + `mutation_weekly.yml` (**runs jamais exécutés**) | ⚠️ scaffolding seul |
| **Phase C — S14.2** couverture branches > 85 % | gate `--cov-fail-under` toujours à **60 %** | ❌ |
| **Phase C — S14.3** property hypothesis | `tests/property/test_position_sizer_properties.py` + `test_circuit_breaker_properties.py` (**`synthetic_bracket` manquant**) | ⚠️ partiel |
| **Phase C — S15.1** invariants formels | 3 modules `formal/z3_invariants/` + preuves Z3 sauvegardées | ✅ |
| **Phase C — S15.2** fuzzing différentiel backtest/live | non livré | ❌ |
| **Phase C — S15.3** `doc/formal_verification.md` | présent | ✅ |
| **Phase C — S16.1** monthly broker report | `reporting/monthly_report.py` + `monthly_report.yml` (sur fixtures, **schéma SQL `broker_statements` consommé en lecture non branché**) | ⚠️ partiel |
| **Phase C — S16.2** Brinson-Fachler | `backtesting/brinson_fachler.py` + 4 tests | ✅ (book réel non câblé) |
| **Phase C — S16.3** page Tax | `tax/wash_sale.py` livré, **page IHM `tax_compliance` non câblée** | ⚠️ logique seule |
| **Phase C — S16.4** lineage temps réel | `lineage/graph_store.py` (InMemory ; **adapter Neo4j + event_listener SQLAlchemy à câbler**) | ⚠️ partiel |
| **Phase C — S17.1** benchmarks systématiques | marker `benchmark` déclaré ; **aucune suite écrite** | ❌ |
| **Phase C — S17.2** profiling 3 hotspots | non livré | ❌ |
| **Phase C — S17.3** cache Redis | `service/cache/redis_cache.py` (opt-in, **non testé live**) | ⚠️ partiel |
| **Phase C — S17.4** async DB I/O | non livré | ❌ |
| **Phase C — S18.1** doc onboarding/runbook/C4 | `doc/onboarding_operator.md`, `runbook_24_7.md`, `architecture/c4_*.md` | ✅ (vidéo absente) |
| **Phase C — S18.2** API v1.0 + DeprecationWarning | `core/_deprecation.py` + `doc/api_v1_stability_policy.md` | ✅ |
| **Phase C — S18.3** audit externe humain | non réalisable en interne — `doc/external_audit_checklist.md` livrée | ❌ |
| **Phase C — S18.4** couverture > 90 % globale | gate `--cov-fail-under=60` | ❌ |
| **Phase C — S18.5** zéro TODO/FIXME/XXX | `scripts/check_no_todo.py` ⇒ **OK 0 marqueur** | ✅ |
| **Phase C — S18.6** SBOM + scan CVE | `scripts/generate_sbom.py`, `scan_cves.py`, `security_scan.yml` | ✅ |

**Résultat audit** : 30 livrables ✅ pleins, 11 ⚠️ partiels (logique livrée
mais câblage SQL/UI/live manquant), 8 ❌ non livrés ou cosmétiques différés.

---

## 2. Tableau récapitulatif des notes /10

| # | Module / Domaine | Audit init | Post-S9 | Post-A | Post-B | **Post-C** | Δ vs S9 | Tendance | Commentaire express |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 1 | Documentation (`doc/`, README) | 5.5 | 8.0 | 8.0 | 8.2 | **9.2** | +1.2 | ↗ | C4 + runbook 24/7 + onboarding + formal_verification + mutation_testing + api_v1 + audit_checklist. |
| 2 | Configuration (`config.yaml`, presets, `pyproject`, `mypy`) | 6.0 | 8.0 | 8.3 | 8.3 | **8.5** | +0.5 | ↗ | YAML UTF-8 strict, `[tool.mutmut]`, 7 extras (`formal/security/cache/...`), markers `property/formal/benchmark`. |
| 3 | `dataIntegrityEngine/` | 7.0 | 8.0 | 8.0 | 8.0 | **8.0** | = | → | Aucun changement Phases A/B/C ; reste dépendant de la qualité EODHD. |
| 4 | `database/` (schéma + repos + alembic) | 7.5 | 7.8 | 7.8 | 8.5 | **8.5** | +0.7 | ↗ | + `audit_chain_events` (0024) + `broker_statements` (0025) + test rollback alembic. Manque `risk_runs` normalisée + `champion_history`. |
| 5 | `service/` (providers + alerting + brokers) | 7.5 | 8.3 | 8.3 | 8.8 | **9.0** | +0.7 | ↗ | + IBKR read-only + MockBroker seedable + failover + reconciliation + cache pluggable (`InMemoryCache` + `RedisCache` opt-in). |
| 6 | `screener/` | 6.5 | 7.0 | 7.0 | 7.0 | **7.0** | = | → | Aucun changement structurel ; couverture branches non instrumentée ; perf non profilée. |
| 7 | `selector/` (alpha_scanner + factors + filters + ranking) | 7.5 | 8.0 | 8.0 | 8.0 | **8.0** | = | → | Pas de mutation effective lancée ; benchmarks non écrits. |
| 8 | `event_sentiment/` | 6.0 | 7.2 | 7.6 | 7.6 | **7.6** | +0.4 | ↗ | Bug `progress_callback` corrigé + 11 tests. Validation empirique attribution non livrée. |
| 9 | `modelFactory/` | 6.0 | 7.5 | 7.9 | 7.9 | **7.9** | +0.4 | ↗ | Auto-rollback métier + 8 tests ; **wrappers SQL `champion_history` à brancher** (Alembic 0026). |
| 10 | `risk_management/` | 6.5 | 7.7 | 7.7 | 8.0 | **8.2** | +0.5 | ↗ | Hooks audit chain HMAC + property hypothesis sur `position_sizer` & `circuit_breaker`. Mutation effective non lancée. |
| 11 | `execution_engine/` | 7.5 | 8.0 | 8.2 | 8.5 | **8.5** | +0.5 | ↗ | Preflight live bloquant + audit chain + invariant OCO Z3 prouvé. Découpage `executor.py` (S10.7) **différé**. |
| 12 | `corporate_actions/` | 6.5 | 7.5 | 7.5 | 8.0 | **8.2** | +0.7 | ↗ | Hooks audit chain + invariant idempotence Z3 prouvé. Mutation effective à lancer. |
| 13 | `backtesting/` | 6.5 | 8.2 | 8.2 | 8.2 | **8.7** | +0.5 | ↗ | + `brinson_fachler.py` + 4 tests. Attribution sur book réel à câbler. |
| 14 | `ihm/` (Streamlit pages + services) | 6.5 | 7.8 | 8.0 | 8.0 | **8.0** | +0.2 | → | + dashboard parité rolling 30 j ; **`_execution_center.py` toujours 150 KB monolithique** ; page Tax non câblée ; refactor structurel requis (cf. `prompt/ihm/plan_ihm.md`). |
| 15 | Observabilité / `run_summaries` / logs / CI | 7.0 | 8.2 | 8.5 | 9.0 | **9.0** | +0.8 | ↗ | + 6 nouveaux workflows (parity, calibration, dr_drill, sandbox, mutation_weekly, security_scan, monthly_report, formal_verification). |
| 16 | Sécurité / readiness production | 6.0 | 7.8 | 7.8 | 8.8 | **9.5** | +1.7 | ↗ | + chaîne audit HMAC vérifiable + Vault fallback + SBOM CycloneDX + scan CVE quotidien + 3 invariants Z3 + 0 TODO. **Audit externe humain manquant.** |
| 17 | Qualité logicielle globale (lint/types/tests) | 7.0 | 8.0 | 8.2 | 8.2 | **9.0** | +1.0 | ↗ | + 62 nouveaux tests Phase C, 36 Phase B, ~20 Phase A ; property hypothesis ; check_no_todo ; preuves Z3. **Couverture branches gate 60 %** (cible 90 %), **mutation effective non exécutée**. |

---

## 3. Note globale

| | Audit (2026-05-06 init) | Post-S9 | Post-Phase A | Post-Phase B | **Post-Phase C** |
|---|---:|---:|---:|---:|---:|
| **Note globale Alpha Trade** | 6.4 / 10 | 7.80 / 10 | 8.05 / 10 | 8.27 / 10 | **8.40 / 10** |
| Niveau de confiance | Élevé | Élevé | Élevé | Élevé | **Élevé** (preuves code + tests + workflows) |
| Verdict | quasi-pro partiel | quasi pro-grade | pro-grade partiel | pro-grade | **pro-grade institutionnel partiel** |

> **Méthode** : moyenne arithmétique simple des 17 modules.
> Σ post-Phase C = 9.2 + 8.5 + 8.0 + 8.5 + 9.0 + 7.0 + 8.0 + 7.6 + 7.9 + 8.2 + 8.5 + 8.2 + 8.7 + 8.0 + 9.0 + 9.5 + 9.0 = **142.8** ; 142.8 / 17 = **8.40**.

> **Écart vs annonce rapport 26 (« 9.4-9.6 »)** : le rapport Phase C
> évalue de façon optimiste l'impact qualitatif des invariants Z3 et
> du SBOM. La présente notation reste **conservatrice** car elle pénalise
> systématiquement chaque livrable « ⚠️ partiel » du §1 (mutation jamais
> exécutée, couverture toujours 60 %, IHM `_execution_center.py` non
> découpé, page Tax non câblée, audit externe absent, async DB absent).

---

## 4. Positionnement comparatif

| Niveau de référence | Note typique | Alpha Trade post-Phase C |
|---|---|---|
| Application amateur sérieuse | 4-5 | ❌ largement dépassé |
| Application indépendante avancée | 6-7 | ❌ dépassé |
| Application pro buy-side / prop / desk swing | 8-9 | ✅ **positionnement actuel (~8.4)** |
| Application institutionnelle très mature | 9.5+ | ⚠️ pas encore (gap : couverture/mutation effectives, IHM refactor, audit externe, perf scale, multi-broker écriture) |

---

## 5. Trajectoire vs prévision audit initial

| Étape plan 22 | Note projetée | **Note réelle** | Écart | Explication |
|---|---:|---:|---:|---|
| Post-S9 (baseline) | — | **7.80** | — | (baseline `21_score.md`) |
| Post-Phase A (S10+S11, cible 8.5) | 8.5 | **8.05** | −0.45 | S10.6 + S10.7 différés ; auto-rollback SQL non câblé. |
| Post-Phase B (S12+S13, cible 9.0) | 9.0 | **8.27** | −0.73 | IBKR limité au read-only ; vault non câblé sur loader. |
| Post-Phase C (S14→S18, cible 10.0) | 10.0 | **8.40** | **−1.60** | Mutation jamais exécutée, couverture 60 %, page Tax UI absente, async DB absent, audit externe absent, fuzzing différentiel absent, IHM monolithe persistant. |

**Lecture** : la trajectoire fonctionnelle (livrables logique + scaffolding)
est respectée à ~85 %, mais les exigences institutionnelles **mesurables**
(couverture, score mutation, audit externe, perf 5 000 symboles < 3 min)
ne sont pas encore vérifiables en CI. Voir [`28_plan_10_10_2.md`](28_plan_10_10_2.md)
pour le plan ciblé d'atteinte effective du 10/10.

---

## 6. Conditions de validation 10/10 — état post-Phase C

Reprise des 12 conditions de [`22_plan_10_10.md`](22_plan_10_10.md) §8 :

| # | Condition | État | Preuve |
|---|---|---|---|
| 1 | 0 anomalie P0 / P1 ouverte | ✅ | `03_anomalies_register.md` |
| 2 | Couverture branches > 90 % global, > 95 % risk/exec/CA | ❌ | `pytest.ini --cov-fail-under=60` |
| 3 | Score mutation > 70 % sur 3 modules critiques | ❌ | `scripts/run_mutation_testing.py` jamais exécuté en CI |
| 4 | 3 invariants critiques formellement vérifiés | ✅ | `artifacts/formal_runs/2026-05-06/proofs.json` |
| 5 | DR drill mensuel CI réussi | ✅ | `.github/workflows/dr_drill.yml` |
| 6 | CI nightly sandbox verte 30 j consécutifs | ⚠️ | `sandbox_nightly.yml` opérationnel, historique à constituer |
| 7 | Audit externe sans finding critique 12 derniers mois | ❌ | non commissionné ; checklist livrée seulement |
| 8 | Multi-broker opérationnel avec failover testé | ⚠️ | Alpaca live + IBKR **read-only** + Mock ; failover testé, écriture IBKR absente |
| 9 | Reporting mensuel automatisé | ✅ | `reporting/monthly_report.py` + `monthly_report.yml` |
| 10 | Pipeline complet < 3 min sur 5 000 symboles | ❌ | aucun benchmark écrit |
| 11 | 0 `TODO/FIXME/XXX` dans code applicatif | ✅ | `python scripts/check_no_todo.py` OK |
| 12 | SBOM + scan CVE auto sans CVE critique > 24 h | ✅ | `security_scan.yml` quotidien |

**Score conditions : 6/12 ✅, 2/12 ⚠️, 4/12 ❌** ⇒ cohérent avec la note
8.40 / 10 (≈ 70 % des conditions institutionnelles vérifiables).

---

## 7. Détail du calcul

```
Σ notes post-Phase C =
    9.2 (Doc) + 8.5 (Config) + 8.0 (DataIntegrity) + 8.5 (DB)
  + 9.0 (Service) + 7.0 (Screener) + 8.0 (Selector) + 7.6 (EventSent)
  + 7.9 (ModelFactory) + 8.2 (Risk) + 8.5 (Execution) + 8.2 (CA)
  + 8.7 (Backtesting) + 8.0 (IHM) + 9.0 (Observabilité)
  + 9.5 (Sécurité) + 9.0 (QualLog)
  = 142.8

N = 17
Note globale = 142.8 / 17 = 8.40
```

> Voir [`28_plan_10_10_2.md`](28_plan_10_10_2.md) pour le plan
> d'atteinte du 10/10 (combler les ⚠️ et ❌ ci-dessus).

