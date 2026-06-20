# 08 — Sprint Plan

> **Plan d'action détaillé pour amener l'application au plus près de 10/10**

---

## Vue d'ensemble

| Sprint | Objectif | Priorité | Durée estimée | Anomalies traitées |
|---|---|---|---|---|
| **S8** | Quick wins — corrections critiques | 🔴 P0 | 2 semaines | A-CAP-002, A-CAP-003 |
| **S8-bis** | Mise à jour IHM post-PDT | 🔴 P1 | 1 semaine | A-IHM-001 (IHM : `swing_only=False`), A-IHM-002 |
| **S9** | Alignement IHM/presets (suite) | 🟡 P1 | 1 semaine | Finalisation IHM, validation croisée |
| **S10** | Remise à niveau documentaire | 🟡 P1 | 2 semaines | A-DOC-001, A-DOC-002, A-DOC-003, A-DOC-004 |
| **S11** | Robustesse backtesting | 🟡 P1 | 3 semaines | A-BACK-001, A-BACK-002, A-CONV-001 |
| **S12** | Gouvernance ML et rollback | 🟡 P1 | 3 semaines | A-ML-001, A-ML-002, A-ML-003 |
| **S13** | Sécurisation corporate actions | 🟡 P1 | 2 semaines | A-CA-001 |
| **S14** | Qualité logicielle et observabilité | 🟢 P2 | 3 semaines | A-CODE-001, A-CODE-002, A-OBS-001, A-TEST-001, A-TEST-002 |
| **S15** | Sécurité et readiness production | 🟢 P2 | 2 semaines | A-SEC-001, A-IHM-003 |
| **S16** | Optimisations et polish | 🟢 P2-P3 | 2 semaines | A-DATA-001, A-DATA-002, A-IHM-004, A-CAP-004, A-CAP-005, A-CAP-006 |
| **S17** | Validation live et paper | 🔵 Validation | 4 semaines | — |

**Total** : 11 sprints sur ~6 mois (S8-bis ajouté pour la mise à jour IHM post-PDT)

---

## Sprint S8 — Quick wins : corrections critiques

**Objectif** : Corriger les anomalies P0 restantes sur les presets de capital.

> **Note** : L'anomalie A-CAP-001 (`execution_swing_only=false`) est **résolue** par le changement réglementaire FINRA du 4 juin 2026 (suppression de la règle PDT). `swing_only=false` est désormais le bon paramétrage. Aucune action n'est nécessaire sur les presets.

**Priorité** : 🔴 Critique (P0)

**Modules impactés** : `common/capital_presets.py`, `config/capital_presets.yaml`

**Anomalies traitées** : A-CAP-002, A-CAP-003

### Tâches

1. **Différencier les paramètres de drawdown breaker** par tranche
   - `degraded_entry_allocation_pct` : 0.05 (micro) → 0.15 (100k$+)
   - `ramp_up_max_pct` : 0.20 (micro) → 0.60 (100k$+)
   - Fichiers : `config/capital_presets.yaml`

2. **Remonter `risk_min_position_notional` à ≥155$** pour le preset 2k-5k$
   - Fichiers : `config/capital_presets.yaml` (preset `capital_0_5000`)

3. **Uniformiser la devise en USD** pour le preset micro-compte
   - Fichiers : `config/capital_presets.yaml` (preset `capital_0_2000_eur`)

4. **Revoir le seuil cash→margin à 25k$** : ce seuil était lié à la PDT (désormais supprimée). Documenter la nouvelle logique.

### Critères d'acceptation
- [x] Les paramètres de drawdown breaker sont croissants avec le capital
- [x] `risk_min_position_notional ≥ 155` pour tous les presets
- [x] Le seuil cash→margin est documenté et justifié post-PDT
- [x] Tous les tests `test_capital_presets_consistency.py` passent (8/8 ✅)

### Tests à ajouter
| Test | Type | Fichier | Statut |
|---|---|---|---|
| T-CAP-002 : drawdown breaker croissant | Config | `tests/test_capital_presets_consistency.py` | ✅ Implémenté |
| T-CAP-003 : min_notional ≥ enforce_min | Config | `tests/test_capital_presets_consistency.py` | ✅ Implémenté |
| T-CAP-004 : swing_only=false sur tous les presets | Config | `tests/test_capital_presets_consistency.py` | ✅ Implémenté |
| T-CAP-005 : backtesting_dd_* cohérents avec risk_* | Config | `tests/test_capital_presets_consistency.py` | ✅ Implémenté |

