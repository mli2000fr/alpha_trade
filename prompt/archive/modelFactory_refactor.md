# Prompt — Plan complet de refactor `modelFactory`

## Mission

Tu interviens sur le module `modelFactory` de `F:\projets` avec un objectif clair : **corriger toutes les anomalies structurelles, fonctionnelles et opérationnelles qui empêchent le module d’atteindre un niveau professionnel pour un usage swing trade réel**, sans casser les acquis déjà présents.

Tu dois travailler comme un **agent de refactor senior**, guidé par le code comme source de vérité, et livrer un résultat **testé, traçable, documenté et exploitable en production**.

---

## Contexte

Le module `modelFactory` est déjà avancé et dispose notamment de :

- walk-forward training / validation,
- calibration probabiliste,
- optimisation du `decision_threshold`,
- gouvernance champion/challenger,
- monitoring de drift,
- cache d’inférence,
- persistance DB des sorties ML,
- artefacts disque avec manifestes.

Cependant, l’audit existant et l’analyse du code ont identifié plusieurs **zones de fragilité** incompatibles avec un niveau “desk swing trade pro” si elles ne sont pas durcies.

### Documents d’appui déjà disponibles

À lire avant toute modification :

- `F:\projets\prompt\tod1\07_swing_trade_fitness_assessment.md`
- `F:\projets\prompt\tod1\02_module_scorecards.md`
- `F:\projets\doc\modelFactory.md`

### Fichiers cœur probables à inspecter

#### Entraînement / dataset / features
- `F:\projets\modelFactory\trainer.py`
- `F:\projets\modelFactory\dataset.py`
- `F:\projets\modelFactory\evaluation.py`
- `F:\projets\modelFactory\target_optimization.py`
- `F:\projets\modelFactory\config.py`
- `F:\projets\modelFactory\data_loader.py`

#### Serving / orchestration / gouvernance
- `F:\projets\modelFactory\predictor.py`
- `F:\projets\modelFactory\orchestrator.py`
- `F:\projets\modelFactory\champion_selection.py`
- `F:\projets\modelFactory\db_registry.py`
- `F:\projets\modelFactory\drift_monitor.py`
- `F:\projets\modelFactory\drift_policy.py`
- `F:\projets\modelFactory\runtime_status.py`

#### Consommation downstream risk
- `F:\projets\risk_management\ml_gate.py`
- `F:\projets\risk_management\db_io.py`
- `F:\projets\risk_management\cli.py`
- tout autre point de consommation effectif de `model_predictions`

#### Tests existants à étendre
- `F:\projets\tests\test_model_factory.py`
- `F:\projets\tests\test_model_factory_cli.py`
- `F:\projets\tests\test_model_factory_config.py`
- `F:\projets\tests\test_model_factory_data_loader.py`
- `F:\projets\tests\test_model_factory_dataset.py`
- `F:\projets\tests\test_model_factory_orchestrator.py`
- `F:\projets\tests\test_model_factory_predictor.py`
- `F:\projets\tests\test_model_factory_run_summary.py`
- `F:\projets\tests\test_ml_drift_policy_gate.py`
- `F:\projets\tests\test_ml_disable_modes.py`
- `F:\projets\tests\test_ml_artifacts_backup.py`
- `F:\projets\tests\test_services_ml_artifacts.py`

---

## Objectifs

1. **Garantir l’intégrité temporelle complète** du pipeline ML (`train` → `predict` → `risk`).
2. **Éliminer tout risque de fuite de données / look-ahead bias**.
3. **Propager correctement le drift gate ML** jusqu’au refus effectif de consommation côté `risk_management`.
4. **Rendre les runs reproductibles** à configuration et seed identiques.
5. **Durcir la gouvernance des artefacts** et leur cohérence avec la DB.
6. **Renforcer l’observabilité** : logs, `run_summary`, statuts, erreurs exploitables.
7. **Sécuriser les contrats de features** pour éviter les prédictions silencieusement incorrectes.
8. **Améliorer la résilience opérationnelle** en cas d’artefacts absents, corrompus ou d’environnement partiellement dégradé.
9. **Étendre la couverture de tests** sur tous les scénarios critiques.
10. **Documenter les invariants** et procédures de reprise.

