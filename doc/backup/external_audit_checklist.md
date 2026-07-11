# Checklist d'auto-audit externe — Phase C / S18.3

> Substitut documentaire à l'audit externe humain (qui reste à
> commissionner post-Phase C). Cette checklist constitue le **dossier
> de revue** à présenter à un ingénieur senior buy-side.

## 1. Architecture (10 points)

- [ ] Diagrammes C4 niveaux 1-3 livrés (`doc/architecture/c4_*.md`).
- [ ] Liste exhaustive des dépendances externes (cf. SBOM).
- [ ] Modes de défaillance documentés par container.
- [ ] Diagramme séquence pour `submit_order` (happy path + failover).
- [ ] DR runbook formalisé (`doc/disaster_recovery.md`).
- [ ] RPO/RTO mesurés et reproductibles (`dr_drill.yml`).
- [ ] Multi-broker substituable (Liskov) — `tests/test_broker_interface_contract.py`.
- [ ] Ségrégation audit-chain / business data.
- [ ] Lineage temps réel disponible (`lineage/`).
- [ ] Cache pluggable + fallback InMemory.

## 2. Qualité du code (10 points)

- [ ] Couverture tests ≥ 90 % global (`pytest --cov`).
- [ ] Couverture ≥ 95 % sur risk + execution + CA.
- [ ] Mutation testing ≥ 50 % (cible 70 %) — `doc/mutation_testing.md`.
- [ ] 0 TODO/FIXME/XXX dans code applicatif (`scripts/check_no_todo.py`).
- [ ] Ruff + mypy verts (`pre-commit`).
- [ ] Imports linter respecté (Phase 7.1).
- [ ] Property-based tests sur composants critiques (`tests/property/`).
- [ ] Pas de cycle d'imports (import-linter contracts).
- [ ] Logging structuré + niveaux corrects.
- [ ] Pas de `print()` dans le code applicatif.

## 3. Sécurité (10 points)

- [ ] SBOM CycloneDX généré quotidiennement.
- [ ] Scan CVE (pip-audit) automatique, 0 critique > 24 h.
- [ ] Secrets en Vault (jamais en clair dans le repo).
- [ ] Audit chain HMAC-SHA256 vérifiable (`verify_audit_chain.py`).
- [ ] Signature HMAC sur rapports mensuels (`reporting/`).
- [ ] Rotation secrets documentée (90 j).
- [ ] Pas d'exécution SQL non paramétrée.
- [ ] Pas d'eval / exec / pickle sur input non-sûr.
- [ ] HTTPS-only sur les providers REST.
- [ ] Logs scrubbés (pas de credentials, pas de PII).

## 4. Observabilité & ops (10 points)

- [ ] Dashboard parité IHM 30 j.
- [ ] Endpoint Prometheus `/metrics` exposé (Phase 7.5).
- [ ] CI nightly sandbox verte 30 j consécutifs.
- [ ] Runbook 24/7 (`doc/runbook_24_7.md`).
- [ ] Procédure d'escalade documentée.
- [ ] Alerting Slack pour P0/P1.
- [ ] Backup config dans Vault (Phase B / S12.5).
- [ ] Onboarding opérateur < 60 min (`doc/onboarding_operator.md`).
- [ ] DR drill mensuel automatisé.
- [ ] Reporting mensuel sans intervention humaine.

## 5. Conformité & gouvernance (10 points)

- [ ] Vérification formelle de 3 invariants (`doc/formal_verification.md`).
- [ ] Détection wash sales (`tax/wash_sale.py`).
- [ ] Holding periods + cost basis FIFO (S16.3).
- [ ] Attribution Brinson-Fachler par secteur (`backtesting/brinson_fachler.py`).
- [ ] Reconciliation broker quotidienne (`run_broker_reconciliation.py`).
- [ ] API publique versionnée v1.0 (`doc/api_v1_stability_policy.md`).
- [ ] Politique de dépréciation tracée (`@deprecated_v1`).
- [ ] Lignage SQL → graph navigable (`lineage/`).
- [ ] Politique de retention artifacts (`doc/artifacts_retention_policy.md`).
- [ ] Documentation fonctionnelle exhaustive (`doc/DOC_FONCTIONNELLE.md`).

## Score

* **50 / 50** = prêt pour audit externe formel.
* **45-49** = audit externe possible avec lettre d'engagement.
* **< 45** = compléter Phase C avant audit.

## Items justifiés (non bloquants)

* L'audit externe humain reste à commissionner — voir
  `doc/external_audit_engagement.md` (lettre de mission template,
  Sprint S25.2) et `scripts/check_external_audit_freshness.py`
  pour la vérification CI de fraîcheur (< 12 mois).
* La vidéo onboarding est livrée Sprint S25.3 — script complet
  dans `doc/onboarding_video_script.md`, assets dans
  `doc/onboarding_assets/`.
* TLA+ TLAPS : Sprint S24.3 — wrapper `scripts/run_tlaps.py`,
  doc engagement `doc/tlaps_proofs.md` ; les 3 invariants restent
  garantis par les preuves Z3 exécutables tant que la mission
  consultant n'est pas terminée.
* Fuzzing différentiel backtest/live : Sprint S24.1 — workflow
  hebdo `fuzz_weekly.yml`, doc `doc/fuzz_diff.md`.
* Sandbox health 30 j : Sprint S24.2 — page IHM `🟢 Sandbox health`,
  runbook `doc/sandbox_health_runbook.md`.
* Pré-audit interne automatisé : Sprint S25.1 —
  `scripts/run_pre_audit_checklist.py`, registre
  `doc/pre_audit_findings.md`.
* API publique v1.0 figée (247 symboles) : Sprint S25.4 —
  `doc/api_v1_public_symbols.txt`, test
  `tests/test_api_v1_stability.py`.
* Index doc cherchable : Sprint S25.5 — `doc/INDEX.md` généré par
  `scripts/generate_doc_index.py` ; check liens morts via
  `scripts/check_doc_links.py`.

