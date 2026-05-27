# 03 — Registre des anomalies

Date : mai 2026

---

## Légende

- **P0** : Bloquant — empêche le fonctionnement nominal ou présente un risque financier immédiat
- **P1** : Majeur — impact significatif sur la qualité, la sécurité ou l'exploitabilité
- **P2** : Modéré — dette technique, incohérence non critique, amélioration nécessaire
- **P3** : Mineur — cosmétique, optimisation, suggestion

---

## Anomalies P0

*Aucune anomalie P0 détectée.*

---

## Anomalies P1

### A-001 — Incohérence provider news par défaut doc ↔ doc

- **ID** : A-001
- **Titre** : Provider news par défaut incohérent entre README.md et docs techniques
- **Sévérité** : P1
- **Domaine** : Documentation, Event Sentiment
- **Description** : `README.md` §6 indique `eodhd` comme provider news par défaut, tandis que `doc/DOC_FONCTIONNELLE.md`, `doc/DOC_TECHNIQUE.md` et `doc/CONVENTIONS.md` indiquent `alpaca`. L'opérateur ne sait pas quel provider sera utilisé.
- **Preuve** :
  - `README.md` : « `event_sentiment` utilise désormais `eodhd` comme provider news par défaut »
  - `doc/CONVENTIONS.md` §2 : « News provider par défaut : `alpaca`. »
  - `doc/DOC_TECHNIQUE.md` entête : « Provider NEWS par défaut : `Alpaca` »
- **Impact métier** : Opérateur peut lancer le mauvais pipeline de news, avec des résultats différents
- **Impact technique** : Incohérence de configuration, comportement imprévisible
- **Probabilité** : Élevée (chaque run)
- **Niveau de confiance** : Élevé (95%)
- **Recommandation** : Vérifier le code réel de `event_sentiment/__main__.py` pour déterminer le défaut canonique, puis aligner TOUTE la documentation sur cette valeur unique.
- **Test à ajouter** :
  - **Objectif** : Vérifier que le provider news par défaut est documenté de manière cohérente
  - **Type** : Non-régression / config
  - **Priorité** : P1
  - **Fichier probable** : `tests/test_doc_news_provider_consistency.py`
  - **Scénario** : GIVEN les fichiers README.md, doc/CONVENTIONS.md, doc/DOC_FONCTIONNELLE.md, doc/DOC_TECHNIQUE.md WHEN on extrait la valeur du provider news par défaut THEN toutes les valeurs doivent être identiques et correspondre au défaut du code
  - **Fixtures** : Accès aux fichiers de doc
  - **Oracle** : Une seule valeur de défaut, cohérente avec le code
  - **Empêche** : Divergence future entre docs

### A-002 — Défaut `bars_provider` : code vs documentation

- **ID** : A-002
- **Titre** : La documentation affirme `eodhd` comme défaut, le code utilise `alpaca`
- **Sévérité** : P1
- **Domaine** : DataIntegrityEngine, Configuration
- **Description** : `import_alpaca_bar.py:441` et `import_eodhd_bar.py:90` utilisent `.get("bars_provider", "alpaca")` comme défaut. La documentation affirme qu'EODHD est le défaut.
- **Preuve** : `import_alpaca_bar.py:441` — `str(((cfg.get("market_data") or {}).get("bars_provider", "alpaca"))).lower()`
- **Impact métier** : Un opérateur qui suit la doc mais ne configure pas explicitement `bars_provider` utilisera Alpaca au lieu d'EODHD
- **Impact technique** : Données de qualité inférieure (IEX vs EODHD consolidé)
- **Probabilité** : Moyenne (nécessite absence de config explicite)
- **Niveau de confiance** : Élevé (90%)
- **Recommandation** : Changer le défaut code à `eodhd` pour correspondre à la documentation et à la recommandation du projet.
- **Test à ajouter** :
  - **Objectif** : Vérifier que le défaut `bars_provider` est `eodhd` dans le code
  - **Type** : Unitaire
  - **Priorité** : P1
  - **Fichier probable** : `tests/test_bars_provider_default.py`
  - **Scénario** : GIVEN un config.yaml sans clé `market_data.bars_provider` WHEN on appelle `resolve_bars_provider()` THEN la valeur retournée est `"eodhd"`
  - **Fixtures** : Config vide `{}`
  - **Oracle** : `"eodhd"`
  - **Empêche** : Régression du défaut