---

## Non-objectifs

- Ne pas réécrire entièrement l’architecture si des corrections ciblées suffisent.
- Ne pas changer la logique métier swing trade sans preuve par tests/mesures.
- Ne pas ajouter de complexité inutile ou de dépendance externe non justifiée.
- Ne pas casser les contrats publics existants sans migration/documentation claire.

---

## Inventaire des anomalies à traiter

### A. Intégrité temporelle / fuite de données

Traiter en priorité tout ce qui peut créer un signal non PIT-safe :

- features calculées avec informations postérieures à la date de décision,
- `shift(-horizon)` ou cibles futures mal isolées,
- merges benchmark / sentiment / cross-sectional non bornés temporellement,
- splits chrono insuffisamment protecteurs,
- recouvrement entre fenêtres d’entraînement, validation, test, séquences et horizon de prévision,
- absence de purge / embargo explicite si nécessaire.

### B. Propagation incomplète du drift gate

Point déjà suspecté par l’audit :

- le drift gate existe côté ML,
- mais sa propagation effective jusqu’au refus de consommation côté `risk_management` doit être vérifiée et, si besoin, corrigée.

Le système doit garantir qu’un modèle drifté ne continue pas à influencer silencieusement les décisions risk via un chemin secondaire.

### C. Reproductibilité incomplète

Vérifier et corriger :

- seeds `numpy`, `torch`, challengers tabulaires,
- modes déterministes CPU/GPU quand possible,
- ordre des splits et de sélection de champion,
- cohérence entre `trainer`, `orchestrator`, `predictor`.

### D. Gouvernance d’artefacts insuffisamment stricte

Traiter :

- manifestes incomplets ou incohérents,
- divergence disque ↔ DB ↔ route d’inférence,
- comportement flou si champion absent/non inférable,
- stratégie de backup/rotation insuffisante,
- fallback implicite ou silencieux.

### E. Contrat de features trop permissif

Durcir :

- fingerprint des features,
- colonnes manquantes / extra,
- ordre et typage,
- stratégie explicite selon la sévérité : warning, fail-fast, fallback contrôlé.

### F. Observabilité et diagnostic trop faibles

Améliorer :

- logs structurés,
- présence systématique d’un `run_id`,
- statuts de fallback,
- statut drift/gate,
- backend sélectionné,
- seuil de décision,
- contexte `training_start_date`,
- messages d’erreur actionnables.

### G. Résilience opérationnelle

Couvrir les cas :

- artefact absent,
- JSON invalide,
- modèle incompatible,
- cache obsolète,
- route d’inférence incohérente,
- indisponibilité DB partielle,
- zéro champion éligible,
- mode dégradé ML → quant pur.

### H. Couverture de test insuffisante

Ajouter ou compléter les tests sur :

- anti-fuite,
- splits temporels,
- drift gate end-to-end,
- contrat de features,
- corruption d’artefacts,
- reproductibilité,
- fallback risk,
- cohérence run summaries.

---

## Plan d’exécution priorisé

## P0 — Sécurité métier et intégrité temporelle

### P0.1 — Audit anti-fuite complet

Auditer et corriger les chemins suivants :

- construction du dataset,
- préparation des features symboliques et globales,
- alignement séquences / labels,
- jointures benchmark / sentiment / cross-sectionnel,
- génération de cible,
- prédiction as-of.

#### Exigences
- démontrer par tests que les lignes à la date `t` n’utilisent aucune information de `t+1` ou au-delà pour la décision à `t`,
- vérifier explicitement les colonnes “future return”, target, rolling windows, normalisations, merges et sélections.

### P0.2 — Durcissement des splits temporels

Vérifier et corriger les fonctions de split temporel (ou équivalents) pour garantir :

