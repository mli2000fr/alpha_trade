# 32 — Plan d'atteinte du 10/10 (post-Phase G + UX, ré-actualisé)

> Établi le **2026-05-06** sur la base de [`31_score_3.md`](31_score_3.md)
> (note actuelle : **8.71 / 10**). Objectif : combler le gap de
> **+1.29** pour atteindre **10/10** institutionnel auditable.
>
> Hypothèse de cadence : 1 dev senior + 1 quant senior + 1 SRE
> mi-temps (identique aux plans précédents). Sprint = 2 semaines.

---

## 1. Résumé exécutif

Le plan 28 a livré, sur les sprints S19→S25 :

* **Phase D** (refactor IHM) : ~85 % livré (3 monolithes
  `__init__.py` résiduels, help YAML 80/150) ;
* **Phase E** (câblage SQL/UI/live) : ~90 % livré (`broker_statements`
  branchement non confirmé) ;
* **Phase F** (couverture/mutation/perf) : ~50 % livré (gate cov
  inchangée, `executor_phases.py` scaffold seul, mutation non publiée,
  async DB POC théorique) ;
* **Phase G** (fuzz + sandbox + TLAPS + audit + INDEX) : ~80 % livré
  (TLAPS preuves vides, audit externe humain absent, vidéo onboarding
  absente, `compliance_audit` KPI placeholder).

**Bilan anomalies** : **6 P0** + **7 P1** + **5 P2** identifiées
(cf. §2). **3 sprints suffisants** pour clôturer (~6 semaines avec la
même équipe) :

| Phase | Sprints | Note cible | Effort |
|---|---|---:|---|
| **F-bis — Couverture & mesures effectives** | S26 | 9.10 | 2 sem |
| **D-bis — Refactor IHM résiduel + UX completion** | S27 | 9.45 | 2 sem |
| **G-bis — Validations humaines & async DB** | S28 | **10.00** | 2 sem |

**Budget total : 3 sprints (~6 semaines / 1.5 mois calendaire).**

---

## 2. Anomalies détectées (P0 / P1 / P2)

### 2.1 P0 — Bloquantes (6 items)

| ID | Anomalie | Module | Cause racine | Effort | Sprint cible |
|---|---|---|---|---|:---:|
| **A1** | `pytest.ini --cov-fail-under=60` jamais monté alors que S22.1a/b/c prévoyaient 60→75→85→90 | qualité log | gate cosmétique non touchée ; tests non ajoutés module par module | 2 j | S26 |
| **A2** | `scripts/check_branch_coverage_critical.py` **non appelé dans `ci.yml`** ⇒ seuil > 95 % branches sur risk/exec/CA jamais vérifié | risk/exec/CA | step CI oublié à l'intégration | 0.5 j | S26 |
| **A3** | `execution_engine/executor.py` = **977 lignes** ; `executor_phases.py` = scaffold 138 l. (« branchement à faire dans une PR dédiée ») ⇒ S23.5 / S10.7 jamais réellement livré | execution | refactor différé itérativement depuis S10 | 4 j | S26 |
| **A4** | Mutation runs **jamais publiés** : `mutation_weekly.yml` + `list_mutation_survivors.py` présents, aucun artifact `mutation_runs/<date>/score.json` versionné | qualité log | workflow non déclenché manuellement, pas d'auto-commit | 2 j | S26 |
| **A5** | Test `tests/test_ihm_process_registry.py::test_pipeline_workflow_stops_on_failed_step` flaky (verrou pipeline non libéré entre tests) | observabilité | pas de fixture autouse de cleanup | 0.5 j | S26 |
| **A6** | 3 monolithes IHM `__init__.py` persistent : `_execution_center/` 2 877 l., `backtesting/` 2 083 l., `_workflow/` 935 l. ⇒ critère C1 du `plan_ihm.md` toujours ❌ | IHM | scope plan 28 §2 sous-estimé pour Phase D | 6 j | S27 |

### 2.2 P1 — Importantes (7 items)