### A-003 — Hétérogénéité des run_summary — pas de persistance SQL uniforme

- **ID** : A-003
- **Titre** : Les résumés de run ne sont pas persistés de manière uniforme en base de données
- **Sévérité** : P1
- **Domaine** : Observabilité, DataIntegrityEngine, Screener, Selector
- **Description** : Certains modules émettent un `run_summary` sur stdout avec le préfixe `::alpha_trade_run_summary::` mais ne le persistent pas en SQL. L'IHM capture ces résumés depuis stdout, mais si le run est lancé hors IHM, le résumé est perdu.
- **Preuve** : `dataIntegrityEngine/data_sanitizer_daily.py` émet un résumé structuré mais ne l'insère pas dans une table SQL dédiée. `dataIntegrityEngine/import_alpaca_bar.py` fait de même.
- **Impact métier** : Perte de traçabilité, difficulté à auditer un run passé
- **Impact technique** : Pas d'historique requêtable des runs
- **Probabilité** : Élevée (tout run hors IHM)
- **Niveau de confiance** : Élevé (95%)
- **Recommandation** : Créer une table `run_summaries` centralisée et faire en sorte que chaque module y insère son résumé.
- **Test à ajouter** :
  - **Objectif** : Vérifier que chaque module CLI persiste son run_summary en SQL
  - **Type** : Intégration
  - **Priorité** : P1
  - **Fichier probable** : `tests/test_run_summary_persistence.py`
  - **Scénario** : GIVEN un module CLI exécuté avec succès WHEN on interroge la table `run_summaries` THEN une entrée correspondante existe avec les champs obligatoires
  - **Fixtures** : DB de test, mock provider
  - **Oracle** : Présence du run_summary en SQL avec run_id, module, statut, timestamp
  - **Empêche** : Perte de résumé non détectée

### A-004 — Tables ML listées dans lineage matrix non confirmées dans le code

- **ID** : A-004
- **Titre** : `doc/data_lineage_matrix.md` référence des tables ML qui pourraient ne pas exister
- **Sévérité** : P1
- **Domaine** : Database, ModelFactory
- **Description** : La lineage matrix liste `model_governance`, `model_metrics_full`, `ml_drift_runs`, `shadow_drift_runs` comme des tables existantes. Le code réel de `modelFactory/` ne montre pas de création explicite de ces tables.
- **Preuve** : `doc/data_lineage_matrix.md` §3 — table `model_governance` listée avec producteur `modelFactory.champion_selection`, mais le code de `champion_selection.py` écrit dans le filesystem, pas dans une table SQL.
- **Impact métier** : Documentation trompeuse, attentes fausses sur la traçabilité
- **Impact technique** : Si ces tables n'existent pas, la doc est fausse ; si elles existent, elles ne sont pas documentées dans le code
- **Probabilité** : Élevée
- **Niveau de confiance** : Moyen (70% — nécessite vérification DB)
- **Recommandation** : Vérifier l'existence réelle de ces tables dans le schéma SQL. Si absentes, les retirer de la lineage matrix ou les créer.
- **Test à ajouter** :
  - **Objectif** : Vérifier que toutes les tables listées dans la lineage matrix existent dans le schéma
  - **Type** : SQL / data quality
  - **Priorité** : P1
  - **Fichier probable** : `tests/test_lineage_matrix_consistency.py`
  - **Scénario** : GIVEN `doc/data_lineage_matrix.md` WHEN on extrait la liste des tables THEN chaque table existe dans `database/sql/` ou est créée par Alembic
  - **Fixtures** : Parsing du fichier lineage
  - **Oracle** : 100% des tables listées existent
  - **Empêche** : Documentation fantôme

### A-005 — Absence de validation de cohérence entre presets de capital et profil strict