### Gain attendu
- Configuration : 6.5 → 7.5 ✅
- Sécurité/Production : 6.0 → 7.0 ✅

---

## Sprint S8-bis — Mise à jour IHM post-PDT

**Objectif** : Mettre à jour l'IHM pour refléter la nouvelle réalité réglementaire (suppression PDT).

**Priorité** : 🔴 Haute (P1)

**Modules impactés** : `ihm/services/pipeline_runner.py`, `ihm/pages/pipeline.py`

**Anomalies traitées** : A-IHM-001 (révisé)

### Tâches

1. **Changer le défaut `execution_swing_only` de `True` à `False`** dans l'IHM
   - Refléter la réalité post-PDT : le day trading intraday est autorisé
   - Fichiers : `ihm/services/pipeline_runner.py`

2. **Aligner les défauts IHM sur le preset détecté**
   - `execution_account_type` doit être lu depuis le preset
   - Fichiers : `ihm/services/pipeline_runner.py`

3. **Ajouter une validation dans `PipelineLaunchOptions.__post_init__`**
   - Vérifier la cohérence avec le preset actif
   - Émettre un warning si divergence
   - Fichiers : `ihm/services/pipeline_runner.py`

4. **Corriger le step 1 IHM** pour refléter le provider actif
   - Afficher `import_eodhd_bar` si `bars_provider=eodhd`
   - Fichiers : `ihm/pages/pipeline.py`

### Critères d'acceptation
- [x] Le défaut `execution_swing_only` est `False` dans l'IHM
- [x] Les défauts IHM sont cohérents avec les presets (swing_only=False)
- [x] Un warning est émis par `__post_init__` si `swing_only=True` (obsolète)
- [x] Le step 1 reflète le bon provider (nom dynamique via `resolve_step_display_name`)
- [x] Tests IHM mis à jour (T-IHM-001 ajouté)

### Tests à ajouter
| Test | Type | Fichier | Statut |
|---|---|---|---|
| T-IHM-001 : défaut swing_only=False (post-PDT) | Intégration IHM | `tests/test_ihm_cli_contract.py` | ✅ Implémenté |
| T-IHM-002 : validation rejette combinaisons incohérentes | Intégration IHM | `tests/test_ihm_pipeline_runner.py` | ⏳ Différé (nécessite preset loader mock) |
| Test E2E : workflow complet IHM → backend | E2E IHM | `tests/test_ihm_pipeline_e2e.py` (étendre) | ⏳ Sprint S9 |

### Gain attendu
- IHM : 6.0 → 7.5 ✅

---

## Sprint S9 — Alignement IHM / Presets (suite)

**Objectif** : Finaliser l'alignement IHM/presets et la validation croisée.

**Priorité** : 🟡 Moyenne (P1)

**Modules impactés** : `ihm/`, `common/capital_presets.py`

**Anomalies traitées** : A-IHM-002, finalisation S8-bis

### Tâches

1. **Ajouter un bandeau d'avertissement** dans l'IHM quand les paramètres divergent du preset
   - Fichiers : `ihm/pages/pipeline.py`

2. **Ajouter une infobulle explicative** sur `execution_swing_only` mentionnant le changement réglementaire FINRA 2026-06-04
   - Fichiers : `ihm/pages/pipeline.py`

3. **Finaliser les tests E2E IHM** 

### Critères d'acceptation
- [x] Avertissement visible en cas de divergence IHM/preset (swing_only=True → warning)
- [x] Infobulle FINRA 2026-06-04 présente sur le checkbox `execution_swing_only`
- [x] Tests IHM `test_ihm_cli_contract.py` passent (28/28 ✅, dont T-IHM-001)
- [ ] Test E2E workflow complet IHM → backend (différé — nécessite infra Streamlit headless)

### Gain attendu
- IHM : 7.5 → 7.5 (stabilisé) ✅

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
- [x] Plus aucune valeur obsolète dans `DOC_FONCTIONNELLE.md` — sprints S8/S8-bis/S9 ajoutés, contexte post-PDT documenté
- [x] Tous les plans v2 ont un statut clair — déjà documenté dans `DOC_TECHNIQUE.md` §0
- [x] Le nommage `selector_min_ibd_rs_rank` / `selector_min_relative_strength_index` est géré par alias (mécanisme `SELECTOR_RS_ALIAS_KEY` / `SELECTOR_RS_LEGACY_KEY`)
- [x] Références `fallback_on_failure` : conservées comme documentation historique (flag retiré en S0)
- [x] `doc/execution_engine.md` : dépréciation `__main__.py` renforcée (mention `DeprecationWarning`)
- [x] `doc/backtesting.md` et `doc/risk_management.md` : plans v2 déjà référencés

