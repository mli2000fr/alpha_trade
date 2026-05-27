# 08 — Plan d'action par sprints

Date : mai 2026

---

## Vue d'ensemble

Ce plan vise à amener Alpha Trade de **7.3/10** à **9.0+/10** (niveau professionnel buy-side) en 8 sprints.

> **Contre-revue 2026-05-27** : plusieurs éléments initialement prévus en correctif
> pur ont été requalifiés en **mise à jour documentaire / garde-fou de
> régression** (`A-004`, `A-011`, `A-026`) ou en **extension d'existant**
> (`A-007`, `A-021`).

| Sprint | Focus | Impact | Anomalies |
|---|---|---|---|
| **S1** | Corrections critiques doc/config | P1 | A-001, A-002 |
| **S2** | Uniformisation observabilité | P1 | A-003, A-004, A-005 |
| **S3** | Renforcement tests | P1-P2 | A-006, A-012, A-024 |
| **S4** | Industrialisation orchestration | P2 | A-020, A-023 |
| **S5** | Alerting & monitoring | P1-P2 | A-007, A-021 |
| **S6** | Backtesting & recherche | P2 | A-015, A-016, A-017 |
| **S7** | ML & gouvernance données | P2 | A-011, A-004 |
| **S8** | Sécurité & conteneurisation | P2-P3 | A-014, A-034 |

---

## Sprint 1 — Corrections critiques doc/config (priorité P1)

### Objectif
Corriger les incohérences documentaires et les défauts de configuration qui peuvent induire l'opérateur en erreur.

### Modules impactés
Documentation, Configuration, DataIntegrityEngine, Event Sentiment

### Anomalies traitées
- A-001 : Incohérence provider news par défaut
- A-002 : Défaut `bars_provider` code vs documentation
- A-013 : Redondance DOC_FONCTIONNELLE / DOC_TECHNIQUE (partiel)

### Tâches
1. **T1.1** : Acter le défaut réel du provider news déjà vérifié dans le code (`event_sentiment/cli.py`, `event_sentiment/config.py`) : `eodhd`
2. **T1.2** : Aligner toute la documentation (README.md, CONVENTIONS.md, DOC_FONCTIONNELLE.md, DOC_TECHNIQUE.md) sur cette valeur canonique
3. **T1.3** : Décider si le fallback interne `bars_provider` sans config doit rester `alpaca` (rétrocompat) ou être aligné sur `eodhd`
   - Fichiers : `dataIntegrityEngine/import_alpaca_bar.py:441`, `dataIntegrityEngine/import_eodhd_bar.py:90`
4. **T1.4** : Mettre à jour la documentation pour refléter explicitement le défaut code
5. **T1.5** : Supprimer les alias rétrocompatibles redondants dans `capital_presets.yaml` (A-025)
6. **T1.6** : Mettre à jour `doc/` selon les écarts détectés (A-026, A-027)

### Justification
Ces incohérences peuvent amener un opérateur à utiliser le mauvais provider sans le savoir, avec un impact direct sur la qualité des données et des décisions.

### Critères d'acceptation
- [ ] La valeur du provider news par défaut est identique dans tous les fichiers de documentation
- [ ] La doctrine sur le fallback interne `bars_provider` est explicitée (code + doc + tests)
- [ ] Les tests provider existants reflètent la doctrine retenue
- [ ] Les documents POC portent un bandeau explicite

### Tests
- `tests/test_doc_news_provider_consistency.py` (nouveau ou équivalent) — non-régression documentation
- `tests/test_eodhd_provider_switch.py` (existant) — symétrie / fallback provider
- `tests/test_config_no_literal_secrets.py` (existant) — passe toujours

### Gain attendu
- Documentation : 7.0 → 8.0
- Configuration : 6.5 → 7.5

---

## Sprint 2 — Uniformisation observabilité (priorité P1)

### Objectif
Uniformiser les résumés de run et assurer leur persistance SQL pour tous les modules.

### Modules impactés
DataIntegrityEngine, Screener, Selector, Event Sentiment, Database, IHM

### Anomalies traitées
- A-003 : Hétérogénéité des run_summary
- A-004 : Tables ML non confirmées
- A-005 : Validation cohérence presets/profil strict

### Tâches
1. **T2.1** : Concevoir un schéma commun de `run_summary` (tous les modules)
2. **T2.2** : Créer la table `run_summaries` dans `database/sql/`
3. **T2.3** : Implémenter un helper `core/run_summary.py` pour la persistance SQL
4. **T2.4** : Mettre à jour chaque module CLI pour persister son résumé
5. **T2.5** : Remplacer le faux doute sur les tables ML par un garde-fou de synchronisation doc/génération (`data_lineage_matrix`)
6. **T2.6** : Renforcer, si besoin, les tests de cohérence entre presets et profil strict déjà existants