- **ID** : A-005
- **Titre** : Les presets de `capital_presets.yaml` peuvent diverger du profil `STRICT_SWING_CASH_FILTERS`
- **Sévérité** : P1
- **Domaine** : Configuration, Selector, Risk Management
- **Description** : Le profil strict (`core/filter_profiles.py:STRICT_SWING_CASH_FILTERS`) définit des seuils canoniques. Les presets de capital définissent des overrides par tranche. Rien ne garantit qu'un preset ne contredit pas le profil strict (ex: `selector_min_close` inférieur à 10.0 dans un preset).
- **Preuve** : Dans `capital_presets.yaml`, le preset `capital_0_2000_eur` a `selector_min_close: 10.0` et `selector_min_beta_126: 0.65` alors que `STRICT_SWING_CASH_FILTERS.min_beta_126 = 0.8`.
- **Impact métier** : Un preset peut être trop permissif et laisser passer des candidats de mauvaise qualité
- **Impact technique** : Incohérence non détectée entre les deux sources de vérité
- **Probabilité** : Moyenne (les presets sont écrits manuellement)
- **Niveau de confiance** : Élevé (85%)
- **Recommandation** : Ajouter un test qui valide que chaque preset est cohérent avec le profil strict (les overrides doivent être documentés et justifiés).
- **Test à ajouter** :
  - **Objectif** : Valider que les presets de capital ne contredisent pas le profil strict sans justification
  - **Type** : Config / non-régression
  - **Priorité** : P1
  - **Fichier probable** : `tests/test_capital_presets_consistency.py`
  - **Scénario** : GIVEN `STRICT_SWING_CASH_FILTERS` et `capital_presets.yaml` WHEN on compare les seuils de chaque preset THEN tout écart doit être justifié par un commentaire dans le YAML
  - **Fixtures** : Fichiers de config
  - **Oracle** : Aucun écart non documenté
  - **Empêche** : Dérive des presets

### A-006 — Pas de test E2E du pipeline complet

- **ID** : A-006
- **Titre** : Absence de tests end-to-end couvrant le pipeline 1→14
- **Sévérité** : P1
- **Domaine** : Qualité logicielle, Tous les modules
- **Description** : Aucun test ne valide l'enchaînement complet du pipeline quotidien (ingestion → sanitize → screener → selector → sentiment → risk → execution → CA). Les tests sont unitaires ou d'intégration partielle.
- **Preuve** : `tests/` ne contient pas de test qui exécute séquentiellement toutes les étapes du pipeline.
- **Impact métier** : Risque de régression non détectée sur l'interaction entre modules
- **Impact technique** : Bugs d'intégration possibles en production
- **Probabilité** : Moyenne
- **Niveau de confiance** : Élevé (90%)
- **Recommandation** : Créer un test E2E qui exécute le pipeline complet sur un petit univers de test (5-10 symboles) et vérifie les sorties.
- **Test à ajouter** :
  - **Objectif** : Valider l'enchaînement complet du pipeline quotidien
  - **Type** : E2E / intégration
  - **Priorité** : P1
  - **Fichier probable** : `tests/test_pipeline_e2e.py`
  - **Scénario** : GIVEN un univers de 5 symboles avec données mockées WHEN on exécute les étapes 1→14 du pipeline THEN chaque étape produit les sorties attendues et aucune erreur critique n'est levée
  - **Fixtures** : DB de test, mocks providers Alpaca/EODHD/Finnhub
  - **Oracle** : Toutes les tables cibles sont alimentées, les résumés sont cohérents
  - **Empêche** : Régression d'intégration

### A-007 — Absence d'alerting externe

- **ID** : A-007
- **Titre** : Pas de notifications email/SMS/Slack pour les événements critiques
- **Sévérité** : P1
- **Domaine** : Observabilité, Sécurité
- **Description** : Le circuit breaker, les erreurs critiques, les fins de run anormales ne génèrent que des logs fichiers. Aucune alerte externe n'est envoyée.
- **Preuve** : `doc/DOC_FONCTIONNELLE.md` §6 : « Pas de notification externe — Pas d'email/SMS/Slack » (listé comme limitation).
- **Impact métier** : Un incident peut passer inaperçu pendant des heures
- **Impact technique** : Pas de réactivité opérationnelle
- **Probabilité** : Élevée (tout incident)
- **Niveau de confiance** : Élevé (95%)
- **Recommandation** : Intégrer un système de notification (Slack webhook, email SMTP, SMS).
- **Test à ajouter** :
  - **Objectif** : Vérifier que les alertes sont envoyées pour les événements critiques
  - **Type** : Intégration
  - **Priorité** : P1
  - **Fichier probable** : `tests/test_alerting.py`
  - **Scénario** : GIVEN un circuit breaker déclenché WHEN le run se termine THEN une alerte est envoyée (mock du webhook/email)
  - **Fixtures** : Mock SMTP / webhook
  - **Oracle** : L'alerte est envoyée avec le bon contenu
  - **Empêche** : Absence d'alerte en production

