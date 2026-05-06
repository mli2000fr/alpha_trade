# Relecture documentation — Phase G (Sprint S25.5)

> Checklist humaine : passer en revue tous les fichiers `doc/` pour
> typos, cohérence terminologique, et mise à jour des références
> ajoutées en Phase G.

## Process

1. Lancer `python scripts/generate_doc_index.py` pour avoir l'INDEX.
2. Lancer `python scripts/check_doc_links.py --strict` (objectif : 0).
3. Cocher chaque doc ci-dessous au fil de la relecture.
4. Soumettre 1 PR par lot de 5 docs (revue plus simple).

## Documents à relire

### Architecture & Design
- [ ] `doc/architecture/` (lot complet)
- [ ] `doc/DOC_TECHNIQUE.md`
- [ ] `doc/DOC_FONCTIONNELLE.md`

### Modules métier
- [ ] `doc/backtesting.md`
- [ ] `doc/backtesting_report_schema.md`
- [ ] `doc/corporate_actions.md`
- [ ] `doc/dataIntegrityEngine.md`
- [ ] `doc/database.md`
- [ ] `doc/event_sentiment.md`
- [ ] `doc/execution_engine.md`
- [ ] `doc/modelFactory.md`
- [ ] `doc/risk_management.md`
- [ ] `doc/screener.md`
- [ ] `doc/selector.md`
- [ ] `doc/service.md`
- [ ] `doc/watcher.md`
- [ ] `doc/ihm.md`

### Conformité & Audit
- [ ] `doc/api_v1_stability_policy.md` (mis à jour S25.4 — vérifier liste 247)
- [ ] `doc/external_audit_checklist.md` (mis à jour S24.3 — TLAPS prouvé)
- [ ] `doc/external_audit_engagement.md` (nouveau S25.2)
- [ ] `doc/external_audit_findings_template.md` (nouveau S25.2)
- [ ] `doc/pre_audit_findings.md` (nouveau S25.1)
- [ ] `doc/tlaps_proofs.md` (nouveau S24.3)
- [ ] `doc/formal_verification.md`

### Tests & Vérification
- [ ] `doc/fuzz_diff.md` (nouveau S24.1)
- [ ] `doc/mutation_testing.md`
- [ ] `doc/mutation_history.md`

### Ops & Runbooks
- [ ] `doc/runbook_24_7.md`
- [ ] `doc/runbook_provider_incident.md`
- [ ] `doc/runbook_reconciliation.md`
- [ ] `doc/sandbox_health_runbook.md` (nouveau S24.2)
- [ ] `doc/disaster_recovery.md`
- [ ] `doc/observability.md`
- [ ] `doc/pre_live_checklist.md`

### Performance
- [ ] `doc/perf_hotspots.md`
- [ ] `doc/perf_pipeline.md`
- [ ] `doc/async_db_poc.md`

### Onboarding & Guides
- [ ] `doc/onboarding_operator.md` (mis à jour S25.3 — lien vidéo)
- [ ] `doc/onboarding_video_script.md` (nouveau S25.3)
- [ ] `doc/onboarding_assets/README.md` (nouveau S25.3)
- [ ] `doc/guide_add_new_table.md`
- [ ] `doc/ibkr_setup.md`

### Autres
- [ ] `doc/artifacts_retention_policy.md`
- [ ] `doc/core_common.md`
- [ ] `doc/data_lineage_matrix.md`
- [ ] `doc/phase_f_implementation.md`

## Critères de relecture

* Pas de TODO/FIXME laissés.
* Liens internes valides (script `check_doc_links.py`).
* Cohérence terminologique : « OCO », « bracket », « champion », « PIT »
  écrits de façon identique partout.
* Exemples de commandes copiables sans modification.
* Date de dernière mise à jour mentionnée (en-tête).
* Cross-références à jour (notamment vers les nouveautés Phase G).

## Statut

* Total docs : 40+
* Relus : 0
* Lots PR créés : 0

