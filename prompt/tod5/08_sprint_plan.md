# 08 — Sprint Plan

> **Plan d'action détaillé pour amener l'application au plus près de 10/10**

---

## Vue d'ensemble

| Sprint | Objectif | Priorité | Durée estimée | Anomalies traitées |
|---|---|---|---|---|
| **S8** | Quick wins — corrections critiques | 🔴 P0 | 2 semaines | A-CAP-001, A-CAP-002, A-CAP-003 |
| **S9** | Alignement IHM/presets | 🔴 P0-P1 | 2 semaines | A-IHM-001, A-IHM-002 |
| **S10** | Remise à niveau documentaire | 🟡 P1 | 2 semaines | A-DOC-001, A-DOC-002, A-DOC-003, A-DOC-004 |
| **S11** | Robustesse backtesting | 🟡 P1 | 3 semaines | A-BACK-001, A-BACK-002, A-CONV-001 |
| **S12** | Gouvernance ML et rollback | 🟡 P1 | 3 semaines | A-ML-001, A-ML-002, A-ML-003 |
| **S13** | Sécurisation corporate actions | 🟡 P1 | 2 semaines | A-CA-001 |
| **S14** | Qualité logicielle et observabilité | 🟢 P2 | 3 semaines | A-CODE-001, A-CODE-002, A-OBS-001, A-TEST-001, A-TEST-002 |
| **S15** | Sécurité et readiness production | 🟢 P2 | 2 semaines | A-SEC-001, A-IHM-003 |
| **S16** | Optimisations et polish | 🟢 P2-P3 | 2 semaines | A-DATA-001, A-DATA-002, A-IHM-004, A-CAP-004, A-CAP-005, A-CAP-006 |
| **S17** | Validation live et paper | 🔵 Validation | 4 semaines | — |

**Total** : 10 sprints sur ~6 mois

---

## Sprint S8 — Quick wins : corrections critiques

**Objectif** : Corriger les 3 anomalies P0 sur les presets de capital.

**Priorité** : 🔴 Critique (P0)

**Modules impactés** : `common/capital_presets.py`, `config/capital_presets.yaml`

**Anomalies traitées** : A-CAP-001, A-CAP-002, A-CAP-003

### Tâches

1. **Activer `execution_swing_only=true`** sur tous les presets (a minima les comptes cash)
   - Fichiers : `config/capital_presets.yaml` (tous les presets)
   
2. **Différencier les paramètres de drawdown breaker** par tranche
   - `degraded_entry_allocation_pct` : 0.05 (micro) → 0.15 (100k$+)
   - `ramp_up_max_pct` : 0.20 (micro) → 0.60 (100k$+)
   - Fichiers : `config/capital_presets.yaml`

3. **Remonter `risk_min_position_notional` à ≥155$** pour le preset 2k-5k$
   - Fichiers : `config/capital_presets.yaml` (preset `capital_0_5000`)

4. **Uniformiser la devise en USD** pour le preset micro-compte
   - Fichiers : `config/capital_presets.yaml` (preset `capital_0_2000_eur`)

### Critères d'acceptation
- [ ] Tous les presets cash ont `execution_swing_only: true`
- [ ] Les paramètres de drawdown breaker sont croissants avec le capital
- [ ] `risk_min_position_notional ≥ 155` pour tous les presets
- [ ] Tous les tests `test_capital_presets_consistency.py` passent

### Tests à ajouter
| Test | Type | Fichier |
|---|---|---|
| T-CAP-001 : swing_only sur presets cash | Config | `tests/test_capital_presets_consistency.py` |
| T-CAP-002 : drawdown breaker croissant | Config | `tests/test_capital_presets_consistency.py` |
| T-CAP-003 : min_notional ≥ enforce_min | Config | `tests/test_capital_presets_consistency.py` |

### Gain attendu
- Configuration : 6.0 → 7.5
- Sécurité/Production : 6.0 → 7.0

---

## Sprint S9 — Alignement IHM / Presets

**Objectif** : Résoudre les incohérences entre les défauts IHM et les presets de capital.

**Priorité** : 🔴 Haute (P0-P1)

**Modules impactés** : `ihm/services/pipeline_runner.py`, `ihm/pages/pipeline.py`, `common/capital_presets.py`

**Anomalies traitées** : A-IHM-001, A-IHM-002