---

## Anomalies P2

### A-010 — Duplication de code entre les deux importeurs de barres

- **ID** : A-010
- **Titre** : `import_alpaca_bar.py` et `import_eodhd_bar.py` partagent des patterns similaires sans abstraction commune
- **Sévérité** : P2
- **Domaine** : DataIntegrityEngine
- **Description** : Les deux modules implémentent indépendamment la résolution d'univers, la lecture des dernières barres, la construction de run_summary, etc. Le refactor S7-bis a déplacé la logique EODHD dans `dataIntegrityEngine/eodhd/` mais Alpaca n'a pas suivi.
- **Preuve** : Comparaison de `import_alpaca_bar.py` et `import_eodhd_bar.py`.
- **Impact métier** : Maintenance plus coûteuse, risque de divergence
- **Impact technique** : Code dupliqué, bugs corrigés dans l'un mais pas l'autre
- **Probabilité** : Faible (impact indirect)
- **Niveau de confiance** : Élevé (95%)
- **Recommandation** : Extraire une classe abstraite `BaseBarImporter` et factoriser le code commun.
- **Test à ajouter** :
  - **Objectif** : Vérifier que les deux importeurs produisent des run_summary de structure identique
  - **Type** : Unitaire
  - **Fichier probable** : `tests/test_bar_importers_consistency.py`
  - **Scénario** : GIVEN un import réussi via EODHD et via Alpaca WHEN on compare les structures des run_summary THEN les clés obligatoires sont identiques
  - **Fixtures** : Mocks providers
  - **Oracle** : Structures de run_summary équivalentes

### A-011 — `model_predictions` n'inclut pas le modèle utilisé

- **ID** : A-011
- **Titre** : La table `model_predictions` ne persiste pas `selected_model`, `decision_threshold`, `calibration_method`
- **Sévérité** : P2
- **Domaine** : ModelFactory, Database
- **Description** : Documenté dans `doc/DOC_TECHNIQUE.md` §8 comme dette technique P1. Le code de `modelFactory/predictor.py` ne persiste que `symbol`, `prediction_date`, `predicted_proba`, `predicted_class`, `run_id`.
- **Preuve** : `doc/DOC_TECHNIQUE.md` §8 : « `model_predictions` n'inclut pas `selected_model` / `decision_threshold` / `calibration_method` — gouvernance ML incomplète en DB | P1 → Sprint S2 »
- **Impact métier** : Impossibilité de tracer quel modèle a produit quelle prédiction
- **Impact technique** : Gouvernance ML incomplète
- **Probabilité** : Élevée (à chaque prédiction)
- **Niveau de confiance** : Élevé (90%)
- **Recommandation** : Ajouter les colonnes manquantes et les peupler lors de l'inférence.
- **Test à ajouter** :
  - **Objectif** : Vérifier que `model_predictions` contient les colonnes de gouvernance
  - **Type** : SQL / intégration
  - **Fichier probable** : `tests/test_model_predictions_schema.py`
  - **Scénario** : GIVEN une prédiction persistée WHEN on lit la table THEN les colonnes `selected_model`, `decision_threshold`, `calibration_method` sont non nulles
  - **Fixtures** : DB de test, artefacts ML mockés
  - **Oracle** : Colonnes peuplées

### A-012 — Pas de test d'intégration MySQL avec Docker

- **ID** : A-012
- **Titre** : Les tests utilisent principalement des mocks ou SQLite, pas MySQL réel
- **Sévérité** : P2
- **Domaine** : Qualité logicielle, Database
- **Description** : `doc/DOC_TECHNIQUE.md` §9 recommande des tests d'intégration avec MySQL Docker (« testcontainers ») mais ce n'est pas implémenté.
- **Preuve** : `doc/DOC_TECHNIQUE.md` §9 : « Tests d'intégration avec MySQL Docker (testcontainers) » (listé comme recommandation moyen terme).
- **Impact métier** : Bugs spécifiques à MySQL non détectés en test
- **Impact technique** : Différences SQLite/MySQL masquées
- **Probabilité** : Faible (si les tests SQLite sont représentatifs)
- **Niveau de confiance** : Moyen (60%)
- **Recommandation** : Ajouter une configuration pytest avec testcontainers ou Docker Compose pour les tests d'intégration.