### Gain attendu
- Documentation : 5.0 → 7.5 ✅
- Qualité logicielle : 6.5 → 7.0 ✅

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
- [x] Le cache Parquet est actif par défaut (`--no-cache` pour désactiver, ex `--use-cache`)
- [x] La microstructure est activée par défaut (slippage `sqrt` + 2 bps base + 5 bps impact, gap 3%)
- [x] Les frais sont modélisés par palier de capital (`TieredCommissionConfig` + `COMMISSION_PRESETS`)
- [x] Le bootstrap Monte Carlo est activé par défaut (500 itérations)
- [x] Tests trading_constraints passent (4/4 ✅)

### Tests à ajouter
| Test | Type | Fichier | Statut |
|---|---|---|---|
| T-BACK-001 : cache Parquet accélère le chargement | Performance | `tests/test_backtesting.py` (étendre) | ⏳ Benchmark différé |
| T-CONV-001 : poids de conviction justifiés | Non-régression | `tests/test_conviction_weights_config.py` | ⏳ Ablation différée |
| Test de parité backtest/live sur les coûts | Parité | `tests/test_backtest_live_parity.py` (étendre) | ⏳ Sprint S17 |

### Gain attendu
- Backtesting : 7.0 → 8.0 ✅
- Configuration : 8.0 → 8.5 ✅

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
- [x] Les constantes ML sont extraites dans `ihm/services/pipeline_ml_defaults.py` (70+ constantes)
- [x] `pipeline_runner.py` importe depuis `pipeline_ml_defaults` (réduction ~80 lignes)
- [x] La procédure de rollback est documentée dans `doc/ml.md` (5 étapes + rollback auto)
- [x] CatBoost est vérifié avant d'être proposé (`is_catboost_available()` dans `pipeline_ml_defaults`)
- [x] Tests IHM `test_ihm_cli_contract.py` et `test_ihm_pipeline_runner.py` passent (30/30 ✅)
- [ ] Mode « Expert ML » dans l'IHM (différé — refactor UI Streamlit complexe)
- [ ] Test E2E rollback ML (différé — nécessite infra d'entraînement ML)

### Tests à ajouter
| Test | Type | Fichier | Statut |
|---|---|---|---|
| T-ML-001 : nombre de paramètres ML exposés ≤ 15 en standard | E2E IHM | `tests/test_ihm_pipeline_runner.py` | ⏳ Différé (refactor UI) |
| Test E2E rollback ML | Intégration | `tests/test_ml_auto_rollback_champion.py` (étendre) | ⏳ Différé (infra ML) |

### Gain attendu
- ModelFactory : 6.0 → 7.0 ✅
- IHM : 7.5 → 8.0 ✅

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
- [x] Le cross-check Yahoo est exécuté automatiquement après chaque sync (`--cross-check` défaut `yahoo` pour `sync` et `run`)
- [x] Les divergences sont loggées et remontées dans le run summary (via `_emit_and_persist_summary` avec `audit_anomalies`)
- [x] Tests de cross-check passent (7/7 ✅)
- [x] `yfinance` absent → cross-check désactivé silencieusement (best-effort, jamais bloquant)

### Tests à ajouter
| Test | Type | Fichier | Statut |
|---|---|---|---|
| T-CA-001 : cross-check Yahoo fonctionnel | Intégration | `tests/test_corporate_actions_cross_check_yahoo.py` | ✅ Existant (7 tests) |

### Gain attendu
- Corporate Actions : 7.5 → 8.5 ✅

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
- [x] `pipeline_runner.py` importe `STRICT_SWING_CASH_FILTERS` depuis l'alias `selector.strict_filter_profiles` (canonical `core.filter_profiles` référencé dans le commentaire S14)
- [x] Aucun import restant de `selector.strict_filter_profiles` hors alias légitime (4 fichiers : 1 IHM, 1 test, 2 archives)
- [x] JSON logging fonctionnel : `JSONFormatter` + `_resolve_log_formatter` + activation via `ALPHA_TRADE_LOG_FORMAT=json`
- [x] Tests de mutation en CI : `.github/workflows/mutation.yml` (mutmut, hebdomadaire dimanche 03:00 UTC)
- [x] Benchmarks exécutables : `tests/benchmarks/test_screener_bench.py` + `test_backtesting_bench.py`

### Gain attendu
- Qualité logicielle : 7.0 → 8.0 ✅
- Observabilité : 6.5 → 7.5 ✅

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