- ordre chronologique strict,
- absence de chevauchement train/val/test,
- compatibilité avec `sequence_length`,
- compatibilité avec `forecast_horizon`,
- purge/embargo si nécessaire,
- déterminisme du découpage.

#### Attendus
- documenter les invariants temporels exacts,
- ajouter des tests qui échouent si un recouvrement apparaît.

### P0.3 — Drift gate ML → risk_management

Vérifier le flux complet depuis :

- `modelFactory/drift_policy.py`
- `modelFactory/drift_monitor.py`
- stockage DB / indicateurs de gate
- lecture côté `risk_management`
- application effective du fallback quant pur ou blocage ML.

#### Attendus
- aucune consommation indirecte des signaux ML si le gate désactive ML,
- traçabilité claire dans logs et résumés,
- tests d’intégration de bout en bout.

### P0.4 — Politique explicite de fallback

Formaliser le comportement dans tous les cas suivants :

- champion absent,
- artefact tabulaire non chargeable,
- mismatch de contrat de features,
- calibrateur absent,
- drift gate actif,
- backend sélectionné non inférable.

#### Attendus
- fallback documenté,
- identique entre code, logs, DB et run summaries,
- jamais silencieux.

---

## P1 — Reproductibilité, gouvernance et observabilité

### P1.1 — Politique centralisée de seeds

Créer ou consolider une politique commune pour :

- `numpy`,
- `torch`,
- modèles tabulaires,
- sélection / tri / shuffle éventuels,
- paramètres de déterminisme.

#### Attendus
- configuration centralisée,
- comportement stable entre runs comparables,
- documentation des limites de reproductibilité éventuelles selon CPU/GPU.

### P1.2 — Logs structurés et corrélation runtime

Standardiser les logs autour de :

- `run_id`,
- `symbol`,
- `selected_model`,
- `decision_threshold`,
- `calibration_method`,
- `training_start_date`,
- `drift_status`,
- `gate_status`,
- `fallback_reason`.

#### Attendus
- logs compréhensibles par un opérateur,
- messages d’erreur orientés diagnostic,
- cohérence entre entraînement, serving et risk.

### P1.3 — Gouvernance des artefacts

Durcir :

- contenu de `config.json` et `metrics.json`,
- cohérence disque/DB,
- présence et validité des artefacts requis,
- politique de version des manifestes,
- backup / rotation / restauration.

#### Attendus
- impossible de servir silencieusement un artefact invalide ou incomplet,
- diagnostic clair si incohérence détectée.

### P1.4 — Contrat de features

Mettre en place une politique claire sur :

- fingerprint,
- colonnes obligatoires,
- typage attendu,
- tolérance éventuelle aux colonnes supplémentaires,
- stratégie de blocage vs warning.

#### Attendus
- aucun scoring silencieusement faux,
- règle lisible et testée.

---

## P2 — Qualité, robustesse et documentation

### P2.1 — Résilience modes dégradés

Ajouter ou durcir les garde-fous pour :

- fichiers artefacts absents ou corrompus,
- DB indisponible ou partiellement lisible,
- modèle ou calibrateur incompatible,
- cache périmé,
- zéro champion éligible,
- backend fallback non documenté.

### P2.2 — Documentation technique

Mettre à jour `F:\projets\doc\modelFactory.md` pour inclure :

- invariants PIT,
- stratégie de split temporel,
- drift gate et fallback risk,
- politique de contrat de features,
- gouvernance des artefacts,
- procédures de reprise incident.

### P2.3 — Dette technique résiduelle

Identifier clairement en fin de chantier :

- ce qui est corrigé,
- ce qui reste volontairement ouvert,
- ce qui demanderait un chantier ultérieur.

---

## Méthode de travail obligatoire

1. **Lire le code avant toute modification.**
2. **Tracer chaque symbole critique jusqu’à ses usages.**
3. **Écrire ou ajuster les tests avant / pendant les correctifs sur les zones sensibles.**
4. **Faire des changements minimaux mais complets.**
5. **Valider après chaque étape significative.**
6. **Ne jamais laisser un fallback implicite non loggé.**
7. **Ne jamais conclure sans exécuter des tests ciblés puis transverses.**