### Tâches

1. **Aligner les défauts IHM sur le preset détecté**
   - `execution_account_type` et `execution_swing_only` doivent être lus depuis le preset
   - Fichiers : `ihm/services/pipeline_runner.py`

2. **Ajouter une validation dans `PipelineLaunchOptions.__post_init__`**
   - Vérifier la cohérence avec le preset actif
   - Émettre un warning si divergence
   - Fichiers : `ihm/services/pipeline_runner.py`

3. **Corriger le step 1 IHM** pour refléter le provider actif
   - Afficher `import_eodhd_bar` si `bars_provider=eodhd`
   - Fichiers : `ihm/pages/pipeline.py`

4. **Ajouter un bandeau d'avertissement** dans l'IHM quand les paramètres divergent du preset
   - Fichiers : `ihm/pages/pipeline.py`

### Critères d'acceptation
- [ ] Les défauts IHM sont lus depuis le preset de capital
- [ ] Un warning est affiché en cas de divergence
- [ ] Le step 1 reflète le bon provider
- [ ] Tests IHM mis à jour

### Tests à ajouter
| Test | Type | Fichier |
|---|---|---|
| T-IHM-001 : défauts IHM cohérents avec preset | Intégration IHM | `tests/test_ihm_cli_contract.py` |
| T-IHM-002 : validation rejette combinaisons incohérentes | Intégration IHM | `tests/test_ihm_pipeline_runner.py` |
| Test E2E : workflow complet IHM → backend | E2E IHM | `tests/test_ihm_pipeline_e2e.py` (étendre) |

### Gain attendu
- IHM : 6.0 → 7.5
- Configuration : 7.5 → 8.0

---

## Sprint S10 — Remise à niveau documentaire

**Objectif** : Aligner `doc/` avec le code réel, nettoyer les valeurs obsolètes, documenter les plans v2.

**Priorité** : 🟡 Moyenne (P1)

**Modules impactés** : `doc/` (tous les fichiers)

**Anomalies traitées** : A-DOC-001, A-DOC-002, A-DOC-003, A-DOC-004, A-EXE-001

### Tâches

1. **Nettoyer `DOC_FONCTIONNELLE.md`**
   - Supprimer les valeurs historiques commentées
   - Mettre à jour les valeurs canoniques
   - Ajouter le statut des plans v2
   - Fichier : `doc/DOC_FONCTIONNELLE.md`

2. **Mettre à jour `DOC_TECHNIQUE.md`**
   - Clarifier le statut d'implémentation des plans v2 (⏳/✅/🔮)
   - Mettre à jour le schéma des tables
   - Fichier : `doc/DOC_TECHNIQUE.md`

3. **Uniformiser le nommage `selector_min_ibd_rs_rank` → `selector_min_relative_strength_index`**
   - Dans `config/capital_presets.yaml`
   - Dans `common/capital_presets.py`
   - Fichiers concernés

4. **Nettoyer les références à `fallback_on_failure`**
   - Fichiers : `doc/dataIntegrityEngine.md`, `doc/DOC_TECHNIQUE.md`

5. **Documenter la dépréciation de `execution_engine/__main__.py`**
   - Fichier : `doc/execution_engine.md`

6. **Mettre à jour `doc/backtesting.md`** avec les plans v2 short selling

7. **Mettre à jour `doc/risk_management.md`** avec les trackers de concentration

### Critères d'acceptation
- [ ] Plus aucune valeur obsolète dans `DOC_FONCTIONNELLE.md`
- [ ] Tous les plans v2 ont un statut clair
- [ ] Le nommage est uniformisé
- [ ] `test_docs_provider_consistency.py` passe

### Tests à ajouter
| Test | Type | Fichier |
|---|---|---|
| T-DOC-001 : valeurs numériques doc = code | Non-régression doc | `tests/test_docs_provider_consistency.py` (étendre) |
| Test de cohérence des noms de champs | Config | `tests/test_capital_presets_consistency.py` (étendre) |

### Gain attendu
- Documentation : 5.0 → 7.5
- Qualité logicielle : 6.5 → 7.0

---

## Sprint S11 — Robustesse backtesting

**Objectif** : Améliorer le réalisme du backtesting (cache, frais, microstructure).

**Priorité** : 🟡 Moyenne (P1)

**Modules impactés** : `backtesting/`