| ID | Anomalie | Module | Effort | Sprint cible |
|---|---|---|---|:---:|
| **A7** | Vidéo onboarding non enregistrée (`doc/onboarding_assets/` ne contient que `.gitkeep` + `README.md`) ⇒ S25.3 incomplet | doc | 1 j | S28 |
| **A8** | TLA+ proofs **vides** (`formal/tla/proofs/.gitkeep` seul) ⇒ condition 4-bis du plan 28 ❌ ; mission consultant non lancée | sécurité | 5 j (consultant) | S28 |
| **A9** | Audit externe humain **non commissionné** ; job `external-audit-freshness` `continue-on-error: true` ⇒ silencieusement bypass | sécurité | 5 j (auditeur) | S28 |
| **A10** | Async DB POC **théorique** : `database/async_engine.py` et `async_loaders.py` n'importent ni `asyncpg` ni `aiosqlite` ⇒ pas de gain perf, condition #10 (< 3 min) non démontrable | service / DB | 3 j | S28 |
| **A11** | Branchement réel `broker_statements` → `monthly_report.py` non confirmé sur disque (script présent, lecture SQL effective vs fixtures à vérifier) ⇒ S21.4 reste ⚠️ | service / backtesting | 1 j | S26 |
| **A12** | Help YAML incomplet : ~80 clés / ~150 cibles ⇒ `tests/test_ihm_help_tooltips.py` repose sur `LEGACY_ALLOWLIST` (19 pages) | IHM | 2 j | S27 |
| **A13** | `compliance_audit.py` = **stub** : KPI placeholder, pas de lien réel HMAC chain / DR drill / CVE / mutation (D7 résiduel) | observabilité | 2 j | S27 |

### 2.3 P2 — Confort (5 items)

| ID | Anomalie / Amélioration | Module | Effort | Sprint cible |
|---|---|---|---|:---:|
| **A14** | Sidebar : 3 expanders masqués sans toggle « Mode avancé » ⇒ régression de découvrabilité | IHM/UX | 0.5 j | S27 |
| **A15** | `tests/test_ihm_help_tooltips.py` non hard-fail CI (allow-list) | IHM/qualité | 0.5 j | S27 |
| **A16** | Couverture IHM (C13) jamais mesurée (`--cov=ihm --cov-fail-under=80`) | IHM/qualité | 1 j | S27 |
| **A17** | Pas de `tests/test_executor_phases*.py` alors que le scaffold est livré | execution | 0.5 j | S26 |
| **A18** | Quick wins plan 28 §9 (5 items, gain projeté +0.25) **jamais formalisés en commit** ; absorbés implicitement dans Phase G | continu | 0.5 j | continu |

---

## 3. Plan sprints H — clôture du 10/10

### Sprint S26 — Couverture & mesures effectives (Phase F-bis) — 2 sem.

**Objectif** : faire **vraiment tourner** ce qui était scaffoldé en
Phase F + clore les anomalies P0 mesurables.

| # | Tâche | Cible note | Réf anomalie |
|---|---|---|---|
| **S26.1** | Monter `pytest.ini --cov-fail-under` 60 → 75 (paliers via `--cov-fail-under=75` en CI ; ajouter tests ciblés sur modules sous le seuil) | qual log 9.2 → 9.4 | A1 |
| **S26.2** | Ajouter step CI `coverage-critical` (`needs: test`) qui appelle `python scripts/check_branch_coverage_critical.py` avec seuil > 95 % sur `risk_management/`, `execution_engine/`, `corporate_actions/` | risk/exec/CA 8.5 → 9.0 | A2 |
| **S26.3** | Découpage effectif `executor.execute_run` (630 l. au cœur de `executor.py` 977 l.) en 4 phases dans `executor_phases.py` (`prepare_orders`, `submit_orders`, `track_fills`, `finalize_run`) + suite `tests/test_executor_phases.py` (smoke + round-trip bracket) | exec 8.7 → 9.2 | A3 / A17 |
| **S26.4** | Job CI `mutation-test-publish` qui upload `artifacts/mutation_runs/<date>/score.json` + commit hebdo automatique dans `doc/mutation_history.md` ; cible **score > 70 %** sur `risk_management/`, `execution_engine/`, `corporate_actions/` | qual log 9.4 → 9.5 | A4 |
| **S26.5** | Stabiliser le verrou pipeline (`autouse fixture` libérant `process_registry` en teardown) ⇒ flakiness test résolue | obs 9.5 → 9.6 | A5 |
| **S26.6** | Confirmer / brancher lecture SQL `broker_statements` dans `reporting/monthly_report.py` (retire fixtures) ; vérifier 3 mois consécutifs sans intervention | service 9.4 → 9.5 | A11 |

**Critère** : couverture branches global > 75 %, > 95 % sur risk/exec/CA ;
score mutation > 70 % publié et historisé ; `executor.execute_run`
découpé en 4 phases avec round-trip bracket vert ; aucun test flaky.

**Note cible : 8.71 → 9.10.**