---

## Stratégie de validation

### 1. Tests unitaires à renforcer

Créer/compléter des tests sur :

- split chronologique,
- alignement séquences / labels,
- absence de fuite via features/targets,
- fingerprint de features,
- seeds et reproductibilité minimale,
- sélection de champion et fallback.

### 2. Tests d’intégration

Ajouter des tests de bout en bout sur :

- entraînement → persistance artefacts → serving,
- drift gate → lecture risk → fallback quant pur,
- incohérence d’artefact → comportement explicite,
- backend non disponible → stratégie documentée.

### 3. Non-régression

S’assurer que restent corrects :

- walk-forward,
- calibration,
- optimisation de seuil,
- gouvernance champion/challenger,
- cache d’inférence,
- compatibilité avec les artefacts attendus.

### 4. Exigence minimale de preuve

Chaque anomalie P0 doit être couverte par :

- un constat précis,
- un correctif précis,
- au moins un test qui protège durablement le comportement.

---

## Critères d’acceptation

Le chantier n’est considéré terminé que si :

1. aucun cas crédible de fuite de données ou look-ahead non justifié ne subsiste,
2. le drift gate est effectivement propagé jusqu’à la consommation risk,
3. les fallbacks ML sont explicites, cohérents et tracés,
4. les splits temporels sont déterministes et protégés par tests,
5. les artefacts sont validés avant serving,
6. le contrat de features est strictement contrôlé,
7. les runs sont raisonnablement reproductibles à config/seed identiques,
8. la documentation technique est mise à jour,
9. les tests critiques passent,
10. les risques résiduels sont explicitement documentés.

---

## Livrables attendus

### Code
- correctifs sur les modules `modelFactory` impactés,
- correctifs éventuels sur `risk_management` si nécessaire,
- amélioration des logs / résumés / politiques de fallback.

### Tests
- nouveaux tests ciblés,
- ajustements des tests existants,
- validation des scénarios critiques.

### Documentation
- mise à jour de `F:\projets\doc\modelFactory.md`,
- éventuelles notes complémentaires si un arbitrage important est introduit.

### Compte-rendu final
Le compte-rendu doit contenir :

1. **Résumé exécutif** (5 à 10 lignes)
2. **Anomalies traitées** classées en P0 / P1 / P2
3. **Fichiers modifiés** avec justification par fichier
4. **Tests exécutés** et ce qu’ils valident
5. **Risques résiduels** et recommandations de suite
6. **Tableau avant / après** sur :
   - intégrité temporelle,
   - drift gate,
   - reproductibilité,
   - observabilité,
   - gouvernance des artefacts.

---

## Ordre recommandé d’intervention

1. Cartographier le flux complet `train` → `predict` → `risk`.
2. Traiter en premier l’anti-fuite et les splits temporels.
3. Corriger ensuite la propagation du drift gate.
4. Durcir les fallbacks et la gouvernance des artefacts.
5. Standardiser la reproductibilité et les logs.
6. Étendre les tests.
7. Mettre à jour la documentation.
8. Produire le compte-rendu final.

---

## Règles d’exécution

- Toujours préférer des correctifs petits, lisibles et fortement testés.
- Ne pas masquer un problème par un warning si un fail-fast contrôlé est plus sûr.
- Ne pas laisser un comportement “best effort” sur une zone critique sans l’expliciter.
- Si un arbitrage est nécessaire, choisir l’option la plus sûre pour un usage swing trade réel.
- Toute décision de compatibilité legacy doit être documentée et testée.

---

## Verdict attendu en fin de chantier

À la fin, tu dois être capable de conclure, preuves à l’appui, si `modelFactory` atteint désormais un niveau **professionnel exploitable pour du swing trade**, ou s’il reste des points bloquants à lever avant usage live.