**Anomalies traitées** : A-BACK-001, A-BACK-002, A-CONV-001

### Tâches

1. **Activer le cache Parquet par défaut**
   - Brancher `backtesting/cache.py` dans la commande `run`
   - Ajouter `--no-cache` pour désactiver
   - Fichiers : `backtesting/cli/_impl.py`, `backtesting/cache.py`

2. **Activer le module microstructure par défaut**
   - Slippage volume-aware
   - Filtre de gap
   - Fichiers : `backtesting/microstructure.py`

3. **Implémenter un modèle de frais réaliste**
   - Commission par action + bps pour les petits ordres
   - Fichiers : `backtesting/trading_constraints.py`

4. **Calibrer les poids de conviction sur données out-of-sample**
   - Lancer une ablation walk-forward
   - Documenter les résultats
   - Fichiers : `artifacts/ablation/`

5. **Activer `analytics.py` et `statistical_validation.py`**
   - Brancher l'export HTML interactif
   - Activer le bootstrap Monte Carlo
   - Fichiers : `backtesting/analytics.py`, `backtesting/statistical_validation.py`

### Critères d'acceptation
- [ ] Le cache Parquet est actif et mesurablement plus rapide
- [ ] La microstructure est activée par défaut en mode `pipeline`
- [ ] Les frais sont modélisés par type d'ordre
- [ ] Les poids de conviction sont justifiés par l'ablation
- [ ] Tests de performance ajoutés

### Tests à ajouter
| Test | Type | Fichier |
|---|---|---|
| T-BACK-001 : cache Parquet accélère le chargement | Performance | `tests/test_backtesting.py` (étendre) |
| T-CONV-001 : poids de conviction justifiés | Non-régression | `tests/test_conviction_weights_config.py` |
| Test de parité backtest/live sur les coûts | Parité | `tests/test_backtest_live_parity.py` (étendre) |

### Gain attendu
- Backtesting : 7.0 → 8.0
- Configuration : 8.0 → 8.5

---

## Sprint S12 — Gouvernance ML et rollback

**Objectif** : Simplifier l'exposition ML dans l'IHM et documenter le rollback.

**Priorité** : 🟡 Moyenne (P1)

**Modules impactés** : `modelFactory/`, `ihm/services/pipeline_runner.py`

**Anomalies traitées** : A-ML-001, A-ML-002, A-ML-003

### Tâches

1. **Créer un mode « Expert ML » dans l'IHM**
   - Mode standard : 5-6 paramètres essentiels
   - Mode expert : tous les paramètres
   - Fichiers : `ihm/pages/pipeline.py`, `ihm/services/pipeline_runner.py`

2. **Documenter la procédure de rollback champion ML**
   - Dans `doc/ml.md`
   - Procédure pas à pas
   - Fichier : `doc/ml.md`

3. **Vérifier la disponibilité de CatBoost avant de le proposer**
   - Dans l'IHM, griser l'option si non installé
   - Fichiers : `ihm/services/pipeline_runner.py`

4. **Ajouter un test E2E de rollback ML**
   - Simuler une dégradation → rollback automatique
   - Fichiers : `tests/test_ml_auto_rollback_champion.py` (étendre)

5. **Simplifier les constantes ML dans `pipeline_runner.py`**
   - Extraire dans `ihm/services/pipeline_ml_defaults.py`
   - Fichiers : nouveau + `pipeline_runner.py`

### Critères d'acceptation
- [ ] Le mode standard IHM expose ≤ 10 paramètres ML
- [ ] La procédure de rollback est documentée et testée
- [ ] CatBoost est vérifié avant d'être proposé
- [ ] Tests ML mis à jour

### Tests à ajouter
| Test | Type | Fichier |
|---|---|---|
| T-ML-001 : nombre de paramètres ML exposés ≤ 15 en standard | E2E IHM | `tests/test_ihm_pipeline_runner.py` |
| Test E2E rollback ML | Intégration | `tests/test_ml_auto_rollback_champion.py` (étendre) |

### Gain attendu
- ModelFactory : 6.0 → 7.0
- IHM : 7.5 → 8.0

---

## Sprint S13 — Sécurisation corporate actions

**Objectif** : Ajouter le cross-check multi-provider pour les corporate actions.

**Priorité** : 🟡 Moyenne (P1)

**Modules impactés** : `corporate_actions/`