### Critères d'acceptation
- [ ] Tous les modules émettent un `run_summary` conforme au schéma commun
- [ ] Tous les résumés sont persistés dans `run_summaries`
- [ ] La documentation lineage reste synchronisée avec le schéma réel
- [ ] Les tests de cohérence presets/profil couvrent explicitement les écarts métier assumés

### Tests
- `tests/test_run_summary_persistence.py` (nouveau) — intégration
- `tests/test_run_summary_schema.py` (nouveau) — unitaire schéma
- `tests/test_capital_presets_consistency.py` (nouveau) — config
- `tests/test_lineage_matrix_consistency.py` (nouveau) — SQL

### Gain attendu
- Observabilité : 7.0 → 8.0
- Database : 7.5 → 8.0

---

## Sprint 3 — Renforcement des tests (priorité P1-P2)

### Objectif
Ajouter des tests E2E, des tests d'intégration MySQL, et améliorer la couverture globale.

### Modules impactés
Tous

### Anomalies traitées
- A-006 : Pas de test E2E du pipeline complet
- A-012 : Pas de test MySQL Docker
- A-024 : Pas de test de parité backtest/live
- A-039 : Couverture inégale

### Tâches
1. **T3.1** : Créer un test E2E du pipeline 1→14 sur un univers de 5 symboles mockés
2. **T3.2** : Ajouter une configuration Docker Compose pour MySQL de test
3. **T3.3** : Ajouter des tests d'intégration avec MySQL réel pour les modules critiques
4. **T3.4** : Ajouter un test de parité backtest/exécution sur données historiques
5. **T3.5** : Identifier les modules sous-testés et ajouter des tests unitaires ciblés

### Critères d'acceptation
- [ ] Le test E2E passe sur le pipeline complet
- [ ] Les tests d'intégration MySQL passent
- [ ] La couverture globale atteint ≥ 75%
- [ ] Le test de parité backtest/live est fonctionnel

### Tests
- `tests/test_pipeline_e2e.py` (nouveau) — E2E
- `tests/test_backtest_live_parity.py` (nouveau) — intégration
- Extension des tests existants sur event_sentiment, modelFactory

### Gain attendu
- Qualité logicielle : 7.5 → 8.5
- Backtesting : 8.0 → 8.5

---

## Sprint 4 — Industrialisation orchestration (priorité P2)

### Objectif
Mettre en place un orchestrateur pour automatiser le pipeline quotidien avec reprise sur erreur.

### Modules impactés
Architecture, Tous les modules

### Anomalies traitées
- A-020 : Pas d'orchestrateur formel
- A-023 : Pool DB modeste

### Tâches
1. **T4.1** : Évaluer et choisir un orchestrateur (recommandé : Prefect pour Python natif)
2. **T4.2** : Créer un flow Prefect pour le pipeline quotidien 1→14
3. **T4.3** : Ajouter la reprise sur erreur par étape
4. **T4.4** : Configurer le scheduling automatique
5. **T4.5** : Ajuster le pool DB pour la production

### Critères d'acceptation
- [ ] Le pipeline peut être lancé automatiquement à heure fixe
- [ ] En cas d'échec d'une étape, les étapes précédentes ne sont pas rejouées
- [ ] Le dashboard Prefect permet de suivre l'état du pipeline

### Tests
- `tests/test_prefect_flow.py` (nouveau) — intégration orchestrateur

### Gain attendu
- Observabilité : 8.0 → 8.5
- Sécurité/Readiness : 7.0 → 7.5

---

## Sprint 5 — Alerting & monitoring (priorité P1-P2)

### Objectif
Industrialiser les notifications et le monitoring déjà amorcés (email workflow IHM + métriques Prometheus minimales).

### Modules impactés
Observabilité, Execution, Risk, Tous

### Anomalies traitées
- A-007 : Absence d'alerting externe
- A-021 : Pas de monitoring Prometheus/Grafana

### Tâches
1. **T5.1** : Étendre les notifications email existantes aux événements critiques hors workflow terminal
2. **T5.2** : Ajouter un webhook Slack / webhook générique
3. **T5.3** : Brancher plus largement les métriques Prometheus existantes
4. **T5.4** : Créer un dashboard Grafana de base
5. **T5.5** : Configurer des alertes Grafana sur les métriques clés

### Critères d'acceptation
- [ ] Une alerte Slack est envoyée quand le circuit breaker se déclenche
- [ ] Les métriques Prometheus sont accessibles sur un endpoint HTTP
- [ ] Le dashboard Grafana affiche l'état du dernier run

### Tests
- `tests/test_alerting.py` (nouveau) — intégration alertes
- `tests/test_metrics.py` (nouveau) — unitaire métriques

### Gain attendu
- Observabilité : 8.0 → 9.0
- Sécurité/Readiness : 7.0 → 8.0

---

## Sprint 6 — Backtesting & recherche (priorité P2)

### Objectif
Activer les fonctionnalités de backtesting existantes mais non branchées, ajouter l'analyse de sensibilité.

### Modules impactés
Backtesting