### A-013 — Redondance entre DOC_FONCTIONNELLE.md et DOC_TECHNIQUE.md

- **ID** : A-013
- **Titre** : Duplication de contenu entre la doc fonctionnelle et la doc technique
- **Sévérité** : P2
- **Domaine** : Documentation
- **Description** : Les sections sur le pipeline quotidien, les modules, et les commandes sont dupliquées entre les deux documents, avec des variations mineures.
- **Preuve** : Comparaison des sections « Pipeline quotidien » dans `DOC_FONCTIONNELLE.md` §3.1 et `DOC_TECHNIQUE.md` §10.
- **Impact métier** : Maintenance documentaire plus lourde, risque de divergence
- **Impact technique** : Mise à jour incohérente
- **Probabilité** : Élevée (à chaque mise à jour)
- **Niveau de confiance** : Élevé (95%)
- **Recommandation** : Réduire la duplication : garder le détail technique dans DOC_TECHNIQUE.md, le flux métier dans DOC_FONCTIONNELLE.md, avec des renvois explicites.

### A-014 — Absence de mode read-only pour l'IHM

- **ID** : A-014
- **Titre** : L'IHM n'a pas de mode consultation seule (read-only)
- **Sévérité** : P2
- **Domaine** : IHM, Sécurité
- **Description** : L'IHM permet de lancer des pipelines et de modifier des données. En production, un mode read-only serait souhaitable pour la supervision sans risque.
- **Preuve** : `doc/CONVENTIONS.md` §5 : « IHM : profil DB read-only souhaitable côté exploitation, mais non bloquant tant qu'il n'est pas livré. »
- **Impact métier** : Risque de modification accidentelle en production
- **Probabilité** : Faible (si l'opérateur est formé)
- **Niveau de confiance** : Élevé (90%)
- **Recommandation** : Implémenter un flag `--read-only` ou un profil DB avec droits SELECT uniquement.

### A-015 — Pas de parallélisation des runs de backtesting

- **ID** : A-015
- **Titre** : Le backtesting ne supporte pas la parallélisation des runs
- **Sévérité** : P2
- **Domaine** : Backtesting
- **Description** : Les runs de backtesting sont séquentiels. Pour explorer un espace de paramètres, l'opérateur doit lancer plusieurs runs manuellement.
- **Preuve** : `backtesting/cli.py` ne propose pas d'option `--parallel` ou `--workers`.
- **Impact métier** : Recherche plus lente
- **Probabilité** : Faible (impact recherche, pas production)
- **Niveau de confiance** : Élevé (90%)
- **Recommandation** : Ajouter un mode parallèle pour les sweeps de paramètres.

### A-016 — Cache Parquet non branché par défaut dans le backtesting

- **ID** : A-016
- **Titre** : `backtesting/cache.py` existe mais n'est pas activé par défaut
- **Sévérité** : P2
- **Domaine** : Backtesting
- **Description** : Le cache Parquet pour OHLCV/scores/predictions est implémenté mais pas branché à la CLI standard.
- **Preuve** : `backtesting/cache.py` est présent ; `doc/DOC_TECHNIQUE.md` §2.1 : « pas encore branché par défaut à la commande `run` ».
- **Impact métier** : Backtesting plus lent qu'il ne pourrait l'être
- **Probabilité** : Élevée (à chaque run)
- **Niveau de confiance** : Élevé (95%)
- **Recommandation** : Activer le cache par défaut avec une option `--no-cache` pour le désactiver.

### A-017 — Pas d'analyse de sensibilité automatisée dans le backtesting

- **ID** : A-017
- **Titre** : Les fonctions d'analyse de sensibilité existent mais ne sont pas branchées à la CLI
- **Sévérité** : P2
- **Domaine** : Backtesting
- **Description** : `backtesting/statistical_validation.py` contient `bootstrap_trades()` et `parameter_sensitivity()` mais ces fonctions ne sont pas exposées via la CLI standard.
- **Preuve** : `doc/DOC_TECHNIQUE.md` §2.1 : « briques disponibles côté code mais non encore automatiquement branchées à la CLI standard ».
- **Impact métier** : Recherche moins rigoureuse
- **Probabilité** : Faible (impact recherche)
- **Niveau de confiance** : Élevé (90%)
- **Recommandation** : Exposer ces fonctions via des sous-commandes CLI (`bootstrap`, `sensitivity`).

### A-018 — Pas de fallback si les quotes sont absentes dans le selector

- **ID** : A-018
- **Titre** : Si `stock_quote_snapshots` est vide, le filtre `spread_bps` peut rejeter tous les candidats
- **Sévérité** : P2
- **Domaine** : Selector
- **Description** : Le filtre `max_spread_bps` dans `apply_filters()` rejette les symboles sans quote. Si la synchronisation des quotes a échoué, l'univers peut être vide.
- **Preuve** : `selector/alpha_scanner.py:apply_filters()` — le filtre spread exige `spread_bps.notna() & (spread_bps <= max_spread_bps)`.
- **Impact métier** : Univers potentiellement vide si les quotes sont indisponibles
- **Probabilité** : Faible (si le pipeline est bien exécuté)
- **Niveau de confiance** : Moyen (70%)
- **Recommandation** : Ajouter un warning explicite et un mode fallback (`--skip-spread-filter`).

### A-019 — Pas de health check pré-run des providers

- **ID** : A-019
- **Titre** : Aucun test de disponibilité des providers avant le lancement du pipeline
- **Sévérité** : P2
- **Domaine** : Service/Providers
- **Description** : Le pipeline démarre sans vérifier qu'Alpaca, EODHD, et Finnhub sont accessibles. L'échec n'est détecté qu'au premier appel API.
- **Preuve** : `run_execution.py` a un mode `check` mais il est limité à l'environnement d'exécution, pas aux providers.
- **Impact métier** : Pipeline partiellement exécuté avant échec
- **Probabilité** : Faible (providers généralement stables)
- **Niveau de confiance** : Élevé (90%)
- **Recommandation** : Ajouter un `health_check()` pour chaque provider, exécuté en préflight.

### A-020 — Pas d'orchestrateur formel (Airflow/Prefect)

- **ID** : A-020
- **Titre** : Le pipeline repose sur un lancement manuel ou semi-manuel
- **Sévérité** : P2
- **Domaine** : Architecture
- **Description** : Documenté comme limitation dans `doc/DOC_TECHNIQUE.md` §9. L'IHM fournit un workflow mais pas d'orchestration automatique avec reprise sur erreur, scheduling, etc.
- **Preuve** : `doc/DOC_TECHNIQUE.md` §9 : « Orchestrateur pipeline (Airflow/Prefect) » (recommandation long terme).
- **Impact métier** : Dépendance à l'opérateur humain
- **Probabilité** : Élevée (chaque jour)
- **Niveau de confiance** : Élevé (95%)
- **Recommandation** : Intégrer un orchestrateur (Prefect recommandé pour la simplicité Python).

### A-021 — Pas de monitoring Prometheus/Grafana

- **ID** : A-021
- **Titre** : Absence de métriques exposées pour monitoring
- **Sévérité** : P2
- **Domaine** : Observabilité
- **Description** : Documenté comme recommandation dans `doc/DOC_TECHNIQUE.md` §9. Aucune métrique Prometheus n'est exposée.
- **Preuve** : `doc/DOC_TECHNIQUE.md` §9 : « Monitoring (Prometheus/Grafana) » (recommandation long terme).
- **Impact métier** : Pas de visibilité sur la santé du système en temps réel
- **Probabilité** : Faible (impact opérationnel indirect)
- **Niveau de confiance** : Élevé (95%)
- **Recommandation** : Exposer des métriques Prometheus (durée des runs, taux de succès, latence API).

### A-022 — Pas de gestion des fills partiels dans l'executor

- **ID** : A-022
- **Titre** : Les ordres partiellement exécutés ne sont pas gérés explicitement
- **Sévérité** : P2
- **Domaine** : Execution Engine
- **Description** : L'executor attend le fill complet ou le timeout. Un fill partiel n'est pas traité comme un cas spécifique.
- **Preuve** : `execution_engine/executor.py` — la boucle de polling attend `terminal_state` mais ne distingue pas fill partiel vs total.
- **Impact métier** : Positions partielles non détectées
- **Probabilité** : Faible (marchés liquides)
- **Niveau de confiance** : Moyen (60%)
- **Recommandation** : Ajouter une gestion explicite des fills partiels avec ajustement des enfants.

### A-023 — Pool de connexion DB modeste pour la production

- **ID** : A-023
- **Titre** : `pool_size=2`, `max_overflow=3` peut être insuffisant en production
- **Sévérité** : P2
- **Domaine** : Database
- **Description** : La configuration du pool DB est dimensionnée pour le développement, pas pour une charge de production avec parallélisme.
- **Preuve** : `doc/DOC_TECHNIQUE.md` §4.3 : « Pool : `pool_size=2`, `max_overflow=3`, `pool_pre_ping=True`, `pool_recycle=3600` »
- **Impact métier** : Risque de contention DB si plusieurs modules tournent en parallèle
- **Probabilité** : Moyenne (si parallélisme)
- **Niveau de confiance** : Élevé (90%)
- **Recommandation** : Permettre la configuration du pool via `config.yaml` avec des valeurs par défaut plus élevées.

### A-024 — Pas de test de parité backtest ↔ exécution réelle

- **ID** : A-024
- **Titre** : Aucun test ne compare les résultats du backtest avec l'exécution réelle/paper
- **Sévérité** : P2
- **Domaine** : Backtesting, Execution Engine
- **Description** : La fidélité du backtest est documentée et les phases de fidélité existent, mais aucun test automatisé ne vérifie que les résultats du backtest sont proches de l'exécution réelle.
- **Preuve** : `tests/` ne contient pas de test `test_backtest_live_parity.py`.
- **Impact métier** : Illusion de performance possible
- **Probabilité** : Faible (si les phases de fidélité sont utilisées)
- **Niveau de confiance** : Moyen (60%)
- **Recommandation** : Ajouter un test de parité sur un jeu de données historiques avec des ordres simulés.

### A-025 — Incohérence mineure : `selector_min_ibd_rs_rank` vs `selector_min_relative_strength_index`

- **ID** : A-025
- **Titre** : Deux noms pour le même paramètre dans les presets
- **Sévérité** : P2
- **Domaine** : Configuration
- **Description** : Les presets de capital utilisent `selector_min_ibd_rs_rank` (nouveau nom) avec `selector_min_relative_strength_index` comme « alias rétrocompatible ». La présence des deux dans le même fichier peut prêter à confusion.
- **Preuve** : `capital_presets.yaml` : chaque preset a `selector_min_ibd_rs_rank: X` et `selector_min_relative_strength_index: X` avec le même commentaire « alias rétrocompatible ».
- **Impact métier** : Confusion sur le paramètre effectif
- **Probabilité** : Faible
- **Niveau de confiance** : Élevé (95%)
- **Recommandation** : Supprimer l'alias et ne garder que le nom canonique.

### A-026 — `doc/data_lineage_matrix.md` mentionne `stock_assets` mais la table réelle est `stock_metadata`

- **ID** : A-026
- **Titre** : Nom de table inexact dans la matrice de lineage
- **Sévérité** : P2
- **Domaine** : Documentation
- **Description** : La lineage matrix référence `stock_assets` comme table, mais le code utilise `stock_metadata`.
- **Preuve** : `doc/data_lineage_matrix.md` §1 : « `stock_assets` », alors que le code référence `stock_metadata`.
- **Impact métier** : Confusion pour le mainteneur
- **Probabilité** : Faible
- **Niveau de confiance** : Élevé (90%)
- **Recommandation** : Corriger le nom dans la lineage matrix.

### A-027 — Certains documents dans `doc/` sont des POC non marqués

- **ID** : A-027
- **Titre** : Documents POC sans bandeau explicite
- **Sévérité** : P2
- **Domaine** : Documentation
- **Description** : `doc/CONVENTIONS.md` §6 demande un bandeau « POC non activé » mais certains fichiers (ex: `async_db_poc.md`, `async_db_benchmark.md`, `mode_regime.md`) n'en ont pas.
- **Preuve** : `doc/CONVENTIONS.md` §6.
- **Impact métier** : Un mainteneur pourrait croire qu'une fonctionnalité POC est active
- **Probabilité** : Faible
- **Niveau de confiance** : Moyen (70%)
- **Recommandation** : Ajouter le bandeau aux documents POC.

---

## Anomalies P3

### A-030 — Absence de glossaire centralisé

- **ID** : A-030
- **Titre** : Pas de glossaire des termes métier et techniques
- **Sévérité** : P3
- **Domaine** : Documentation
- **Description** : Les termes comme PIT, PDT, OCO, VCP, TCA, etc. sont utilisés dans la documentation sans définition centralisée.
- **Recommandation** : Ajouter un fichier `doc/GLOSSAIRE.md`.

### A-031 — `dataIntegrityEngine/update_sector.py` — nom trompeur

- **ID** : A-031
- **Titre** : Le script `update_sector.py` met aussi à jour `market_cap`
- **Sévérité** : P3
- **Domaine** : DataIntegrityEngine
- **Description** : Documenté dans `doc/dataIntegrityEngine.md` §7.4 : « le nom du fichier est devenu un peu trompeur ».
- **Recommandation** : Renommer en `update_fundamentals.py` ou documenter explicitement.

### A-032 — Variables d'environnement legacy `CLE_FINNHUB`

- **ID** : A-032
- **Titre** : Compatibilité historique `CLE_FINNHUB` encore supportée
- **Sévérité** : P3
- **Domaine** : Service/Providers
- **Description** : `README.md` §3 mentionne `CLE_FINNHUB` pour compatibilité historique. Cette variable legacy devrait être dépréciée.
- **Recommandation** : Émettre un DeprecationWarning quand `CLE_FINNHUB` est utilisée, puis supprimer.

### A-033 — `prompt/` non structuré

- **ID** : A-033
- **Titre** : Le dossier `prompt/` contient un historique non homogène
- **Sévérité** : P3
- **Domaine** : Documentation
- **Description** : Documenté dans `doc/DOC_TECHNIQUE.md` §8 : « homogénéisation du reste de `prompt/` encore perfectible | P3 ».
- **Recommandation** : Archiver les anciens prompts dans `prompt/archive/`.

### A-034 — Pas de conteneurisation Docker

- **ID** : A-034
- **Titre** : Pas de Dockerfile officiel
- **Sévérité** : P3
- **Domaine** : Architecture
- **Description** : Documenté comme recommandation dans `doc/DOC_TECHNIQUE.md` §9.
- **Recommandation** : Ajouter un Dockerfile et un docker-compose.yml.

### A-035 — Pas de support multi-devises

- **ID** : A-035
- **Titre** : Limitation assumée : USD uniquement
- **Sévérité** : P3
- **Domaine** : Risk Management, Execution
- **Description** : Documenté dans `doc/DOC_FONCTIONNELLE.md` §6.
- **Recommandation** : Documenter plus explicitement cette limitation dans les presets de capital.

### A-036 — Pas de short selling

- **ID** : A-036
- **Titre** : Stratégie long-only uniquement
- **Sévérité** : P3
- **Domaine** : Risk Management, Execution
- **Description** : Documenté comme limitation assumée.
- **Recommandation** : Ajouter à la roadmap long terme.

### A-037 — Pas de streaming temps réel

- **ID** : A-037
- **Titre** : Polling périodique au lieu de WebSocket pour les fills
- **Sévérité** : P3
- **Domaine** : Execution Engine
- **Description** : Documenté comme limitation dans `doc/DOC_FONCTIONNELLE.md` §6.
- **Recommandation** : Implémenter le streaming WebSocket Alpaca pour les fills.

### A-038 — `mypy.ini` et `pytest.ini` pourraient être migrés vers `pyproject.toml`

- **ID** : A-038
- **Titre** : Configuration dispersée entre plusieurs fichiers
- **Sévérité** : P3
- **Domaine** : Qualité logicielle
- **Description** : Une partie de la config est dans `pyproject.toml`, le reste dans `mypy.ini` et `pytest.ini`.
- **Recommandation** : Tout migrer dans `pyproject.toml`.

### A-039 — Tests manquants pour certains modules

- **ID** : A-039
- **Titre** : Couverture de tests inégale entre modules
- **Sévérité** : P3
- **Domaine** : Qualité logicielle
- **Description** : Certains modules (Execution Engine) sont bien testés, d'autres (Event Sentiment) le sont moins.
- **Recommandation** : Augmenter la couverture à ≥ 80% global.

### A-040 — Documentation IHM en anglais dans `ihm/README.md`

- **ID** : A-040
- **Titre** : Mix français/anglais dans la documentation
- **Sévérité** : P3
- **Domaine** : Documentation
- **Description** : La doc principale est en français, mais `ihm/README.md` est en anglais.
- **Recommandation** : Uniformiser en français ou documenter le choix.