**Anomalies traitées** : A-CA-001

### Tâches

1. **Activer le cross-check Yahoo par défaut**
   - Mode warning (ne pas bloquer le pipeline)
   - Logger les divergences
   - Fichiers : `corporate_actions/cross_check_yahoo.py`, `corporate_actions/engine.py`

2. **Ajouter un test de détection de divergence**
   - Simuler un dividende manqué par EODHD mais présent chez Yahoo
   - Fichiers : `tests/test_corporate_actions_cross_check_yahoo.py`

3. **Ajouter une alerte si un dividende est détecté par un provider mais pas l'autre**
   - Intégration dans les run summaries
   - Fichiers : `corporate_actions/engine.py`

### Critères d'acceptation
- [ ] Le cross-check Yahoo est exécuté automatiquement après chaque sync
- [ ] Les divergences sont loggées et remontées dans le run summary
- [ ] Tests de cross-check passent

### Tests à ajouter
| Test | Type | Fichier |
|---|---|---|
| T-CA-001 : cross-check Yahoo fonctionnel | Intégration | `tests/test_corporate_actions_cross_check_yahoo.py` (étendre) |

### Gain attendu
- Corporate Actions : 7.5 → 8.5

---

## Sprint S14 — Qualité logicielle et observabilité

**Objectif** : Améliorer la maintenabilité du code et l'observabilité.

**Priorité** : 🟢 Modérée (P2)

**Modules impactés** : Tous

**Anomalies traitées** : A-CODE-001, A-CODE-002, A-OBS-001, A-TEST-001, A-TEST-002

### Tâches

1. **Scinder `pipeline_runner.py`**
   - `pipeline_defaults.py` : constantes
   - `pipeline_options.py` : `PipelineLaunchOptions`
   - `pipeline_commands.py` : construction des commandes
   - Fichiers : `ihm/services/`

2. **Migrer les imports de `selector.strict_filter_profiles` → `core.filter_profiles`**
   - Fichiers : `ihm/services/pipeline_runner.py`, tous les consommateurs

3. **Ajouter le JSON logging**
   - Formatteur JSON optionnel
   - Activé via variable d'environnement
   - Fichiers : `common/logging_setup.py`

4. **Ajouter les tests de mutation en CI**
   - Job GitHub Actions hebdomadaire
   - Fichier : `.github/workflows/mutation.yml`

5. **Ajouter des benchmarks pytest**
   - Screener, selector, backtesting
   - Fichiers : `tests/benchmarks/`

### Critères d'acceptation
- [ ] `pipeline_runner.py` est scindé en 3 modules
- [ ] Aucun import restant de `selector.strict_filter_profiles`
- [ ] JSON logging fonctionnel
- [ ] Tests de mutation en CI
- [ ] Benchmarks exécutables

### Tests à ajouter
| Test | Type | Fichier |
|---|---|---|
| Test de non-régression après refactor | Non-régression | `tests/test_ihm_pipeline_runner.py` |
| Test de format de log JSON | Unitaire | `tests/test_common_utils.py` (étendre) |

### Gain attendu
- Qualité logicielle : 7.0 → 8.0
- Observabilité : 6.5 → 7.5

---

## Sprint S15 — Sécurité et readiness production

**Objectif** : Renforcer la sécurité et préparer le passage en production.

**Priorité** : 🟢 Modérée (P2)

**Modules impactés** : `core/secrets/`, `ihm/`, `execution_engine/`

**Anomalies traitées** : A-SEC-001, A-IHM-003

### Tâches

1. **Ajouter un mode « lecture seule » dans l'IHM**
   - Désactiver tous les boutons d'action
   - Fichiers : `ihm/app.py`, `ihm/pages/`

2. **Chiffrer les colonnes sensibles en base**
   - P&L, positions (si nécessaire)
   - Fichiers : `database/sql/`, `core/secrets/`

3. **Ajouter une sandbox de pré-production**
   - Mode « paper strict » simulant exactement les contraintes live
   - Fichiers : `execution_engine/config.py`

4. **Documenter la checklist pre-live**
   - Mettre à jour `doc/pre_live_checklist.md`
   - Fichier : `doc/pre_live_checklist.md`

### Critères d'acceptation
- [ ] Le mode lecture seule est fonctionnel
- [ ] Les colonnes sensibles sont chiffrées
- [ ] La sandbox paper strict existe
- [ ] La checklist pre-live est à jour