### Sprint S27 — Refactor IHM résiduel + UX completion (Phase D-bis) — 2 sem.

**Objectif** : éclater les 3 derniers monolithes IHM, compléter le help
YAML et les KPI réels de la page audit.

| # | Tâche | Cible note | Réf anomalie |
|---|---|---|---|
| **S27.1** | Découpage `ihm/pages/_execution_center/__init__.py` (2 877 l.) en 10 fichiers `_render_<section>.py` ; façade `__init__.py` < 200 l. ; suite AppTest minimale | IHM 8.7 → 9.1 | A6 (D1) |
| **S27.2** | Découpage `ihm/pages/backtesting/__init__.py` (2 083 l.) en 6 fichiers `_<section>.py` (config, runner, results, attribution, replay, runtime) | IHM 9.1 → 9.3 | A6 (D2) |
| **S27.3** | Découpage `ihm/pages/_workflow/__init__.py` (935 l.) en 3 fichiers `_<section>.py` | IHM 9.3 → 9.4 | A6 (D3) |
| **S27.4** | Compléter ~70 entrées YAML help manquantes (`ihm/help/*.yaml`) + retirer `LEGACY_ALLOWLIST` ⇒ `tests/test_ihm_help_tooltips.py` en hard-fail CI | IHM 9.4 → 9.5 | A12 / A15 |
| **S27.5** | Compléter `ihm/pages/compliance_audit.py` avec KPI réels : HMAC chain (lecture `database/audit_chain.py`), DR drill (lecture artifact `dr_drill_<date>.json`), CVE (lecture `artifacts/sbom/cve_report.json`), couverture (lecture `coverage.xml`), mutation (lecture `mutation_runs/<latest>/score.json`) | obs 9.6 → 9.7 | A13 |
| **S27.6** | Mesure couverture IHM (`--cov=ihm --cov-fail-under=80`) en job CI dédié `coverage-ihm` | qual log 9.5 → 9.6 | A16 |
| **S27.7** | Réintroduire les 3 expanders sidebar derrière un toggle `« Mode avancé »` (settings) plutôt que masquage total ⇒ découvrabilité préservée | UX | A14 |

**Critère** : aucun fichier `ihm/pages/**/__init__.py` > 800 lignes ;
help YAML ≥ 95 % couverture ; `compliance_audit.py` lit des sources
réelles ; couverture IHM ≥ 80 % en CI.

**Note cible : 9.10 → 9.45.**

### Sprint S28 — Validations humaines & async DB (Phase G-bis) — 2 sem.

**Objectif** : commissionner les livrables humains restants et
matérialiser le gain async DB.

| # | Tâche | Cible note | Réf anomalie |
|---|---|---|---|
| **S28.1** | Enregistrement vidéo onboarding (10-15 min) selon `doc/onboarding_video_script.md` ; livraison `doc/onboarding_assets/onboarding_v1.mp4` (Git LFS ou pointeur S3 + SHA-256) ; lien direct dans `doc/onboarding_operator.md` | doc 9.6 → 9.8 | A7 |
| **S28.2** | Mission consultant TLA+ (5-10 j/h) → preuves dans `formal/tla/proofs/<spec>_proof.tla` (3 specs) ; `python scripts/run_tlaps.py --strict` exit 0 ; basculer job CI `tlaps` en bloquant (`continue-on-error: false`) ; mettre à jour `doc/tlaps_proofs.md` (tableau Statut ⚠️ → ✅) | sécu 9.7 → 9.9 | A8 |
| **S28.3** | Audit externe humain (5-10 j/h, ingénieur senior buy-side hors équipe) → rapport déposé dans `doc/external_audit/<auditor>_<date>/` ; corriger findings critiques sous 2 sem ; basculer `external-audit-freshness` en bloquant | sécu 9.9 → 10.0 | A9 |
| **S28.4** | Vraie implémentation async DB : importer `aiosqlite` (dev) + `asyncpg` (prod) dans `database/async_loaders.py` ; benchmark before/after publié dans `doc/async_db_benchmark.md` ; gain ≥ 30 % sur 3 loaders read-only chauds | service 9.5 → 9.7, screener 7.5 → 8.5, selector 8.3 → 8.8 | A10 |
| **S28.5** | Atelier usability opérateur externe (test in vivo) + remontées corrigées (max 1 sprint correctif) | IHM 9.5 → 9.6 | — |
| **S28.6** | Activer en prod les 11 workflows GH Actions (vérifier secrets `SLACK_WEBHOOK_URL`, `ALPHA_TRADE_AUDIT_HMAC_KEY`, `ALPACA_API_KEY`, `IBKR_*`, `VAULT_*`, etc.) + checklist e2e | obs 9.7 → 9.8 | A18 |