### Anomalies traitées
- A-015 : Pas de parallélisation des runs
- A-016 : Cache Parquet non branché
- A-017 : Analyse de sensibilité non exposée

### Tâches
1. **T6.1** : Activer le cache Parquet par défaut avec option `--no-cache`
2. **T6.2** : Exposer les fonctions d'analyse de sensibilité dans la CLI
3. **T6.3** : Ajouter un mode parallèle pour les sweeps de paramètres
4. **T6.4** : Brancher les modules `analytics.py` et `statistical_validation.py`

### Critères d'acceptation
- [ ] Le cache Parquet est utilisé par défaut
- [ ] `python -m backtesting sensitivity` fonctionne
- [ ] `python -m backtesting run --parallel 4` fonctionne

### Tests
- `tests/test_backtest_cache.py` (existant, à étendre)
- `tests/test_backtest_sensitivity.py` (nouveau)

### Gain attendu
- Backtesting : 8.0 → 9.0

---

## Sprint 7 — ML & gouvernance données (priorité P2)

### Objectif
Compléter la gouvernance ML et améliorer la qualité des données.

### Modules impactés
ModelFactory, Database, DataIntegrityEngine

### Anomalies traitées
- A-011 : `model_predictions` incomplet
- A-004 : Tables ML non confirmées
- A-010 : Duplication importeurs barres

### Tâches
1. **T7.1** : Ajouter un garde-fou de régression sur les colonnes `selected_model`, `decision_threshold`, `calibration_method` déjà présentes dans `model_predictions`
2. **T7.2** : Synchroniser la documentation/audit avec ce schéma réel
3. **T7.3** : Vérifier le peuplement effectif lors de l'inférence sur les chemins critiques
4. **T7.4** : Factoriser le code commun entre `import_alpaca_bar.py` et `import_eodhd_bar.py`
5. **T7.5** : Ajouter un test de walk-forward pour le ML

### Critères d'acceptation
- [ ] `model_predictions` reste conforme au schéma de gouvernance ML attendu
- [ ] La documentation et les tests reflètent ce schéma réel
- [ ] Le test de walk-forward passe

### Tests
- `tests/test_model_predictions_schema.py` (nouveau) — SQL
- `tests/test_model_walk_forward.py` (nouveau) — intégration ML
- `tests/test_bar_importers_consistency.py` (nouveau) — unitaire

### Gain attendu
- ModelFactory : 6.5 → 8.0
- Database : 8.0 → 8.5

---

## Sprint 8 — Sécurité & conteneurisation (priorité P2-P3)

### Objectif
Renforcer la sécurité et faciliter le déploiement.

### Modules impactés
Architecture, Sécurité, IHM

### Anomalies traitées
- A-014 : Pas de mode read-only IHM
- A-034 : Pas de conteneurisation Docker
- A-035, A-036, A-037 : Limitations documentées
- A-038 : Configuration dispersée

### Tâches
1. **T8.1** : Créer un Dockerfile et docker-compose.yml
2. **T8.2** : Ajouter un mode `--read-only` à l'IHM
3. **T8.3** : Migrer `mypy.ini` et `pytest.ini` dans `pyproject.toml`
4. **T8.4** : Documenter les limitations (USD only, long-only, pas de streaming)
5. **T8.5** : Ajouter un health check des providers en préflight

### Critères d'acceptation
- [ ] `docker compose up` lance l'IHM et la DB
- [ ] L'IHM en mode `--read-only` ne permet pas de lancer des pipelines
- [ ] `pyproject.toml` contient toute la configuration

### Tests
- `tests/test_ihm_readonly.py` (nouveau) — E2E IHM
- `tests/test_provider_health.py` (nouveau) — intégration providers

### Gain attendu
- IHM : 7.5 → 8.5
- Sécurité/Readiness : 7.0 → 8.5

---

## Ce qu'il restera à faire pour atteindre un vrai 10/10 pro-grade

1. **Vault/AWS SSM** pour la gestion des secrets
2. **Chiffrement de la base de données** au repos
3. **Audit de sécurité externe** (pentest)
4. **Support multi-devises** (EUR, GBP, CHF)
5. **Support short selling** avec stratégies baissières
6. **Streaming temps réel** (WebSocket Alpaca)
7. **Calibration automatique** des poids sentiment par walk-forward
8. **Backtesting sur plusieurs années** avec validation croisée
9. **Documentation de l'API interne** (Sphinx/autodoc)
10. **Séparation des privilèges** (opérateur vs administrateur)

---

## À partir de quel sprint l'application devient-elle suffisamment robuste pour du swing trading réel discipliné ?

**Sprint 3** — après correction des P1, uniformisation des résumés, et renforcement des tests, l'application est suffisamment robuste pour du paper trading avancé et une préparation au live.

**Sprint 5** — après industrialisation de l'orchestration et ajout de l'alerting, l'application est prête pour du live trading avec de l'argent réel, sous supervision humaine disciplinée.

**Post-Sprint 8** — l'application atteint un niveau professionnel buy-side (8.5-9/10).