### Tests à ajouter
| Test | Type | Fichier |
|---|---|---|
| Test de chiffrement/déchiffrement | Unitaire | `tests/test_phase1_secrets.py` (étendre) |
| Test IHM mode lecture seule | E2E IHM | `tests/test_ihm_security.py` (étendre) |

### Gain attendu
- Sécurité/Production : 7.0 → 8.0

---

## Sprint S16 — Optimisations et polish

**Objectif** : Traiter les anomalies P2-P3 restantes.

**Priorité** : 🟢 Modérée (P2-P3)

**Modules impactés** : Tous

**Anomalies traitées** : A-DATA-001, A-DATA-002, A-IHM-004, A-CAP-004, A-CAP-005, A-CAP-006

### Tâches

1. **Documenter la transition cash→margin à 25k$**
   - Ajouter un commentaire dans `capital_presets.yaml`
   - Fichier : `config/capital_presets.yaml`

2. **Uniformiser la devise du preset micro-compte en USD**
   - Conversion 2000€ → ~2150$
   - Fichier : `config/capital_presets.yaml`

3. **Uniformiser `screener_first_pass_window_days`**
   - Valeur standard : 252 pour toutes les tranches
   - Fichier : `config/capital_presets.yaml`

4. **Ajouter EODHD comme source de fondamentaux**
   - Alternative à Finnhub pour market_cap
   - Fichiers : `dataIntegrityEngine/update_sector.py`

5. **Afficher les logs en temps réel dans l'IHM**
   - Flux de logs dans la page Pipeline
   - Fichiers : `ihm/pages/pipeline.py`

### Critères d'acceptation
- [ ] La transition cash→margin est documentée
- [ ] La devise est uniformisée
- [ ] Les logs sont visibles en temps réel

### Gain attendu
- Configuration : 8.5 → 9.0
- IHM : 8.0 → 8.5

---

## Sprint S17 — Validation live et paper

**Objectif** : Valider l'application en conditions réelles (paper trading).

**Priorité** : 🔵 Validation

**Modules impactés** : Tous

### Tâches

1. **Exécuter 4 semaines de paper trading continu**
   - Tous les jours de marché
   - Avec le preset adapté au capital

2. **Comparer les résultats paper vs backtest**
   - Sur la même période
   - Analyser les écarts

3. **Documenter les écarts et leurs causes**
   - Slippage réel vs modélisé
   - Ordres non remplis
   - Divergences de données

4. **Ajuster les paramètres si nécessaire**
   - Frais, slippage, filtres

5. **Produire un rapport de validation**
   - Fichier : `doc/validation_report.md`

### Critères d'acceptation
- [ ] 20 jours de paper trading exécutés
- [ ] Écart backtest/paper < 10% sur le P&L
- [ ] Rapport de validation produit
- [ ] Aucun incident critique

### Gain attendu
- Confiance dans le passage en live
- Validation de la parité backtest/live

---

## Ce qu'il restera à faire pour un vrai 10/10 pro-grade

Après les 10 sprints (note estimée : 8.5/10) :

1. **Audit de sécurité externe** (pentest, revue de code par un tiers)
2. **Conformité réglementaire** (enregistrement RIA/CTA si gestion de capital tiers)
3. **Multi-brokers** : IBKR en production, backup broker automatique
4. **Infrastructure haute disponibilité** : serveur dédié, backup DB, disaster recovery testé
5. **Surveillance 24/7** : alerting, escalation, runbook opérateur
6. **Rapports GIPS** : pour présentation à des investisseurs
7. **Backtest 20+ ans** : validation sur plusieurs cycles de marché
8. **Paper trading 6+ mois** : avant tout passage en live

---

## À partir de quel sprint l'application devient suffisamment robuste pour un swing trading réel discipliné ?

**Réponse : Après le Sprint S9 (alignement IHM/presets) + Sprint S11 (robustesse backtesting).**

Soit **~2 mois** de travail. À ce stade :
- Les presets sont cohérents et sécurisés (S8)
- L'IHM ne peut pas induire l'opérateur en erreur (S9)
- Le backtesting est réaliste (S11)
- La documentation est à jour (S10)

**Avant le live, le Sprint S17 (validation paper 4 semaines) est IMPÉRATIF.**