**Critère** : 13/13 conditions du §5 vérifiées ; audit externe **sans
finding critique** ; preuves TLAPS exécutables sans `continue-on-error`.

**Note cible : 9.45 → 10.00.**

---

## 4. Synthèse plan complet S26 → S28

| Sprint | Nom | Durée | Note cible | Modules majoritairement impactés |
|---|---|---|---:|---|
| **S26** | Couverture & mesures effectives (F-bis) | 2 sem | 9.10 | qualité log, risk, exec, CA, observabilité, service |
| **S27** | Refactor IHM résiduel + UX completion (D-bis) | 2 sem | 9.45 | IHM, observabilité, qualité log |
| **S28** | Validations humaines & async DB (G-bis) | 2 sem | **10.00** | doc, sécurité, service, screener, selector, observabilité |

**Effort total : 6 semaines (~1.5 mois)** avec l'équipe hypothèse.

---

## 5. Conditions de validation 10/10 — checklist d'atteinte ré-actualisée

| # | Condition | Sprint clôturant | Statut Post-G/UX | Statut Post-H |
|---|---|:---:|:---:|:---:|
| 1 | 0 anomalie P0 / P1 ouverte | S26+S27+S28 | ⚠️ | ✅ |
| 2 | Couverture branches > 90 % global, > 95 % risk/exec/CA | S26 | ❌ | ✅ |
| 3 | Score mutation > 70 % sur 3 modules | S26 | ❌ | ✅ |
| 4 | 3 invariants formels Z3 | déjà ✅ | ✅ | ✅ |
| 4-bis | TLAPS sur les 3 invariants | S28 | ❌ | ✅ |
| 5 | DR drill mensuel CI | déjà ✅ | ✅ | ✅ |
| 6 | CI nightly sandbox 30 j consécutifs | continu | ⚠️ | ✅ (historique constitué) |
| 7 | Audit externe sans finding critique | S28 | ❌ | ✅ |
| 8 | Multi-broker complet (lecture + écriture) avec failover | déjà ✅ | ✅ | ✅ |
| 9 | Reporting mensuel automatisé sur 3 mois | S26 | ⚠️ | ✅ |
| 10 | Pipeline complet < 3 min sur 5 000 symboles | S28 | ⚠️ | ✅ (async DB réel) |
| 11 | 0 `TODO/FIXME/XXX` | continu | ✅ | ✅ |
| 12 | SBOM + scan CVE auto, sans CVE critique > 24 h | déjà ✅ | ✅ | ✅ |
| 13 | IHM pro (toutes pages < 800 l. ; tooltips ?) | S27 | ⚠️ | ✅ |

**À l'issue de S28, ces 13 conditions sont conjointement vérifiables
en CI ⇒ note 10/10 revendiquable et auditable.**

---

## 6. Risques & mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Découpage `executor.execute_run` casse OCO/brackets silencieusement | Élevée | Élevé | Suite `tests/test_executor_phases.py` round-trip bracket **avant** chaque extraction ; revue manuelle pas-à-pas |
| Vidéo onboarding 10-15 min lourde à produire (Git ou S3) | Moyenne | Faible | Loom screen-record + transcription auto-générée ; pointeur S3 + SHA-256 (recommandation S25.3) |
| Audit externe rejette livrables P0/P1 résiduels | Moyenne | Élevé | Pré-audit interne en S26+S27 (`scripts/run_pre_audit_checklist.py --min-score 70`) ; corriger findings avant S28.3 |
| Async DB introduit régressions silencieuses | Moyenne | Élevé | Toggle `ALPHA_TRADE_DB_ASYNC` env ; benchmark régression bloquant > 10 % en CI |
| Coût consultant TLA+ + auditeur ~10-20 k€ | Élevée | Moyen | Budgéter en amont ; chercher consultant universitaire (TLAPS) ; alternative : enrichir Z3 |
| Refactor 3 monolithes IHM casse pages les plus utilisées | Élevée | Élevé | AppTest exhaustif **avant** découpage (cf. risque homologue plan 28) ; opérateur valide pas-à-pas |
| Mutation testing > 70 % difficile sur code legacy | Élevée | Moyen | Itérer module par module ; baseline 50 % puis 70 % ; `list_mutation_survivors.py` priorise les survivants critiques |

---

## 7. Quick wins immédiats avant S26 (< 1 jour chacun)

1. **Bump `pytest.ini --cov-fail-under` 60 → 70** (mesure préalable
   sans tests supplémentaires si déjà atteint). +0.05 (qualité log).
2. **Ajouter step CI `coverage-critical`** appelant
   `scripts/check_branch_coverage_critical.py` (script déjà présent).
   +0.05 (risk/exec/CA).
3. **Activer `tests/test_ihm_help_tooltips.py` hard-fail** sur les
   pages déjà refactorées (Phase D). +0.05 (IHM).
4. **Retirer `continue-on-error: true`** du job
   `external-audit-freshness` après réception du 1er audit
   (anticipation S28.3). +0.05 (sécurité).
5. **Documenter dans `README.md`** l'opération « masquage 3 expanders
   sidebar + bouton menu actif gris » (quick wins UX). UX/doc.
6. **Activer en prod** les workflows GH Actions clés
   (`pre_audit_weekly`, `fuzz_weekly`, `mutation_weekly`,
   `sandbox_nightly`) en vérifiant secrets. +0.05 (observabilité).

**Gain immédiat sans sprint dédié : 8.71 → ~8.95.**

---

## 8. Conditions inclusives / exclusion 10/10

Le 10/10 ne sera revendiquable que **simultanément** avec :

* ✅ Toutes les 13 conditions du §5 vérifiées en CI ;
* ✅ Audit externe formel rendu < 12 mois ;
* ✅ Sandbox nightly verte sans interruption sur 30 j glissants ;
* ✅ Couverture branches mesurée et publiée hebdomadairement ;
* ✅ Score mutation publié hebdomadairement ;
* ✅ Aucune CVE critique non patchée > 24 h ;
* ✅ IHM relue par un opérateur externe sans incompréhension majeure
  (test usability) ;
* ✅ Documentation à jour (≤ 1 commit hors-sync entre code et `doc/`).

Toute défaillance d'un de ces critères ramène la note à **9.7** (cf.
règle de pondération institutionnelle, plan 28 §10).

---

## 9. Trajectoire complète A → H

| Phase | Sprints | Note pré | Note post | Δ | Statut |
|---|---|---:|---:|---:|---|
| Audit init | — | — | 6.40 | — | référence |
| **S1 → S9** (correctifs anomalies + fitness) | 9 sprints | 6.40 | 7.80 | +1.40 | ✅ livré |
| **A** (S10+S11) | 2 sprints | 7.80 | 8.05 | +0.25 | ✅ livré |
| **B** (S12+S13) | 2 sprints | 8.05 | 8.27 | +0.22 | ✅ livré |
| **C** (S14→S18) | 5 sprints | 8.27 | 8.40 | +0.13 | ✅ livré |
| **D** (S19+S20) | 2 sprints | 8.40 | 8.55 | +0.15 | ⚠️ ~85 % livré |
| **E** (S21) | 1 sprint | 8.55 | 8.62 | +0.07 | ⚠️ ~90 % livré |
| **F** (S22+S23) | 2 sprints | 8.62 | 8.68 | +0.06 | ⚠️ ~50 % livré |
| **G** (S24+S25) + UX | 2 sprints | 8.68 | 8.71 | +0.03 | ⚠️ ~80 % livré |
| **H** (S26+S27+S28) | 3 sprints | 8.71 | **10.00** | +1.29 | 📋 planifié (ce document) |

**Effort cumulé total** : 28 sprints (~14 mois calendaires, équipe
hypothèse 1 dev senior + 1 quant senior + 1 SRE mi-temps).

---

> **Lecture finale** : Alpha Trade est aujourd'hui **8.71 / 10**, soit
> **87 % du gap au 10/10 fermé**. L'écart résiduel n'est **pas
> fonctionnel** (la quasi-totalité des fonctionnalités institutionnelles
> est livrée ou scaffoldée) mais **mesurable et opérationnel** :
>
> * faire **vraiment tourner** ce qui est scaffoldé (couverture montée,
>   mutation publiée, async DB réelle, executor découpé) — Sprint S26 ;
> * **finir le refactor IHM** (3 monolithes restants) et compléter le
>   help YAML — Sprint S27 ;
> * **commissionner les livrables humains** (vidéo, TLAPS consultant,
>   audit externe) et activer les workflows en prod — Sprint S28.
>
> 6 semaines, 3 sprints, 18 anomalies à clore. Le 10/10 est à portée.

